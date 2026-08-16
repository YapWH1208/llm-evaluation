# Project guidance

LLM/SLM evaluation platform: FastAPI backend (`backend/`, Python ≥3.12, SQLite-first with an optional MongoDB document store) + React 19 / Vite / TypeScript web app (`frontend/`). End-to-end flow: [docs/evaluation-workflow.md](docs/evaluation-workflow.md). Ops: [docs/deployment.md](docs/deployment.md).

## Skills — STOP. Load a skill before you act.

Skills (playbooks) are user-level, in `~/.agents/skills/`, loaded via the `skill` tool — never `run_skill`, and the names have no `superpowers-` prefix. A repo-local skill (`superdesign`) may live in `.agents/skills/` (gitignored, pinned via `skills-lock.json`).

**The rule:** before you do ANYTHING non-trivial — before you `explore`, run `bash`,
write code, or answer — STOP and check the skills index. If a skill might fit, load it.
Loading a skill is cheap. Skipping it is the #1 mistake. Process skill FIRST. Action SECOND.

| If… | Load this FIRST |
|---|---|
| starting a feature, or you have a rough idea | **brainstorming** |
| a bug, a failing or flaky test, or anything surprising | **systematic-debugging** |
| writing or fixing any code | **test-driven-development** |
| you have a spec for a multi-step task | **writing-plans** |
| executing a written plan in this session | **executing-plans** |
| about to say "done" / "fixed" / "passing" | **verification-before-completion** |
| work is done and tests pass | **finishing-a-development-branch** |
| you got code-review feedback (from `review` or a human) | **receiving-code-review** |
| need an isolated workspace | **using-git-worktrees** |
| making or editing a skill | **writing-skills** |

These skills **supplement** the native tools — they don't replace them. For
dispatching subagents, code review, parallel work, and codebase exploration, use the
native tools directly: **`task`** (run a subagent), **`review`** (code-review a diff),
**`wait`** (join parallel jobs), **`explore`** (investigate the codebase).

If you catch yourself about to explore, fix, or answer without loading a skill — STOP and load it.
"Build X" → brainstorming first. "Fix this bug" → systematic-debugging first.

## Commands (repo root)

- Install backend deps: `python -m pip install -e ".[dev]"` (editable install from repo root; `pythonpath=["backend"]` comes from pyproject.toml). No requirements.txt. MongoDB needs the extra: `"…[dev,mongodb]"` (pymongo is not in the base dev install).
- Backend tests: `python -m pytest -q` (config sets `pythonpath=["backend"]`, `testpaths=["tests"]`). Single file: `python -m pytest tests/test_x.py -q`.
- Run API: `uvicorn app.main:app --app-dir backend --reload` (docs at `/docs` on port 8000).
- DB CLI: `python -m app.cli database preview|initialize|validate` (migrations also run automatically at startup).
- Docker deploy: `docker compose up --build` (API with SQLite + web container) needs `LLE_SECRET_ENCRYPTION_KEY`, `LLE_ADMIN_TOKEN`; see docs/deployment.md.
- Frontend deps/dev server: `npm ci` / `npm run dev` **inside `frontend/`** (vite, port 5173). Root `package-lock.json` is a stub — never `npm install` at repo root. Node 22 is what CI uses.
- Frontend tests: `npm test -- --run` in `frontend/` — bare `npm test` is vitest **watch mode** (config lives in `vite.config.ts`: jsdom, `src/test-setup.ts`).
- Frontend typecheck + build: `npm run build` (runs `tsc -b && vite build`). No lint script exists for either end.
- One-command local launch: `quick-launch.sh` / `quick-launch.command` / `quick-launch.bat` (installs deps, starts both services, creates `data/.lle-secret-key` on first run).

## Environment (LLE_*)

- `LLE_ADMIN_TOKEN` is required at startup unless `LLE_ALLOW_INSECURE_LOCAL_AUTH=true` (enforced in `backend/app/core/config.py`).
- `LLE_SECRET_ENCRYPTION_KEY` — Fernet key for encrypted endpoint credentials; if unset the launchers persist one at `data/.lle-secret-key` (gitignored).
- `LLE_DATABASE_URL` — defaults to `sqlite:///./data/llm_evaluation.db`; `mongodb://` switches to the document store.
- `LLE_DATABASE_INIT_MODE` — `auto_migrate` (default) | `preview` | `validate`.
- Full list (concurrency ceilings, dataset host allowlists, CORS, etc.): `backend/app/core/config.py` is the single source of truth.

## Architecture

- App factory `create_app()` in `backend/app/main.py`; routers in `backend/app/api/*.py`; business logic in `backend/app/services/*.py`; SQLAlchemy models in `backend/app/db/models.py`.
- SQLite owns the SQLAlchemy schema and forward-only migrations (`backend/app/db/migrations.py`). MongoDB is a separate document store (`backend/app/db/mongo.py`) with parallel service modules (`mongo_*.py`) — changes to a feature usually need both relational and Mongo paths.
- Builtin benchmark plugins live in `backend/app/benchmarks/` (registry + `text_quick_check.py`).

## Testing quirks

- pytest is configured with `asyncio_default_fixture_loop_scope = "function"`; no asyncio markers needed.
- MongoDB tests fake the client — never require a live MongoDB.
- Avoid wall-clock-dependent tests (history: rate-window tests were made deterministic for this reason).
- CI (`.github/workflows/ci.yml`) runs exactly: `python -m pytest -q`, then in `frontend/`: `npm ci`, `npm test -- --run`, `npm run build`. Passing these is the definition of done.

## Frontend conventions

- All UI copy goes through the typed i18n catalog `frontend/src/i18n/catalog.ts` (8 locales, strict key parity — a missing key fails `src/i18n/locales.test.ts`).
- Tests are colocated as `src/*.test.ts(x)` (vitest + jsdom + Testing Library).

## Repo gotchas

- `.code-review-graph/` is a local-only knowledge graph DB (gitignored). A pre-commit hook runs `code-review-graph update` and `detect-changes --brief`. If the graph warns it was built on another branch, run `code-review-graph build`.
- `/docs` and `/data` are gitignored (existing docs are force-tracked; new files under `docs/` need `git add -f`). `reasonix.toml` is gitignored too.
- Default branch is `master`; feature work is done on `agent/...` branches merged via PRs. Keep commits conventional (`feat:`, `fix:`, `docs:`, `test:`, `ci:`).
- Keep `CHANGELOG.md` updated under `## Unreleased` (or a new version section) when user-facing behavior changes.
