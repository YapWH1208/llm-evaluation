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


def test_public_web_url_is_a_clean_absolute_http_url(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LLE_PUBLIC_WEB_URL", "https://evaluation.example.test/")
    assert Settings.from_environment().public_web_url == "https://evaluation.example.test"

    monkeypatch.setenv("LLE_PUBLIC_WEB_URL", "https://evaluation.example.test/?token=secret")
    with pytest.raises(ValueError, match="LLE_PUBLIC_WEB_URL"):
        Settings.from_environment()


def test_compose_requires_runtime_secrets_and_binds_api_to_loopback() -> None:
    compose = (Path(__file__).resolve().parents[1] / "docker-compose.yml").read_text(encoding="utf-8")

    assert "${LLE_ADMIN_TOKEN:?" in compose
    assert "${LLE_SECRET_ENCRYPTION_KEY:?" in compose
    assert "${LLE_POSTGRES_PASSWORD:?" in compose
    assert '"127.0.0.1:8000:8000"' in compose


def test_posix_launcher_creates_only_private_atomic_secret_files() -> None:
    launcher = (Path(__file__).resolve().parents[1] / "quick-launch.sh").read_text(encoding="utf-8")

    assert "os.O_EXCL" in launcher
    assert "0o600" in launcher
    assert "mode != 0o600" in launcher
