# Deployment runbook

## Local SQLite mode

Use the default `sqlite:///./data/llm_evaluation.db` URL for a single-host workspace. Startup enables foreign keys, WAL mode, and a five-second busy timeout. Keep one API process and a controlled worker count for write-heavy workloads.

Set `LLE_SECRET_ENCRYPTION_KEY` before adding an endpoint. Use a stable Fernet key in the platform secret store; changing it prevents decryption of existing endpoint credentials.

## PostgreSQL team mode

Install the PostgreSQL dependency extra, set `LLE_DATABASE_URL` to a `postgresql+psycopg://` URL, and run the database CLI before serving traffic:

```powershell
python -m pip install -e ".[postgresql]"
$env:LLE_DATABASE_URL = "postgresql+psycopg://lle:password@db.example/lle"
python -m app.cli database preview
python -m app.cli database initialize
python -m app.cli database validate
```

The task lease protocol uses conditional state updates and lease tokens. Run multiple worker processes only with PostgreSQL or another shared durable deployment; SQLite is intentionally optimized for local/lightweight use.

Optional admission ceilings can be set before starting the API: `LLE_SYSTEM_MAX_CONCURRENCY` limits all active leases, and `LLE_WORKER_MAX_CONCURRENCY` limits leases held by one worker ID. Each queued run may set its own ceiling; administrators can set a user ceiling; each endpoint can set an endpoint ceiling and a shared API-key ceiling; and a benchmark manifest may set `max_concurrency`. The scheduler admits work only when every configured ceiling has capacity.

Endpoint configuration also supports RPS plus distinct input-token and output-token TPM ceilings. They use durable fixed-window accounting in both relational and MongoDB document stores, so a restart or an additional worker cannot reset an already consumed provider budget.

## Docker Compose

1. Generate a Fernet key.
2. Replace `LLE_SECRET_ENCRYPTION_KEY` and the PostgreSQL password in `docker-compose.yml` before use.
3. Run `docker compose up --build`.
4. Build/serve the Vite frontend separately with `frontend/npm.cmd run build`, configuring `VITE_API_BASE_URL` when the API is remote.

## Migration and backup policy

`auto_migrate` is the default startup mode. Production services can set `LLE_DATABASE_INIT_MODE=validate` and perform migrations through CI or the CLI. SQLite backups can be enabled with `LLE_DATABASE_BACKUP_BEFORE_MIGRATE=true`; the backup uses SQLite's online backup API and writes to `<data-root>/backups`.

Before upgrades, run `python -m app.cli database preview`. After upgrades, run `python -m app.cli database validate` and check `/health` for the expected schema version.

## Operational checks

- `/health` confirms the configured relational database type and schema version.
- `/api/v1/dashboard` exposes queue, endpoint, dataset, cost, error-rate, and worker-lease summaries.
- `/api/v1/evaluation-runs/{run_id}/events` emits server-sent progress snapshots.
- `/api/v1/audit-events` exposes successful mutating operation metadata to administrators.
