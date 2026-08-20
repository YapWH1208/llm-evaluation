from __future__ import annotations

from typing import Any


class ApplicationError(Exception):
    """Small typed hierarchy shared by feature services and infrastructure ports."""

    code = "application_error"
    http_status = 500

    def __init__(self, message: str, *, context: dict[str, Any] | None = None) -> None:
        super().__init__(message)
        self.context = context or {}


class NotFoundError(ApplicationError):
    code = "not_found"
    http_status = 404


class ConflictError(ApplicationError):
    code = "conflict"
    http_status = 409


class ValidationError(ApplicationError):
    code = "validation_error"
    http_status = 422


class ExternalServiceError(ApplicationError):
    code = "external_service_error"
    http_status = 502


class ConfigurationError(ApplicationError):
    code = "configuration_error"
    http_status = 503
