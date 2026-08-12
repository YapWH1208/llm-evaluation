import pytest

from app.services.judge_scoring import (
    JudgeScoringError,
    build_pairwise_judge_input,
    build_single_judge_input,
    is_llm_judge_rule,
    judge_endpoint_snapshot,
    normalize_judge_rule,
    parse_judge_response,
)


class Endpoint:
    id = "judge-1"
    base_url = "https://models.example.test/v1"
    model_name = "judge-model"
    protocol_profile = "openai_chat_completions"
    default_request_body = {"temperature": 0}
    timeout_seconds = 45
    input_cost_per_million = 1.5
    output_cost_per_million = 2.5
    currency = "USD"
    encrypted_api_key = "must-not-appear"
    custom_headers = {"Authorization": "must-not-appear"}


def test_normalizes_a_complete_llm_judge_rule() -> None:
    rule = normalize_judge_rule(
        {
            "type": "LLM_JUDGE",
            "judge_endpoint_id": " judge-1 ",
            "system_message": " Judge the response against the reference. ",
        }
    )

    assert rule == {
        "type": "llm_judge",
        "judge_endpoint_id": "judge-1",
        "system_message": "Judge the response against the reference.",
    }
    assert is_llm_judge_rule(rule) is True
    assert is_llm_judge_rule({"type": "exact_match"}) is False


@pytest.mark.parametrize(
    "rule, message",
    [
        ({"type": "llm_judge", "system_message": "Judge."}, "judge_endpoint_id"),
        ({"type": "llm_judge", "judge_endpoint_id": "judge-1"}, "system_message"),
        ({"type": "llm_judge", "judge_endpoint_id": " ", "system_message": "Judge."}, "judge_endpoint_id"),
        ({"type": "llm_judge", "judge_endpoint_id": "judge-1", "system_message": " "}, "system_message"),
        ({"type": "exact_match", "judge_endpoint_id": "judge-1", "system_message": "Judge."}, "type"),
    ],
)
def test_rejects_incomplete_or_wrong_judge_rules(rule: dict[str, object], message: str) -> None:
    with pytest.raises(JudgeScoringError, match=message):
        normalize_judge_rule(rule)


def test_builds_secret_safe_endpoint_snapshot_and_judge_inputs() -> None:
    snapshot = judge_endpoint_snapshot(Endpoint())

    assert snapshot == {
        "id": "judge-1",
        "base_url": "https://models.example.test/v1",
        "model_name": "judge-model",
        "protocol_profile": "openai_chat_completions",
        "timeout_seconds": 45,
        "input_cost_per_million": 1.5,
        "output_cost_per_million": 2.5,
        "currency": "USD",
    }
    assert "must-not-appear" not in str(snapshot)

    single = build_single_judge_input(
        system_message="Judge the answer.",
        rubric={"criterion": "correctness"},
        input_snapshot={"messages": [{"role": "user", "content": "Question"}]},
        reference_snapshot={"answer": "Reference"},
        prediction="Candidate",
    )
    assert single["messages"][0] == {"role": "system", "content": "Judge the answer."}
    assert '"prediction": "Candidate"' in str(single["messages"][1]["content"])

    pairwise = build_pairwise_judge_input(
        system_message="Compare answers.",
        rubric={"criterion": "correctness"},
        input_snapshot={"messages": [{"role": "user", "content": "Question"}]},
        reference_snapshot={"answer": "Reference"},
        answers={"A": "Candidate A", "B": "Candidate B"},
    )
    assert pairwise["messages"][0] == {"role": "system", "content": "Compare answers."}
    assert '"answers"' in str(pairwise["messages"][1]["content"])


def test_parses_valid_and_rejects_invalid_judge_responses() -> None:
    parsed = parse_judge_response('```json\n{"score": 0.75, "label": "good", "rationale": "Matches."}\n```')
    assert parsed == {"score": 0.75, "label": "good", "rationale": "Matches."}

    for payload in ("not json", "[]", '{"score": "NaN"}', '{"score": 1.1}', '{"score": -0.1}', '{"score": 0.5, "label": 3}'):
        with pytest.raises(JudgeScoringError):
            parse_judge_response(payload)
