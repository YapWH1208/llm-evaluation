# Deployment runbook

## Local SQLite mode

Use the default `sqlite:///./data/llm_evaluation.db` URL for a single-host workspace. Startup enables foreign keys, WAL mode, and a five-second busy timeout. Keep one API process and a controlled worker count for write-heavy workloads.

Set `LLE_SECRET_ENCRYPTION_KEY` before adding an endpoint. Use a stable Fernet key in the platform secret store; changing it prevents decryption of existing endpoint credentials.

The platform has no built-in authentication layer: the API is open to any caller that can reach it, and the web app binds both services to `127.0.0.1` locally. Only expose the API on a trusted network or loopback; anyone who can reach the port can read and mutate everything, including redirecting stored provider credentials.

## Team mode

Run the database CLI before serving traffic:

```powershell
python -m app.cli database preview
python -m app.cli database initialize
python -m app.cli database validate
```

The task lease protocol uses conditional state updates, lease tokens, and monotonically increasing lease versions. Admission serializes relational capacity/rate reservations before a task is leased, so a failed claim cannot consume budget and a reclaimed worker cannot extend its old lease. Run multiple worker processes only with MongoDB; SQLite is intentionally optimized for local/lightweight single-process use.

Optional admission ceilings can be set before starting the API: `LLE_SYSTEM_MAX_CONCURRENCY` limits all active leases, and `LLE_WORKER_MAX_CONCURRENCY` limits leases held by one worker ID. Each queued run may set its own ceiling; each endpoint can set an endpoint ceiling and a shared API-key ceiling; and a benchmark manifest may set `max_concurrency`. The scheduler admits work only when every configured ceiling has capacity.

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

Before each connection probe, capability probe, and model request, the platform resolves every A/AAAA address for the provider host and rejects loopback, private, link-local, multicast, reserved, and unspecified targets. Redirects are refused rather than followed. The explicit `ollama_chat` profile is the sole local-loopback exception. Provider response bodies are streamed and capped at 4 MiB by default; set `LLE_PROVIDER_RESPONSE_MAX_BYTES` to a positive deployment-specific limit when needed.

## Dataset sources and credentials

Dataset versions accept only `https://` URLs and Hugging Face dataset references in canonical `hf://datasets/owner/repository/path/to/file` or backward-compatible shorthand `hf://owner/repository/path/to/file` form. For example, `hf://datasets/hf-internal-testing/textfolder/hello.txt` and `hf://hf-internal-testing/textfolder/hello.txt` resolve the same repository file. Paths are strict repository-file paths: Dataset Viewer split names do not create virtual folders, so `train/hello.txt` fails when only root-level `hello.txt` exists. Model and Space repository types are rejected. `file://` URLs, local paths, HTTP, and custom downloader schemes are also rejected; upload local revisions through the dataset upload endpoint instead. Downloads are streamed with a 64 MiB default cap, adjustable with `LLE_DATASET_DOWNLOAD_MAX_BYTES`.

Administrators configure credential bindings outside evaluator input using `LLE_DATASET_CREDENTIAL_BINDINGS_JSON`. Each logical ID names one environment variable and the exact hosts that may receive its bearer token. For example:

```powershell
$env:HUGGINGFACE_TOKEN = "..."
$env:LLE_DATASET_CREDENTIAL_BINDINGS_JSON = '{"huggingface":{"environment_variable":"HUGGINGFACE_TOKEN","allowed_hosts":["huggingface.co"]}}'
```

Evaluators submit `credential_binding_id: "huggingface"`; they never submit an environment-variable name. Existing `credential_env_var` database values remain historical metadata and are never dereferenced. Use `LLE_DATASET_ALLOWED_HOSTS` as an optional comma-separated deployment-wide source-host allowlist in addition to the restricted-address checks.

## Docker Compose

1. Run `docker compose up --build` — no environment variables are required. The stack is `api` (FastAPI backend, SQLite database under the mounted `./data` volume) and `web` (nginx serving the built SPA). The API is published on `http://127.0.0.1:8000` and the SPA on `http://127.0.0.1:5173`.
2. On first start the API container auto-provisions a Fernet key at `./data/.lle-secret-key` (mode 0600) and reuses it on later starts, so endpoint API keys stay encrypted at rest and remain decryptable across restarts. To use your own key instead, set `LLE_SECRET_ENCRYPTION_KEY` in the environment (or pass it to the container); the entrypoint honors it and skips provisioning. Never delete or change the key file after endpoints have been saved, or their stored credentials can no longer be decrypted.
3. The `web` container builds the frontend with Vite, and nginx rewrites `/dashboard`, `/guide`, `/models`, `/datasets`, `/prompts`, `/runs`, `/leaderboard`, `/analysis`, `/settings`, and `/shared-reports/<token>` to `index.html` so direct loads and refreshes reach the client router. These are internal rewrites, not redirects.
4. For a remote API deployment, rebuild the `web` image with the API base URL baked in: `docker compose build --build-arg VITE_API_BASE_URL=https://api.example/api/v1 web`. For password-protected public shares, follow the `LLE_PUBLIC_WEB_URL` / `VITE_PUBLIC_API_BASE_URL` origin guidance in the [Public report sharing](#public-report-sharing) section below.

This delivery validates the Compose configuration with `docker compose config`, builds both images (`docker build ./frontend` and `docker build .`), and smoke-tests the full stack (API with SQLite + nginx web) from the built images, including SPA deep-link rewrites.

## Container image releases

Tagging the repository with a `v*` tag (for example `v0.4.4`) triggers the
`Docker release` workflow (`.github/workflows/docker-release.yml`): it first
runs the backend and frontend test suites and, only when they pass, builds and
publishes two images to GitHub Container Registry:

- `ghcr.io/yapwh1208/llm-evaluation-api` — the FastAPI backend.
- `ghcr.io/yapwh1208/llm-evaluation-web` — the nginx-served SPA, built with
  `VITE_API_BASE_URL=http://127.0.0.1:8000/api/v1` baked in; rebuild with the
  `VITE_API_BASE_URL` build arg for a remote API origin.

Each image is tagged with the release version (for example `0.4.4`) and
`latest`. To consume a release in Compose, replace a service's `build:`
block with its published image, for example
`image: ghcr.io/yapwh1208/llm-evaluation-api:0.4.4`. Packages inherit the
repository visibility; on a private repository, pull with a GitHub token.

## Migration and backup policy

`auto_migrate` is the default startup mode. Production services can set `LLE_DATABASE_INIT_MODE=validate` and perform migrations through CI or the CLI. SQLite backups can be enabled with `LLE_DATABASE_BACKUP_BEFORE_MIGRATE=true`; the backup uses SQLite's online backup API and writes to `<data-root>/backups`.

Validation checks migration records, tables, columns, indexes, unique constraints, foreign keys, and Mongo collection validators. Very early SQLite databases retain their original `evaluation_runs` table without three later foreign-key declarations; this compatibility exception is reported in source and avoids a destructive table rebuild, while newly created and all other persisted structures remain checked.

Before upgrades, run `python -m app.cli database preview`. After upgrades, run `python -m app.cli database validate` and check `/health` for the expected schema version.

## Operational checks

- `/health` confirms the configured database type, schema version, disk capacity, and queue counters. It returns HTTP 503 when the backing store cannot be reached; do not route traffic to an instance until it returns HTTP 200 with `database_connected: true`.
- `/api/v1/dashboard` exposes queue, endpoint, dataset, cost, error-rate, and worker-lease summaries. Its evidence window is intentionally bounded to recent runs/samples so operators should use run-specific reports for full historical analysis.
- `/api/v1/evaluation-runs/{run_id}/events` emits server-sent progress snapshots.
- `/api/v1/audit-events` exposes successful mutating operation metadata to administrators.

## Public report sharing

Set `LLE_PUBLIC_WEB_URL` to the externally served frontend origin and include that exact origin in `LLE_CORS_ORIGINS` (for example, `LLE_PUBLIC_WEB_URL=https://evaluation.example.test`, `LLE_CORS_ORIGINS=https://evaluation.example.test`). Public report links use this origin and the frontend posts the optional password only as the `X-Report-Password` request header to `VITE_PUBLIC_API_BASE_URL`; never place a password in a URL, query string, or browser storage. Apply the same `index.html` SPA rewrite to `/shared-reports/<token>` as the workspace paths above, and allow `X-Report-Password` in CORS preflights.

## Worker rollout and verification

Deploy the lease-aware API before increasing worker count. Confirm a worker can claim, heartbeat, complete, and reclaim a test task after the deployment, then monitor the bounded worker event stream and queue counters. For remote/multi-worker use MongoDB; keep SQLite to a single controlled API/worker process.

Run the following non-Docker checks before publishing a deployment artifact:

```powershell
python -m pytest -q
Set-Location frontend
npm.cmd ci
npm.cmd test -- --run
npm.cmd run build
```

On a POSIX host, also run `bash -n quick-launch.sh`. The local launcher atomically creates `data/.lle-secret-key` with mode `0600` and refuses an existing insecure or non-regular key file.
