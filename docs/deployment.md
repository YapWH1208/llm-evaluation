# Deployment runbook

## Local SQLite mode

Use the default `sqlite:///./data/llm_evaluation.db` URL for a single-host workspace. Startup enables foreign keys, WAL mode, and a five-second busy timeout. Keep one API process and a controlled worker count for write-heavy workloads.

Set `LLE_SECRET_ENCRYPTION_KEY` before adding an endpoint. Use a stable Fernet key in the platform secret store; changing it prevents decryption of existing endpoint credentials.

Set `LLE_ADMIN_TOKEN` before serving shared or remote traffic. The API refuses to start without it unless `LLE_ALLOW_INSECURE_LOCAL_AUTH=true` is explicitly set for local development. The local launcher sets that opt-in only when no administrator token is supplied and binds both services to `127.0.0.1`.

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

## Provider protocol profiles

Choose the protocol profile when creating a model endpoint. The platform appends the route shown below, owns authentication headers from the encrypted API key, and records the rendered provider request with each sample (never the key).

| Profile | Base URL to save | Authentication and route |
| --- | --- | --- |
| OpenAI-compatible Chat Completions | API version root, for example `https://provider.example/v1` | Bearer key; appends `/chat/completions`. |
| OpenAI Responses | API version root | Bearer key; appends `/responses`. |
| Anthropic Messages | Provider origin, for example `https://api.anthropic.com` | `x-api-key` plus `anthropic-version` (defaults to `2023-06-01`); appends `/v1/messages`. |
| Gemini GenerateContent | Gemini API version root, for example `https://generativelanguage.googleapis.com/v1beta` | `x-goog-api-key`; appends `/models/{model}:generateContent`. |
| Azure OpenAI Chat Completions | Deployment route including its `api-version` query, for example `https://resource.openai.azure.com/openai/deployments/deployment?api-version=2025-01-01-preview` | `api-key`; appends `/chat/completions` before the query string. |
| Ollama Chat | Ollama origin, for example `http://127.0.0.1:11434` | Appends `/api/chat`; its API key may be blank for an unauthenticated local service. |
| Custom HTTP JSON | The complete provider endpoint, including any query string | Sends the conventional non-streaming chat JSON body and accepts `prediction`, `text`, `response`, `output_text`, or OpenAI-style output text. |

Use custom headers for non-secret routing metadata such as a project identifier. Authentication headers are reserved for the encrypted endpoint credential. Native adapters reject unsupported media shapes before sending them; run capability detection after a successful connection test to persist the exact profile evidence.

## Dataset sources and credentials

Dataset versions accept HTTP(S) and Git-release URLs, `hf://owner/repository/path/to/file` Hugging Face references, `file://` URLs, and local file paths. Optional credentials are referenced only by an environment-variable name (for example, `HUGGINGFACE_TOKEN`); the token value is never stored in the database or returned by the API. A download without its configured credential is marked `credential_required` until the deployment environment is updated.

## Docker Compose

1. Generate a Fernet key and choose a strong administrator token.
2. Set `LLE_SECRET_ENCRYPTION_KEY`, `LLE_ADMIN_TOKEN`, and `LLE_POSTGRES_PASSWORD` in the deployment environment before use; Compose intentionally fails when any is missing and publishes the API only on loopback by default.
3. Build/serve the Vite frontend separately with `frontend/npm.cmd run build`, configuring `VITE_API_BASE_URL` when the API is remote.

This delivery validates the Compose configuration statically and does not run Docker or Docker Compose.

## Migration and backup policy

`auto_migrate` is the default startup mode. Production services can set `LLE_DATABASE_INIT_MODE=validate` and perform migrations through CI or the CLI. SQLite backups can be enabled with `LLE_DATABASE_BACKUP_BEFORE_MIGRATE=true`; the backup uses SQLite's online backup API and writes to `<data-root>/backups`.

Before upgrades, run `python -m app.cli database preview`. After upgrades, run `python -m app.cli database validate` and check `/health` for the expected schema version.

## Operational checks

- `/health` confirms the configured relational database type and schema version.
- `/api/v1/dashboard` exposes queue, endpoint, dataset, cost, error-rate, and worker-lease summaries.
- `/api/v1/evaluation-runs/{run_id}/events` emits server-sent progress snapshots.
- `/api/v1/audit-events` exposes successful mutating operation metadata to administrators.
