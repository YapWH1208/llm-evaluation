from __future__ import annotations

import random
from typing import Any


DEFAULT_RETRY_POLICY = {
    "max_attempts": 3,
    "base_delay_seconds": 2,
    "max_delay_seconds": 60,
    "strategy": "exponential_jitter",
    "jitter_ratio": 0.2,
    "max_total_wait_seconds": 600,
    "respect_retry_after": True,
    "retry_response_parse_errors": True,
}


def is_retryable(error_type: str | None, policy: dict[str, Any]) -> bool:
    if error_type in {"timeout", "connection_error"}:
        return True
    if error_type == "response_parse_error":
        return bool(policy["retry_response_parse_errors"])
    if not error_type or not error_type.startswith("http_"):
        return False
    try:
        status_code = int(error_type.removeprefix("http_"))
    except ValueError:
        return False
    return status_code in {408, 409, 425, 429} or 500 <= status_code <= 599


def retry_policy(payload: dict[str, Any]) -> dict[str, Any]:
    configured = payload.get("retry_policy") if isinstance(payload, dict) else None
    configured = configured if isinstance(configured, dict) else {}
    strategy = configured.get("strategy", DEFAULT_RETRY_POLICY["strategy"])
    if strategy not in {"fixed", "exponential", "exponential_jitter"}:
        strategy = DEFAULT_RETRY_POLICY["strategy"]
    return {
        "max_attempts": max(1, int(configured.get("max_attempts", DEFAULT_RETRY_POLICY["max_attempts"]))),
        "base_delay_seconds": max(
            0,
            int(configured.get("base_delay_seconds", DEFAULT_RETRY_POLICY["base_delay_seconds"])),
        ),
        "max_delay_seconds": max(
            0,
            int(configured.get("max_delay_seconds", DEFAULT_RETRY_POLICY["max_delay_seconds"])),
        ),
        "strategy": strategy,
        "jitter_ratio": min(
            1.0,
            max(0.0, float(configured.get("jitter_ratio", DEFAULT_RETRY_POLICY["jitter_ratio"]))),
        ),
        "max_total_wait_seconds": max(
            0,
            int(configured.get("max_total_wait_seconds", DEFAULT_RETRY_POLICY["max_total_wait_seconds"])),
        ),
        "respect_retry_after": bool(configured.get("respect_retry_after", DEFAULT_RETRY_POLICY["respect_retry_after"])),
        "retry_response_parse_errors": bool(
            configured.get(
                "retry_response_parse_errors",
                DEFAULT_RETRY_POLICY["retry_response_parse_errors"],
            )
        ),
    }


def retry_delay_seconds(
    attempt_count: int,
    policy: dict[str, Any],
    *,
    provider_retry_after_seconds: float | None,
) -> float:
    base_delay = float(policy["base_delay_seconds"])
    delay = base_delay if policy["strategy"] == "fixed" else base_delay * (2 ** max(0, attempt_count - 1))
    delay = min(float(policy["max_delay_seconds"]), delay)
    if policy["strategy"] == "exponential_jitter" and delay:
        delay *= 1 + random.uniform(-policy["jitter_ratio"], policy["jitter_ratio"])
    if policy["respect_retry_after"] and provider_retry_after_seconds is not None:
        delay = max(delay, provider_retry_after_seconds)
    return round(max(0.0, delay), 3)


def nonnegative_float(value: object) -> float:
    try:
        return max(0.0, float(value))
    except (TypeError, ValueError):
        return 0.0
