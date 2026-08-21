from enum import StrEnum


class EndpointStatus(StrEnum):
    UNVERIFIED = "unverified"
    AVAILABLE = "available"
    UNAVAILABLE = "unavailable"


class CapabilityDeclaration(StrEnum):
    SUPPORTED = "supported"
    UNSUPPORTED = "unsupported"
    UNKNOWN = "unknown"


class CapabilityDetection(StrEnum):
    PASSED = "passed"
    FAILED = "failed"
    INCONCLUSIVE = "inconclusive"
    NOT_TESTED = "not_tested"
    UNSUPPORTED_BY_ADAPTER = "unsupported_by_adapter"
