from __future__ import annotations

import json
import re
from pathlib import Path

from app.core.config import Settings
from app.version import VERSION


ROOT = Path(__file__).resolve().parents[1]


def test_project_versions_are_stable_v1() -> None:
    pyproject = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    python_version = re.search(r'^version = "([^"]+)"$', pyproject, re.MULTILINE)
    assert python_version is not None

    frontend_package = json.loads((ROOT / "frontend/package.json").read_text(encoding="utf-8"))
    frontend_lock = json.loads((ROOT / "frontend/package-lock.json").read_text(encoding="utf-8"))

    assert python_version.group(1) == "1.0.0"
    assert VERSION == "1.0.0"
    assert Settings.local_development(database_url="sqlite://").application_version == VERSION
    assert frontend_package["version"] == "1.0.0"
    assert frontend_lock["version"] == "1.0.0"
    assert frontend_lock["packages"][""]["version"] == "1.0.0"
    assert "## 1.0.0" in (ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
