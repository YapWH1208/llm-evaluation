from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Any, Iterable

from app.db.models import SampleAttemptStatus
from app.modules.reviews.scoring import is_valid_judge_score
from app.modules.benchmarks.scoring import score_prediction


METRIC_PROFILE_VERSION = "1.1.0"
MAX_RETAINED_TOKEN_LOGPROBS = 100_000


@dataclass(frozen=True, slots=True)
class MetricDefinition:
    metric_name: str
    label: str
    unit: str
    profile: str
    required_evidence: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class MetricResult:
    metric_name: str
    value: float | None
    sample_count: int
    availability_reason: str | None = None
    confidence_interval: dict[str, object] | None = None


_DEFINITIONS = {
    definition.metric_name: definition
    for definition in (
        MetricDefinition("score", "Primary score", "ratio", "all", ("primary_score",)),
        MetricDefinition("accuracy", "Accuracy", "ratio", "classification", ("predicted_label", "reference_label")),
        MetricDefinition("precision_macro", "Macro precision", "ratio", "classification", ("predicted_label", "reference_label")),
        MetricDefinition("recall_macro", "Macro recall", "ratio", "classification", ("predicted_label", "reference_label")),
        MetricDefinition("f1_macro", "Macro F1", "ratio", "classification", ("predicted_label", "reference_label")),
        MetricDefinition("exact_match", "Exact match", "ratio", "generation", ("prediction", "reference_text")),
        MetricDefinition("normalized_exact_match", "Normalized exact match", "ratio", "generation", ("prediction", "reference_text")),
        MetricDefinition("token_f1", "Token F1", "ratio", "generation", ("prediction", "reference_text")),
        MetricDefinition("bleu", "BLEU", "ratio", "generation", ("prediction", "reference_text")),
        MetricDefinition("rouge_l", "ROUGE-L", "ratio", "generation", ("prediction", "reference_text")),
        MetricDefinition("llm_judge", "LLM-as-judge", "ratio", "all", ("llm_judge.score",)),
        MetricDefinition("pass@1", "pass@1", "ratio", "code", ("trusted_passed", "trusted_source")),
        MetricDefinition("perplexity", "Perplexity", "perplexity", "language_modeling", ("complete_token_logprobs",)),
        MetricDefinition("completion_rate", "Completion rate", "ratio", "operational", ("terminal_status",)),
        MetricDefinition("success_rate", "Success rate", "ratio", "operational", ("terminal_status",)),
        MetricDefinition("error_rate", "Error rate", "ratio", "operational", ("terminal_status",)),
        MetricDefinition("average_latency_ms", "Average latency", "milliseconds", "operational", ("latency_ms",)),
        MetricDefinition("p50_latency_ms", "p50 latency", "milliseconds", "operational", ("latency_ms",)),
        MetricDefinition("p95_latency_ms", "p95 latency", "milliseconds", "operational", ("latency_ms",)),
        MetricDefinition("p99_latency_ms", "p99 latency", "milliseconds", "operational", ("latency_ms",)),
        MetricDefinition("input_tokens", "Input tokens", "tokens", "operational", ("input_tokens",)),
        MetricDefinition("output_tokens", "Output tokens", "tokens", "operational", ("output_tokens",)),
        MetricDefinition("estimated_cost", "Estimated cost", "currency", "operational", ("estimated_cost",)),
    )
}


def metric_definition(metric_name: str) -> MetricDefinition:
    try:
        return _DEFINITIONS[metric_name]
    except KeyError as error:
        raise ValueError(f"Unknown metric: {metric_name}.") from error


def metric_definitions() -> tuple[MetricDefinition, ...]:
    return tuple(_DEFINITIONS.values())


def evaluation_type_from_snapshot(snapshot: object) -> str:
    if not isinstance(snapshot, dict):
        return "custom"
    profile = snapshot.get("dataset_profile")
    evaluation_type = profile.get("evaluation_type") if isinstance(profile, dict) else None
    return evaluation_type if isinstance(evaluation_type, str) and evaluation_type in {
        "classification",
        "generation",
        "code",
        "language_modeling",
        "custom",
    } else "custom"


def build_execution_metric_evidence(
    *,
    token_logprobs: Iterable[float] | None,
    existing: dict[str, object] | None = None,
) -> dict[str, object]:
    evidence = dict(existing or {})
    evidence["profile_version"] = METRIC_PROFILE_VERSION
    if token_logprobs is None:
        evidence.pop("token_logprobs", None)
        evidence.pop("token_logprobs_complete", None)
        evidence.pop("token_logprobs_reason", None)
        return evidence
    values = list(token_logprobs)
    if len(values) > MAX_RETAINED_TOKEN_LOGPROBS:
        evidence.update({
            "token_logprobs_complete": False,
            "token_logprobs_reason": f"Token log probabilities exceed the {MAX_RETAINED_TOKEN_LOGPROBS}-value retention limit.",
        })
        evidence.pop("token_logprobs", None)
        return evidence
    if not values or any(not isinstance(value, int | float) or not math.isfinite(float(value)) or float(value) > 0 for value in values):
        evidence.update({
            "token_logprobs_complete": False,
            "token_logprobs_reason": "Token log probabilities are missing or invalid.",
        })
        evidence.pop("token_logprobs", None)
        return evidence
    evidence.update({
        "token_logprobs": [float(value) for value in values],
        "token_logprobs_complete": True,
    })
    evidence.pop("token_logprobs_reason", None)
    return evidence


def compute_profile_metrics(
    attempts: list[Any],
    *,
    evaluation_type: str,
    include_llm_judge: bool = False,
) -> list[MetricResult]:
    successful = [
        attempt
        for attempt in attempts
        if _value(attempt, "status") == SampleAttemptStatus.SUCCEEDED.value
    ]
    scores = [
        float(score)
        for attempt in successful
        if _finite_number(score := _value(attempt, "score"))
    ]
    results = [
        MetricResult(
            "score",
            _average(scores),
            len(scores),
            None if scores else "No successful samples contain a primary score.",
        )
    ]
    if evaluation_type == "classification":
        results += _classification_metrics(successful)
    elif evaluation_type == "generation":
        results += _generation_metrics(successful)
    elif evaluation_type == "code":
        results.append(_pass_at_one(successful))
    elif evaluation_type == "language_modeling":
        results.append(_perplexity(successful))
    else:
        reason = "Metric is unavailable because the dataset uses the custom evaluation profile."
        results += [
            MetricResult(definition.metric_name, None, 0, reason)
            for definition in _DEFINITIONS.values()
            if definition.profile not in {"all", "operational"} and definition.metric_name != "accuracy"
        ]
    if include_llm_judge:
        results.append(_llm_judge_metric(successful))
    return results


def _llm_judge_metric(attempts: list[Any]) -> MetricResult:
    scores: list[float] = []
    for attempt in attempts:
        evidence = _value(attempt, "metric_evidence")
        judge = evidence.get("llm_judge") if isinstance(evidence, dict) else None
        if not isinstance(judge, dict) or judge.get("status") != "succeeded":
            continue
        score = judge.get("score")
        if is_valid_judge_score(score):
            scores.append(float(score))
    if not scores:
        return MetricResult(
            "llm_judge",
            None,
            0,
            "No successful LLM-as-judge scores are available for this run.",
        )
    return MetricResult("llm_judge", _average(scores), len(scores))


def _classification_metrics(attempts: list[Any]) -> list[MetricResult]:
    pairs = _prediction_reference_pairs(attempts)
    names = ("accuracy", "precision_macro", "recall_macro", "f1_macro")
    if not pairs:
        return _unavailable(names, "Classification metrics require valid predicted and reference labels.")
    labels = sorted({label for pair in pairs for label in pair})
    accuracy = sum(predicted == reference for predicted, reference in pairs) / len(pairs)
    precisions: list[float] = []
    recalls: list[float] = []
    f1_values: list[float] = []
    for label in labels:
        true_positive = sum(predicted == label and reference == label for predicted, reference in pairs)
        false_positive = sum(predicted == label and reference != label for predicted, reference in pairs)
        false_negative = sum(predicted != label and reference == label for predicted, reference in pairs)
        precision = true_positive / (true_positive + false_positive) if true_positive + false_positive else 0.0
        recall = true_positive / (true_positive + false_negative) if true_positive + false_negative else 0.0
        f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
        precisions.append(precision)
        recalls.append(recall)
        f1_values.append(f1)
    values = (accuracy, _average(precisions), _average(recalls), _average(f1_values))
    return [MetricResult(name, _rounded(value), len(pairs)) for name, value in zip(names, values)]


def _generation_metrics(attempts: list[Any]) -> list[MetricResult]:
    pairs = _prediction_reference_pairs(attempts)
    names_and_rules = (
        ("exact_match", "exact_match"),
        ("normalized_exact_match", "normalized_exact_match"),
        ("token_f1", "token_f1"),
        ("bleu", "bleu"),
        ("rouge_l", "rouge_l"),
    )
    if not pairs:
        return _unavailable(
            tuple(name for name, _rule in names_and_rules),
            "Generation metrics require prediction and reference text evidence.",
        )
    return [
        MetricResult(
            name,
            _average([
                score_prediction(
                    predicted,
                    {"answer": reference, "scoring": {"type": rule}},
                )
                for predicted, reference in pairs
            ]),
            len(pairs),
        )
        for name, rule in names_and_rules
    ]


def _pass_at_one(attempts: list[Any]) -> MetricResult:
    outcomes: list[bool] = []
    for attempt in attempts:
        evidence = _value(attempt, "metric_evidence")
        result = evidence.get("trusted_test_result") if isinstance(evidence, dict) else None
        passed = result.get("passed") if isinstance(result, dict) else None
        source = result.get("source") if isinstance(result, dict) else None
        if not isinstance(passed, bool) or not isinstance(source, str) or not source.startswith("trusted:"):
            return MetricResult(
                "pass@1",
                None,
                0,
                "pass@1 requires a recorded deterministic outcome from a trusted evaluation source.",
            )
        outcomes.append(passed)
    if not outcomes:
        return MetricResult(
            "pass@1",
            None,
            0,
            "pass@1 requires a recorded deterministic outcome from a trusted evaluation source.",
        )
    return MetricResult("pass@1", _average([float(value) for value in outcomes]), len(outcomes))


def _perplexity(attempts: list[Any]) -> MetricResult:
    log_probabilities: list[float] = []
    for attempt in attempts:
        evidence = _value(attempt, "metric_evidence")
        values = evidence.get("token_logprobs") if isinstance(evidence, dict) else None
        complete = evidence.get("token_logprobs_complete") if isinstance(evidence, dict) else None
        if complete is not True or not isinstance(values, list) or not values:
            return MetricResult(
                "perplexity",
                None,
                0,
                "Perplexity requires complete finite per-token log probabilities for every successful sample.",
            )
        if any(not _finite_number(value) or float(value) > 0 for value in values):
            return MetricResult(
                "perplexity",
                None,
                0,
                "Perplexity requires complete finite per-token log probabilities for every successful sample.",
            )
        log_probabilities.extend(float(value) for value in values)
    if not log_probabilities:
        return MetricResult(
            "perplexity",
            None,
            0,
            "Perplexity requires complete finite per-token log probabilities for every successful sample.",
        )
    negative_mean = -sum(log_probabilities) / len(log_probabilities)
    if negative_mean > 700:
        return MetricResult("perplexity", None, 0, "Perplexity exceeds the finite numeric range.")
    return MetricResult("perplexity", _rounded(math.exp(negative_mean)), len(log_probabilities))


def _prediction_reference_pairs(attempts: list[Any]) -> list[tuple[str, str]]:
    pairs: list[tuple[str, str]] = []
    for attempt in attempts:
        prediction = _value(attempt, "parsed_prediction")
        reference_snapshot = _value(attempt, "reference_snapshot")
        reference = reference_snapshot.get("answer") if isinstance(reference_snapshot, dict) else None
        if isinstance(prediction, str) and isinstance(reference, str | int | float | bool):
            pairs.append((prediction.strip(), str(reference).strip()))
    return pairs


def _unavailable(names: tuple[str, ...], reason: str) -> list[MetricResult]:
    return [MetricResult(name, None, 0, reason) for name in names]


def _value(attempt: Any, key: str) -> Any:
    return attempt.get(key) if isinstance(attempt, dict) else getattr(attempt, key, None)


def _finite_number(value: object) -> bool:
    return isinstance(value, int | float) and not isinstance(value, bool) and math.isfinite(float(value))


def _average(values: list[float]) -> float | None:
    return _rounded(sum(values) / len(values)) if values else None


def _rounded(value: float | None) -> float | None:
    return round(float(value), 12) if value is not None else None
