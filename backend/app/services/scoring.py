from __future__ import annotations

import json
import math
import re
from collections import Counter
from typing import Any

from app.services.model_executor import normalize_exact_match


class ScoringError(ValueError):
    """Raised when a deterministic scoring rule cannot be applied safely."""


def score_prediction(prediction: str, reference: dict[str, object]) -> float:
    """Score one parsed prediction using the immutable sample scoring snapshot."""

    config = reference.get("scoring")
    rule = dict(config) if isinstance(config, dict) else {"type": reference.get("type", "exact_match")}
    rule_type = str(rule.get("type", "exact_match")).strip().lower()
    expected = reference.get("answer")
    if rule_type == "exact_match":
        return float(prediction.strip() == str(expected).strip())
    if rule_type in {"normalized_exact_match", "multiple_choice"}:
        return float(_normalized(prediction) == _normalized(str(expected)))
    if rule_type == "numeric_match":
        return _numeric_match(prediction, expected, rule)
    if rule_type == "regex_match":
        pattern = rule.get("pattern", expected)
        if not isinstance(pattern, str) or not pattern:
            raise ScoringError("Regex scoring requires a non-empty pattern.")
        try:
            return float(re.search(pattern, prediction, re.DOTALL) is not None)
        except re.error as error:
            raise ScoringError(f"Invalid regex scoring pattern: {error}") from error
    if rule_type == "json_schema":
        schema = rule.get("schema")
        if not isinstance(schema, dict):
            raise ScoringError("JSON schema scoring requires a schema object.")
        try:
            value = json.loads(prediction)
        except json.JSONDecodeError:
            return 0.0
        return float(_matches_schema(value, schema))
    if rule_type in {"token_f1", "f1"}:
        return _token_f1(prediction, str(expected))
    if rule_type == "contains":
        return float(_normalized(str(expected)) in _normalized(prediction))
    raise ScoringError(f"Unsupported deterministic scoring type: {rule_type}.")


def _numeric_match(prediction: str, expected: object, rule: dict[str, object]) -> float:
    try:
        actual = float(prediction.strip())
        target = float(expected)
    except (TypeError, ValueError):
        return 0.0
    if not math.isfinite(actual) or not math.isfinite(target):
        return 0.0
    absolute_tolerance = _nonnegative_float(rule.get("absolute_tolerance", 0.0), "absolute_tolerance")
    relative_tolerance = _nonnegative_float(rule.get("relative_tolerance", 0.0), "relative_tolerance")
    return float(abs(actual - target) <= max(absolute_tolerance, abs(target) * relative_tolerance))


def _nonnegative_float(value: object, field: str) -> float:
    try:
        parsed = float(value)
    except (TypeError, ValueError) as error:
        raise ScoringError(f"{field} must be a non-negative number.") from error
    if not math.isfinite(parsed) or parsed < 0:
        raise ScoringError(f"{field} must be a non-negative number.")
    return parsed


def _token_f1(prediction: str, expected: str) -> float:
    predicted_tokens = _normalized(prediction).split()
    expected_tokens = _normalized(expected).split()
    if not predicted_tokens or not expected_tokens:
        return float(predicted_tokens == expected_tokens)
    overlap = sum((Counter(predicted_tokens) & Counter(expected_tokens)).values())
    precision = overlap / len(predicted_tokens)
    recall = overlap / len(expected_tokens)
    return round(2 * precision * recall / (precision + recall), 12) if precision + recall else 0.0


def _normalized(value: str) -> str:
    return normalize_exact_match(value).casefold()


def _matches_schema(value: object, schema: dict[str, object]) -> bool:
    if "const" in schema and value != schema["const"]:
        return False
    enum = schema.get("enum")
    if isinstance(enum, list) and value not in enum:
        return False
    declared_type = schema.get("type")
    if declared_type == "object":
        if not isinstance(value, dict):
            return False
        required = schema.get("required", [])
        if not isinstance(required, list) or any(not isinstance(key, str) or key not in value for key in required):
            return False
        properties = schema.get("properties", {})
        if isinstance(properties, dict):
            for key, child_schema in properties.items():
                if key in value and isinstance(child_schema, dict) and not _matches_schema(value[key], child_schema):
                    return False
    elif declared_type == "array":
        if not isinstance(value, list):
            return False
        item_schema = schema.get("items")
        if isinstance(item_schema, dict) and any(not _matches_schema(item, item_schema) for item in value):
            return False
    elif declared_type == "string" and not isinstance(value, str):
        return False
    elif declared_type == "number" and (not isinstance(value, (int, float)) or isinstance(value, bool)):
        return False
    elif declared_type == "integer" and (not isinstance(value, int) or isinstance(value, bool)):
        return False
    elif declared_type == "boolean" and not isinstance(value, bool):
        return False
    elif declared_type == "null" and value is not None:
        return False
    return True
