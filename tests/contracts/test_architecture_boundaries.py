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
    "modules/reports/api.py",
    "modules/reports/assets_api.py",
    "modules/reviews/api.py",
    "modules/reviews/judges_api.py",
}
KNOWN_STRING_ERROR_ROUTING: set[str] = set()
KNOWN_SHARED_TO_FEATURE_IMPORTS: set[str] = set()
KNOWN_FRONTEND_WORKSPACE_OWNERSHIP_DEBT: set[str] = set()


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


def test_evaluation_application_does_not_select_persistence_backend() -> None:
    forbidden = ("database_kind", "app.db.mongo", "app.infrastructure.persistence", "if store is not None")
    offenders = {
        _relative(path, BACKEND)
        for path in _python_files(BACKEND / "modules" / "evaluations")
        if any(token in path.read_text(encoding="utf-8") for token in forbidden)
    }
    assert offenders == set()


def test_provider_orchestrators_do_not_branch_on_protocol_profiles() -> None:
    provider_root = BACKEND / "infrastructure" / "providers"
    orchestrators = ("capabilities.py", "connection.py", "executor.py")
    profile_names = (
        "openai_chat_completions",
        "openai_responses",
        "anthropic_messages",
        "gemini_generate_content",
        "azure_openai_chat_completions",
        "ollama_chat",
        "custom_http_json",
    )
    offenders = {
        name
        for name in orchestrators
        if any(profile in (provider_root / name).read_text(encoding="utf-8") for profile in profile_names)
    }
    assert offenders == set()
    common = (provider_root / "common.py").read_text(encoding="utf-8")
    assert "def extract_prediction(" not in common
    assert "def extract_token_logprobs(" not in common
    assert "def adapter_defaults(" not in common
    assert "def translate_chat_messages(" not in common
    assert "def translate_responses_messages(" not in common
    assert "def translate_anthropic_messages(" not in common
    assert "def translate_gemini_messages(" not in common
    assert "def translate_ollama_messages(" not in common


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


def test_superseded_frontend_owners_are_deleted() -> None:
    workspace = FRONTEND / "components" / "ApplicationWorkspace.tsx"
    assert not workspace.exists()
    assert not (FRONTEND / "shared" / "api" / "index.ts").exists()
    assert KNOWN_FRONTEND_WORKSPACE_OWNERSHIP_DEBT == set()
    assert len((FRONTEND / "App.tsx").read_text(encoding="utf-8").splitlines()) <= 25
