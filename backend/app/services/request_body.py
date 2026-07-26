"""Deterministic, auditable Request Body configuration resolution.

Provider-owned fields (model, input/messages, streaming controls and tool schema)
are deliberately never configurable at a run layer.  The resolver preserves the
values supplied by every accepted layer and explains which values won, making a
completed sample reproducible without retaining credentials.
"""

from __future__ import annotations

from collections.abc import Mapping
from copy import deepcopy
from typing import Any

from app.services.provider_headers import PROTECTED_REQUEST_FIELDS


def adapter_defaults(protocol_profile: str) -> dict[str, object]:
    """Return the platform's safe generation defaults for a protocol profile."""

    if protocol_profile == "openai_responses":
        return {"max_output_tokens": 32, "store": False}
    if protocol_profile == "gemini_generate_content":
        return {"max_output_tokens": 32, "temperature": 0}
    if protocol_profile == "ollama_chat":
        return {"max_tokens": 32, "temperature": 0}
    return {"max_tokens": 32, "temperature": 0}


def resolve_request_body(
    *,
    protocol_profile: str,
    model_defaults: Mapping[str, object] | None,
    suite_defaults: Mapping[str, object] | None = None,
    benchmark_defaults: Mapping[str, object] | None = None,
    run_override: Mapping[str, object] | None = None,
    benchmark_forced: Mapping[str, object] | None = None,
) -> dict[str, object]:
    """Apply the documented configuration order and retain field-level evidence.

    The returned JSON-safe value has the immutable configuration layers, a merged
    ``effective_request_body``, ignored protected fields, and every field that
    displaced a lower-priority value.  Objects are merged recursively so a run can
    override one nested provider option without silently losing its sibling keys.
    """

    layers: tuple[tuple[str, Mapping[str, object] | None], ...] = (
        ("adapter_defaults", adapter_defaults(protocol_profile)),
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
        _deep_merge(
            effective,
            safe_layer,
            layer_name=layer_name,
            provenance=provenance,
            overridden_fields=overridden_fields,
        )

    return {
        "protocol_profile": protocol_profile,
        "layers": snapshots,
        "effective_request_body": effective,
        "overridden_fields": overridden_fields,
        "ignored_fields": ignored_fields,
    }


def effective_request_options(input_snapshot: Mapping[str, object], *, protocol_profile: str, model_defaults: Mapping[str, object] | None) -> dict[str, object]:
    """Read precomputed evidence, or resolve endpoint-only defaults for ad hoc use."""

    evidence = input_snapshot.get("request_body_evidence")
    if isinstance(evidence, Mapping):
        effective = evidence.get("effective_request_body")
        if isinstance(effective, Mapping):
            return deepcopy(dict(effective))
    return dict(
        resolve_request_body(
            protocol_profile=protocol_profile,
            model_defaults=model_defaults,
        )["effective_request_body"]
    )


def request_snapshot_metadata(input_snapshot: Mapping[str, object]) -> dict[str, object] | None:
    """Return immutable evidence ready to embed alongside an outbound request."""

    evidence = input_snapshot.get("request_body_evidence")
    return deepcopy(dict(evidence)) if isinstance(evidence, Mapping) else None


def _normalise_layer(
    value: Mapping[str, object] | None,
    layer_name: str,
    ignored_fields: list[dict[str, object]],
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
    destination: dict[str, object],
    incoming: Mapping[str, object],
    *,
    layer_name: str,
    provenance: dict[str, str],
    overridden_fields: list[dict[str, object]],
    prefix: str = "",
) -> None:
    for key, value in incoming.items():
        path = f"{prefix}.{key}" if prefix else key
        existing = destination.get(key)
        if isinstance(existing, dict) and isinstance(value, Mapping):
            _deep_merge(
                existing,
                value,
                layer_name=layer_name,
                provenance=provenance,
                overridden_fields=overridden_fields,
                prefix=path,
            )
            continue
        if key in destination:
            overridden_fields.append(
                {
                    "field": path,
                    "previous_layer": provenance.get(path, "unknown"),
                    "new_layer": layer_name,
                    "previous_value": deepcopy(existing),
                    "effective_value": deepcopy(value),
                }
            )
        destination[key] = deepcopy(value)
        provenance[path] = layer_name
