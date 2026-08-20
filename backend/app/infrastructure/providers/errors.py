from __future__ import annotations

from app.core.errors import ConfigurationError


class UnsupportedProviderProfileError(ConfigurationError):
    """Raised when an endpoint uses a profile without a registered adapter."""
