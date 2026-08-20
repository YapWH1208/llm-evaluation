"""Provider protocol adapters and their application-facing contracts."""

from app.infrastructure.providers.registry import ProviderRegistry
from app.infrastructure.providers.contracts import (
    CapabilityDetectionResult,
    ConnectionTestRequest,
    ConnectionTestResult,
    ModelExecutor,
    SampleExecutionResult,
)

__all__ = [
    "CapabilityDetectionResult",
    "ConnectionTestRequest",
    "ConnectionTestResult",
    "ModelExecutor",
    "ProviderRegistry",
    "SampleExecutionResult",
]
