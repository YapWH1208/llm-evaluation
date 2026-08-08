# Dataset Management and In-App Guide Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add dataset preview, input/reference field defaults, edit/delete capabilities, and an in-app usage guide to the LLM/SLM evaluation platform.

**Architecture:** Forward-only SQLAlchemy migration v24 adds `input_field`/`reference_field` to `dataset_versions`; three new API endpoints (preview, PUT update, DELETE) with parallel Mongo service paths; the React app gains catalog actions, run-form prefill, and a new `guide` view.

**Tech Stack:** FastAPI + SQLAlchemy + pydantic (Python ≥3.12, SQLite-first), React 19 + Vite + TypeScript, vitest + Testing Library, typed i18n catalog with 8 locales.

## Global Constraints

- Backend tests: `python -m pytest -q` from repo root (pyproject.toml sets `pythonpath=["backend"]`).
- Frontend tests: `npm test -- --run` from `frontend/` (bare `npm test` is watch mode).
- Frontend build: `npm run build` from `frontend/` (runs `tsc -b && vite build`). No lint script exists.
- MongoDB tests fake the client — never require a live MongoDB.
- All UI copy goes through the typed i18n catalog `frontend/src/i18n/catalog.ts` (8 locales, strict key parity enforced by `src/i18n/locales.test.ts`) and the static phrase/word lists in `frontend/src/i18n/operationalCopy.ts`.
- No code comments. Conventional commits (`feat:`, `fix:`, `test:`, `docs:`). Commit after every step.
- Spec: `docs/reasonix/specs/2026-08-07-dataset-management-and-guide-design.md`.

---

### Task 1: Migration v24 + model columns + API schema fields

**Files:**
- Modify: `backend/app/db/models.py` (DatasetVersion class, ~line 232)
- Modify: `backend/app/db/migrations.py` (add `_upgrade_v24_dataset_field_defaults` and register it in `MIGRATIONS`)
- Modify: `backend/app/api/datasets.py` (DatasetCreate + DatasetResponse)

**Interfaces:**
- Consumes: existing `_add_column_if_missing` helper in `migrations.py`, `DatasetStatus` enum in `models.py`.
- Produces: `DatasetVersion.input_field: str | None`, `DatasetVersion.reference_field: str | None` columns; `DatasetCreate.input_field/reference_field` optional fields; `DatasetResponse.input_field/reference_field` fields.

- [ ] **Step 1: Write the failing tests** — in `tests/test_datasets.py`:

```python
def test_dataset_create_and_response_carry_input_and_reference_fields(tmp_path: Path) -> None:
    app = create_app(Settings.local_development(database_url=f"sqlite:///{tmp_path/'db.sqlite'}", data_root=str(tmp_path / "data")))
    with TestClient(app) as client:
        created = client.post("/api/v1/datasets", json={
            "dataset_id": "fields", "version": "1",
            "input_field": "question", "reference_field": "answer",
        })
        assert created.status_code == 201
        body = created.json()
        assert body["input_field"] == "question"
        assert body["reference_field"] == "answer"
        listed = {item["id"]: item for item in client.get("/api/v1/datasets").json()}
        assert listed[body["id"]]["input_field"] == "question"
        assert listed[body["id"]]["reference_field"] == "answer"
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `python -m pytest tests/test_datasets.py::test_dataset_create_and_response_carry_input_and_reference_fields -q`
Expected: FAIL (KeyError / response missing fields).

- [ ] **Step 3: Add the model columns** in `backend/app/db/models.py` inside `DatasetVersion` (after `license_accepted_at`, before `status`):

```python
    input_field: Mapped[str | None] = mapped_column(String(255), nullable=True)
    reference_field: Mapped[str | None] = mapped_column(String(255), nullable=True)
```

- [ ] **Step 4: Add migration v24** in `backend/app/db/migrations.py` (place the function above the `MIGRATIONS` tuple):

```python
def _upgrade_v24_dataset_field_defaults(connection: Connection) -> None:
    _add_column_if_missing(connection, "dataset_versions", "input_field", "input_field VARCHAR(255)")
    _add_column_if_missing(connection, "dataset_versions", "reference_field", "reference_field VARCHAR(255)")
```

Then register at the end of the `MIGRATIONS` tuple (before the closing `)`):

```python
    Migration(
        version=24,
        migration_id="20260807_add_dataset_field_defaults",
        description="Add optional input and reference field defaults to dataset versions.",
        upgrade=_upgrade_v24_dataset_field_defaults,
    ),
```

- [ ] **Step 5: Extend the API schemas** in `backend/app/api/datasets.py`:

In `DatasetCreate` add:

```python
    input_field: str | None = None; reference_field: str | None = None
```

Add to the `model_validator` body (before `return self`):

```python
        if self.input_field is not None and not self.input_field.strip():
            raise ValueError("input_field must not be blank when provided.")
        if self.reference_field is not None and not self.reference_field.strip():
            raise ValueError("reference_field must not be blank when provided.")
        if self.input_field is not None:
            self.input_field = self.input_field.strip()
        if self.reference_field is not None:
            self.reference_field = self.reference_field.strip()
```

In `DatasetResponse` add:

```python
    input_field: str | None; reference_field: str | None
```

- [ ] **Step 6: Run the test to verify it passes**

Run: `python -m pytest tests/test_datasets.py::test_dataset_create_and_response_carry_input_and_reference_fields -q`
Expected: PASS.

- [ ] **Step 7: Run the full backend suite**

Run: `python -m pytest -q`
Expected: PASS (all tests, including migration tests).

- [ ] **Step 8: Commit**

```bash
git add backend/app/db/models.py backend/app/db/migrations.py backend/app/api/datasets.py tests/test_datasets.py
git commit -m "feat: store input and reference field defaults on dataset versions"
```

---

### Task 2: Backend — dataset preview endpoint

**Files:**
- Modify: `backend/app/services/datasets.py` (add `preview_dataset_records` service function)
- Modify: `backend/app/api/datasets.py` (GET preview endpoint)
- Test: `tests/test_datasets.py`

**Interfaces:**
- Consumes: `iter_dataset_records` from `app.services.dataset_records` (yields `{"source", "record_number", "fields"}` dicts), `DatasetStatus.READY.value`.
- Produces: `preview_dataset_records(prepared_path: str, data_root: str, *, limit: int) -> dict[str, object]` returning `{"fields": list[str], "rows": list[dict[str, str]]}`; HTTP `GET /api/v1/datasets/{id}/preview?limit=N` returning `DatasetPreviewResponse`.

- [ ] **Step 1: Write the failing tests** — in `tests/test_datasets.py`:

```python
def test_dataset_preview_returns_first_rows_from_the_prepared_cache(tmp_path: Path) -> None:
    content = b'{"question":"what is 2 + 2?","answer":"4"}\n{"question":"what is 3 + 3?","answer":"6"}\n{"question":"what is 4 + 4?","answer":"8"}\n'
    app = create_app(Settings.local_development(database_url=f"sqlite:///{tmp_path/'db.sqlite'}", data_root=str(tmp_path / "data")))
    with TestClient(app) as client:
        created = client.post("/api/v1/datasets", json={"dataset_id": "preview", "version": "1"}).json()
        uploaded = client.post(f"/api/v1/datasets/{created['id']}/upload", json={"filename": "rows.jsonl", "base64_data": base64.b64encode(content).decode("ascii")})
        assert uploaded.status_code == 200
        preview = client.get(f"/api/v1/datasets/{created['id']}/preview")
        assert preview.status_code == 200
        body = preview.json()
        assert body["fields"] == ["question", "answer"]
        assert len(body["rows"]) == 2
        assert body["rows"][0] == {"question": "what is 2 + 2?", "answer": "4"}
        limited = client.get(f"/api/v1/datasets/{created['id']}/preview?limit=1")
        assert len(limited.json()["rows"]) == 1


def test_dataset_preview_requires_a_ready_dataset_and_caps_the_limit(tmp_path: Path) -> None:
    app = create_app(Settings.local_development(database_url=f"sqlite:///{tmp_path/'db.sqlite'}", data_root=str(tmp_path / "data")))
    with TestClient(app) as client:
        created = client.post("/api/v1/datasets", json={"dataset_id": "notready", "version": "1"}).json()
        blocked = client.get(f"/api/v1/datasets/{created['id']}/preview")
        assert blocked.status_code == 409
        assert "not ready" in blocked.json()["detail"]
        missing = client.get("/api/v1/datasets/does-not-exist/preview")
        assert missing.status_code == 404
        oversized = client.get(f"/api/v1/datasets/{created['id']}/preview?limit=999")
        assert oversized.status_code == 422
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `python -m pytest tests/test_datasets.py::test_dataset_preview_returns_first_rows_from_the_prepared_cache tests/test_datasets.py::test_dataset_preview_requires_a_ready_dataset_and_caps_the_limit -q`
Expected: FAIL (404 on unknown route).

- [ ] **Step 3: Add the service function** in `backend/app/services/datasets.py` (imports: `from app.services.dataset_records import iter_dataset_records` at top of file; place function after `clear_dataset_cache`):

```python
def preview_dataset_records(prepared_path: str, data_root: str, *, limit: int) -> dict[str, object]:
    fields: list[str] = []
    seen: set[str] = set()
    rows: list[dict[str, str]] = []
    for record in iter_dataset_records(prepared_path, data_root, limit=limit):
        raw_fields = record["fields"]
        if not isinstance(raw_fields, dict):
            continue
        for key in raw_fields:
            if key not in seen:
                seen.add(key)
                fields.append(key)
        rows.append({str(key): _stringify_preview_value(value) for key, value in raw_fields.items()})
    return {"fields": fields, "rows": rows}


def _stringify_preview_value(value: object) -> str:
    if value is None:
        return ""
    if isinstance(value, (dict, list)):
        return json.dumps(value, ensure_ascii=False)
    return str(value)
```

(Confirm `import json` exists at the top of `backend/app/services/datasets.py`; add it if missing.)

- [ ] **Step 4: Add the endpoint and response model** in `backend/app/api/datasets.py`:

```python
class DatasetPreviewResponse(BaseModel):
    fields: list[str]
    rows: list[dict[str, str]]
```

Add import: `from fastapi import Query` (extend the existing fastapi import) and `from app.services.datasets import preview_dataset_records`. Add the route after `list_datasets`:

```python
@router.get("/{dataset_version_id}/preview", response_model=DatasetPreviewResponse)
def preview_dataset_version(dataset_version_id: str, request: Request, session: SessionDependency, limit: int = Query(default=5, ge=1, le=50)) -> dict[str, object]:
    store = get_document_store(request)
    if store is not None:
        dataset = store.get_document("dataset_versions", dataset_version_id)
        if dataset is None:
            raise HTTPException(404, "Dataset version not found")
        prepared_path = dataset.get("prepared_path")
        ready = dataset.get("status") == "ready" and isinstance(prepared_path, str)
    else:
        assert session is not None
        dataset = get_dataset_or_404(session, dataset_version_id)
        prepared_path = dataset.prepared_path
        ready = dataset.status == "ready" and prepared_path is not None
    if not ready:
        raise HTTPException(409, "Dataset is not ready; download and verify it before previewing.")
    return preview_dataset_records(str(prepared_path), request.app.state.settings.data_root, limit=limit)
```

- [ ] **Step 5: Run the tests to verify they pass**

Run: `python -m pytest tests/test_datasets.py::test_dataset_preview_returns_first_rows_from_the_prepared_cache tests/test_datasets.py::test_dataset_preview_requires_a_ready_dataset_and_caps_the_limit -q`
Expected: PASS.

- [ ] **Step 6: Run the full backend suite**

Run: `python -m pytest -q`
Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add backend/app/services/datasets.py backend/app/api/datasets.py tests/test_datasets.py
git commit -m "feat: add dataset data preview endpoint"
```

---

### Task 3: Backend — dataset update (PUT) endpoint

**Files:**
- Modify: `backend/app/services/datasets.py` (add `update_dataset` service function)
- Modify: `backend/app/services/mongo_datasets.py` (add `update_mongo_dataset`)
- Modify: `backend/app/api/datasets.py` (PUT endpoint)
- Test: `tests/test_datasets.py`

**Interfaces:**
- Consumes: `_validate_dataset_registration` (already in `datasets.py` API module), `DatasetCreate` payload model from Task 1, `DatasetError`, `_get_dataset` in `mongo_datasets.py`.
- Produces: `update_dataset(session, dataset, payload)` relational + `update_mongo_dataset(store, dataset_id, payload)` returning the updated dataset/dict; HTTP `PUT /api/v1/datasets/{id}` accepting `DatasetCreate` and returning `DatasetResponse`.

- [ ] **Step 1: Write the failing tests** — in `tests/test_datasets.py`:

```python
def test_dataset_update_edits_metadata_and_enforces_uniqueness(tmp_path: Path) -> None:
    app = create_app(Settings.local_development(database_url=f"sqlite:///{tmp_path/'db.sqlite'}", data_root=str(tmp_path / "data")))
    with TestClient(app) as client:
        first = client.post("/api/v1/datasets", json={"dataset_id": "dup", "version": "1"}).json()
        second = client.post("/api/v1/datasets", json={"dataset_id": "target", "version": "1"}).json()
        updated = client.put(f"/api/v1/datasets/{second['id']}", json={
            "dataset_id": "renamed", "version": "2", "revision": "fixed",
            "input_field": "prompt", "reference_field": "expected",
        })
        assert updated.status_code == 200
        body = updated.json()
        assert body["dataset_id"] == "renamed"
        assert body["version"] == "2"
        assert body["revision"] == "fixed"
        assert body["input_field"] == "prompt"
        assert body["reference_field"] == "expected"
        conflicting = client.put(f"/api/v1/datasets/{second['id']}", json={"dataset_id": "dup", "version": "1", "revision": "default"})
        assert conflicting.status_code == 409
        bad_source = client.put(f"/api/v1/datasets/{second['id']}", json={"dataset_id": "renamed", "version": "2", "revision": "fixed", "source_url": "file:///tmp/x.jsonl"})
        assert bad_source.status_code == 422
        missing = client.put("/api/v1/datasets/does-not-exist", json={"dataset_id": "x", "version": "1"})
        assert missing.status_code == 404
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `python -m pytest tests/test_datasets.py::test_dataset_update_edits_metadata_and_enforces_uniqueness -q`
Expected: FAIL (405 or 404 on unknown route).

- [ ] **Step 3: Add the relational service function** in `backend/app/services/datasets.py` (imports: `from sqlalchemy.exc import IntegrityError`, `from sqlalchemy import select`, `from app.db.models import DatasetVersion` — check the existing imports at the top of the file and extend):

```python
def update_dataset(session: Session, dataset: DatasetVersion, *, dataset_id: str, version: str, revision: str, source_url: str | None, checksum: str | None, license_text: str | None, credential_binding_id: str | None, input_field: str | None, reference_field: str | None) -> DatasetVersion:
    dataset.dataset_id = dataset_id
    dataset.version = version
    dataset.revision = revision
    dataset.source_url = source_url
    dataset.checksum = checksum
    dataset.license_text = license_text
    dataset.credential_binding_id = credential_binding_id
    dataset.input_field = input_field
    dataset.reference_field = reference_field
    try:
        session.commit()
    except IntegrityError as error:
        session.rollback()
        raise DatasetError("Dataset revision already exists.") from error
    session.refresh(dataset)
    return dataset
```

- [ ] **Step 4: Add the Mongo service function** in `backend/app/services/mongo_datasets.py` (place after `clear_mongo_dataset_cache`):

```python
def update_mongo_dataset(store: MongoDocumentStore, dataset_id: str, payload: dict[str, Any]) -> dict[str, Any]:
    _get_dataset(store, dataset_id)
    values = {
        "dataset_id": payload["dataset_id"],
        "version": payload["version"],
        "revision": payload["revision"],
        "source_url": payload.get("source_url"),
        "checksum": payload.get("checksum"),
        "license_text": payload.get("license_text"),
        "credential_binding_id": payload.get("credential_binding_id"),
        "input_field": payload.get("input_field"),
        "reference_field": payload.get("reference_field"),
    }
    duplicates = store.list_documents("dataset_versions", query={
        "dataset_id": values["dataset_id"], "version": values["version"], "revision": values["revision"],
    })
    if any(str(item.get("id")) != dataset_id for item in duplicates):
        raise DatasetError("Dataset revision already exists.")
    updated = store.update_document("dataset_versions", dataset_id, values)
    assert updated is not None
    return updated
```

- [ ] **Step 5: Add the API endpoint** in `backend/app/api/datasets.py` (import `update_dataset` from `app.services.datasets` and `update_mongo_dataset` from `app.services.mongo_datasets`). Place after `list_datasets`:

```python
@router.put("/{dataset_version_id}", response_model=DatasetResponse)
def update_dataset_version(dataset_version_id: str, payload: DatasetCreate, request: Request, session: SessionDependency) -> DatasetVersion | dict:
    _validate_dataset_registration(payload, request)
    store = get_document_store(request)
    try:
        if store is not None:
            return update_mongo_dataset(store, dataset_version_id, payload.model_dump())
        assert session is not None
        return update_dataset(session, get_dataset_or_404(session, dataset_version_id), **payload.model_dump())
    except DatasetError as error:
        raise HTTPException(409, str(error)) from error
```

- [ ] **Step 6: Run the tests to verify they pass**

Run: `python -m pytest tests/test_datasets.py::test_dataset_update_edits_metadata_and_enforces_uniqueness -q`
Expected: PASS.

- [ ] **Step 7: Run the full backend suite**

Run: `python -m pytest -q`
Expected: PASS.

- [ ] **Step 8: Commit**

```bash
git add backend/app/services/datasets.py backend/app/services/mongo_datasets.py backend/app/api/datasets.py tests/test_datasets.py
git commit -m "feat: add dataset metadata update endpoint"
```

---

### Task 4: Backend — dataset delete endpoint

**Files:**
- Modify: `backend/app/services/datasets.py` (extend `_ensure_dataset_is_not_referenced`, add `delete_dataset`)
- Modify: `backend/app/services/mongo_datasets.py` (add `delete_mongo_dataset`)
- Modify: `backend/app/api/datasets.py` (DELETE endpoint)
- Test: `tests/test_datasets.py`

**Interfaces:**
- Consumes: `clear_prepared_dataset_cache`, `DatasetError`, `DatasetStatus` from existing modules; `delete_document` on `MongoDocumentStore` (exists at `mongo.py:658`).
- Produces: `delete_dataset(session, dataset, data_root)` and `delete_mongo_dataset(store, dataset_id, data_root)`; HTTP `DELETE /api/v1/datasets/{id}` returning `DatasetResponse`.

- [ ] **Step 1: Write the failing tests** — in `tests/test_datasets.py`:

```python
def test_dataset_delete_removes_registration_and_cache_but_guards_referenced_versions(tmp_path: Path) -> None:
    app = create_app(Settings.local_development(database_url=f"sqlite:///{tmp_path/'db.sqlite'}", data_root=str(tmp_path / "data")))
    with TestClient(app) as client:
        created = client.post("/api/v1/datasets", json={"dataset_id": "doomed", "version": "1"}).json()
        content = b'{"question":"q?","answer":"a"}\n'
        uploaded = client.post(f"/api/v1/datasets/{created['id']}/upload", json={"filename": "rows.jsonl", "base64_data": base64.b64encode(content).decode("ascii")})
        assert uploaded.status_code == 200
        deleted = client.delete(f"/api/v1/datasets/{created['id']}")
        assert deleted.status_code == 200
        listed = client.get("/api/v1/datasets").json()
        assert all(item["id"] != created["id"] for item in listed)
        gone = client.get(f"/api/v1/datasets/{created['id']}/preview")
        assert gone.status_code == 404
        missing = client.delete("/api/v1/datasets/does-not-exist")
        assert missing.status_code == 404


def test_dataset_delete_is_blocked_while_a_run_references_the_revision(tmp_path: Path) -> None:
    app = create_app(Settings.local_development(database_url=f"sqlite:///{tmp_path/'db.sqlite'}", data_root=str(tmp_path / "data")))
    session = app.state.database.get_session()
    try:
        created = client_post(session, app, "/api/v1/datasets", json={"dataset_id": "referenced", "version": "1"})
        content = b'{"question":"q?","answer":"a"}\n'
        uploaded = client_post(session, app, f"/api/v1/datasets/{created['id']}/upload", json={"filename": "rows.jsonl", "base64_data": base64.b64encode(content).decode("ascii")})
        assert uploaded.status_code == 200
        dataset = session.get(DatasetVersion, created["id"])
        assert dataset is not None
        dataset.status = "ready"
        session.add(EvaluationRun(
            model_endpoint_id="endpoint-x",
            benchmark_id="dataset-evaluation",
            benchmark_version="1",
            configuration_snapshot={"datasets": [{"dataset_version_id": created["id"]}]},
            status="completed",
            total_samples=1,
        ))
        session.commit()
        blocked = client_delete(session, app, f"/api/v1/datasets/{created['id']}")
        assert blocked.status_code == 409
        assert "references this revision" in blocked.json()["detail"]
        listed = client_get(session, app, "/api/v1/datasets").json()
        assert any(item["id"] == created["id"] for item in listed)
    finally:
        session.close()
```

Note: the `EvaluationRun` row requires `model_endpoint_id` to exist? No — there is no FK constraint on `model_endpoint_id` in `evaluation_runs` (check `backend/app/db/models.py`; if a FK exists, create a minimal endpoint row first, mirroring `tests/test_dataset_runs.py`). To keep the plan simple, use the helper `client_post = lambda session, app, path, json: ...` pattern: prefer the existing `TestClient` for the first two calls and a second `TestClient` context after committing the run row; both share the same SQLite file. Rewrite the test using two `with TestClient(app) as client:` blocks (client creation before the run, deletion after) — this avoids session/TestClient interleaving entirely:

```python
def test_dataset_delete_is_blocked_while_a_run_references_the_revision(tmp_path: Path) -> None:
    app = create_app(Settings.local_development(database_url=f"sqlite:///{tmp_path/'db.sqlite'}", data_root=str(tmp_path / "data")))
    with TestClient(app) as client:
        created = client.post("/api/v1/datasets", json={"dataset_id": "referenced", "version": "1"}).json()
        content = b'{"question":"q?","answer":"a"}\n'
        uploaded = client.post(f"/api/v1/datasets/{created['id']}/upload", json={"filename": "rows.jsonl", "base64_data": base64.b64encode(content).decode("ascii")})
        assert uploaded.status_code == 200
        session = app.state.database.get_session()
        try:
            from app.db.models import DatasetVersion, EvaluationRun
            dataset = session.get(DatasetVersion, created["id"])
            assert dataset is not None
            session.add(EvaluationRun(
                model_endpoint_id="endpoint-x",
                benchmark_id="dataset-evaluation",
                benchmark_version="1",
                configuration_snapshot={"datasets": [{"dataset_version_id": created["id"]}]},
                status="completed",
                total_samples=1,
            ))
            session.commit()
        finally:
            session.close()
    with TestClient(app) as client:
        blocked = client.delete(f"/api/v1/datasets/{created['id']}")
        assert blocked.status_code == 409
        assert "references this revision" in blocked.json()["detail"]
        listed = client.get("/api/v1/datasets").json()
        assert any(item["id"] == created["id"] for item in listed)
```

Check `EvaluationRun`'s required constructor columns in `backend/app/db/models.py` (around line 400) and fill any extra required fields with the same values `tests/test_dataset_runs.py` uses.

- [ ] **Step 2: Run the tests to verify they fail**

Run: `python -m pytest tests/test_datasets.py::test_dataset_delete_removes_registration_and_cache_but_guards_referenced_versions -q`
Expected: FAIL (405 or 404 on unknown route).

- [ ] **Step 3: Extend the reference guard** in `backend/app/services/datasets.py` — change the message in `_ensure_dataset_is_not_referenced` to cover both clear and delete:

```python
            raise DatasetError("Dataset cache cannot be cleared while an evaluation run references this revision.")
```
becomes
```python
            raise DatasetError("Dataset cannot be deleted while an evaluation run references this revision.")
```

(Update `clear_dataset_cache`'s catch so tests expecting the old message still pass — grep for the old message in `tests/` and update any assertions.)

- [ ] **Step 4: Add the relational delete service** in `backend/app/services/datasets.py` (after `clear_dataset_cache`):

```python
def delete_dataset(session: Session, dataset: DatasetVersion, data_root: str) -> DatasetVersion:
    _ensure_dataset_is_not_referenced(session, dataset.id)
    if dataset.status in {
        DatasetStatus.DOWNLOADING.value, DatasetStatus.PREPARING.value,
        DatasetStatus.VERIFYING.value, DatasetStatus.REMOVING.value,
    }:
        raise DatasetError("Dataset cannot be deleted while it is downloading or preparing.")
    if dataset.local_path:
        root = (Path(data_root).resolve() / "datasets").resolve()
        target = Path(dataset.local_path).resolve()
        if not target.is_relative_to(root):
            raise DatasetError("Dataset cache path is outside the configured dataset root.")
        target.unlink(missing_ok=True)
    clear_prepared_dataset_cache(dataset.prepared_path, data_root)
    upload_dir = (Path(data_root).resolve() / "datasets" / "uploads" / dataset.id).resolve()
    if upload_dir.is_relative_to((Path(data_root).resolve() / "datasets").resolve()):
        import shutil
        shutil.rmtree(upload_dir, ignore_errors=True)
    session.delete(dataset)
    session.commit()
    return dataset
```

- [ ] **Step 5: Add the Mongo delete service** in `backend/app/services/mongo_datasets.py` (after `clear_mongo_dataset_cache`):

```python
def delete_mongo_dataset(store: MongoDocumentStore, dataset_id: str, data_root: str) -> dict[str, Any]:
    dataset = _get_dataset(store, dataset_id)
    for run in store.list_documents("evaluation_runs"):
        snapshot = run.get("configuration_snapshot") if isinstance(run.get("configuration_snapshot"), dict) else {}
        descriptors = snapshot.get("datasets") if isinstance(snapshot, dict) else None
        if isinstance(descriptors, list) and any(isinstance(descriptor, dict) and descriptor.get("dataset_version_id") == dataset_id for descriptor in descriptors):
            raise DatasetError("Dataset cannot be deleted while an evaluation run references this revision.")
    if dataset.get("status") in {"downloading", "preparing", "verifying", "removing"}:
        raise DatasetError("Dataset cannot be deleted while it is downloading or preparing.")
    local_path = dataset.get("local_path")
    if isinstance(local_path, str) and local_path:
        root = (Path(data_root).resolve() / "datasets").resolve()
        target = Path(local_path).resolve()
        if not target.is_relative_to(root):
            raise DatasetError("Dataset cache path is outside the configured dataset root.")
        target.unlink(missing_ok=True)
    clear_prepared_dataset_cache(dataset.get("prepared_path") if isinstance(dataset.get("prepared_path"), str) else None, data_root)
    import shutil
    upload_dir = (Path(data_root).resolve() / "datasets" / "uploads" / dataset_id).resolve()
    if upload_dir.is_relative_to((Path(data_root).resolve() / "datasets").resolve()):
        shutil.rmtree(upload_dir, ignore_errors=True)
    store.delete_document("dataset_versions", dataset_id)
    return dataset
```

- [ ] **Step 6: Add the API endpoint** in `backend/app/api/datasets.py` (import `delete_dataset` from `app.services.datasets` and `delete_mongo_dataset` from `app.services.mongo_datasets`). Place after the `upload` endpoint:

```python
@router.delete("/{dataset_version_id}", response_model=DatasetResponse)
def delete_dataset_version(dataset_version_id: str, request: Request, session: SessionDependency) -> DatasetVersion | dict:
    store = get_document_store(request)
    try:
        if store is not None:
            return delete_mongo_dataset(store, dataset_version_id, request.app.state.settings.data_root)
        assert session is not None
        return delete_dataset(session, get_dataset_or_404(session, dataset_version_id), request.app.state.settings.data_root)
    except DatasetError as error:
        raise HTTPException(409, str(error)) from error
```

- [ ] **Step 7: Run the tests to verify they pass**

Run: `python -m pytest tests/test_datasets.py::test_dataset_delete_removes_registration_and_cache_but_guards_referenced_versions -q`
Expected: PASS.

- [ ] **Step 8: Run the full backend suite**

Run: `python -m pytest -q`
Expected: PASS.

- [ ] **Step 9: Commit**

```bash
git add backend/app/services/datasets.py backend/app/services/mongo_datasets.py backend/app/api/datasets.py tests/test_datasets.py
git commit -m "feat: add guarded dataset delete endpoint"
```

---

### Task 5: Backend — Mongo parallel tests

**Files:**
- Test: `tests/test_mongo_document_store.py` (existing file — find the fake-client fixture pattern first and follow it)

**Interfaces:**
- Consumes: fake `MongoDocumentStore` client established in `test_mongo_document_store.py`, `update_mongo_dataset`, `delete_mongo_dataset`, `preview_dataset_records` from Tasks 2–4.

- [ ] **Step 1: Read the existing fake pattern**

Run: `rg -n "class Fake|def create_app|document_store|FakeMongo|mongo" tests/test_mongo_document_store.py | head -30`
Expected: identify how tests fake the Mongo client and wire a document store into `create_app`. If another test file (e.g. `tests/test_dataset_runs.py` or `tests/test_mongo_document_store.py`) has a fixture for a Mongo-backed app, reuse that exact fixture.

- [ ] **Step 2: Write the failing tests** — append to the Mongo test file (adapt the fixture from Step 1; the example below assumes a `mongo_app(tmp_path)` fixture helper that builds an app whose `app.state.document_store` is a fake `MongoDocumentStore` backed by in-memory documents):

```python
def test_mongo_dataset_update_and_delete_guard(tmp_path: Path) -> None:
    app = create_app(Settings.local_development(database_url="mongodb://fake", data_root=str(tmp_path / "data")))
    with TestClient(app) as client:
        created = client.post("/api/v1/datasets", json={"dataset_id": "m", "version": "1", "input_field": "q", "reference_field": "a"})
        assert created.status_code == 201
        body = created.json()
        assert body["input_field"] == "q"
        updated = client.put(f"/api/v1/datasets/{body['id']}", json={"dataset_id": "m2", "version": "2", "revision": "default"})
        assert updated.status_code == 200
        assert updated.json()["dataset_id"] == "m2"
        deleted = client.delete(f"/api/v1/datasets/{body['id']}")
        assert deleted.status_code == 200
        assert client.get("/api/v1/datasets").json() == []
```

- [ ] **Step 3: Run the tests to verify they fail**

Run: `python -m pytest tests/test_mongo_document_store.py -q`
Expected: FAIL or ERROR (route exists but the fake store lacks persistence, or no Mongo-backed app fixture exists yet — then create the fixture in this step as part of the test file).

- [ ] **Step 4: Make the test pass** — if the fake store needs an in-memory `update_document`/`delete_document`/`get_document`/`list_documents`, extend the fake class in the test file so `update_mongo_dataset`/`delete_mongo_dataset`/`preview` behave correctly. Confirm `update_mongo_dataset` handles the payload dict keys (Task 3) and that the store's `update_document` returns the merged document.

- [ ] **Step 5: Run the tests to verify they pass**

Run: `python -m pytest tests/test_mongo_document_store.py -q`
Expected: PASS.

- [ ] **Step 6: Run the full backend suite**

Run: `python -m pytest -q`
Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add tests/test_mongo_document_store.py
git commit -m "test: cover mongo dataset update and delete paths"
```

---

### Task 6: Frontend — api.ts dataset functions and types

**Files:**
- Modify: `frontend/src/api.ts` (`Dataset` type at ~line 135, `api` object at ~line 300)
- Test: `frontend/src/api.test.ts` (existing file — follow its mock pattern)

**Interfaces:**
- Consumes: `request<T>` helper in `api.ts`.
- Produces: `Dataset` gains `input_field: string | null; reference_field: string | null`; `api.previewDataset(datasetId, limit) -> Promise<{fields: string[]; rows: Array<Record<string, string>>}>`, `api.updateDataset(datasetId, body) -> Promise<Dataset>`, `api.deleteDataset(datasetId) -> Promise<Dataset>`.

- [ ] **Step 1: Write the failing tests** — in `frontend/src/api.test.ts` (follow the existing test setup; check how requests are mocked with `vi.stubGlobal` or similar):

```ts
describe("dataset management API", () => {
  it("previews, updates, and deletes dataset versions", async () => {
    const calls: Array<{ url: string; init?: RequestInit }> = [];
    vi.stubGlobal("fetch", vi.fn(async (url: string, init?: RequestInit) => {
      calls.push({ url: String(url), init });
      return new Response(JSON.stringify({ fields: ["q"], rows: [{ q: "?" }] }), { status: 200, headers: { "Content-Type": "application/json" } });
    }));
    const preview = await api.previewDataset("ds-1", 3);
    expect(preview.rows).toEqual([{ q: "?" }]);
    expect(calls[0].url.endsWith("/datasets/ds-1/preview?limit=3")).toBe(true);
    const updated = await api.updateDataset("ds-1", { dataset_id: "x", version: "1" });
    expect(updated.fields).toEqual(["q"]);
    expect(calls[1].init?.method).toBe("PUT");
    await api.deleteDataset("ds-1");
    expect(calls[2].init?.method).toBe("DELETE");
    vi.unstubAllGlobals();
  });
});
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `npm test -- --run src/api.test.ts` in `frontend/`
Expected: FAIL (methods don't exist / type errors).

- [ ] **Step 3: Update the Dataset type** in `frontend/src/api.ts`:

```ts
export type Dataset = {
  id: string;
  dataset_id: string;
  version: string;
  revision: string;
  source_url: string | null;
  credential_binding_id: string | null;
  checksum: string | null;
  local_path: string | null;
  size_bytes: number | null;
  license_text: string | null;
  license_accepted_at: string | null;
  status: string;
  error_message: string | null;
  input_field: string | null;
  reference_field: string | null;
};
```

- [ ] **Step 4: Add the api methods** in `frontend/src/api.ts` (near `createDataset` at ~line 304):

```ts
  previewDataset: (datasetId: string, limit = 5) => request<{ fields: string[]; rows: Array<Record<string, string>> }>(`/datasets/${datasetId}/preview?limit=${limit}`),
  updateDataset: (datasetId: string, body: Record<string, unknown>) => request<Dataset>(`/datasets/${datasetId}`, { method: "PUT", body: JSON.stringify(body) }),
  deleteDataset: (datasetId: string) => request<Dataset>(`/datasets/${datasetId}`, { method: "DELETE" }),
```

- [ ] **Step 5: Run the tests to verify they pass**

Run: `npm test -- --run src/api.test.ts` in `frontend/`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add frontend/src/api.ts frontend/src/api.test.ts
git commit -m "feat: add dataset preview, update, and delete api functions"
```

---

### Task 7: Frontend — registration form fields + run-form prefill

**Files:**
- Modify: `frontend/src/App.tsx` (`initialDataset` at ~line 64, `initialDatasetRun` at ~line 66, `createDataset` at ~line 507, `queueDatasetRun` at ~line 538, registration form at ~line 770, run form at ~line 780)
- Modify: `frontend/src/i18n/catalog.ts` (new `datasetRegister.*` and `datasetRun.inputField` keys in all 8 locales)
- Modify: `frontend/src/i18n/operationalCopy.ts` (`staticSourceTexts` + phrase lists: "Input field", "Reference (output) field")
- Test: `frontend/src/dataset-registration.test.tsx` (extend), `frontend/src/dataset-run.test.tsx` (extend)

**Interfaces:**
- Consumes: `api.createDataset` (Task 6), `Dataset.reference_field` (Task 6).
- Produces: `datasetForm` gains `input_field`/`reference_field`; run-form reference field prefills from the selected dataset.

- [ ] **Step 1: Write the failing tests** — extend `frontend/src/dataset-registration.test.tsx` (add a new `it` in the existing describe):

```tsx
  it("submits optional input and reference field defaults", async () => {
    const user = userEvent.setup();
    vi.spyOn(api, "listEndpoints").mockResolvedValue([]);
    vi.spyOn(api, "listRuns").mockResolvedValue([]);
    vi.spyOn(api, "dashboard").mockResolvedValue(null as never);
    vi.spyOn(api, "listPromptPackages").mockResolvedValue([]);
    vi.spyOn(api, "listDatasets").mockResolvedValue([]);
    vi.spyOn(api, "listSuites").mockResolvedValue([]);
    vi.spyOn(api, "listBenchmarks").mockResolvedValue([]);
    vi.spyOn(api, "listTasks").mockResolvedValue([]);
    vi.spyOn(api, "analyticsMatrix").mockResolvedValue(null as never);
    vi.spyOn(api, "listUsers").mockResolvedValue([]);
    vi.spyOn(api, "listAuditEvents").mockResolvedValue([]);
    vi.spyOn(api, "systemHealth").mockResolvedValue(null as never);
    const createDataset = vi.spyOn(api, "createDataset").mockResolvedValue({} as never);

    render(<LocaleProvider><App /></LocaleProvider>);
    await user.click(screen.getByRole("button", { name: "Workspace" }));
    await user.type(screen.getByLabelText("Dataset ID"), "fields-demo");
    await user.type(screen.getByLabelText("Input field"), "question");
    await user.type(screen.getByLabelText("Reference (output) field"), "answer");
    await user.click(screen.getByRole("button", { name: "Register dataset" }));

    expect(createDataset).toHaveBeenCalledWith(expect.objectContaining({
      dataset_id: "fields-demo",
      input_field: "question",
      reference_field: "answer",
    }));
  }, 10_000);
```

Extend `frontend/src/dataset-run.test.tsx` with a prefill test: mock `listDatasets` to return one ready dataset with `reference_field: "expected"`, open Runs, select the dataset, and assert the reference field input value becomes `"expected"` (inspect how the existing run test opens the Runs view and fills the form first).

- [ ] **Step 2: Run the tests to verify they fail**

Run: `npm test -- --run src/dataset-registration.test.tsx src/dataset-run.test.tsx` in `frontend/`
Expected: FAIL (labels not found / no prefill).

- [ ] **Step 3: Add i18n catalog keys** in `frontend/src/i18n/catalog.ts` — add to the `en` const (and the same keys to `zhCN`, `fr`, `de`, `ru`, `ja`, `ko`, `ms` in the same positions):

```
  "datasetRegister.title": "Register dataset version",
  "datasetRegister.inputField": "Input field",
  "datasetRegister.referenceField": "Reference (output) field",
  "datasetRegister.inputFieldHint": "Optional record field used as the prompt input",
  "datasetRegister.referenceFieldHint": "Optional record field holding the expected answer",
  "datasetRun.inputField": "Input field",
```

Translations (use these exact values):
- zh-CN: `"数据集注册"`, `"输入字段"`, `"参考答案（输出）字段"`, `"可选：用作提示词输入的记录字段"`, `"可选：保存预期答案的记录字段"`, `"输入字段"`
- fr: `"Enregistrer une version de jeu de données"`, `"Champ d’entrée"`, `"Champ de référence (sortie)"`, `"Champ d’enregistrement facultatif utilisé comme entrée du prompt"`, `"Champ d’enregistrement facultatif contenant la réponse attendue"`, `"Champ d’entrée"`
- de: `"Datensatzversion registrieren"`, `"Eingabefeld"`, `"Referenzfeld (Ausgabe)"`, `"Optionaler Datensatzfeld als Prompt-Eingabe"`, `"Optionaler Datensatzfeld mit der erwarteten Antwort"`, `"Eingabefeld"`
- ru: `"Регистрация версии набора данных"`, `"Поле ввода"`, `"Поле эталонного ответа (вывод)"`, `"Необязательное поле записи, используемое как вход промпта"`, `"Необязательное поле записи с ожидаемым ответом"`, `"Поле ввода"`
- ja: `"データセット バージョンの登録"`, `"入力フィールド"`, `"参照フィールド（出力）"`, `"プロンプト入力として使用するレコード フィールド（省略可能）"`, `"期待される回答を保持するレコード フィールド（省略可能）"`, `"入力フィールド"`
- ko: `"데이터 세트 버전 등록"`, `"입력 필드"`, `"참조 필드(출력)"`, `"프롬프트 입력으로 사용되는 레코드 필드(선택 사항)"`, `"예상 답변이 포함된 레코드 필드(선택 사항)"`, `"입력 필드"`
- ms: `"Daftar versi set data"`, `"Medan input"`, `"Medan rujukan (output)"`, `"Medan rekod pilihan yang digunakan sebagai input prom"`, `"Medan rekod pilihan yang mengandungi jawapan yang dijangkakan"`, `"Medan input"`

- [ ] **Step 4: Add static phrase words** in `frontend/src/i18n/operationalCopy.ts`:

In the `words` map add:

```ts
  input: ["输入", "entrée", "Eingabe", "вход", "入力", "입력", "input"],
  output: ["输出", "sortie", "Ausgabe", "вывод", "出力", "출력", "output"],
```

In `staticSourceTexts` (the list near line 414) add the new literal strings on the dataset registration line (line 419, which starts with `"Register dataset version", "Dataset ID", ...`):

```ts
  ..., "Input field", "Reference (output) field",
```

- [ ] **Step 5: Update App.tsx registration form** — extend `initialDataset`:

```ts
const initialDataset = { dataset_id: "", version: "1", revision: "default", source_url: "", checksum: "", credential_binding_id: "", license_text: "", input_field: "", reference_field: "" };
```

In `createDataset` (~line 509) pass the new fields:

```ts
      await api.createDataset({ ...datasetForm, source_url: datasetForm.source_url || null, checksum: datasetForm.checksum || null, credential_binding_id: datasetForm.credential_binding_id || null, license_text: datasetForm.license_text || null, input_field: datasetForm.input_field || null, reference_field: datasetForm.reference_field || null });
```

In the registration form JSX (line 770), after the `License text` label, add:

```tsx
<label>{t("datasetRegister.inputField")}<input value={datasetForm.input_field} onChange={(event) => setDatasetForm({ ...datasetForm, input_field: event.target.value })} placeholder={t("datasetRegister.inputFieldHint")} /></label><label>{t("datasetRegister.referenceField")}<input value={datasetForm.reference_field} onChange={(event) => setDatasetForm({ ...datasetForm, reference_field: event.target.value })} placeholder={t("datasetRegister.referenceFieldHint")} /></label>
```

- [ ] **Step 6: Update App.tsx run-form prefill** — in `queueDatasetRun` (~line 541), send the stored input field too (informational):

```ts
        reference_field: datasetRunForm.reference_field,
```

stays; add before the `api.createDatasetRun` call a prefill effect: in the run form's dataset `<select>` `onChange` (line 780), replace with a handler that prefills the reference field when the selected dataset carries one:

```tsx
<label>{t("datasetRun.dataset")}<select required value={datasetRunForm.dataset_version_id} onChange={(event) => { const next = event.target.value; const dataset = datasets.find((item) => item.id === next); setDatasetRunForm((current) => ({ ...current, dataset_version_id: next, reference_field: dataset?.reference_field ?? current.reference_field })); }}>...
```

Add `{t("datasetRun.inputField")}` display under the reference field label in the run form, showing the selected dataset's stored input field as muted text (informational only):

```tsx
{(() => { const selected = datasets.find((item) => item.id === datasetRunForm.dataset_version_id); return selected?.input_field ? <p className="muted">{t("datasetRun.inputField")}: <span data-i18n-preserve>{selected.input_field}</span></p> : null; })()}
```

- [ ] **Step 7: Run the tests to verify they pass**

Run: `npm test -- --run src/dataset-registration.test.tsx src/dataset-run.test.tsx src/i18n/locales.test.ts` in `frontend/`
Expected: PASS.

- [ ] **Step 8: Run the frontend build (typecheck)**

Run: `npm run build` in `frontend/`
Expected: PASS.

- [ ] **Step 9: Commit**

```bash
git add frontend/src/App.tsx frontend/src/i18n/catalog.ts frontend/src/i18n/operationalCopy.ts frontend/src/dataset-registration.test.tsx frontend/src/dataset-run.test.tsx
git commit -m "feat: add input and reference field defaults to dataset registration and run form"
```

---

### Task 8: Frontend — dataset catalog preview, edit, and delete actions

**Files:**
- Modify: `frontend/src/App.tsx` (`DatasetCatalog` component at ~line 821, its usage at line 763, plus new handlers in the App component)
- Modify: `frontend/src/i18n/operationalCopy.ts` (static phrases: "Preview", "Edit", "Delete", "Save changes", "Data preview", "Delete dataset version?")
- Create: `frontend/src/dataset-catalog.test.tsx`
- Test: existing `overview-dashboard.test.tsx` / `app-shell.test.tsx` patterns for navigation

**Interfaces:**
- Consumes: `api.previewDataset`, `api.updateDataset`, `api.deleteDataset` (Task 6), `Dataset` type (Task 6).
- Produces: `DatasetCatalog` gains `onPreview`, `onUpdate`, `onDelete` props; preview state renders a table; edit renders an inline form; delete confirms via `window.confirm`.

- [ ] **Step 1: Write the failing tests** — create `frontend/src/dataset-catalog.test.tsx`:

```tsx
import { cleanup, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import App from "./App";
import { api } from "./api";
import { LocaleProvider } from "./i18n/LocaleProvider";

afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
});

const readyDataset = {
  id: "ds-1",
  dataset_id: "demo",
  version: "1",
  revision: "default",
  source_url: null,
  credential_binding_id: null,
  checksum: "abc",
  local_path: "/data/datasets/x",
  size_bytes: 10,
  license_text: null,
  license_accepted_at: null,
  status: "ready",
  error_message: null,
  input_field: "question",
  reference_field: "answer",
};

async function renderApp(datasets = [readyDataset]) {
  vi.spyOn(api, "listEndpoints").mockResolvedValue([]);
  vi.spyOn(api, "listRuns").mockResolvedValue([]);
  vi.spyOn(api, "dashboard").mockResolvedValue(null as never);
  vi.spyOn(api, "listPromptPackages").mockResolvedValue([]);
  vi.spyOn(api, "listDatasets").mockResolvedValue(datasets);
  vi.spyOn(api, "listSuites").mockResolvedValue([]);
  vi.spyOn(api, "listBenchmarks").mockResolvedValue([]);
  vi.spyOn(api, "listTasks").mockResolvedValue([]);
  vi.spyOn(api, "analyticsMatrix").mockResolvedValue(null as never);
  vi.spyOn(api, "listUsers").mockResolvedValue([]);
  vi.spyOn(api, "listAuditEvents").mockResolvedValue([]);
  vi.spyOn(api, "systemHealth").mockResolvedValue(null as never);
  vi.spyOn(api, "datasetDiskUsage").mockResolvedValue({ root: "/data", cache_bytes: 10, available_bytes: 1000, total_bytes: 2000 });
  render(<LocaleProvider><App /></LocaleProvider>);
  const user = userEvent.setup();
  await user.click(screen.getByRole("button", { name: "Datasets" }));
  return { user };
}

describe("dataset catalog", () => {
  it("previews the first rows of a ready dataset", async () => {
    const preview = vi.spyOn(api, "previewDataset").mockResolvedValue({ fields: ["question", "answer"], rows: [{ question: "2+2?", answer: "4" }] });
    const { user } = await renderApp();
    await user.click(screen.getByRole("button", { name: "Preview" }));
    await waitFor(() => expect(screen.getByRole("heading", { name: /Data preview/i })).toBeTruthy());
    expect(preview).toHaveBeenCalledWith("ds-1", 5);
    expect(screen.getByText("2+2?")).toBeTruthy();
  }, 10_000);

  it("edits dataset metadata through the inline form", async () => {
    const update = vi.spyOn(api, "updateDataset").mockResolvedValue({ ...readyDataset, dataset_id: "renamed" });
    const list = vi.spyOn(api, "listDatasets");
    list.mockResolvedValue([readyDataset]);
    const { user } = await renderApp();
    await user.click(screen.getByRole("button", { name: "Edit" }));
    const idInput = screen.getByLabelText("Dataset ID");
    await user.clear(idInput);
    await user.type(idInput, "renamed");
    await user.click(screen.getByRole("button", { name: "Save changes" }));
    expect(update).toHaveBeenCalledWith("ds-1", expect.objectContaining({ dataset_id: "renamed" }));
  }, 10_000);

  it("deletes a dataset after confirmation", async () => {
    const remove = vi.spyOn(api, "deleteDataset").mockResolvedValue({ ...readyDataset });
    vi.spyOn(window, "confirm").mockReturnValue(true);
    const { user } = await renderApp();
    await user.click(screen.getByRole("button", { name: "Delete" }));
    expect(remove).toHaveBeenCalledWith("ds-1");
  }, 10_000);
});
```

Note: if the preview/edit/delete buttons clash with existing catalog buttons by accessible name, scope queries with the dataset card (`within(...)`).

- [ ] **Step 2: Run the tests to verify they fail**

Run: `npm test -- --run src/dataset-catalog.test.tsx` in `frontend/`
Expected: FAIL (buttons don't exist).

- [ ] **Step 3: Add static phrases** in `frontend/src/i18n/operationalCopy.ts` — add to `words`:

```ts
  preview: ["预览", "aperçu", "Vorschau", "предпросмотр", "プレビュー", "미리보기", "pratonton"],
  delete: ["删除", "supprimer", "löschen", "удалить", "削除", "삭제", "padam"],
  edit: ["编辑", "modifier", "bearbeiten", "изменить", "編集", "편집", "sunting"],
```

Add to the `staticSourceTexts` list (line 419–420 area):

```ts
  ..., "Preview", "Edit", "Delete", "Save changes", "Cancel", "Data preview", "Delete dataset version?"
```

Add phrases to the `phrases` record per locale (a few needed; use word-level fallback for the rest):

```ts
  "zh-CN": { ..., "Data preview": "数据预览", "Delete dataset version?": "删除数据集版本？", "Save changes": "保存更改" },
  fr: { ..., "Data preview": "Aperçu des données", "Delete dataset version?": "Supprimer la version du jeu de données ?", "Save changes": "Enregistrer les modifications" },
  de: { ..., "Data preview": "Datenvorschau", "Delete dataset version?": "Datensatzversion löschen?", "Save changes": "Änderungen speichern" },
  ru: { ..., "Data preview": "Предпросмотр данных", "Delete dataset version?": "Удалить версию набора данных?", "Save changes": "Сохранить изменения" },
  ja: { ..., "Data preview": "データのプレビュー", "Delete dataset version?": "データセット バージョンを削除しますか?", "Save changes": "変更を保存" },
  ko: { ..., "Data preview": "데이터 미리보기", "Delete dataset version?": "데이터 세트 버전을 삭제하시겠습니까?", "Save changes": "변경 사항 저장" },
  ms: { ..., "Data preview": "Pratonton data", "Delete dataset version?": "Padam versi set data?", "Save changes": "Simpan perubahan" },
```

- [ ] **Step 4: Add App-level handlers** in `frontend/src/App.tsx` (place near `clearDatasetCache` ~line 630):

```ts
  async function updateDatasetRecord(dataset: Dataset, payload: Record<string, string>) {
    setBusy(`dataset-edit-${dataset.id}`);
    try { await api.updateDataset(dataset.id, payload); showNotice("Dataset version updated."); await refresh(); }
    catch (error) { showError(error); }
    finally { setBusy(null); }
  }

  async function deleteDatasetRecord(dataset: Dataset) {
    if (!window.confirm(translateStaticTemplate(locale, "Delete dataset version?"))) return;
    setBusy(`dataset-delete-${dataset.id}`);
    try { await api.deleteDataset(dataset.id); showNotice("Dataset version deleted."); await refresh(); }
    catch (error) { showError(error); }
    finally { setBusy(null); }
  }
```

Update the usage at line 763:

```tsx
      {view === "datasets" && <DatasetCatalog datasets={datasets} busy={busy} onPrepare={prepareDataset} onPause={pauseDataset} onUpload={uploadDataset} onValidate={validateDataset} onClear={clearDatasetCache} onUpdate={updateDatasetRecord} onDelete={deleteDatasetRecord} />}
```

- [ ] **Step 5: Extend DatasetCatalog** in `frontend/src/App.tsx` — update the signature:

```tsx
function DatasetCatalog({ datasets, busy, onPrepare, onPause, onUpload, onValidate, onClear, onUpdate, onDelete }: { datasets: Dataset[]; busy: string | null; onPrepare: (dataset: Dataset) => Promise<void>; onPause: (dataset: Dataset) => Promise<void>; onUpload: (dataset: Dataset, event: ChangeEvent<HTMLInputElement>) => Promise<void>; onValidate: (dataset: Dataset) => Promise<void>; onClear: (dataset: Dataset) => Promise<void>; onUpdate: (dataset: Dataset, payload: Record<string, string>) => Promise<void>; onDelete: (dataset: Dataset) => Promise<void> }) {
```

Add local state at the top of the component:

```tsx
  const [preview, setPreview] = useState<{ datasetId: string; fields: string[]; rows: Array<Record<string, string>> } | null>(null);
  const [previewError, setPreviewError] = useState<string | null>(null);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [editForm, setEditForm] = useState<Record<string, string>>({});
```

Add the preview loader:

```tsx
  async function loadPreview(dataset: Dataset) {
    setPreviewError(null);
    try {
      const data = await api.previewDataset(dataset.id, 5);
      setPreview({ datasetId: dataset.id, fields: data.fields, rows: data.rows });
    } catch (error) {
      setPreviewError(error instanceof Error ? error.message : "Preview unavailable.");
      setPreview(null);
    }
  }
```

In the card actions, after the existing buttons (before the closing `</div>` of `.actions`), add:

```tsx
{dataset.status === "ready" && <button className="secondary" onClick={() => void loadPreview(dataset)}>Preview</button>}<button className="secondary" onClick={() => { setEditingId(dataset.id); setEditForm({ dataset_id: dataset.dataset_id, version: dataset.version, revision: dataset.revision, source_url: dataset.source_url ?? "", checksum: dataset.checksum ?? "", license_text: dataset.license_text ?? "", credential_binding_id: dataset.credential_binding_id ?? "", input_field: dataset.input_field ?? "", reference_field: dataset.reference_field ?? "" }); }}>Edit</button><button className="secondary" onClick={() => void onDelete(dataset)}>Delete</button>
```

In the card body, after the error paragraph and before the actions div, add the preview and edit blocks:

```tsx
{preview?.datasetId === dataset.id && <div className="table-wrap"><h3>Data preview</h3><table><thead><tr>{preview.fields.map((field) => <th key={field}>{field}</th>)}</tr></thead><tbody>{preview.rows.map((row, index) => <tr key={index}>{preview.fields.map((field) => <td key={field}>{row[field] ?? ""}</td>)}</tr>)}</tbody></table></div>}{editingId === dataset.id && <form className="form" onSubmit={(event) => { event.preventDefault(); setEditingId(null); void onUpdate(dataset, editForm); }}><label>Dataset ID<input required value={editForm.dataset_id} onChange={(event) => setEditForm({ ...editForm, dataset_id: event.target.value })} /></label><div className="field-row"><label>Version<input required value={editForm.version} onChange={(event) => setEditForm({ ...editForm, version: event.target.value })} /></label><label>Revision<input required value={editForm.revision} onChange={(event) => setEditForm({ ...editForm, revision: event.target.value })} /></label></div><label>Source HTTPS URL<input value={editForm.source_url} onChange={(event) => setEditForm({ ...editForm, source_url: event.target.value })} placeholder="https://… or hf://owner/repository/path" /></label><label>Expected SHA-256 checksum<input value={editForm.checksum} onChange={(event) => setEditForm({ ...editForm, checksum: event.target.value })} /></label><label>Credential binding ID<input value={editForm.credential_binding_id} onChange={(event) => setEditForm({ ...editForm, credential_binding_id: event.target.value })} /></label><label>Input field<input value={editForm.input_field} onChange={(event) => setEditForm({ ...editForm, input_field: event.target.value })} /></label><label>Reference (output) field<input value={editForm.reference_field} onChange={(event) => setEditForm({ ...editForm, reference_field: event.target.value })} /></label><label>License text<textarea value={editForm.license_text} onChange={(event) => setEditForm({ ...editForm, license_text: event.target.value })} /></label><button className="primary">Save changes</button></form>}
```

Render `previewError` above the card list when set:

```tsx
{previewError && <p className="error">{previewError}</p>}
```

- [ ] **Step 6: Run the tests to verify they pass**

Run: `npm test -- --run src/dataset-catalog.test.tsx` in `frontend/`
Expected: PASS.

- [ ] **Step 7: Run the frontend test suite and build**

Run: `npm test -- --run` and `npm run build` in `frontend/`
Expected: PASS.

- [ ] **Step 8: Commit**

```bash
git add frontend/src/App.tsx frontend/src/i18n/operationalCopy.ts frontend/src/dataset-catalog.test.tsx
git commit -m "feat: add dataset preview, edit, and delete actions to the catalog"
```

---

### Task 9: Frontend — in-app guide page

**Files:**
- Modify: `frontend/src/i18n/catalog.ts` (`workspaceViews` + `navigationCopy` for 8 locales — add `guide` after `dashboard`)
- Modify: `frontend/src/dashboard/navigation.ts` (overview group gains guide item)
- Modify: `frontend/src/App.tsx` (View union + `view === "guide"` render)
- Create: `frontend/src/components/Guide.tsx`
- Create: `frontend/src/guide.test.tsx`
- Test: existing `app-shell.test.tsx` (nav parity) and `locales.test.ts`

**Interfaces:**
- Consumes: `navigationCopy.items.guide` from catalog, existing `.panel`/`.card`/`.section-title` CSS classes.
- Produces: `guide` view renders `<Guide />`; nav item visible in the overview group.

- [ ] **Step 1: Write the failing tests** — create `frontend/src/guide.test.tsx`:

```tsx
import { cleanup, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import App from "./App";
import { api } from "./api";
import { LocaleProvider } from "./i18n/LocaleProvider";

afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
});

describe("usage guide", () => {
  it("opens the guide from navigation and shows the workflow steps", async () => {
    const user = userEvent.setup();
    vi.spyOn(api, "listEndpoints").mockResolvedValue([]);
    vi.spyOn(api, "listRuns").mockResolvedValue([]);
    vi.spyOn(api, "dashboard").mockResolvedValue(null as never);
    vi.spyOn(api, "listPromptPackages").mockResolvedValue([]);
    vi.spyOn(api, "listDatasets").mockResolvedValue([]);
    vi.spyOn(api, "listSuites").mockResolvedValue([]);
    vi.spyOn(api, "listBenchmarks").mockResolvedValue([]);
    vi.spyOn(api, "listTasks").mockResolvedValue([]);
    vi.spyOn(api, "analyticsMatrix").mockResolvedValue(null as never);
    vi.spyOn(api, "listUsers").mockResolvedValue([]);
    vi.spyOn(api, "listAuditEvents").mockResolvedValue([]);
    vi.spyOn(api, "systemHealth").mockResolvedValue(null as never);

    render(<LocaleProvider><App /></LocaleProvider>);
    await user.click(screen.getByRole("button", { name: "Guide" }));
    expect(screen.getByRole("heading", { name: /How to use this workspace/i })).toBeTruthy();
    expect(screen.getByText(/1\. Add a model endpoint/i)).toBeTruthy();
  }, 10_000);
});
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `npm test -- --run src/guide.test.tsx` in `frontend/`
Expected: FAIL (no "Guide" nav button / no heading).

- [ ] **Step 3: Add the view to the catalog** in `frontend/src/i18n/catalog.ts`:

```ts
export const workspaceViews = ["dashboard", "guide", "models", "capabilities", "workspace", "benchmarks", "datasets", "suites", "runs", "queue", "workers", "analysis", "compare", "reports", "reviews", "users", "settings"] as const;
```

Update every locale's `navigation(...)` items array — insert a `["Guide", "Step-by-step usage walkthrough"]` (translated per locale) tuple immediately after the Dashboard tuple. Translations:
- en: `["Guide", "Step-by-step usage walkthrough"]`
- zh-CN: `["指南", "分步使用说明"]`
- fr: `["Guide", "Parcours d’utilisation pas à pas"]`
- de: `["Leitfaden", "Schritt-für-Schritt-Anleitung"]`
- ru: `["Руководство", "Пошаговое руководство по использованию"]`
- ja: `["ガイド", "ステップバイステップの使い方"]`
- ko: `["가이드", "단계별 사용 안내"]`
- ms: `["Panduan", "Panduan penggunaan langkah demi langkah"]`

- [ ] **Step 4: Add the nav item** in `frontend/src/dashboard/navigation.ts`:

```ts
  { id: "overview", items: [{ view: "dashboard", glyph: "⌂" }, { view: "guide", glyph: "?" }] },
```

- [ ] **Step 5: Create `frontend/src/components/Guide.tsx`** — static content; all copy goes through StaticCopy's phrase/word translation. Keep sentences short so word-level fallback works, and add longer phrases to `staticSourceTexts` + the `phrases` map for the 7 non-English locales:

```tsx
import { useTranslation } from "../i18n/LocaleProvider";

const steps = [
  ["1. Add a model endpoint", "Models · configure the provider, run a connection test, and confirm it is available."],
  ["2. Register a dataset", "Datasets · declare the source and, optionally, the input and reference fields."],
  ["3. Download and verify", "Download the dataset and wait until its status is ready."],
  ["4. Create a prompt package", "Workspace · write the user template; record fields render through {{ placeholders }}."],
  ["5. Queue a dataset run", "Runs · pick the dataset, reference field, and endpoint, then queue the run."],
  ["6. Inspect evidence", "Open the run to review samples, scores, latency, cost, and errors."],
  ["7. Judge, review, and report", "Run blind pairwise judging, save human reviews, and generate reports."],
] as const;

export function Guide() {
  const { formatNumber } = useTranslation();
  void formatNumber;
  return (
    <section className="panel">
      <div className="section-title"><h2>How to use this workspace</h2><span>7 steps</span></div>
      <p className="muted">Register a model endpoint and a dataset, then queue evaluation runs and inspect the evidence.</p>
      <div className="cards">
        {steps.map(([title, description]) => (
          <article className="card" key={title}>
            <h3>{title}</h3>
            <p className="muted">{description}</p>
          </article>
        ))}
      </div>
    </section>
  );
}
```

(Adjust the `useTranslation` import to match the actual hook API in `frontend/src/i18n/LocaleProvider.tsx` — check it and drop unused imports.)

Add the static strings to `staticSourceTexts` (one line in `operationalCopy.ts`):

```ts
  "How to use this workspace", "7 steps", "Register a model endpoint and a dataset, then queue evaluation runs and inspect the evidence.", "1. Add a model endpoint", "Models · configure the provider, run a connection test, and confirm it is available.", "2. Register a dataset", "Datasets · declare the source and, optionally, the input and reference fields.", "3. Download and verify", "Download the dataset and wait until its status is ready.", "4. Create a prompt package", "Workspace · write the user template; record fields render through {{ placeholders }}.", "5. Queue a dataset run", "Runs · pick the dataset, reference field, and endpoint, then queue the run.", "6. Inspect evidence", "Open the run to review samples, scores, latency, cost, and errors.", "7. Judge, review, and report", "Run blind pairwise judging, save human reviews, and generate reports.",
```

Add per-locale `phrases` entries for the full sentences (word-level fallback handles the rest). Example for zh-CN (repeat for fr, de, ru, ja, ko, ms):

```ts
  "How to use this workspace": "如何使用此工作区",
  "1. Add a model endpoint": "1. 添加模型端点",
  "2. Register a dataset": "2. 注册数据集",
  "3. Download and verify": "3. 下载并验证",
  "4. Create a prompt package": "4. 创建提示词包",
  "5. Queue a dataset run": "5. 将数据集评测加入队列",
  "6. Inspect evidence": "6. 检查证据",
  "7. Judge, review, and report": "7. 评审、审核并生成报告",
```

- [ ] **Step 6: Wire the view into App.tsx** — extend the View union (line 39) and add the render:

```tsx
type View = "dashboard" | "guide" | "models" | ...;
```

```tsx
      {view === "guide" && <Guide />}
```

Add the import next to the OverviewDashboard import (line 32):

```tsx
import { Guide } from "./components/Guide";
```

- [ ] **Step 7: Run the tests to verify they pass**

Run: `npm test -- --run src/guide.test.tsx src/i18n/locales.test.ts src/app-shell.test.tsx` in `frontend/`
Expected: PASS.

- [ ] **Step 8: Run the frontend test suite and build**

Run: `npm test -- --run` and `npm run build` in `frontend/`
Expected: PASS.

- [ ] **Step 9: Commit**

```bash
git add frontend/src/i18n/catalog.ts frontend/src/dashboard/navigation.ts frontend/src/App.tsx frontend/src/components/Guide.tsx frontend/src/guide.test.tsx frontend/src/i18n/operationalCopy.ts
git commit -m "feat: add in-app usage guide view"
```

---

### Task 10: Docs — workflow guide and changelog

**Files:**
- Modify: `docs/evaluation-workflow.md`
- Modify: `CHANGELOG.md`

- [ ] **Step 1: Update the workflow doc** — in `docs/evaluation-workflow.md`, in the dataset registration section, add a paragraph covering the new capabilities (check the actual section heading first with `rg -n "^#" docs/evaluation-workflow.md`):

```markdown
Registered versions can declare an optional **input field** and **reference
(output) field** used as run defaults; the run form still allows per-run
overrides. Ready datasets expose a **Preview** action that shows the first
five rows of the prepared cache, plus **Edit** and **Delete** actions.
Deleting is blocked while an evaluation run references the revision or while
the download is in progress.
```

- [ ] **Step 2: Update the changelog** — in `CHANGELOG.md`, under `## Unreleased` → `### Added`, add:

```markdown
- Dataset versions can declare optional input and reference field defaults,
  and the catalog gains preview, edit, and delete actions (delete is blocked
  while a run references the revision).
- New in-app usage guide view walking through the evaluation workflow.
```

- [ ] **Step 3: Verify**

Run: `python -m pytest -q` (repo root) and `npm test -- --run` + `npm run build` (frontend/)
Expected: all PASS.

- [ ] **Step 4: Commit**

```bash
git add -f docs/evaluation-workflow.md CHANGELOG.md
git commit -m "docs: document dataset management and usage guide"
```

---

## Self-Review Notes

- Task 1 (migration + fields) → spec section 1 (model/migration). ✔
- Task 2 (preview) → spec section 2 (preview endpoint) + AC2. ✔
- Task 3 (update) + Task 4 (delete) → spec section 2 (PUT/DELETE) + AC4. ✔
- Task 5 (Mongo tests) → spec section 6 (Mongo fakes) + spec section 2 (Mongo parallel service functions). The Mongo service functions themselves are written in Tasks 3–4; Task 5 only adds their tests. ✔
- Task 6 (api.ts) + Task 7 (registration/run form) → spec section 5 + AC3. ✔
- Task 8 (catalog actions) → spec section 4 + AC2/AC4. ✔
- Task 9 (guide) → spec section 3 + AC1. ✔
- Task 10 (docs) → spec section 7 + AC5 verification. ✔
- Placeholder scan: every step carries concrete code; no TBD/TODO.
- Type consistency: `preview_dataset_records(prepared_path, data_root, *, limit)` used identically in Task 2; `update_mongo_dataset(store, dataset_id, payload)` matches its API call in Task 3; `api.previewDataset/updateDataset/deleteDataset` names match between Task 6 and Tasks 7–8.
