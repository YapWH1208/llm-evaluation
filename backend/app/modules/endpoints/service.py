from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import ipaddress
from typing import Any
from urllib.parse import urlparse

from app.core.errors import NotFoundError, ValidationError
from app.core.secrets import SecretCipher, mask_secret
from app.modules.endpoints.models import CapabilityDeclaration, CapabilityDetection, EndpointStatus
from app.infrastructure.providers.capabilities import CapabilityDetector
from app.infrastructure.providers.contracts import CapabilityDetectionResult
from app.infrastructure.providers.connection import build_connection_test_request
from app.infrastructure.providers.common import effective_request_options
from app.infrastructure.providers.registry import ProviderRegistry
from app.modules.endpoints.ports import EndpointRepository


class EndpointService:
    """Store-neutral endpoint use cases; persistence adapters only store primitives."""

    def __init__(self, repository: EndpointRepository, providers: ProviderRegistry | None = None) -> None:
        self._repository = repository
        self._providers = providers or ProviderRegistry()

    def create(self, payload: Any, cipher: SecretCipher) -> Any:
        api_key = payload.api_key.get_secret_value()
        now = datetime.now(timezone.utc)
        return self._repository.create(
            {
                "display_name": payload.display_name or payload.model_name,
                "base_url": payload.base_url,
                "model_name": payload.model_name,
                "protocol_profile": payload.protocol_profile,
                "encrypted_api_key": cipher.encrypt(api_key),
                "api_key_fingerprint": _api_key_fingerprint(api_key),
                "api_key_mask": mask_secret(api_key),
                "custom_headers": payload.custom_headers,
                "default_request_body": payload.default_request_body,
                "timeout_seconds": payload.timeout_seconds,
                "max_concurrency": payload.max_concurrency,
                "api_key_max_concurrency": payload.api_key_max_concurrency,
                "requests_per_second": payload.requests_per_second,
                "requests_per_minute": payload.requests_per_minute,
                "tokens_per_minute": payload.tokens_per_minute,
                "input_tokens_per_minute": payload.input_tokens_per_minute,
                "output_tokens_per_minute": payload.output_tokens_per_minute,
                "input_cost_per_million": payload.input_cost_per_million,
                "output_cost_per_million": payload.output_cost_per_million,
                "currency": payload.currency.upper(),
                "tags": payload.tags,
                "notes": payload.notes,
                "status": EndpointStatus.UNVERIFIED.value,
                "last_tested_at": None,
                "last_connection_error": None,
                "created_at": now,
                "updated_at": now,
            }
        )

    def list(self) -> list[Any]:
        return self._repository.list()

    def get(self, endpoint_id: str) -> Any:
        endpoint = self._repository.get(endpoint_id)
        if endpoint is None:
            raise NotFoundError("Model endpoint not found.", context={"endpoint_id": endpoint_id})
        return endpoint

    def update(self, endpoint_id: str, payload: Any, cipher: SecretCipher) -> Any:
        endpoint = self.get(endpoint_id)
        nullable_fields = {
            "api_key_max_concurrency",
            "requests_per_second",
            "requests_per_minute",
            "tokens_per_minute",
            "input_tokens_per_minute",
            "output_tokens_per_minute",
            "input_cost_per_million",
            "output_cost_per_million",
            "notes",
        }
        values = payload.model_dump(exclude_unset=True, exclude={"api_key"})
        values = {key: value for key, value in values.items() if value is not None or key in nullable_fields}
        base_url = str(values.get("base_url", _value(endpoint, "base_url")))
        profile = str(values.get("protocol_profile", _value(endpoint, "protocol_profile", "openai_chat_completions")))
        _validate_loopback_profile(base_url, profile)
        if "currency" in values:
            values["currency"] = str(values["currency"]).upper()
        if "api_key" in payload.model_fields_set and payload.api_key is not None:
            api_key = payload.api_key.get_secret_value()
            values.update(
                {
                    "encrypted_api_key": cipher.encrypt(api_key),
                    "api_key_mask": mask_secret(api_key),
                    "api_key_fingerprint": _api_key_fingerprint(api_key),
                }
            )
        if _connection_fields_changed(payload, values, endpoint):
            values.update(
                {"status": EndpointStatus.UNVERIFIED.value, "last_tested_at": None, "last_connection_error": None}
            )
        updated = self._repository.update(endpoint_id, values)
        if updated is None:
            raise NotFoundError("Model endpoint not found.", context={"endpoint_id": endpoint_id})
        return updated

    def delete(self, endpoint_id: str) -> None:
        if not self._repository.delete(endpoint_id):
            raise NotFoundError("Model endpoint not found.", context={"endpoint_id": endpoint_id})

    def connection_request(self, endpoint_id: str) -> Any:
        endpoint = self.get(endpoint_id)
        return endpoint, build_connection_test_request(_endpoint_proxy(endpoint), self._providers)

    def record_connection_test(self, endpoint_id: str, *, success: bool, message: str, tested_at: datetime) -> Any:
        updated = self._repository.update(
            endpoint_id,
            {
                "last_tested_at": tested_at,
                "status": EndpointStatus.AVAILABLE.value if success else EndpointStatus.UNAVAILABLE.value,
                "last_connection_error": None if success else message,
            },
        )
        if updated is None:
            raise NotFoundError("Model endpoint not found.", context={"endpoint_id": endpoint_id})
        return updated

    def preview_request(self, endpoint_id: str, messages: list[dict[str, Any]]) -> tuple[str, dict[str, Any]]:
        endpoint = self.get(endpoint_id)
        adapter = self._providers.for_endpoint(_endpoint_proxy(endpoint))
        try:
            request = adapter.build_request_with_options(
                _endpoint_proxy(endpoint),
                messages,
                effective_request_options(
                    {}, protocol_profile=adapter.profile, model_defaults=_value(endpoint, "default_request_body", {})
                ),
            )
        except ValueError as error:
            raise ValidationError(str(error)) from error
        return adapter.profile, request.body

    def list_capabilities(self, endpoint_id: str) -> list[Any]:
        self.get(endpoint_id)
        return self._repository.list_capabilities(endpoint_id)

    def list_capability_conflicts(self, endpoint_id: str) -> list[dict[str, Any]]:
        conflicts = []
        for capability in self.list_capabilities(endpoint_id):
            values = _capability_values(capability)
            if values["effective_status"] in {"user_declared_detection_failed", "detected_user_unsupported"}:
                conflicts.append({**values, "resolution_options": ["keep_disabled", "force_enable", "redetect"]})
        return conflicts

    def declare_capability(self, endpoint_id: str, capability_key: str, user_status: str) -> Any:
        self.get(endpoint_id)
        existing = self._repository.find_capability(endpoint_id, capability_key)
        detected = _value(existing, "auto_detection_status", CapabilityDetection.NOT_TESTED.value)
        return self._repository.upsert_capability(
            endpoint_id,
            capability_key,
            {
                "user_declared_status": user_status,
                "auto_detection_status": detected,
                "effective_status": effective_capability(user_status, str(detected)),
                "detection_evidence": _value(existing, "detection_evidence"),
                "detector_version": _value(existing, "detector_version"),
                "last_detected_at": _value(existing, "last_detected_at"),
            },
        )

    def detect_capabilities(
        self, endpoint_id: str, capability_keys: list[str], cipher: SecretCipher, detector: CapabilityDetector
    ) -> list[Any]:
        endpoint = self.get(endpoint_id)
        keys = list(dict.fromkeys(key.strip() for key in capability_keys if key.strip()))
        if not keys:
            raise ValidationError("At least one capability key is required")
        proxy = _endpoint_proxy(endpoint)
        encrypted = _value(endpoint, "encrypted_api_key")
        results: list[CapabilityDetectionResult] = detector.detect(proxy, cipher.decrypt(str(encrypted)), keys)
        now = datetime.now(timezone.utc)
        by_key = {result.capability_key: result for result in results}
        updated = []
        for key in keys:
            result = by_key.get(key)
            if result is None:
                continue
            existing = self._repository.find_capability(endpoint_id, key)
            user_status = str(_value(existing, "user_declared_status", CapabilityDeclaration.UNKNOWN.value))
            updated.append(
                self._repository.upsert_capability(
                    endpoint_id,
                    key,
                    {
                        "user_declared_status": user_status,
                        "auto_detection_status": result.status.value,
                        "effective_status": effective_capability(user_status, result.status.value),
                        "detection_evidence": result.evidence,
                        "detector_version": str(result.evidence.get("adapter_version", "unknown")),
                        "last_detected_at": now,
                    },
                )
            )
        return updated


def _value(endpoint: Any, key: str, default: Any = None) -> Any:
    return endpoint.get(key, default) if isinstance(endpoint, dict) else getattr(endpoint, key, default)


def _capability_values(capability: Any) -> dict[str, Any]:
    return {
        "id": str(_value(capability, "id")),
        "capability_key": str(_value(capability, "capability_key")),
        "user_declared_status": str(_value(capability, "user_declared_status")),
        "auto_detection_status": str(_value(capability, "auto_detection_status")),
        "effective_status": str(_value(capability, "effective_status")),
        "detection_evidence": _value(capability, "detection_evidence"),
        "detector_version": _value(capability, "detector_version"),
        "last_detected_at": _value(capability, "last_detected_at"),
    }


def effective_capability(user: str, detected: str) -> str:
    if user == CapabilityDeclaration.UNSUPPORTED.value and detected == CapabilityDetection.PASSED.value:
        return "detected_user_unsupported"
    if user == CapabilityDeclaration.UNSUPPORTED.value:
        return "unsupported"
    if user == CapabilityDeclaration.SUPPORTED.value and detected == CapabilityDetection.PASSED.value:
        return "verified_by_both"
    if user == CapabilityDeclaration.SUPPORTED.value and detected == CapabilityDetection.FAILED.value:
        return "user_declared_detection_failed"
    if user == CapabilityDeclaration.SUPPORTED.value:
        return "user_verified"
    if detected == CapabilityDetection.PASSED.value:
        return "auto_detected"
    return "unverified"


def _endpoint_proxy(endpoint: Any) -> Any:
    return type("DocumentEndpoint", (), endpoint)() if isinstance(endpoint, dict) else endpoint


def _connection_fields_changed(payload: Any, values: dict[str, Any], current: Any) -> bool:
    connection_fields = {
        "api_key",
        "base_url",
        "model_name",
        "protocol_profile",
        "custom_headers",
        "default_request_body",
        "timeout_seconds",
    }
    if "api_key" in payload.model_fields_set and payload.api_key is not None:
        return True
    for field in connection_fields.intersection(payload.model_fields_set):
        if field == "api_key":
            continue
        new_value = values.get(field)
        if new_value is not None and new_value != _value(current, field):
            return True
    return False


def _validate_loopback_profile(base_url: str, protocol_profile: str) -> None:
    hostname = urlparse(base_url).hostname
    if hostname is None:
        return
    try:
        is_loopback = ipaddress.ip_address(hostname).is_loopback
    except ValueError:
        is_loopback = hostname.lower() == "localhost"
    if is_loopback and protocol_profile != "ollama_chat":
        raise ValidationError("Loopback model endpoints are allowed only for the local Ollama adapter.")


def _api_key_fingerprint(api_key: str) -> str:
    return hashlib.sha256(api_key.encode("utf-8")).hexdigest()
