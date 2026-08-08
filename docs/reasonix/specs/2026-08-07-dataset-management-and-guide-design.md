# Design: Dataset management (preview, input/reference fields, edit/delete) and an in-app usage guide

- Date: 2026-08-07
- Status: Approved by user (brainstorming session)
- Scope: `backend/`, `frontend/`, `tests/`, `docs/` in the `llm-evaluation` workspace

## Problem statement

Four user-requested improvements to the dataset workflow:

1. **No in-app guidance.** New users have no walkthrough of how to use the
   platform (register dataset → download/verify → create prompt package →
   queue run → inspect evidence → judge/review → reports). Documentation
   exists at `docs/evaluation-workflow.md`, but nothing in the web app.
2. **No way to inspect a dataset.** The Dataset catalog shows metadata only
   (status, size, checksum, credential binding). Users cannot see the rows
   that will be evaluated. The "go to the file location" requirement was
   explicitly skipped by the user — only data preview remains.
3. **Input/reference fields are not part of dataset registration.** The
   reference field is typed per-run (`reference_field` in
   `backend/app/api/evaluation_runs.py`), but a dataset that is registered
   for LLM testing has no declared input field or reference (output) field,
   so every run form must re-type the same value.
4. **No way to edit or delete a dataset version.** Once registered, a dataset
   can only be downloaded/uploaded/validated/cleared. Metadata mistakes
   require deleting the database row manually; stale datasets accumulate.

## Goals

- G1: An in-app guide page explaining how to use the platform end to end.
- G2: A dataset data-preview capability: the first N rows of a ready
  dataset's prepared cache, shown in the catalog.
- G3: Optional `input_field` and `reference_field` stored on
  `DatasetVersion` at registration; the dataset-run form prefills from the
  selected dataset but stays editable.
- G4: Edit (all metadata) and delete (guarded) for dataset versions, in both
  the relational and Mongo paths.
- G5: All changes covered by tests; the full existing suite stays green.

## Non-goals

- Revealing the cached file's location on the server, or downloading the
  cached file ("go to the file location" — skipped by the user).
- Previewing before download/ready state.
- Multimodal dataset records (dataset runs are text/tabular only).
- Changes to authentication, the security model, or the benchmark manifest
  system.

## Design

### 1. Backend — model and migration

`DatasetVersion` (`backend/app/db/models.py`) gains two nullable columns:

- `input_field: Mapped[str | None] = mapped_column(String(255), nullable=True)`
- `reference_field: Mapped[str | None] = mapped_column(String(255), nullable=True)`

Migration `v24` (`backend/app/db/migrations.py`, following the
`_add_column_if_missing` pattern):

- `dataset_versions.input_field VARCHAR(255)`
- `dataset_versions.reference_field VARCHAR(255)`

Mongo parallel: `backend/app/db/mongo.py` — add the two keys to the
`dataset_versions` collection schema.

`DatasetCreate` gains optional `input_field`/`reference_field`
(trimmed; when present, `min_length=1` via field validation or a
`model_validator`). `DatasetResponse` exposes both fields.

### 2. Backend — endpoints (`backend/app/api/datasets.py`)

| Method | Path | Behavior |
|---|---|---|
| `GET` | `/api/v1/datasets/{id}/preview?limit=N` | Default `limit=5`, max `50`. Reads rows from the prepared cache via the existing `iter_dataset_records` (`backend/app/services/dataset_records.py`). Returns `{"fields": [...], "rows": [{...}]}`. 409 if the dataset is not `ready` or has no prepared cache; 404 if unknown id. Values serialized as strings. |
| `PUT` | `/api/v1/datasets/{id}` | Full metadata edit: `dataset_id`, `version`, `revision`, `source_url`, `checksum`, `license_text`, `credential_binding_id`, `input_field`, `reference_field`. Reuses `_validate_dataset_registration` (source URL/credential rules). 409 on uniqueness violation (`uq_dataset_revision`); 404 if unknown. Does not touch cached files or status. Editing `license_text` preserves an existing `license_accepted_at` (the user can clear the cache to re-accept). |
| `DELETE` | `/api/v1/datasets/{id}` | Removes the registration row/document and cached files. Guards: 409 when any evaluation run's `configuration_snapshot.datasets[].dataset_version_id` references the revision (extend `_ensure_dataset_is_not_referenced` in `backend/app/services/datasets.py` with a delete-specific message), or while status is `downloading`/`preparing`/`verifying`/`removing`. Removes the `datasets/uploads/<id>` directory and prepared cache, mirroring `clear_dataset_cache` cleanup. |

Mongo parallel service functions in `backend/app/services/mongo_datasets.py`:

- `preview_mongo_dataset` — reads from the prepared cache the same way the
  relational path does (both call into `dataset_records`).
- `update_mongo_dataset` — document update with uniqueness pre-check.
- `delete_mongo_dataset` — run-snapshot guard (pattern at
  `mongo_datasets.py:135`), in-flight status guard, removes cached files
  under `data_root`, then deletes the document.

### 3. Frontend — guide page

- New `guide` view: add to the `View` union in `App.tsx`, `WorkspaceView`
  in `frontend/src/i18n/catalog.ts`, and a navigation entry (glyph `?`) in
  `frontend/src/dashboard/navigation.ts` (new item under the `overview`
  group, after `dashboard`).
- New `frontend/src/components/Guide.tsx`: static step-by-step walkthrough
  (register dataset → download/verify → create prompt package → queue
  dataset run → inspect evidence → judge/review → generate reports).
  Uses existing `.panel`/`.card` classes; copy goes through
  `StaticCopy`/i18n like the rest of the app.
- All new copy added to `frontend/src/i18n/catalog.ts` (typed, 8-locale
  strict parity enforced by `src/i18n/locales.test.ts`) and to
  `frontend/src/i18n/operationalCopy.ts` for the static strings.

### 4. Frontend — dataset catalog actions (`DatasetCatalog`, `App.tsx`)

- **Preview**: button on `ready` datasets → `api.previewDataset(id, limit)`
  (new function in `frontend/src/api.ts` hitting `GET /datasets/{id}/preview`)
  → modal showing the field list and first rows as a table (values rendered
  as text). 409/not-ready → inline error message. Follow the existing modal/
  panel patterns already in the app.
- **Edit**: button → inline expandable form per card, pre-filled with all
  editable metadata → `api.updateDataset(id, payload)` → success notice +
  `refresh()`.
- **Delete**: button → `window.confirm` (consistent with the existing
  pattern at `App.tsx:631`) → `api.deleteDataset(id)` → success notice +
  `refresh()`; a 409 guard message is shown inline.

### 5. Frontend — registration form and run-form prefill

- The "Register dataset version" form (`App.tsx:770`) gains two optional
  inputs: "Input field" and "Reference (output) field", wired into
  `datasetForm` and `api.createDataset`.
- The dataset-run form's reference-field input (`App.tsx:780`) prefills
  from the selected dataset's stored `reference_field` when the dataset
  changes and the user hasn't typed a custom value; the field stays
  editable. The input field is informational on the run form (prompt
  templates reference it).

### 6. Tests

Backend (`tests/`):

- Create with `input_field`/`reference_field` → returned in the response.
- Preview: happy path returns fields + rows; 409 when not ready; limit
  cap enforced; 404 for unknown id.
- Update: metadata edit persists; uniqueness violation → 409; invalid
  `source_url` → 422.
- Delete: success removes registration + cache files; 409 when a run
  references the revision; 409 when in-flight.
- Mongo fakes mirroring the relational tests (fake the client, never a live
  MongoDB, per AGENTS.md).

Frontend (colocated `src/*.test.tsx`):

- New `dataset-catalog.test.tsx`: preview renders rows; edit submits update;
  delete confirms then calls `api.deleteDataset`.
- Update `dataset-registration.test.tsx`: new fields submitted.
- Run-form prefill test: selecting a dataset prefills the reference field.

### 7. Docs

- `docs/evaluation-workflow.md`: mention input/reference fields at
  registration, preview, edit, and delete.
- `CHANGELOG.md`: add entries under `## Unreleased`.

## Acceptance criteria

- AC1: The guide page is reachable from navigation and renders the full
  workflow in all locales (i18n parity test passes).
- AC2: A `ready` dataset shows its first rows via Preview in the catalog;
  non-ready datasets get a clear 409 message.
- AC3: Registering a dataset with input/reference fields persists them;
  the dataset-run form prefills the reference field from the selection.
- AC4: Editing a dataset updates its metadata; deleting an unreferenced
  dataset removes registration and cached files; deleting a referenced or
  in-flight dataset returns a clear 409.
- AC5: CI definition of done passes: `python -m pytest -q`,
  `npm test -- --run`, `npm run build`.
