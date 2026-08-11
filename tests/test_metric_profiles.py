from math import log
from types import SimpleNamespace

import pytest

from app.services.metric_profiles import (
    METRIC_PROFILE_VERSION,
    build_execution_metric_evidence,
    compute_profile_metrics,
    metric_definition,
)


def _attempt(
    prediction: str,
    answer: str,
    *,
    score: float = 1.0,
    metric_evidence: dict[str, object] | None = None,
) -> SimpleNamespace:
    return SimpleNamespace(
        status="succeeded",
        parsed_prediction=prediction,
        reference_snapshot={"answer": answer},
        score=score,
        metric_evidence=metric_evidence,
    )


def _by_name(results):
    return {result.metric_name: result for result in results}


def test_metric_registry_is_versioned_and_declares_evidence_and_units() -> None:
    assert METRIC_PROFILE_VERSION == "1.0.0"
    assert metric_definition("accuracy").profile == "classification"
    assert metric_definition("f1_macro").required_evidence == (
        "predicted_label",
        "reference_label",
    )
    assert metric_definition("perplexity").unit == "perplexity"


def test_classification_metrics_match_hand_calculated_macro_values() -> None:
    metrics = _by_name(
        compute_profile_metrics(
            [
                _attempt("A", "A"),
                _attempt("B", "A", score=0.0),
                _attempt("B", "B"),
                _attempt("B", "B"),
            ],
            evaluation_type="classification",
        )
    )

    assert metrics["accuracy"].value == 0.75
    assert metrics["precision_macro"].value == pytest.approx(5 / 6)
    assert metrics["recall_macro"].value == 0.75
    assert metrics["f1_macro"].value == pytest.approx(11 / 15)
    assert all(metrics[name].availability_reason is None for name in metrics)


def test_generation_metrics_match_hand_calculated_examples() -> None:
    metrics = _by_name(
        compute_profile_metrics(
            [
                _attempt("Blue answer", "blue answer", score=0.0),
                _attempt("cat", "the cat", score=0.0),
            ],
            evaluation_type="generation",
        )
    )

    assert metrics["exact_match"].value == 0.0
    assert metrics["normalized_exact_match"].value == 0.5
    assert metrics["token_f1"].value == pytest.approx(5 / 6)
    assert metrics["bleu"].value == pytest.approx((1 + 0.367879441171) / 2)
    assert metrics["rouge_l"].value == pytest.approx(5 / 6)


def test_pass_at_one_requires_recorded_trusted_outcomes() -> None:
    available = _by_name(
        compute_profile_metrics(
            [
                _attempt("code-a", "", metric_evidence={"trusted_test_result": {"passed": True, "source": "trusted:sandbox"}}),
                _attempt("code-b", "", metric_evidence={"trusted_test_result": {"passed": False, "source": "trusted:sandbox"}}),
            ],
            evaluation_type="code",
        )
    )["pass@1"]
    unavailable = _by_name(
        compute_profile_metrics(
            [_attempt("print('unsafe')", "")],
            evaluation_type="code",
        )
    )["pass@1"]

    assert available.value == 0.5
    assert available.sample_count == 2
    assert unavailable.value is None
    assert "trusted" in unavailable.availability_reason.lower()


def test_perplexity_requires_complete_finite_token_log_probabilities() -> None:
    available = _by_name(
        compute_profile_metrics(
            [
                _attempt("a", "", metric_evidence={"token_logprobs": [-log(2), -log(2)], "token_logprobs_complete": True}),
                _attempt("b", "", metric_evidence={"token_logprobs": [-log(2)], "token_logprobs_complete": True}),
            ],
            evaluation_type="language_modeling",
        )
    )["perplexity"]
    unavailable = _by_name(
        compute_profile_metrics(
            [
                _attempt("a", "", metric_evidence={"token_logprobs": [-log(2)], "token_logprobs_complete": True}),
                _attempt("b", ""),
            ],
            evaluation_type="language_modeling",
        )
    )["perplexity"]

    assert available.value == pytest.approx(2.0)
    assert available.sample_count == 3
    assert unavailable.value is None
    assert "complete" in unavailable.availability_reason.lower()


def test_custom_profile_preserves_primary_score_and_marks_named_metrics_unavailable() -> None:
    metrics = _by_name(
        compute_profile_metrics(
            [_attempt("x", "x", score=0.25)],
            evaluation_type="custom",
        )
    )

    assert metrics["score"].value == 0.25
    assert metrics["score"].availability_reason is None
    assert metrics["f1_macro"].value is None
    assert metrics["f1_macro"].availability_reason
    assert metrics["perplexity"].value is None


def test_execution_metric_evidence_is_bounded_and_rejects_invalid_log_probabilities() -> None:
    evidence = build_execution_metric_evidence(
        token_logprobs=(-0.1, -0.2),
        existing={"trusted_test_result": {"passed": True, "source": "trusted:sandbox"}},
    )
    assert evidence == {
        "profile_version": "1.0.0",
        "token_logprobs": [-0.1, -0.2],
        "token_logprobs_complete": True,
        "trusted_test_result": {"passed": True, "source": "trusted:sandbox"},
    }

    invalid = build_execution_metric_evidence(token_logprobs=(float("nan"),))
    assert invalid["token_logprobs_complete"] is False
    assert "invalid" in str(invalid["token_logprobs_reason"]).lower()
