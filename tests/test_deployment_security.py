from pathlib import Path

import pytest

from app.core.config import Settings


def test_insecure_local_auth_requires_an_explicit_environment_flag(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("LLE_ALLOW_INSECURE_LOCAL_AUTH", raising=False)
    assert Settings.from_environment().allow_insecure_local_auth is False

    monkeypatch.setenv("LLE_ALLOW_INSECURE_LOCAL_AUTH", "true")
    assert Settings.from_environment().allow_insecure_local_auth is True

    monkeypatch.setenv("LLE_ALLOW_INSECURE_LOCAL_AUTH", "unexpected")
    with pytest.raises(ValueError, match="LLE_ALLOW_INSECURE_LOCAL_AUTH"):
        Settings.from_environment()


def test_compose_requires_runtime_secrets_and_binds_api_to_loopback() -> None:
    compose = (Path(__file__).resolve().parents[1] / "docker-compose.yml").read_text(encoding="utf-8")

    assert "${LLE_ADMIN_TOKEN:?" in compose
    assert "${LLE_SECRET_ENCRYPTION_KEY:?" in compose
    assert "${LLE_POSTGRES_PASSWORD:?" in compose
    assert '"127.0.0.1:8000:8000"' in compose
