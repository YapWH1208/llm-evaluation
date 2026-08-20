from __future__ import annotations

import ast
from pathlib import Path
import re


ROOT = Path(__file__).resolve().parents[2]
BACKEND = ROOT / "backend" / "app"
FRONTEND = ROOT / "frontend" / "src"


# This inventory is deliberately exact. Each migration removes entries until the
# sets are empty; adding another violating module fails immediately.
KNOWN_PERSISTENCE_AWARE_APIS = {
    "modules/analytics/api.py",
    "modules/analytics/comparisons_api.py",
    "modules/analytics/dashboard_api.py",
    "modules/analytics/leaderboard_api.py",
    "modules/benchmarks/api.py",
    "modules/benchmarks/prompts_api.py",
    "modules/endpoints/capabilities_api.py",
    "modules/evaluations/api.py",
    "modules/evaluations/queue_api.py",
    "modules/evaluations/suites_api.py",
    "modules/evaluations/tasks_api.py",
    "modules/reports/api.py",
    "modules/reports/assets_api.py",
    "modules/reviews/api.py",
    "modules/reviews/judges_api.py",
}
KNOWN_STRING_ERROR_ROUTING = {
    "modules/evaluations/api.py",
    "modules/evaluations/queue_api.py",
}
KNOWN_SHARED_TO_FEATURE_IMPORTS = {"shared/api/index.ts"}
KNOWN_FRONTEND_WORKSPACE_OWNERSHIP_DEBT = {"components/ApplicationWorkspace.tsx"}


def _python_files(root: Path):
    yield from sorted(root.rglob("*.py"))


def _relative(path: Path, root: Path) -> str:
    return path.relative_to(root).as_posix()


def _import_names(tree: ast.AST) -> set[str]:
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            names.add(node.module)
    return names


def test_feature_api_persistence_debt_does_not_grow() -> None:
    offenders: set[str] = set()
    for path in _python_files(BACKEND / "modules"):
        if not path.name.endswith("api.py"):
            continue
        imports = _import_names(ast.parse(path.read_text(encoding="utf-8")))
        if any(
            name == "sqlalchemy"
            or name.startswith("sqlalchemy.")
            or name in {"app.db.models", "app.db.mongo", "app.db.database"}
            for name in imports
        ):
            offenders.add(_relative(path, BACKEND))
    assert offenders == KNOWN_PERSISTENCE_AWARE_APIS


def test_string_based_error_routing_debt_does_not_grow() -> None:
    string_control_flow = re.compile(r"str\(error\)\s*(?:==|!=|\bin\b|\bnot\s+in\b)")
    offenders = {
        _relative(path, BACKEND)
        for path in _python_files(BACKEND)
        if string_control_flow.search(path.read_text(encoding="utf-8"))
    }
    assert offenders == KNOWN_STRING_ERROR_ROUTING


def test_shared_frontend_never_adds_more_feature_imports() -> None:
    offenders: set[str] = set()
    for path in sorted((FRONTEND / "shared").rglob("*.ts*")):
        source = path.read_text(encoding="utf-8")
        if "/features/" in source or "../../features/" in source:
            offenders.add(_relative(path, FRONTEND))
    assert offenders == KNOWN_SHARED_TO_FEATURE_IMPORTS


def test_app_shell_does_not_own_feature_state() -> None:
    source = (FRONTEND / "App.tsx").read_text(encoding="utf-8")
    assert "useState(" not in source
    assert "useEffect(" not in source
    assert "/features/" not in source


def test_frontend_workspace_ownership_debt_is_explicit() -> None:
    workspace = FRONTEND / "components" / "ApplicationWorkspace.tsx"
    offenders = {
        _relative(workspace, FRONTEND)
        for _ in [None]
        if workspace.exists()
        and ("useState(" in workspace.read_text(encoding="utf-8") or "api." in workspace.read_text(encoding="utf-8"))
    }
    assert offenders == KNOWN_FRONTEND_WORKSPACE_OWNERSHIP_DEBT
