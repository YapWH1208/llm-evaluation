from __future__ import annotations

import base64
import binascii
import ipaddress
from collections.abc import Mapping
from copy import deepcopy
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from time import perf_counter
from typing import Any
from urllib.parse import urlparse

PROTECTED_REQUEST_FIELDS = frozenset(
    {
        "model",
        "messages",
        "input",
        "contents",
        "system",
        "systemInstruction",
        "stream",
        "tools",
        "response_format",
    }
)
_SENSITIVE_BODY_KEYS = frozenset(
    {"api_key", "apikey", "api-key", "token", "access_token", "auth_token", "authorization", "secret", "password"}
)
_BLOCKED_HEADERS = frozenset(
    {"authorization", "cookie", "host", "content-length", "x-api-key", "x-goog-api-key", "api-key"}
)


def is_sensitive_body_key(name: str) -> bool:
    normalized = str(name).lower().replace("_", "-").replace(" ", "-").strip("-")
    return normalized in _SENSITIVE_BODY_KEYS or normalized.endswith(("-key", "-token", "-secret"))


def validate_custom_headers(value: dict[str, Any]) -> dict[str, str]:
    if len(value) > 32:
        raise ValueError("custom_headers may contain at most 32 headers.")
    normalized: dict[str, str] = {}
    for name, header_value in value.items():
        if not isinstance(name, str) or not name.strip() or any(char in name for char in "\r\n:"):
            raise ValueError("custom_headers contains an invalid header name.")
        if name.lower() in _BLOCKED_HEADERS:
            raise ValueError(f"custom_headers cannot set protected header: {name}.")
        if not isinstance(header_value, str) or "\r" in header_value or "\n" in header_value:
            raise ValueError(f"custom_headers contains an invalid value for {name}.")
        if len(header_value) > 4096:
            raise ValueError(f"custom_headers value for {name} is too long.")
        normalized[name] = header_value
    return normalized


def allowed_defaults(defaults: Mapping[str, object]) -> dict[str, Any]:
    return {
        key: value
        for key, value in defaults.items()
        if key not in PROTECTED_REQUEST_FIELDS and not is_sensitive_body_key(key)
    }


def url_without_fragment(value: str) -> str:
    parsed = urlparse(value)
    return parsed._replace(fragment="").geturl()


def source_as_data_or_remote_url(part: dict[str, Any]) -> str:
    source = part["source"]
    if not isinstance(source, dict):
        raise ValueError("Media content parts require a source object.")
    remote_url = source.get("url")
    if isinstance(remote_url, str):
        validate_remote_media_url(remote_url)
        return remote_url
    encoded = source.get("base64_data")
    if isinstance(encoded, str):
        validate_base64(encoded)
        return f"data:{part['mime_type']};base64,{encoded}"
    if source.get("asset_id"):
        raise ValueError("Stored media assets must be resolved to base64_data or a remote URL before execution.")
    raise ValueError("Media content part has no usable provider source.")


def validate_base64(value: str) -> None:
    try:
        base64.b64decode(value, validate=True)
    except (binascii.Error, ValueError) as error:
        raise ValueError("Media base64_data must be valid base64.") from error


def validate_remote_media_url(value: str) -> None:
    parsed = urlparse(value)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise ValueError("Remote media URLs must be absolute HTTP or HTTPS URLs.")
    host = parsed.hostname
    if host is None:
        raise ValueError("Remote media URL host is missing.")
    try:
        address = ipaddress.ip_address(host)
    except ValueError:
        return
    if address.is_private or address.is_loopback or address.is_link_local or address.is_reserved:
        raise ValueError("Remote media URLs must not target private or local IP addresses.")


def nonnegative_int(value: object) -> int | None:
    if isinstance(value, bool):
        return None
    try:
        number = int(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None
    return number if number >= 0 else None


def parse_retry_after(value: str | None, now: datetime | None = None) -> float | None:
    if not value:
        return None
    try:
        delay = float(value)
    except ValueError:
        try:
            retry_at = parsedate_to_datetime(value)
        except (TypeError, ValueError, IndexError):
            return None
        if retry_at.tzinfo is None:
            retry_at = retry_at.replace(tzinfo=timezone.utc)
        delay = (retry_at - (now or datetime.now(timezone.utc))).total_seconds()
    return max(0.0, delay)


def elapsed_ms(started_at: float) -> float:
    return round((perf_counter() - started_at) * 1000, 3)


def resolve_request_body(
    *,
    protocol_profile: str,
    model_defaults: Mapping[str, object] | None,
    suite_defaults: Mapping[str, object] | None = None,
    benchmark_defaults: Mapping[str, object] | None = None,
    run_override: Mapping[str, object] | None = None,
    benchmark_forced: Mapping[str, object] | None = None,
) -> dict[str, object]:
    from app.infrastructure.providers.registry import ProviderRegistry

    layers: tuple[tuple[str, Mapping[str, object] | None], ...] = (
        ("adapter_defaults", ProviderRegistry().for_profile(protocol_profile).request_defaults()),
        ("model_defaults", model_defaults),
        ("suite_defaults", suite_defaults),
        ("benchmark_defaults", benchmark_defaults),
        ("run_override", run_override),
        ("benchmark_forced", benchmark_forced),
    )
    effective: dict[str, object] = {}
    provenance: dict[str, str] = {}
    overridden_fields: list[dict[str, object]] = []
    ignored_fields: list[dict[str, object]] = []
    snapshots: dict[str, dict[str, object]] = {}
    for layer_name, raw_layer in layers:
        safe_layer = _normalise_layer(raw_layer, layer_name, ignored_fields)
        snapshots[layer_name] = deepcopy(safe_layer)
        _deep_merge(effective, safe_layer, layer_name, provenance, overridden_fields)
    return {
        "protocol_profile": protocol_profile,
        "layers": snapshots,
        "effective_request_body": effective,
        "overridden_fields": overridden_fields,
        "ignored_fields": ignored_fields,
    }


def effective_request_options(
    input_snapshot: Mapping[str, object], *, protocol_profile: str, model_defaults: Mapping[str, object] | None
) -> dict[str, object]:
    evidence = input_snapshot.get("request_body_evidence")
    if isinstance(evidence, Mapping) and isinstance(evidence.get("effective_request_body"), Mapping):
        return deepcopy(dict(evidence["effective_request_body"]))
    return dict(
        resolve_request_body(protocol_profile=protocol_profile, model_defaults=model_defaults)["effective_request_body"]
    )


def request_snapshot_metadata(input_snapshot: Mapping[str, object]) -> dict[str, object] | None:
    evidence = input_snapshot.get("request_body_evidence")
    return deepcopy(dict(evidence)) if isinstance(evidence, Mapping) else None


def _normalise_layer(
    value: Mapping[str, object] | None, layer_name: str, ignored_fields: list[dict[str, object]]
) -> dict[str, object]:
    if not isinstance(value, Mapping):
        return {}
    safe: dict[str, object] = {}
    for key, item in value.items():
        if not isinstance(key, str):
            ignored_fields.append({"layer": layer_name, "field": str(key), "reason": "field names must be strings"})
            continue
        if key in PROTECTED_REQUEST_FIELDS:
            ignored_fields.append({"layer": layer_name, "field": key, "reason": "platform-controlled request field"})
            continue
        safe[key] = deepcopy(item)
    return safe


def _deep_merge(
    target: dict[str, object],
    incoming: Mapping[str, object],
    layer_name: str,
    provenance: dict[str, str],
    overridden_fields: list[dict[str, object]],
    prefix: str = "",
) -> None:
    for key, value in incoming.items():
        field_path = f"{prefix}.{key}" if prefix else str(key)
        existing = target.get(key)
        if isinstance(existing, dict) and isinstance(value, Mapping):
            _deep_merge(existing, value, layer_name, provenance, overridden_fields, field_path)
            continue
        if key in target and target[key] != value:
            overridden_fields.append(
                {"field": field_path, "previous_layer": provenance.get(field_path), "new_layer": layer_name}
            )
        target[key] = deepcopy(value)
        provenance[field_path] = layer_name
