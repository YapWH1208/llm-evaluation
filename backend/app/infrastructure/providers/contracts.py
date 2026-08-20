from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol

from app.db.models import CapabilityDetection, ModelEndpoint


@dataclass(frozen=True, slots=True)
class SampleExecutionResult:
    success: bool
    request_snapshot: dict[str, Any]
    raw_response: str | None
    prediction: str | None
    error_type: str | None = None
    error_message: str | None = None
    latency_ms: float | None = None
    input_tokens: int | None = None
    output_tokens: int | None = None
    retry_after_seconds: float | None = None
    token_logprobs: tuple[float, ...] | None = None


class ModelExecutor(Protocol):
    def execute(
        self,
        endpoint: ModelEndpoint,
        api_key: str,
        input_snapshot: dict[str, object],
    ) -> SampleExecutionResult: ...


@dataclass(frozen=True, slots=True)
class ConnectionTestResult:
    success: bool
    message: str
    provider_status_code: int | None = None


@dataclass(frozen=True, slots=True)
class ConnectionTestRequest:
    """The credential-free provider request sent by a connection test."""

    method: str
    url: str
    body: dict[str, object]


@dataclass(frozen=True, slots=True)
class CapabilityDetectionResult:
    capability_key: str
    status: CapabilityDetection
    evidence: dict[str, object]
