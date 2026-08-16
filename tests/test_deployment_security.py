import os
import stat
import subprocess
from pathlib import Path

import pytest

from app.core.config import Settings


def test_public_web_url_is_a_clean_absolute_http_url(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LLE_PUBLIC_WEB_URL", "https://evaluation.example.test/")
    assert Settings.from_environment().public_web_url == "https://evaluation.example.test"

    monkeypatch.setenv("LLE_PUBLIC_WEB_URL", "https://evaluation.example.test/?token=secret")
    with pytest.raises(ValueError, match="LLE_PUBLIC_WEB_URL"):
        Settings.from_environment()


def test_compose_needs_no_environment_variables_and_binds_api_to_loopback() -> None:
    compose = (Path(__file__).resolve().parents[1] / "docker-compose.yml").read_text(encoding="utf-8")

    assert ":?Set " not in compose
    assert "sqlite:////data/llm_evaluation.db" in compose
    assert '"127.0.0.1:8000:8000"' in compose


def _run_entrypoint(data_root: Path, extra_env: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
    script = Path(__file__).resolve().parents[1] / "backend" / "docker-entrypoint.sh"
    env = {**os.environ, "LLE_DATA_ROOT": str(data_root), **(extra_env or {})}
    return subprocess.run(
        ["bash", str(script), "sh", "-c", 'printf %s "$LLE_SECRET_ENCRYPTION_KEY"'],
        capture_output=True, text=True, env=env, check=False,
    )


def test_api_entrypoint_provisions_and_reuses_a_private_fernet_key_file(tmp_path: Path) -> None:
    first = _run_entrypoint(tmp_path)
    assert first.returncode == 0, first.stderr
    assert len(first.stdout.strip()) > 40

    key_file = tmp_path / ".lle-secret-key"
    assert key_file.is_file()
    assert stat.S_IMODE(key_file.stat().st_mode) == 0o600
    assert key_file.read_text(encoding="utf-8").strip() == first.stdout

    second = _run_entrypoint(tmp_path)
    assert second.returncode == 0, second.stderr
    assert second.stdout == first.stdout


def test_api_entrypoint_honors_an_explicit_key_and_refuses_insecure_files(tmp_path: Path) -> None:
    explicit = _run_entrypoint(tmp_path, {"LLE_SECRET_ENCRYPTION_KEY": "explicit-key"})
    assert explicit.returncode == 0, explicit.stderr
    assert explicit.stdout == "explicit-key"
    assert not (tmp_path / ".lle-secret-key").exists()

    insecure = tmp_path / ".lle-secret-key"
    insecure.write_text("world-readable", encoding="utf-8")
    insecure.chmod(0o644)
    refused = _run_entrypoint(tmp_path)
    assert refused.returncode != 0
    assert "Refusing insecure LLE secret file" in refused.stderr


def test_posix_launcher_creates_only_private_atomic_secret_files() -> None:
    launcher = (Path(__file__).resolve().parents[1] / "quick-launch.sh").read_text(encoding="utf-8")

    assert "os.O_EXCL" in launcher
    assert "0o600" in launcher
    assert "mode != 0o600" in launcher
