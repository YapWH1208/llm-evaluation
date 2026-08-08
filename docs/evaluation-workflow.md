# Evaluation workflow

This guide walks through the complete dataset evaluation workflow in the
workspace, from registering a model endpoint to inspecting scored runs. It uses
the Hugging Face example dataset `hf://lhoestq/demo1/data/train.csv` throughout,
but every step applies to any supported dataset source.

## 1. Register a model endpoint

Open the **Models** view and register the endpoint you want to evaluate with:

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

Open the **Datasets** view and fill in the registration form:

| Field | Example | Meaning |
| --- | --- | --- |
| Dataset ID | `lhoestq/demo1` | Stable identifier of the dataset in the catalog. |
| Version | `1` | Your version label for this dataset revision. |
| Revision | `main` | Branch, tag, or commit of the source repository. |
| Source URL | `hf://lhoestq/demo1/data/train.csv` | Where the file is downloaded from. |

For a Hugging Face dataset, the source uses the `hf://` scheme:

```
hf://owner/repository/path/to/file
```

- `hf://` refers to a Hugging Face **dataset** repository, so the path starts
  directly at the repository root — there is no `resolve/` segment and no
  `https://huggingface.co/datasets/` prefix.
- The **revision** selects the branch, tag, or commit to resolve the file from
  (for example `main`).
- HTTPS source URLs are also supported; local files are added through the
  dataset **upload** action instead of a URL.

You can optionally provide an expected **SHA-256 checksum** — if omitted, the
checksum is calculated and recorded after the first verified download. If the
dataset is gated or private, supply the administrator-configured
**credential binding ID** (never a raw token; see Troubleshooting below).

Registered versions can declare an optional **input field** and **reference
(output) field** used as run defaults; the run form still allows per-run
overrides. Ready datasets expose a **Preview** action that shows the first
five rows of the prepared cache, plus **Edit** and **Delete** actions.
Deleting is blocked while an evaluation run references the revision or while
the download is in progress.

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

## 4. (Optional) Create a prompt package

If you want to control how each record is turned into a model prompt, create a
prompt package from the workspace. The template uses `{{field}}` placeholders
that are substituted with the corresponding record fields at sample-build time.
For the example dataset, whose records contain a `review` and a `star` field:

```
Rate this review: {{review}}
Return only the star count.
```

When no prompt package is selected, the first non-empty string field of each
record is used as the prompt. With a prompt package, records whose fields do
not render a prompt are skipped.

## 5. Queue a dataset evaluation run

In the **Runs** view, open the dataset run form and configure:

- **Dataset** — a dataset version with status `ready`.
- **Prompt package** (optional) — the package whose template is rendered per
  record; leave empty to use the first non-empty record field as the prompt.
- **Reference field** — the record field holding the expected answer, for
  example `star`. Each record's value for this field is the exact-match
  reference the prediction is scored against (or the prompt package's scoring
  when it defines one).
- **Sample limit** — how many records (1–10,000, default 100) to draw from the
  dataset.
- **Endpoint** — any model endpoint with status `available`.

The form queues the run directly; the backend validates it and returns clear
errors when a check fails — for example a dataset version that is not `ready`,
a reference field that matches no record field, or an endpoint that is not
available. For scripted checks, the API additionally exposes
`POST /api/v1/evaluation-runs/dataset/preflight`.

## 6. Watch and inspect

Track the run from the **Runs** view:

- **Run status** — the run moves through queued → running → completed (or a
  terminal failure state) as the task queue schedules it against the endpoint.
- **Sample attempts** — each record becomes a sample attempt with the fully
  rendered prompt, the request sent, the raw provider response, the parsed
  prediction, the reference answer, latency, token usage, and the exact-match
  score.
- **Reports** — once the run finishes, generate report artifacts (HTML, JSON,
  CSV, Parquet) from the run's evidence, and share them with read-only links
  when needed.

Failed samples can be retried, and the run's evidence remains inspectable even
after the run itself is archived.

## Troubleshooting

| Symptom | Cause | Fix |
| --- | --- | --- |
| `401 Unauthorized` or status `credential_required` | The repository is private or gated, and no credential is bound. | Configure a credential binding in the deployment (`LLE_DATASET_CREDENTIAL_BINDINGS_JSON` plus the token environment variable, for example `HUGGINGFACE_TOKEN`), then register the dataset with that `credential_binding_id`. Alternatively, check that the owner/repository name is spelled correctly. |
| `404` on download | The repository or file does not exist. | Verify the repository name and the file path inside it, and that the revision (`main` or another branch/tag/commit) actually contains the file. |
| Checksum mismatch | The download is corrupted or incomplete. | Use **Validate** to re-check the cached file, or clear the dataset cache and download again. |
| `not supported for evaluation runs` | The cached format cannot be read as records. | Use JSONL, JSON, CSV, TSV, or TXT files. Parquet and zip files are cached for reference but are not runnable as evaluation datasets. |
| No usable records | The reference field name does not match any record field. | Check the dataset preview and use the exact field name (for example `star`, not `stars` or `Star`). Records missing the reference field are skipped. |
