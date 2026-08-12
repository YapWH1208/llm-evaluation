"""Shared, storage-agnostic helpers for LLM-as-judge scoring."""

from __future__ import annotations

import json
import math
from collections.abc import Mapping
from typing import Any


LLM_JUDGE_RULE_TYPE = "llm_judge"
DEFAULT_SINGLE_JUDGE_SYSTEM_MESSAGE = (
    "You are an evaluation judge. Return only JSON with score (0 to 1), label, and rationale."
)
DEFAULT_PAIRWISE_JUDGE_SYSTEM_MESSAGE = (
    "You are an evaluation judge. Compare two anonymized candidate answers. Return only JSON "
    "with score (0 to 1), label, rationale, and winner (A, B, or tie). Do not infer model identity."
)
_MAX_SYSTEM_MESSAGE_LENGTH = 10_000


class JudgeScoringError(ValueError):
    """Raised when judge configuration or a structured judge response is invalid."""


def is_llm_judge_rule(rule: object) -> bool:
    """Return whether a scoring rule selects LLM-as-judge scoring."""

    return (
        isinstance(rule, Mapping)
        and isinstance(rule.get("type"), str)
        and rule["type"].strip().lower() == LLM_JUDGE_RULE_TYPE
    )


def normalize_judge_rule(rule: Mapping[str, object]) -> dict[str, str]:
    """Validate and normalize the user-visible LLM-as-judge scoring rule."""

    rule_type = rule.get("type")
    if not isinstance(rule_type, str) or rule_type.strip().lower() != LLM_JUDGE_RULE_TYPE:
        raise JudgeScoringError(f"Judge scoring type must be {LLM_JUDGE_RULE_TYPE}.")
    endpoint_id = _required_text(rule.get("judge_endpoint_id"), "judge_endpoint_id")
    system_message = _required_text(rule.get("system_message"), "system_message")
    if len(system_message) > _MAX_SYSTEM_MESSAGE_LENGTH:
        raise JudgeScoringError(f"system_message must be at most {_MAX_SYSTEM_MESSAGE_LENGTH} characters.")
    return {
        "type": LLM_JUDGE_RULE_TYPE,
        "judge_endpoint_id": endpoint_id,
        "system_message": system_message,
    }


def judge_endpoint_snapshot(endpoint: object) -> dict[str, object]:
    """Build a reproducible endpoint description without credentials or custom headers."""

    return {
        "id": str(_endpoint_value(endpoint, "id")),
        "base_url": str(_endpoint_value(endpoint, "base_url")),
        "model_name": str(_endpoint_value(endpoint, "model_name")),
        "protocol_profile": str(_endpoint_value(endpoint, "protocol_profile")),
        "timeout_seconds": int(_endpoint_value(endpoint, "timeout_seconds")),
        "input_cost_per_million": _optional_float(_endpoint_value(endpoint, "input_cost_per_million")),
        "output_cost_per_million": _optional_float(_endpoint_value(endpoint, "output_cost_per_million")),
        "currency": str(_endpoint_value(endpoint, "currency", "USD")),
    }


def validate_judge_endpoint(
    rule: Mapping[str, object],
    *,
    evaluated_endpoint_id: str,
    judge_endpoint: object | None,
) -> dict[str, str]:
    """Validate the selected judge endpoint without coupling to a storage backend."""

    normalized = normalize_judge_rule(rule)
    if judge_endpoint is None:
        raise JudgeScoringError("Judge model endpoint not found.")
    if str(_endpoint_value(judge_endpoint, "id")) == evaluated_endpoint_id:
        raise JudgeScoringError("A model endpoint cannot judge its own evaluation output.")
    if _endpoint_value(judge_endpoint, "status") != "available":
        raise JudgeScoringError("Judge model endpoint must pass a connection test before scheduling a run.")
    return normalized


def judge_configuration_snapshot(
    rule: Mapping[str, object],
    *,
    judge_endpoint: object,
    reference_field: str,
) -> dict[str, object]:
    """Return the immutable, credential-free configuration retained with a run."""

    normalized = normalize_judge_rule(rule)
    return {
        "endpoint": judge_endpoint_snapshot(judge_endpoint),
        "reference_field": reference_field,
        "system_message": normalized["system_message"],
    }


def judge_preflight_estimate(
    *,
    sample_count: int,
    target_input_tokens: int,
    judge_endpoint: object,
) -> dict[str, object]:
    """Estimate one judge request per sample without changing target-run totals."""

    estimated_input_tokens = target_input_tokens + sample_count * 128
    estimated_output_tokens = sample_count * 64
    input_cost = _optional_float(_endpoint_value(judge_endpoint, "input_cost_per_million"))
    output_cost = _optional_float(_endpoint_value(judge_endpoint, "output_cost_per_million"))
    estimated_cost = (
        (estimated_input_tokens * input_cost + estimated_output_tokens * output_cost) / 1_000_000
        if input_cost is not None and output_cost is not None
        else None
    )
    return {
        "estimated_requests": sample_count,
        "estimated_input_tokens": estimated_input_tokens,
        "estimated_output_tokens": estimated_output_tokens,
        "estimated_cost": estimated_cost,
        "currency": str(_endpoint_value(judge_endpoint, "currency", "USD")),
    }


def build_single_judge_input(
    *,
    system_message: str,
    rubric: Mapping[str, object],
    input_snapshot: Mapping[str, object],
    reference_snapshot: Mapping[str, object],
    prediction: str | None,
) -> dict[str, object]:
    """Build the provider-agnostic prompt for one candidate answer."""

    return _judge_input(
        system_message=system_message,
        payload={
            "rubric": dict(rubric),
            "input": dict(input_snapshot),
            "reference": dict(reference_snapshot),
            "prediction": prediction,
        },
    )


def build_pairwise_judge_input(
    *,
    system_message: str,
    rubric: Mapping[str, object],
    input_snapshot: Mapping[str, object],
    reference_snapshot: Mapping[str, object],
    answers: Mapping[str, str | None],
) -> dict[str, object]:
    """Build the blinded provider-agnostic prompt for two candidate answers."""

    return _judge_input(
        system_message=system_message,
        payload={
            "rubric": dict(rubric),
            "input": dict(input_snapshot),
            "reference": dict(reference_snapshot),
            "answers": dict(answers),
        },
    )


def parse_judge_response(prediction: str) -> dict[str, object]:
    """Parse the constrained JSON response returned by a judge endpoint."""

    text = prediction.strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[-1]
        if text.endswith("```"):
            text = text[:-3].strip()
    try:
        payload = json.loads(text)
    except json.JSONDecodeError as error:
        raise JudgeScoringError("Judge response was not valid JSON.") from error
    if not isinstance(payload, dict):
        raise JudgeScoringError("Judge response must be a JSON object.")
    try:
        score = float(payload["score"])
    except (KeyError, TypeError, ValueError) as error:
        raise JudgeScoringError("Judge response must include a numeric score.") from error
    if not math.isfinite(score) or not 0 <= score <= 1:
        raise JudgeScoringError("Judge score must be a finite number between 0 and 1.")
    parsed: dict[str, object] = {"score": score}
    for field in ("label", "rationale"):
        value = payload.get(field)
        if value is not None and not isinstance(value, str):
            raise JudgeScoringError(f"Judge response field {field} must be a string.")
        if isinstance(value, str):
            parsed[field] = value
    winner = payload.get("winner")
    if winner is not None:
        if not isinstance(winner, str) or winner not in {"A", "B", "tie"}:
            raise JudgeScoringError("Judge response winner must be A, B, or tie.")
        parsed["winner"] = winner
    return parsed


def is_valid_judge_score(value: object) -> bool:
    return (
        isinstance(value, int | float)
        and not isinstance(value, bool)
        and math.isfinite(float(value))
        and 0 <= float(value) <= 1
    )


def _judge_input(*, system_message: str, payload: Mapping[str, object]) -> dict[str, object]:
    return {
        "messages": [
            {"role": "system", "content": system_message},
            {"role": "user", "content": json.dumps(dict(payload), ensure_ascii=False)},
        ]
    }


def _required_text(value: object, field: str) -> str:
    if not isinstance(value, str) or not (normalized := value.strip()):
        raise JudgeScoringError(f"{field} must be a non-empty string.")
    return normalized


def _endpoint_value(endpoint: object, key: str, default: object | None = None) -> object:
    if isinstance(endpoint, Mapping):
        return endpoint.get(key, default)
    return getattr(endpoint, key, default)


def _optional_float(value: object) -> float | None:
    if value is None:
        return None
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return None
    return parsed if math.isfinite(parsed) else None
