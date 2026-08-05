# Design: Hugging Face dataset downloads and the dataset evaluation run mode

- Date: 2026-08-05
- Status: Approved by user (brainstorming session)
- Scope: `backend/`, `frontend/`, `tests/`, `docs/` in the `llm-evaluation` workspace

## Problem statement

Three related issues reported by the user:

1. Registering a dataset with an `hf://` source fails with
   `Client error '401 Unauthorized' for url 'https://huggingface.co/lhoestq/demo1/resolve/main/data/train.csv'`
   — the dataset cannot be downloaded from Hugging Face.
2. After registering a dataset, there is no way to run an evaluation that
   actually tests with the registered dataset's records.
3. There is no clear guidance for the complete evaluation workflow
   (register dataset → download → run → results/report).

## Root causes (verified)

1. **Wrong Hugging Face namespace.** `resolve_dataset_source` in
   `backend/app/services/datasets.py` builds
   `https://huggingface.co/{owner}/{repo}/resolve/{revision}/{path}` for `hf://`
   sources. That URL form addresses the **model** repo namespace. Hugging Face
   returns `401 Unauthorized` ("Invalid username or password") for dataset repos
   requested through the model namespace — verified live against
   `lhoestq/demo1` (public dataset repo, file `data/train.csv` exists):
   the bare form returns 401, while
   `https://huggingface.co/datasets/lhoestq/demo1/resolve/main/data/train.csv`
   returns 307 → 200 with the real CSV. The existing unit test
   (`tests/test_datasets.py`) codifies the wrong bare-form URL.
2. **Redirects are refused during download.** `write_dataset_source` uses
   `follow_redirects=False` plus `raise_for_status()`. Hugging Face `resolve`
   endpoints always answer with a 307 redirect to their content CDN. With the
   namespace fixed, the downloader would silently save the 164-byte redirect
   HTML page as the dataset instead of the file. Redirects are deliberately
   refused platform-wide for SSRF safety (`validate_outbound_url`,
   `read_bounded_response`), so the fix must follow redirects safely, one
   validated hop at a time.
3. **Prepared dataset records are never consumed.** The dataset pipeline
   (register → download → checksum → `prepare_dataset_cache` writing
   `prepared/sample-index.jsonl` + `manifest.json`) is complete, but nothing
   reads records back. Evaluation runs build samples exclusively from
   benchmark inline samples (`plugin.samples(sample_limit)` in
   `backend/app/services/evaluation_runs.py`); the `DATASET_PREPARATION` stage
   only downloads declared datasets to `ready`. There is no record reader, no
   API to start a run over dataset records, and no UI for it.

## Goals

- G1: `hf://owner/repo/path` dataset sources download successfully from
  Hugging Face (dataset namespace), with clear error messages when a repo is
  private/gated, missing, or misnamed.
- G2: A registered, `ready` dataset can drive an evaluation run: records are
  converted to samples via a prompt package plus a reference field, executed
  against a model endpoint, and scored.
- G3: Clear end-to-end workflow guidance in the repository documentation.
- G4: All changes covered by tests; the full existing suite stays green;
  unrelated in-flight working-tree changes stay untouched.

## Non-goals

- Multimodal dataset records (dataset runs are text/tabular only).
- Changes to authentication, report sharing, storage keys, or the benchmark
  manifest system.
- Changing the security model: every outbound request hop remains validated
  and DNS-pinned; no blind redirect following.

## Design

### 1. `hf://` namespace fix (`backend/app/services/datasets.py`)

`resolve_dataset_source` resolves `hf://owner/repository/path/to/file` to

```
https://huggingface.co/datasets/{owner}/{repository}/resolve/{quote(revision)}/{quote(relative_path, safe='/')}
```

- The `/datasets/` prefix is unconditional: this feature registers dataset
  versions, so sources are dataset repos.
- Plain HTTPS sources keep current behavior.
- Update `tests/test_datasets.py` to assert the dataset-namespace URL.
- Error message improvement in `download_dataset` (see section 2).

### 2. Bounded, per-hop validated redirect following (`write_dataset_source`)

Replace the single `follow_redirects=False` request with a loop:

- Start with the resolved URL; call `validate_outbound_url` (scheme/host/DNS/
  private-address checks) and use `pinned_outbound_transport` per hop.
- After each response: if `response.is_redirect` (301/302/303/307/308) and a
  `Location` header exists and the hop count is below the cap (5), resolve the
  next URL with `urljoin`, re-validate it with `validate_outbound_url`, and
  fetch with a fresh pinned transport. Redirects without a `Location`, or past
  the cap, raise `DatasetError`.
- Non-redirect responses: `raise_for_status()` (existing behavior; 4xx/5xx
  become the current status mapping in `download_dataset`), then stream bytes
  with the existing `max_bytes` enforcement. The redirect body is never
  written to disk.
- 401/403 mapping already sets `credential_required` when a credential
  binding is configured (`download_dataset`); additionally, 404 responses get
  a message distinguishing "repo missing or misnamed" from "private/gated"
  where the namespace fix makes the response meaningful.

### 3. Dataset record reader (new, `backend/app/services/dataset_records.py`)

- Inputs: a `DatasetVersion` with `prepared_path` (the `prepared/manifest.json`
  produced by `prepare_dataset_cache`) and `data_root`.
- Validates that the prepared root is inside the configured dataset root
  (same check style as `validate_prepared_dataset_cache`).
- Reads `sample-index.jsonl` entries (`{"source": ..., "record_number": N}`)
  and materializes each record as a field mapping:
  - `.jsonl`: one JSON object per line.
  - `.json`: a JSON array of objects, or a single object (record 1).
  - `.csv` / `.tsv`: dict per row (header row maps fields).
  - `.txt`: one record per non-empty line with field `text`.
  - Other suffixes (e.g. `.zip`, `.parquet`, binary): raise a clear
    `DatasetRecordError` ("dataset format not supported for evaluation runs").
- Records missing the reference field are reported as skipped, not fatal.
- Function shape: `iter_dataset_records(dataset, data_root, *, limit)` plus a
  `count` helper; both used by run creation and preflight.

### 4. Dataset evaluation run mode (backend)

**API:** new endpoint `POST /api/v1/evaluation-runs/dataset` in
`backend/app/api/evaluation_runs.py`, mirroring the existing
`/custom-multimodal` pattern (SQLAlchemy + Mongo document-store variants).

Request body:

```
model_endpoint_id: str
dataset_version_id: str
prompt_package_id: str | None
reference_field: str
sample_limit: int = 100          # 1..10_000
max_concurrency: int | None = None
request_body_override: dict | None = None
```

**Run creation** (`backend/app/services/dataset_runs.py`, new):

- Preflight errors (clear `detail`):
  - dataset not found, or endpoint not found → 404 (matches the existing
    "Model endpoint not found." convention);
  - dataset not `ready` → 409 (message: run the download action first);
  - endpoint not `available` → 409;
  - prompt package id given but not found → 404;
  - reference field missing from every one of the first 100 records (or all
    records when fewer), or zero usable records overall → 409;
  - `sample_limit` larger than the record count clamps to the record count
    (like benchmark `sample_limit`); `sample_limit` must be ≥ 1.
- Materialize at creation time: read up to `sample_limit` records from the
  prepared index, build one `SampleAttempt` per record with:
  - `sample_id`: `${dataset_id}:${version}:${source}#${record_number}` (stable,
    deduplicated);
  - `input_snapshot.messages`: rendered prompt. Rendering reuses the prompt
    package machinery (`_build_messages`-style): system message, few-shot
    examples, then `user_template` rendered via the existing `render_template`
    with the fixed context keys extended by the record fields (record fields
    fill `{{field}}` placeholders; fixed keys keep their existing semantics).
    With no prompt package, the record's first string field becomes the user
    message (deterministic fallback);
  - `reference_snapshot`: `{"type": scoring_rule.type, "answer": record[reference_field], "scoring": scoring_rule}`,
    where `scoring_rule` comes from the prompt package's `scoring_rule` or
    defaults to `{"type": "exact_match"}`.
- Run record: benchmark identity `dataset-evaluation@1.0.0` (synthetic,
  source `"user"`), `configuration_snapshot` freezes dataset version id,
  dataset_id/version/revision, prompt package snapshot, reference field,
  sample limit, and request-body evidence. Status `QUEUED` (records are
  already materialized; the dataset is `ready`).
- Task graph reuses existing pipeline unchanged: `DATASET_PREPARATION`
  (payload carries the frozen dataset descriptor; executor already downloads
  to `ready` idempotently), `BENCHMARK`, then `EVALUATION_SHARD` tasks with
  the same retry policy and sharding helper as benchmark runs.

**Preflight:** new endpoint `POST /api/v1/evaluation-runs/dataset/preflight`
mirroring the dataset create payload (same body shape), returning the same
`EvaluationRunPreflightResponse` shape as benchmark preflight: endpoint/dataset
readiness, usable record count, and a cost estimate based on `sample_limit`.
The existing benchmark `POST /evaluation-runs/validate` endpoint is unchanged.

### 5. Frontend (`frontend/src/App.tsx`, `frontend/src/api.ts`)

- Runs view gains a "Dataset evaluation" form: dataset select (only `ready`
  datasets listed; non-ready entries shown with a status hint), prompt
  package select (optional), reference field input, sample limit input
  (default 100), endpoint select (only `available`), queue button.
- After queueing, the run appears in the runs list with the existing status
  display; results flow through the existing attempt/report views unchanged.
- **i18n constraint:** the workspace was recently fully localized with a typed
  catalog; every new user-facing string gets a typed catalog entry and uses
  the existing translation helpers (`translateStaticTemplate`, `t()` pattern).
  No hardcoded English strings outside the catalog.

### 6. Workflow documentation (new `docs/evaluation-workflow.md`)

Step-by-step guide with the real demo example:

1. Register the dataset: `dataset_id` e.g. `hf-demo1`, `version` `1`,
   `revision` `main`, source
   `hf://lhoestq/demo1/data/train.csv` (note: `hf://` means a Hugging Face
   dataset repo; no `resolve/` segment needed).
2. Accept the license if one is attached; then "Download and verify" (status
   moves `not_downloaded` → `downloading` → `verifying` → `preparing` →
   `ready`; checksum is recorded on first download).
3. Create a prompt package (optional) or use the plain prompt fallback.
4. Start a dataset evaluation run: dataset, prompt package, reference field
   (e.g. `star`), sample limit, endpoint.
5. Watch the run (queue → running → scoring → completed), inspect sample
   attempts and scores, and open the generated report.
6. Troubleshooting: 401/403 → private/gated repo (configure a credential
   binding) or wrong repo name/revision; checksum mismatch → corrupted
   download (validate/clear cache); unsupported format → use JSONL/CSV/TSV/
   TXT/JSON; `license_required` → accept the license first.

README gets a short "Evaluation workflow" pointer section.

### 7. Testing

- `tests/test_datasets.py`: update `hf://` resolution assertion to the
  dataset namespace; add redirect-loop tests (`MockTransport`): 307 chain to
  a validated host succeeds; redirect to a private/loopback host is rejected;
  missing `Location` rejected; hop cap rejected; oversized body still
  rejected after redirects.
- New `tests/test_dataset_records.py`: record materialization for
  `.jsonl`, `.json` (array and object), `.csv`, `.tsv`, `.txt`; missing
  reference field counted as skipped; unsupported format raises; path safety
  (prepared root escape) rejected.
- New `tests/test_dataset_runs.py`: end-to-end API flow (register dataset →
  upload fixture → `POST /evaluation-runs/dataset` → execute → scored
  attempts, exact-match scoring); 409s for not-found/not-ready dataset,
  unknown reference field, unavailable endpoint; prompt-package rendering
  with `{{field}}` placeholders; Mongo store variant covered where the
  existing suite covers it.
- Full suite: `python -m pytest tests/` from the repo root; `node --check`
  on changed frontend files; manual end-to-end against the real
  `hf://lhoestq/demo1` dataset (network verified reachable).

## Acceptance criteria

- AC1: Registering `hf://lhoestq/demo1/data/train.csv` (revision `main`)
  and running download yields status `ready` with the real CSV bytes and a
  recorded checksum.
- AC2: `write_dataset_source` follows Hugging Face 307 redirects safely;
  redirects to unvalidated targets are refused; no redirect body is ever
  stored as a dataset.
- AC3: A dataset run over a fixture dataset scores attempts with
  `exact_match` against the chosen reference field; attempts carry rendered
  prompts and stable sample ids.
- AC4: Non-ready datasets and unknown reference fields produce clear 409
  errors that point at the next action.
- AC5: `python -m pytest tests/` passes; changed frontend files pass
  `node --check`; the workflow guide exists and matches the implemented
  behavior.
- AC6: Unrelated uncommitted changes (connection-tester refactor) remain
  untouched; work lands on its own branch in focused commits.

## Out of scope / deferred

- Serving dataset records from other formats (Parquet, Arrow, zip) in runs —
  the reader may reject them with a clear message; zip stays supported by the
  existing preparation pipeline for caching only.
- LLM-judge scoring for dataset runs (scoring uses the package rule or
  exact_match).
- Editing/annotating records in the UI.
