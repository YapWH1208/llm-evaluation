from __future__ import annotations

from app.core.errors import ConfigurationError, ExternalServiceError


class ProviderError(ExternalServiceError):
    """Base error for provider adapter failures."""


class UnsupportedProviderProfileError(ConfigurationError):
    """Raised when an endpoint uses a profile without a registered adapter."""


class ProviderRequestError(ProviderError):
    """Raised when an adapter cannot construct a safe provider request."""
