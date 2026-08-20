from __future__ import annotations

from cryptography.fernet import Fernet, InvalidToken


class SecretConfigurationError(RuntimeError):
    """Raised when encrypted secret storage has not been configured."""


class SecretCipher:
    """Encrypts API keys before they cross the persistence boundary."""

    def __init__(self, key: str | None) -> None:
        if not key:
            raise SecretConfigurationError("LLE_SECRET_ENCRYPTION_KEY must be configured before storing API keys.")
        try:
            self._fernet = Fernet(key.encode("utf-8"))
        except (TypeError, ValueError) as error:
            raise SecretConfigurationError("LLE_SECRET_ENCRYPTION_KEY must be a valid Fernet key.") from error

    def encrypt(self, value: str) -> str:
        return self._fernet.encrypt(value.encode("utf-8")).decode("utf-8")

    def decrypt(self, value: str) -> str:
        try:
            return self._fernet.decrypt(value.encode("utf-8")).decode("utf-8")
        except InvalidToken as error:
            raise SecretConfigurationError("Stored API key cannot be decrypted.") from error


def mask_secret(value: str) -> str:
    """Return a display-safe marker without preserving secret content."""

    suffix = value[-4:] if len(value) >= 4 else value
    return f"••••{suffix}"
