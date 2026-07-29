# LLM/SLM Evaluation Platform

An API-hosted model evaluation workspace with encrypted endpoint credentials, reproducible runs, durable sample evidence, multimodal custom checks, human/LLM judging, reports, comparisons, queue controls, and a React web application.

## Quick start (SQLite)

For a one-command local launch, run the platform-specific script from the repository root:

- Windows: double-click `quick-launch.bat`.
- macOS: run `chmod +x quick-launch.command && ./quick-launch.command`.
- Linux: run `chmod +x quick-launch.sh && ./quick-launch.sh`.

The launchers install missing development dependencies, start the API and web app, and create `data/.lle-secret-key` on first run. That key is ignored by Git and keeps encrypted endpoint credentials available across restarts. They explicitly enable unauthenticated local-only API access when no `LLE_ADMIN_TOKEN` is supplied; set an administrator token for any shared or remote deployment. Set `LLE_SECRET_ENCRYPTION_KEY` yourself to use a different stable key.

To start the services manually instead:

```powershell
python -m pip install -e ".[dev]"
$env:LLE_SECRET_ENCRYPTION_KEY = (python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())")
uvicorn app.main:app --app-dir backend --reload
```

In another terminal:

```powershell
Set-Location frontend
npm.cmd install
npm.cmd run dev
```

Open the web workspace at `http://127.0.0.1:5173`. The API is available at `http://127.0.0.1:8000/docs` and defaults to `data/llm_evaluation.db`.

## Database operations

SQLite and PostgreSQL share the SQLAlchemy schema, forward-only migrations, queue semantics, and database initialization controls.

```powershell
# Show pending migrations without changing a database
python -m app.cli database preview

# Create/upgrade structures and validate the resulting version
python -m app.cli database initialize

# Fail unless an existing database is complete and current
python -m app.cli database validate
```

Set `LLE_DATABASE_INIT_MODE` to `auto_migrate` (default), `preview`, or `validate`. Set `LLE_DATABASE_BACKUP_BEFORE_MIGRATE=true` to create a consistent SQLite backup in `data/backups` before pending migrations run.

## PostgreSQL team deployment

```powershell
python -m pip install -e ".[dev,postgresql]"
$env:LLE_DATABASE_URL = "postgresql+psycopg://lle:change-me@127.0.0.1:5432/lle"
$env:LLE_SECRET_ENCRYPTION_KEY = "your-Fernet-key"
uvicorn app.main:app --app-dir backend --host 0.0.0.0 --port 8000
```

See [deployment.md](docs/deployment.md) for Docker Compose, environment variables, backups, and production checks.

## Security notes

Endpoint API keys are encrypted at rest and only a masked suffix is returned. `LLE_ADMIN_TOKEN` is required unless `LLE_ALLOW_INSECURE_LOCAL_AUTH=true` is explicitly set for local development; create scoped user tokens for role-based access. The platform audits successful mutating API calls without recording request bodies, keys, prompts, or model responses in the audit entry.
