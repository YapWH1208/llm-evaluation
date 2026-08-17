# Developer Guide

This guide is for developers working on the LLM/SLM Evaluation Platform. It
covers local setup, common commands, architecture notes, and repository
conventions. For product usage and evaluation workflows, see
[README.md](README.md) and [docs/evaluation-workflow.md](docs/evaluation-workflow.md).

## Repository layout

| Path | Purpose |
| --- | --- |
| `backend/` | FastAPI application, SQLAlchemy models, migrations, services, and benchmark plugins. |
| `frontend/` | React 19 + TypeScript + Vite web application. |
| `tests/` | Backend pytest suite. |
| `docs/` | Deployment, evaluation workflow, and project planning documents. |
| `data/` | Local SQLite database, generated reports, datasets, and secrets (gitignored). |

## Prerequisites

- Python 3.12 or newer
- Node.js 22 (the version used by CI)
- npm

## Local setup

Install and start the backend from the repository root:

```bash
python -m pip install -e ".[dev]"
export LLE_SECRET_ENCRYPTION_KEY="$(python -c 'from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())')"
uvicorn app.main:app --app-dir backend --reload
```

The API is then available at `http://127.0.0.1:8000` with interactive docs at
`http://127.0.0.1:8000/docs`.

In a second terminal, install and start the frontend:

```bash
cd frontend
npm ci
npm run dev
```

Open the workspace at `http://127.0.0.1:5173/dashboard`.

The one-command launchers (`quick-launch.sh`, `quick-launch.command`, and
`quick-launch.bat`) automate this setup, including creating a persisted Fernet
key at `data/.lle-secret-key` when `LLE_SECRET_ENCRYPTION_KEY` is not set.

## Common commands

| Task | Command |
| --- | --- |
| Install backend dependencies | `python -m pip install -e ".[dev]"` |
| Install backend + MongoDB support | `python -m pip install -e ".[dev,mongodb]"` |
| Run backend tests | `python -m pytest -q` |
| Run one backend test file | `python -m pytest tests/test_datasets.py -q` |
| Run the API locally | `uvicorn app.main:app --app-dir backend --reload` |
| Inspect database migrations | `python -m app.cli database preview` |
| Apply database migrations | `python -m app.cli database initialize` |
| Validate database schema | `python -m app.cli database validate` |
| Install frontend dependencies | `cd frontend && npm ci` |
| Start the frontend dev server | `cd frontend && npm run dev` |
| Run frontend tests once | `cd frontend && npm test -- --run` |
| Type-check and build the frontend | `cd frontend && npm run build` |
| Start the full local stack with Docker | `docker compose up --build` |

## Environment variables

The most commonly used `LLE_*` variables are:

- `LLE_SECRET_ENCRYPTION_KEY` — Fernet key used to encrypt endpoint credentials.
  If unset, the launchers and Docker entrypoint create `data/.lle-secret-key`.
- `LLE_DATABASE_URL` — defaults to `sqlite:///./data/llm_evaluation.db`; use a
  `mongodb://` URL to switch to the optional MongoDB document store.
- `LLE_DATABASE_INIT_MODE` — `auto_migrate` (default), `preview`, or `validate`.

`backend/app/core/config.py` is the single source of truth for all configuration
options, including concurrency ceilings, dataset host allowlists, CORS, and
provider limits.

## Architecture

- The FastAPI app is created by `create_app()` in `backend/app/main.py`.
- API routes live in `backend/app/api/*.py`.
- Business logic lives in `backend/app/services/*.py`.
- SQLAlchemy models live in `backend/app/db/models.py`; forward-only migrations
  live in `backend/app/db/migrations.py`.
- SQLite is the primary relational store. MongoDB is an optional document store
  with parallel service modules prefixed `mongo_` (for example,
  `mongo_datasets.py`). Feature changes usually need to keep both persistence
  paths in sync.
- Built-in benchmark plugins live in `backend/app/benchmarks/` and are registered
  through `backend/app/services/benchmark_registry.py`.

## Backend conventions

- The backend is Python 3.12+ and FastAPI/Pydantic v2 based.
- Database initialization and schema versioning are controlled by the CLI and
  startup initialization mode; do not bypass the migration helpers.
- Outbound network access is deliberately restricted: provider calls and dataset
  downloads validate addresses, redirects, host allowlists, credential bindings,
  and response/dataset size limits.
- Endpoint API keys are encrypted at rest and never returned in full.

## Frontend conventions

- All UI copy goes through the typed i18n catalog at
  `frontend/src/i18n/catalog.ts`. The catalog has strict key parity across all
  eight locales; a missing key fails `frontend/src/i18n/locales.test.ts`.
- Tests are colocated as `src/*.test.ts(x)` and use Vitest + jsdom + Testing
  Library.
- The frontend uses URL-backed task tabs. The main workspace paths are
  `/dashboard`, `/guide`, `/models`, `/datasets`, `/prompts`, `/runs`,
  `/leaderboard`, `/analysis`, and `/settings`.

## Testing and CI

CI runs exactly:

1. `python -m pytest -q` from the repository root.
2. `npm ci`
3. `npm test -- --run`
4. `npm run build`

from `frontend/`.

The pytest configuration sets `pythonpath=["backend"]` and
`testpaths=["tests"]`, so backend tests can be run without setting
`PYTHONPATH` manually. MongoDB tests use a fake client and do not require a
live MongoDB.

## Repository conventions

- Keep changes on `agent/...` branches and merge via pull requests.
- Use conventional commits: `feat:`, `fix:`, `docs:`, `test:`, `ci:`, `chore:`.
- Keep `CHANGELOG.md` updated under `## Unreleased` (or a new version section)
  when user-facing behavior changes.
- `/docs` and `/data` are gitignored. Existing docs are force-tracked; new files
  under `docs/` need `git add -f`.
- The API has no built-in authentication. Keep it on loopback or a trusted
  network.
