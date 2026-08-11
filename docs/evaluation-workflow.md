# Evaluation workflow

This guide walks through the complete dataset evaluation workflow in the
workspace, from registering a model endpoint to inspecting scored runs. It uses
the Hugging Face example dataset `hf://lhoestq/demo1/data/train.csv` throughout,
but every step applies to any supported dataset source.

The retained browser workspace is available through these direct paths:

| Path | Task tabs |
| --- | --- |
| `/dashboard` | Summary (default), `?tab=evaluations`, and `?tab=readiness`. |
| `/guide` | Getting started (default), `?tab=prepare-data`, and `?tab=run-and-analyze`. |
| `/models` | Model inventory (default) and `?tab=add-endpoint`. |
| `/datasets` | Dataset inventory (default) and `?tab=register-dataset`. |
| `/runs` | Run inventory (default), `?tab=quick-start`, `?tab=dataset-evaluation`, and `?tab=run-details&run=<run-id>`. |
| `/analysis` | Evidence scatter (default) and `?tab=compare-runs`. |
| `/leaderboard` | Filterable and sortable evaluation leaderboard. |
| `/settings` | Health (default), `?tab=access`, and `?tab=preferences`. |

Opening `/` or an unknown workspace path resolves to `/dashboard`.
The default tab uses the bare page path; non-default tabs use the `tab` query
parameter and participate in direct loading and browser back/forward history.
Run details can be selected from Run inventory or Leaderboard. A bounded `run`
query parameter restores the selected run after a direct load; omitting it shows
guidance to choose a run.

## 1. Register a model endpoint

Open **Models → Add endpoint** at `/models?tab=add-endpoint` and register the
endpoint you want to evaluate with:

- **Protocol profile** — the provider adapter (for example OpenAI-compatible
  Chat Completions, Anthropic Messages, or Custom HTTP JSON).
- **Base URL** — the API root or complete provider endpoint for the profile.
- **Model name** and **API key** (encrypted at rest; only a masked suffix is
  ever returned).

After saving, use **Test connection** to verify the endpoint responds. A
successful connection test moves the endpoint to `available`; only endpoints
with `available` status can be selected for evaluation runs. The **Probe
capabilities** action additionally records the exact capability evidence the
provider declared.

## 2. Register a dataset version

Open **Datasets → Register dataset** at `/datasets?tab=register-dataset` and
fill in the registration form:

| Field | Example | Meaning |
| --- | --- | --- |
| Dataset ID | `lhoestq/demo1` | Stable identifier of the dataset in the catalog. |
| Version | `1` | Your version label for this dataset revision. |
| Revision | `main` | Branch, tag, or commit of the source repository. |
| Source URL | `hf://lhoestq/demo1/data/train.csv` | Where the file is downloaded from. |

For a Hugging Face dataset, the source uses the `hf://` scheme:

```
hf://datasets/owner/repository/path/to/file
```

- The canonical form starts with the repository type, `datasets`. Existing
  registrations using the shorter `hf://owner/repository/path/to/file` form
  remain supported.
- `hf://` refers to a Hugging Face **dataset** repository, so the path starts
  directly at the repository root — there is no `resolve/` segment and no
  `https://huggingface.co/datasets/` prefix.
- The path must name a real repository file; Dataset Viewer split names are not
  virtual folders. For example, the checked textfolder fixture is
  `hf://datasets/hf-internal-testing/textfolder/hello.txt` (or shorthand
  `hf://hf-internal-testing/textfolder/hello.txt`), not
  `hf://hf-internal-testing/textfolder/train/hello.txt`.
- The **revision** selects the branch, tag, or commit to resolve the file from
  and defaults to `main` for new registrations. Existing stored registrations
  keep their original revision value; the new default does not rewrite legacy
  records.
- HTTPS source URLs are also supported; local files are added through the
  dataset **upload** action instead of a URL.

Choose the dataset's **evaluation type**, then add zero or more **capabilities**
and **languages** with the multi-select controls. Curated suggestions are provided,
and valid custom values can be added; saved values are normalized, deduplicated, and
restored when editing the dataset. These fields describe the dataset as a whole and
support Analysis and Leaderboard filtering; they do not overwrite sample-level facts.

You can optionally provide an expected **SHA-256 checksum** — if omitted, the
checksum is calculated and recorded after the first verified download. If the
dataset is gated or private, supply the administrator-configured
**credential binding ID** (never a raw token; see Troubleshooting below).

Registered versions can declare an optional **input field** and **reference
(output) field** used as run defaults. Once a dataset is ready, registration editing
reads the prepared schema and exposes distinct field selectors; missing, stale, or
identical selections are rejected before save. The run launcher uses the same schema
to let you select either field before queueing. Ready datasets expose
a **Preview** action that shows the first five rows of the prepared cache, plus
**Start evaluation**, **Edit**, and **Delete** actions. **Start evaluation**
opens the Runs workspace with that dataset selected but does not queue anything.

Failed, credential-blocked, corrupted, and other inactive registrations retain
**Edit** and **Delete** even when no cache was created, so a source URL,
revision, checksum, license, or credential binding can be corrected. Mutating
actions are hidden while a version is actively downloading, verifying,
preparing, or being removed. Deleting is also blocked while an evaluation run
references the revision.

## 3. Accept the license, then download and verify

If the registered dataset carries license text, its status is
`license_required` until you explicitly **Accept license**. Once accepted (or
when no license is required), trigger **Download and verify**.

A download progresses through these statuses:

```
not_downloaded → downloading → verifying → preparing → ready
```

- `not_downloaded` — registered, nothing cached yet.
- `downloading` — the file is being streamed into the local dataset cache.
- `verifying` — the cached file is checked against the expected SHA-256
  checksum; when no expected checksum was supplied, one is computed and
  recorded on this first verified download.
- `preparing` — the file is being converted/laid out for record reading.
- `ready` — the dataset can be used in evaluation runs.

A failed download lands in `failed` (with the error message shown on the
dataset card) or `credential_required`/`corrupted` where applicable; use
**Retry download** to recover. For local files, use the **upload** action
instead — the uploaded file is checksum-verified and stored in the cache the
same way.

## 4. Quick start without a dataset

For a first endpoint check, open **Runs → Quick start** at
`/runs?tab=quick-start`, choose an available endpoint in the shared **Launch
context**, and use the focused Quick start form. Its
selector lists only available built-in benchmarks. The registry includes small
deterministic fixtures for text, image, silent audio, minimal video, and
combined multimodal requests; they require no dataset download and remain
available offline.

Choose an optional prompt package and sample limit, run **Preflight quick
start**, then queue the evaluation. Preflight checks endpoint compatibility and
capacity without creating a run.

## 5. (Optional) Use a prompt package

If you want to control how each record is turned into a model prompt, select a
pre-provisioned prompt package in **Runs**. Prompt packages can be managed
through `POST /api/v1/prompt-packages`; the focused browser workspace only
selects existing packages. The template uses `{{field}}` placeholders that are
substituted with the corresponding record fields at sample-build time. For the
example dataset, whose records contain a `review` and a `star` field:

```
Rate this review: {{review}}
Return only the star count.
```

When no prompt package is selected, the run's selected **input field** is used
as the prompt. API clients that omit `input_field` retain the legacy behavior
of using the first non-empty string field. With a prompt package, the package
template renders the prompt and the input field is ignored (and not recorded in
the run snapshot); records whose fields do not render a prompt are skipped.
The input and reference fields must name different columns.

## 6. Queue a dataset evaluation run

In **Runs → Dataset evaluation** at `/runs?tab=dataset-evaluation`, choose the
shared endpoint and configure the dataset evaluation form. Quick start and dataset
evaluation retain independent preflight state in separate URL-backed tabs:

- **Dataset** — a dataset version with status `ready`.
- **Input field** — selected from the fields read from the prepared dataset;
  the saved dataset default is preselected when it still exists.
- **Reference field** — also selected from the prepared schema. This field
  holds the expected answer, for example `star`, and is frozen into the run
  snapshot with the input selection.
- **Prompt package** (optional) — the package whose template is rendered per
  record; leave empty to use the selected input field directly.
- **Evaluation metric** — Default, Exact match, Normalized exact match, Token
  F1, BLEU, or ROUGE-L. An explicit selection is frozen into the run and sample
  evidence. **Default** sends no override, so the selected prompt package's
  scoring rule wins when present; otherwise the service falls back to exact
  match. In precedence order: explicit selection → prompt-package rule → exact
  match.
- **Sample limit** — how many records (1–10,000, default 100) to draw from the
  dataset.

Use **Preflight dataset** in the shared launch context to check the complete
selection without creating a run. Queueing remains disabled while schema
reading fails, either field is unresolved, or the input and reference fields
are identical. The backend returns clear errors
when a check fails — for example a dataset version that is not `ready`, a
selected field that is absent, or an endpoint that is not available. Scripted
checks can call `POST /api/v1/evaluation-runs/dataset/preflight` directly.

## 7. Watch and inspect

Track the run from **Runs → Run inventory** at `/runs` or from `/leaderboard`, then
select it to open **Run details**. New runs receive an immutable, URL-safe
`<model_name>_<dataset_or_benchmark_name>_<UTC_datetime>` display name; the UUID
remains visible for exact identity and legacy runs derive a deterministic fallback.
The detail workspace separates Overview, Metrics, Evidence, Lifecycle, Reports, and
Reviews without removing operational controls:

- **Run status** — the run moves through queued → running → completed (or a
  terminal failure state) as the task queue schedules it against the endpoint.
- **Named metrics** — task-aware aggregate metrics show exact values, sample counts,
  confidence intervals, and an explicit N/A reason when required evidence is absent.
- **Sample attempts** — each record becomes a sample attempt with the fully
  rendered prompt, the request sent, the raw provider response, the parsed
  prediction, the reference answer, latency, token usage, and the frozen metric
  score.
- **Reports** — once the run finishes, generate report artifacts (HTML, Markdown,
  PDF, JSON, CSV, or Parquet) from the run's evidence, and share them with read-only
  links when needed.

Failed samples can be retried, and the run's evidence remains inspectable even
after the run itself is archived.

Open **Analysis** at `/analysis` to explore a scatter plot with independent named-
metric axes. All eligible runs are selected initially; narrow them with the run
multi-select or date, model, dataset, status, capability, language, evaluation-type,
quality, latency, and cost filters. The linked evidence table preserves exact values
and unavailable reasons. Use `/analysis?tab=compare-runs` for unit-aware bars, exact
metric deltas, sample counts, and outcome distributions across two compatible run
snapshots.

Open **Leaderboard** at `/leaderboard` to discover all non-archived runs through
server-backed pagination. Filters can be combined, every visible data column can be
sorted, and unscored or incomplete runs remain visible with explicit N/A values.
Selecting a row restores that run in the Run details workspace.

Transient success and error notices can still be dismissed manually and now clear
automatically after five seconds; persistent inline validation remains visible until
the underlying input is corrected.

## Troubleshooting

| Symptom | Cause | Fix |
| --- | --- | --- |
| `401 Unauthorized` or status `credential_required` | The repository is private or gated, and no credential is bound. | Configure a credential binding in the deployment (`LLE_DATASET_CREDENTIAL_BINDINGS_JSON` plus the token environment variable, for example `HUGGINGFACE_TOKEN`), then register the dataset with that `credential_binding_id`. Alternatively, check that the owner/repository name is spelled correctly. |
| `404` on download | The repository or file does not exist. | Verify the repository name and the file path inside it, and that the revision (`main` or another branch/tag/commit) actually contains the file. |
| Checksum mismatch | The download is corrupted or incomplete. | Use **Validate** to re-check the cached file, or clear the dataset cache and download again. |
| `not supported for evaluation runs` | The cached format cannot be read as records. | Use JSONL, JSON, CSV, TSV, or TXT files. Parquet and zip files are cached for reference but are not runnable as evaluation datasets. |
| No usable records | The reference field name does not match any record field. | Check the dataset preview and use the exact field name (for example `star`, not `stars` or `Star`). Records missing the reference field are skipped. |
