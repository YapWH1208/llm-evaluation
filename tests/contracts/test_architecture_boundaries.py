from __future__ import annotations

import ast
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
BACKEND = ROOT / "backend" / "app"
FRONTEND = ROOT / "frontend" / "src"


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


def test_feature_apis_do_not_import_persistence() -> None:
    offenders: set[str] = set()
    for path in _python_files(BACKEND / "modules"):
        if not path.name.endswith("api.py"):
            continue
        imports = _import_names(ast.parse(path.read_text(encoding="utf-8")))
        if any(
            name == "sqlalchemy" or name.startswith("sqlalchemy.") or name == "app.db" or name.startswith("app.db.")
            for name in imports
        ):
            offenders.add(_relative(path, BACKEND))
    assert offenders == set()


def test_string_based_error_routing_is_not_used() -> None:
    def calls_str_error(node: ast.AST) -> bool:
        return any(
            isinstance(item, ast.Call)
            and isinstance(item.func, ast.Name)
            and item.func.id == "str"
            and len(item.args) == 1
            and isinstance(item.args[0], ast.Name)
            and item.args[0].id == "error"
            for item in ast.walk(node)
        )

    offenders: set[str] = set()
    for path in _python_files(BACKEND):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        if any(isinstance(node, (ast.Compare, ast.Match)) and calls_str_error(node) for node in ast.walk(tree)):
            offenders.add(_relative(path, BACKEND))
    assert offenders == set()


def test_evaluation_application_does_not_select_persistence_backend() -> None:
    forbidden = ("database_kind", "app.db.mongo", "app.infrastructure.persistence", "if store is not None")
    offenders = {
        _relative(path, BACKEND)
        for path in _python_files(BACKEND / "modules" / "evaluations")
        if any(token in path.read_text(encoding="utf-8") for token in forbidden)
    }
    assert offenders == set()


def test_feature_application_code_does_not_select_persistence_backend() -> None:
    forbidden = ("database_kind", "MongoDocumentStore", "SqliteEvaluationRepository", "MongoEvaluationRepository")
    offenders = {
        _relative(path, BACKEND)
        for path in _python_files(BACKEND / "modules")
        if path.name != "repositories.py" and any(token in path.read_text(encoding="utf-8") for token in forbidden)
    }
    assert offenders == set()


def test_feature_application_code_does_not_import_persistence() -> None:
    offenders: set[str] = set()
    for path in _python_files(BACKEND / "modules"):
        if path.name == "repositories.py" or path.name.endswith("api.py"):
            continue
        imports = _import_names(ast.parse(path.read_text(encoding="utf-8")))
        if any(
            name == "sqlalchemy" or name.startswith("sqlalchemy.") or name == "app.db" or name.startswith("app.db.")
            for name in imports
        ):
            offenders.add(_relative(path, BACKEND))
    assert offenders == set()


def test_persistence_adapters_do_not_invoke_application_services() -> None:
    offenders: set[str] = set()
    for path in _python_files(BACKEND / "infrastructure" / "persistence"):
        imports = _import_names(ast.parse(path.read_text(encoding="utf-8")))
        if any(name.startswith("app.modules.") and name.endswith(".service") for name in imports):
            offenders.add(_relative(path, BACKEND))
    assert offenders == set()


def test_mongo_document_store_does_not_own_queue_behavior() -> None:
    source = (BACKEND / "db" / "mongo.py").read_text(encoding="utf-8")
    assert "def claim_task(" not in source
    assert "def heartbeat_task(" not in source
    assert "def reclaim_expired_leases(" not in source
    assert "def update_task_if_current_lease(" not in source
    assert (BACKEND / "infrastructure" / "persistence" / "mongo" / "queue.py").exists()


def test_production_modules_do_not_import_private_cross_module_helpers() -> None:
    offenders: set[str] = set()
    for path in _python_files(BACKEND):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        if any(
            isinstance(node, ast.ImportFrom)
            and node.module is not None
            and any(alias.name.startswith("_") for alias in node.names)
            for node in ast.walk(tree)
        ):
            offenders.add(_relative(path, BACKEND))
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
    assert not (FRONTEND / "shared" / "api" / "types.ts").exists()
    assert {path.name for path in (FRONTEND / "shared" / "api").glob("*.ts")} == {"client.ts", "errors.ts"}
    assert KNOWN_FRONTEND_WORKSPACE_OWNERSHIP_DEBT == set()
    assert len((FRONTEND / "App.tsx").read_text(encoding="utf-8").splitlines()) <= 25
