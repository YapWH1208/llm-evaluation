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
    if rule_type == "bleu":
        return _bleu(prediction, str(expected), max_order=_positive_int(rule.get("max_order", 4), "max_order", maximum=4))
    if rule_type in {"rouge", "rouge_l"}:
        return _rouge_l(prediction, str(expected))
    if rule_type in {"rouge_1", "rouge1"}:
        return _rouge_n(prediction, str(expected), order=1)
    if rule_type == "wer":
        return _error_rate_score(_normalized(prediction).split(), _normalized(str(expected)).split())
    if rule_type == "cer":
        return _error_rate_score(list(_normalized(prediction)), list(_normalized(str(expected))))
    if rule_type == "iou":
        return _intersection_over_union(prediction, expected)
    if rule_type in {"temporal_localization_error", "temporal_error"}:
        return _temporal_localization_score(prediction, expected, rule)
    if rule_type in {"unit_test_pass_rate", "unit_test"}:
        return _unit_test_pass_rate(prediction, rule)
    if rule_type == "length_limit":
        return _length_limit(prediction, rule)
    if rule_type == "required_fields":
        return _required_fields(prediction, rule)
    if rule_type == "forbidden_fields":
        return _forbidden_fields(prediction, rule)
    if rule_type in {"output_format", "format"}:
        return _output_format(prediction, rule)
    if rule_type in {"refusal", "refusal_behavior"}:
        return _refusal_behavior(prediction, rule)
    if rule_type == "tool_selection":
        return _tool_selection(prediction, expected, rule)
    if rule_type in {"tool_argument_validity", "tool_arguments"}:
        return _tool_argument_validity(prediction, rule)
    if rule_type in {"citation_presence", "citations"}:
        return _citation_presence(prediction, rule)
    if rule_type in {"schema_compliance", "json_schema_validation"}:
        return score_prediction(prediction, {"answer": expected, "scoring": {**rule, "type": "json_schema"}})
    if rule_type in {"rules", "rule_checks"}:
        checks = rule.get("checks")
        if not isinstance(checks, list) or not checks or any(not isinstance(check, dict) for check in checks):
            raise ScoringError("Rule-check scoring requires a non-empty checks list.")
        return round(sum(score_prediction(prediction, {"answer": expected, "scoring": check}) for check in checks) / len(checks), 12)
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


def _positive_int(value: object, field: str, *, maximum: int | None = None) -> int:
    if isinstance(value, bool):
        raise ScoringError(f"{field} must be a positive integer.")
    try:
        parsed = int(value)
    except (TypeError, ValueError) as error:
        raise ScoringError(f"{field} must be a positive integer.") from error
    if parsed < 1 or (maximum is not None and parsed > maximum):
        suffix = f" no greater than {maximum}" if maximum is not None else ""
        raise ScoringError(f"{field} must be a positive integer{suffix}.")
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


def _bleu(prediction: str, expected: str, *, max_order: int) -> float:
    candidate = _normalized(prediction).split()
    reference = _normalized(expected).split()
    if not candidate or not reference:
        return float(candidate == reference)
    precisions: list[float] = []
    for order in range(1, max_order + 1):
        candidate_counts = _ngrams(candidate, order)
        if not candidate_counts:
            break
        reference_counts = _ngrams(reference, order)
        overlap = sum((candidate_counts & reference_counts).values())
        precisions.append(overlap / sum(candidate_counts.values()))
    if not precisions or any(precision == 0 for precision in precisions):
        return 0.0
    geometric_mean = math.exp(sum(math.log(precision) for precision in precisions) / len(precisions))
    brevity_penalty = 1.0 if len(candidate) > len(reference) else math.exp(1 - len(reference) / len(candidate))
    return round(brevity_penalty * geometric_mean, 12)


def _rouge_n(prediction: str, expected: str, *, order: int) -> float:
    candidate = _normalized(prediction).split()
    reference = _normalized(expected).split()
    reference_counts = _ngrams(reference, order)
    if not reference_counts:
        return float(not candidate)
    overlap = sum((_ngrams(candidate, order) & reference_counts).values())
    return round(overlap / sum(reference_counts.values()), 12)


def _rouge_l(prediction: str, expected: str) -> float:
    candidate = _normalized(prediction).split()
    reference = _normalized(expected).split()
    if not candidate or not reference:
        return float(candidate == reference)
    length = _longest_common_subsequence_length(candidate, reference)
    precision = length / len(candidate)
    recall = length / len(reference)
    return round(2 * precision * recall / (precision + recall), 12) if precision + recall else 0.0


def _error_rate_score(predicted: list[str], expected: list[str]) -> float:
    if not expected:
        return float(not predicted)
    distance = _levenshtein_distance(predicted, expected)
    return round(max(0.0, 1 - distance / len(expected)), 12)


def _intersection_over_union(prediction: str, expected: object) -> float:
    predicted_box = _parse_box(prediction)
    expected_box = _parse_box(expected)
    if predicted_box is None or expected_box is None:
        return 0.0
    px1, py1, px2, py2 = predicted_box
    ex1, ey1, ex2, ey2 = expected_box
    intersection = max(0.0, min(px2, ex2) - max(px1, ex1)) * max(0.0, min(py2, ey2) - max(py1, ey1))
    predicted_area = (px2 - px1) * (py2 - py1)
    expected_area = (ex2 - ex1) * (ey2 - ey1)
    union = predicted_area + expected_area - intersection
    return round(intersection / union, 12) if union > 0 else 0.0


def _temporal_localization_score(prediction: str, expected: object, rule: dict[str, object]) -> float:
    predicted_interval = _parse_interval(prediction)
    expected_interval = _parse_interval(expected)
    if predicted_interval is None or expected_interval is None:
        return 0.0
    tolerance = _nonnegative_float(rule.get("tolerance_seconds", 1.0), "tolerance_seconds")
    if tolerance == 0:
        return float(predicted_interval == expected_interval)
    start_error = abs(predicted_interval[0] - expected_interval[0])
    end_error = abs(predicted_interval[1] - expected_interval[1])
    return round(max(0.0, 1 - (start_error + end_error) / (2 * tolerance)), 12)


def _unit_test_pass_rate(prediction: str, rule: dict[str, object]) -> float:
    try:
        payload = json.loads(prediction)
    except json.JSONDecodeError:
        return 0.0
    values = payload.get("tests") if isinstance(payload, dict) else payload
    if not isinstance(values, list) or not values:
        return 0.0
    passed = [item if isinstance(item, bool) else item.get("passed") if isinstance(item, dict) else None for item in values]
    if any(not isinstance(item, bool) for item in passed):
        raise ScoringError("Unit-test results must be booleans or objects with a boolean passed field.")
    expected_count = rule.get("expected_count")
    if expected_count is not None and expected_count != len(passed):
        return 0.0
    return round(sum(passed) / len(passed), 12)


def _length_limit(prediction: str, rule: dict[str, object]) -> float:
    unit = str(rule.get("unit", "characters"))
    if unit not in {"characters", "tokens"}:
        raise ScoringError("Length-limit unit must be characters or tokens.")
    length = len(_normalized(prediction).split()) if unit == "tokens" else len(prediction)
    minimum = rule.get("min")
    maximum = rule.get("max")
    if minimum is not None and length < _nonnegative_float(minimum, "min"):
        return 0.0
    if maximum is not None and length > _nonnegative_float(maximum, "max"):
        return 0.0
    return 1.0


def _required_fields(prediction: str, rule: dict[str, object]) -> float:
    value = _json_object_or_none(prediction)
    fields = rule.get("fields", rule.get("required"))
    if value is None or not isinstance(fields, list) or not fields or any(not isinstance(field, str) for field in fields):
        raise ScoringError("Required-fields scoring requires a non-empty fields list and JSON object output.")
    return float(all(_json_path_exists(value, field) for field in fields))


def _forbidden_fields(prediction: str, rule: dict[str, object]) -> float:
    value = _json_object_or_none(prediction)
    fields = rule.get("fields", rule.get("forbidden"))
    if value is None or not isinstance(fields, list) or any(not isinstance(field, str) for field in fields):
        raise ScoringError("Forbidden-fields scoring requires a fields list and JSON object output.")
    return float(not any(_json_path_exists(value, field) for field in fields))


def _output_format(prediction: str, rule: dict[str, object]) -> float:
    expected_format = str(rule.get("format", "")).lower()
    if expected_format == "json":
        try:
            json.loads(prediction)
        except json.JSONDecodeError:
            return 0.0
        return 1.0
    if expected_format == "regex":
        pattern = rule.get("pattern")
        if not isinstance(pattern, str) or not pattern:
            raise ScoringError("Regex output-format scoring requires a pattern.")
        try:
            return float(re.fullmatch(pattern, prediction, re.DOTALL) is not None)
        except re.error as error:
            raise ScoringError(f"Invalid regex scoring pattern: {error}") from error
    if expected_format == "plain_text":
        return float(bool(prediction.strip()))
    raise ScoringError("Output-format scoring supports json, regex, and plain_text.")


def _refusal_behavior(prediction: str, rule: dict[str, object]) -> float:
    must_refuse = bool(rule.get("must_refuse", True))
    terms = rule.get("refusal_terms", ["cannot", "can't", "unable", "i'm sorry", "i cannot"])
    if not isinstance(terms, list) or any(not isinstance(term, str) for term in terms):
        raise ScoringError("refusal_terms must be a list of strings.")
    is_refusal = any(term.casefold() in prediction.casefold() for term in terms)
    return float(is_refusal == must_refuse)


def _tool_selection(prediction: str, expected: object, rule: dict[str, object]) -> float:
    value = _json_object_or_none(prediction)
    if value is None:
        return 0.0
    actual = value.get("tool") or value.get("name") or value.get("tool_name")
    target = rule.get("tool", expected)
    return float(isinstance(actual, str) and isinstance(target, str) and actual == target)


def _tool_argument_validity(prediction: str, rule: dict[str, object]) -> float:
    value = _json_object_or_none(prediction)
    schema = rule.get("schema")
    if value is None or not isinstance(schema, dict):
        raise ScoringError("Tool-argument scoring requires JSON output and a schema object.")
    arguments = value.get("arguments", value.get("tool_arguments"))
    if isinstance(arguments, str):
        try:
            arguments = json.loads(arguments)
        except json.JSONDecodeError:
            return 0.0
    return float(_matches_schema(arguments, schema))


def _citation_presence(prediction: str, rule: dict[str, object]) -> float:
    minimum = _positive_int(rule.get("min_count", 1), "min_count")
    citations = re.findall(r"\[[^\]]+\]\([^\s)]+\)|https?://[^\s)]+", prediction)
    return float(len(citations) >= minimum)


def _ngrams(tokens: list[str], order: int) -> Counter[tuple[str, ...]]:
    return Counter(tuple(tokens[index : index + order]) for index in range(max(0, len(tokens) - order + 1)))


def _longest_common_subsequence_length(left: list[str], right: list[str]) -> int:
    previous = [0] * (len(right) + 1)
    for left_token in left:
        current = [0]
        for index, right_token in enumerate(right, start=1):
            current.append(previous[index - 1] + 1 if left_token == right_token else max(previous[index], current[-1]))
        previous = current
    return previous[-1]


def _levenshtein_distance(left: list[str], right: list[str]) -> int:
    previous = list(range(len(right) + 1))
    for left_index, left_value in enumerate(left, start=1):
        current = [left_index]
        for right_index, right_value in enumerate(right, start=1):
            current.append(min(previous[right_index] + 1, current[-1] + 1, previous[right_index - 1] + (left_value != right_value)))
        previous = current
    return previous[-1]


def _parse_box(value: object) -> tuple[float, float, float, float] | None:
    parsed = _parse_json_or_numbers(value)
    if isinstance(parsed, dict):
        parsed = [parsed.get(key) for key in ("x1", "y1", "x2", "y2")]
    if not isinstance(parsed, list) or len(parsed) != 4:
        return None
    try:
        x1, y1, x2, y2 = (float(item) for item in parsed)
    except (TypeError, ValueError):
        return None
    if not all(math.isfinite(item) for item in (x1, y1, x2, y2)) or x2 <= x1 or y2 <= y1:
        return None
    return x1, y1, x2, y2


def _parse_interval(value: object) -> tuple[float, float] | None:
    parsed = _parse_json_or_numbers(value)
    if isinstance(parsed, dict):
        parsed = [parsed.get("start"), parsed.get("end")]
    if not isinstance(parsed, list) or len(parsed) != 2:
        return None
    try:
        start, end = (float(item) for item in parsed)
    except (TypeError, ValueError):
        return None
    if not all(math.isfinite(item) for item in (start, end)) or end < start:
        return None
    return start, end


def _parse_json_or_numbers(value: object) -> object:
    if isinstance(value, (list, dict)):
        return value
    if not isinstance(value, str):
        return None
    try:
        return json.loads(value)
    except json.JSONDecodeError:
        return [part for part in re.split(r"[\s,;]+", value.strip()) if part]


def _json_object_or_none(prediction: str) -> dict[str, object] | None:
    try:
        value = json.loads(prediction)
    except json.JSONDecodeError:
        return None
    return value if isinstance(value, dict) else None


def _json_path_exists(value: dict[str, object], path: str) -> bool:
    current: object = value
    for part in path.split("."):
        if not isinstance(current, dict) or part not in current:
            return False
        current = current[part]
    return True


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
