# HF Dataset Downloads and Dataset Evaluation Runs — Implementation Plan

> **For agentic workers:** implement this plan task-by-task — dispatch a fresh subagent per task with the native `task` tool (recommended for quality), or use the superpowers-executing-plans skill to work through it inline. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix `hf://` dataset downloads (correct Hugging Face namespace + safe redirect following) and add a dataset evaluation run mode that turns records of a registered, ready dataset into scored evaluation samples, plus end-to-end workflow documentation.

**Architecture:** The backend resolves and downloads datasets through `backend/app/services/datasets.py` (fixes land there and in `prompt_templates.py`). A new `dataset_records.py` reads the prepared `sample-index.jsonl` artifacts; a new `dataset_runs.py` service builds runs from records using the existing run/task pipeline (`TaskType.DATASET_PREPARATION`, `BENCHMARK`, `EVALUATION_SHARD`) and the existing prompt-package machinery. Two new API endpoints (`POST /api/v1/evaluation-runs/dataset`, `POST /api/v1/evaluation-runs/dataset/preflight`) dispatch between the SQLAlchemy and Mongo document-store paths exactly like the existing `/custom-multimodal` endpoints. The React app gets a dataset-run form in the runs view; all new strings go through the typed i18n catalog (`frontend/src/i18n/catalog.ts`).

**Tech Stack:** Python 3.12, FastAPI, SQLAlchemy, httpx (pinned transports), MongoDB document store, pytest; React 19 + TypeScript + Vite, vitest; 8-locale typed i18n catalog.

**Spec:** `docs/reasonix/specs/2026-08-05-hf-datasets-and-dataset-evaluation-runs-design.md`
**Branch:** create `agent/dataset-evaluation-runs` from `master` before Task 1. Preserve unrelated working-tree changes (connection-tester refactor) — commit only the files listed in each task.

---

## File structure map

| File | Responsibility | Change |
|---|---|---|
| `backend/app/services/datasets.py` | `hf://` namespace resolution, safe redirects, download error hints | Modify |
| `backend/app/services/prompt_templates.py` | template rendering with record-field variables | Modify |
| `backend/app/services/dataset_records.py` | read prepared dataset records as field mappings | Create |
| `backend/app/services/dataset_runs.py` | dataset-run sample building, run creation, preflight (SQL) | Create |
| `backend/app/services/mongo_run_executor.py` | Mongo dataset-run creation + preflight | Modify |
| `backend/app/api/evaluation_runs.py` | `DatasetRunCreate` model + two endpoints | Modify |
| `tests/test_datasets.py` | namespace + redirect + error-hint tests | Modify |
| `tests/test_prompt_templates.py` | extra-variable rendering tests | Modify |
| `tests/test_dataset_records.py` | record reader tests | Create |
| `tests/test_dataset_runs.py` | dataset-run API end-to-end tests (SQL + Mongo) | Create |
| `frontend/src/api.ts` | `createDatasetRun`, `validateDatasetRun` | Modify |
| `frontend/src/i18n/catalog.ts` | 8 new keys × 8 locales | Modify |
| `frontend/src/App.tsx` | dataset evaluation form in the runs view | Modify |
| `frontend/src/dataset-run.test.tsx` | form behavior test | Create |
| `docs/evaluation-workflow.md` | end-to-end workflow guide | Create |
| `README.md` | pointer to the workflow guide | Modify |

---

### Task 1: Fix the `hf://` namespace in `resolve_dataset_source`

**Files:**
- Modify: `backend/app/services/datasets.py:34-63` (`resolve_dataset_source`)
- Test: `tests/test_datasets.py:91-112` (`test_dataset_source_blocks_unsafe_schemes_private_networks_and_unapproved_bindings`)

- [ ] **Step 1: Update the failing test to assert the dataset namespace**

In `tests/test_datasets.py`, change line 107:

```python
    assert resolved == "https://huggingface.co/owner/repository/resolve/main/path/to/file.jsonl"
```

to:

```python
    assert resolved == "https://huggingface.co/datasets/owner/repository/resolve/main/path/to/file.jsonl"
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `python -m pytest tests/test_datasets.py::test_dataset_source_blocks_unsafe_schemes_private_networks_and_unapproved_bindings -q`
Expected: FAIL — `assert 'https://huggingface.co/owner/repository/...' == 'https://huggingface.co/datasets/owner/repository/...'`

- [ ] **Step 3: Fix the resolver**

In `backend/app/services/datasets.py`, change line 50 from:

```python
        resolved = f"https://huggingface.co/{repository}/resolve/{quote(revision, safe='')}/{quote(relative_path, safe='/')}"
```

to:

```python
        resolved = f"https://huggingface.co/datasets/{repository}/resolve/{quote(revision, safe='')}/{quote(relative_path, safe='/')}"
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `python -m pytest tests/test_datasets.py::test_dataset_source_blocks_unsafe_schemes_private_networks_and_unapproved_bindings -q`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/datasets.py tests/test_datasets.py
git commit -m "fix: resolve hf:// dataset sources through the HF dataset namespace"
```

---

### Task 2: Follow redirects safely and explain download failures

**Files:**
- Modify: `backend/app/services/datasets.py:106-142` (`write_dataset_source`), `:270-327` (`download_dataset` error mapping), import line 10
- Test: `tests/test_datasets.py` (new test functions)

- [ ] **Step 1: Write the failing redirect tests**

Append to `tests/test_datasets.py`:

```python
def _redirect_transport(monkeypatch: pytest.MonkeyPatch, handler) -> None:
    monkeypatch.setattr(
        "app.services.outbound_network.getaddrinfo",
        lambda host, *_args, **_kwargs: [(None, None, None, None, (("93.184.216.34", 0) if host == "datasets.example.test" else ("127.0.0.1", 0)))],
    )
    monkeypatch.setattr(
        "app.services.datasets.pinned_outbound_transport",
        lambda *_args, **_kwargs: httpx.MockTransport(handler),
    )


def test_dataset_download_follows_validated_redirects(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[str] = []
    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(str(request.url))
        if len(calls) == 1:
            return httpx.Response(307, headers={"location": "https://datasets.example.test/final.jsonl"})
        return httpx.Response(200, content=b'{"question":"q","answer":"a"}\n')
    _redirect_transport(monkeypatch, handler)
    digest = write_dataset_source("https://datasets.example.test/start.jsonl", tmp_path / "out.jsonl", {})
    assert digest == hashlib.sha256(b'{"question":"q","answer":"a"}\n').hexdigest()
    assert (tmp_path / "out.jsonl").read_bytes() == b'{"question":"q","answer":"a"}\n'
    assert calls == ["https://datasets.example.test/start.jsonl", "https://datasets.example.test/final.jsonl"]


def test_dataset_download_rejects_redirect_to_private_target(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(307, headers={"location": "https://127.0.0.1/secret.jsonl"})
    _redirect_transport(monkeypatch, handler)
    with pytest.raises(DatasetError, match="private or restricted"):
        write_dataset_source("https://datasets.example.test/start.jsonl", tmp_path / "out.jsonl", {})


def test_dataset_download_rejects_redirect_without_location_and_hop_loops(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    def no_location(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(307)
    _redirect_transport(monkeypatch, no_location)
    with pytest.raises(DatasetError, match="without a Location header"):
        write_dataset_source("https://datasets.example.test/start.jsonl", tmp_path / "out.jsonl", {})

    def loop(request: httpx.Request) -> httpx.Response:
        return httpx.Response(307, headers={"location": str(request.url)})
    _redirect_transport(monkeypatch, loop)
    with pytest.raises(DatasetError, match="redirected more than 5 times"):
        write_dataset_source("https://datasets.example.test/start.jsonl", tmp_path / "out.jsonl", {})


def test_dataset_download_enforces_byte_limit_after_redirects(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if "final" in str(request.url):
            return httpx.Response(200, content=b"123456789")
        return httpx.Response(307, headers={"location": "https://datasets.example.test/final.jsonl"})
    _redirect_transport(monkeypatch, handler)
    with pytest.raises(DatasetError, match="byte limit"):
        write_dataset_source("https://datasets.example.test/start.jsonl", tmp_path / "out.jsonl", {}, max_bytes=6)
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `python -m pytest tests/test_datasets.py -q`
Expected: FAIL — 4 new tests fail (`Client error` or redirect body written instead of the CSV bytes)

- [ ] **Step 3: Implement the redirect loop and error hints**

In `backend/app/services/datasets.py`:

1. Change the import on line 10 from `from urllib.parse import quote, urlparse` to:

```python
from urllib.parse import quote, urljoin, urlparse
```

2. Add a module constant after `MAX_PREPARED_ARCHIVE_BYTES`:

```python
MAX_DOWNLOAD_REDIRECTS = 5
```

3. Replace the body of `write_dataset_source` (lines 111-142) with:

```python
def write_dataset_source(
    source: str,
    target: Path,
    headers: dict[str, str],
    on_chunk: Callable[[], None] | None = None,
    *,
    max_bytes: int = DEFAULT_DATASET_DOWNLOAD_MAX_BYTES,
) -> str:
    """Stream a configured source to a temporary file and return its SHA-256 digest.

    Redirects are followed only after every hop passes the same outbound URL
    validation as the original source, so no unvalidated destination is ever
    contacted and the redirect body is never written to disk.
    """

    digest = hashlib.sha256()
    current = source
    for _hop in range(MAX_DOWNLOAD_REDIRECTS + 1):
        try:
            addresses = validate_outbound_url(current)
        except OutboundNetworkError as error:
            raise DatasetError(str(error)) from error
        with httpx.Client(transport=pinned_outbound_transport(addresses), timeout=60, follow_redirects=False) as client:
            with client.stream("GET", current, headers=headers) as response:
                if response.is_redirect:
                    location = response.headers.get("location")
                    if not location:
                        raise DatasetError("Dataset source redirected without a Location header.")
                    current = urljoin(current, location)
                    continue
                response.raise_for_status()
                content_length = response.headers.get("content-length")
                if content_length and content_length.isdigit() and int(content_length) > max_bytes:
                    raise DatasetError(f"Dataset download exceeds the configured {max_bytes} byte limit.")
                written = 0
                with target.open("wb") as output_file:
                    for chunk in response.iter_bytes():
                        written += len(chunk)
                        if written > max_bytes:
                            raise DatasetError(f"Dataset download exceeds the configured {max_bytes} byte limit.")
                        output_file.write(chunk)
                        digest.update(chunk)
                        if on_chunk:
                            on_chunk()
                return digest.hexdigest()
    raise DatasetError(f"Dataset source redirected more than {MAX_DOWNLOAD_REDIRECTS} times.")
```

4. Replace the `except (httpx.HTTPStatusError, DatasetError) as error:` block in `download_dataset` (lines 318-321) with:

```python
    except (httpx.HTTPStatusError, DatasetError) as error:
        message = str(error)
        status_code = getattr(getattr(error, "response", None), "status_code", None)
        if status_code == 404:
            message = f"{message} The repository or file may not exist; check the owner/repository name and revision."
        elif status_code in {401, 403}:
            message = (
                f"{message} Hugging Face requires authentication for this source "
                "(private or gated repository), or the repository is not a public dataset."
            )
        dataset.status = DatasetStatus.CREDENTIAL_REQUIRED.value if dataset.credential_binding_id and ("credential binding" in message or status_code in {401, 403}) else DatasetStatus.FAILED.value
        dataset.error_message = message[:500]
        session.commit()
        raise DatasetError(str(error)) from error
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `python -m pytest tests/test_datasets.py -q`
Expected: PASS (all existing + 4 new)

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/datasets.py tests/test_datasets.py
git commit -m "fix: follow dataset download redirects with per-hop validation and explain failures"
```

---

### Task 3: Dataset record reader

**Files:**
- Create: `backend/app/services/dataset_records.py`
- Test: `tests/test_dataset_records.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/test_dataset_records.py`:

```python
import json
from pathlib import Path

import pytest

from app.services.dataset_records import DatasetRecordError, count_dataset_records, iter_dataset_records


def _write_prepared(tmp_path: Path, source_name: str, source_bytes: bytes, index_entries: list[dict[str, object]]) -> str:
    prepared = tmp_path / "data" / "datasets" / "demo" / "1" / "main" / "prepared"
    source_root = prepared / "source"
    source_root.mkdir(parents=True)
    (source_root / source_name).write_bytes(source_bytes)
    (prepared / "manifest.json").write_text(json.dumps({"format": "lle.sample-index/v1", "source_files": [source_name], "record_count": len(index_entries), "index_path": "sample-index.jsonl"}), encoding="utf-8")
    (prepared / "sample-index.jsonl").write_text("\n".join(json.dumps(entry) for entry in index_entries) + "\n", encoding="utf-8")
    return str(prepared / "manifest.json")


def test_dataset_records_reads_jsonl(tmp_path: Path) -> None:
    prepared_path = _write_prepared(
        tmp_path,
        "dataset.jsonl",
        b'{"question":"q1","answer":"a1"}\n{"question":"q2","answer":"a2"}\n',
        [{"source": "dataset.jsonl", "record_number": 1}, {"source": "dataset.jsonl", "record_number": 2}],
    )
    records = list(iter_dataset_records(prepared_path, str(tmp_path / "data")))
    assert [record["fields"]["question"] for record in records] == ["q1", "q2"]
    assert records[0]["source"] == "dataset.jsonl" and records[0]["record_number"] == 1


def test_dataset_records_reads_csv_tsv_txt_and_json(tmp_path: Path) -> None:
    prepared_path = _write_prepared(
        tmp_path,
        "dataset.csv",
        b"question,answer\nq1,a1\nq2,a2\n",
        [{"source": "dataset.csv", "record_number": 2}],
    )
    records = list(iter_dataset_records(prepared_path, str(tmp_path / "data")))
    assert records[0]["fields"] == {"question": "q1", "answer": "a1"}
    prepared_path = _write_prepared(
        tmp_path,
        "dataset.txt",
        b"line one\nline two\n",
        [{"source": "dataset.txt", "record_number": 2}],
    )
    records = list(iter_dataset_records(prepared_path, str(tmp_path / "data")))
    assert records[0]["fields"] == {"text": "line two"}
    prepared_path = _write_prepared(
        tmp_path,
        "dataset.json",
        b'[{"question":"q1","answer":"a1"},{"question":"q2","answer":"a2"}]',
        [{"source": "dataset.json", "record_number": 2}],
    )
    records = list(iter_dataset_records(prepared_path, str(tmp_path / "data")))
    assert records[0]["fields"]["question"] == "q2"


def test_dataset_records_respects_limit_and_counts(tmp_path: Path) -> None:
    prepared_path = _write_prepared(
        tmp_path,
        "dataset.jsonl",
        b'{"question":"q1"}\n{"question":"q2"}\n{"question":"q3"}\n',
        [{"source": "dataset.jsonl", "record_number": n} for n in (1, 2, 3)],
    )
    assert len(list(iter_dataset_records(prepared_path, str(tmp_path / "data"), limit=2))) == 2
    assert count_dataset_records(prepared_path, str(tmp_path / "data")) == 3


def test_dataset_records_rejects_unsafe_prepared_path_and_unsupported_format(tmp_path: Path) -> None:
    with pytest.raises(DatasetRecordError, match="outside the configured dataset root"):
        list(iter_dataset_records(str(tmp_path / "elsewhere" / "manifest.json"), str(tmp_path / "data")))
    prepared_path = _write_prepared(
        tmp_path,
        "dataset.parquet",
        b"not-parquet",
        [{"source": "dataset.parquet", "record_number": 1}],
    )
    with pytest.raises(DatasetRecordError, match="not supported"):
        list(iter_dataset_records(prepared_path, str(tmp_path / "data")))
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `python -m pytest tests/test_dataset_records.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.services.dataset_records'`

- [ ] **Step 3: Implement the reader**

Create `backend/app/services/dataset_records.py`:

```python
from __future__ import annotations

import csv
import io
import json
from collections.abc import Iterator
from pathlib import Path
from typing import Any


class DatasetRecordError(ValueError):
    """Raised when a prepared dataset cannot be read as evaluation records."""


_SUPPORTED_RECORD_SUFFIXES = {".jsonl", ".json", ".csv", ".tsv", ".txt"}


def iter_dataset_records(
    prepared_path: str,
    data_root: str,
    *,
    limit: int | None = None,
) -> Iterator[dict[str, object]]:
    """Yield prepared dataset records as ``{"source", "record_number", "fields"}``.

    ``prepared_path`` is the ``manifest.json`` recorded on the dataset version
    (``dataset.prepared_path``).  Only artifacts inside ``data_root/datasets``
    are accepted, mirroring ``validate_prepared_dataset_cache``.
    """

    prepared = _prepared_root(prepared_path, data_root)
    manifest = json.loads((prepared / "manifest.json").read_text(encoding="utf-8"))
    index_path = prepared / str(manifest.get("index_path", "sample-index.jsonl"))
    source_root = prepared / "source"
    if not index_path.is_file():
        raise DatasetRecordError("Dataset sample index is missing from the prepared cache.")
    if not source_root.is_dir():
        raise DatasetRecordError("Dataset source materialization is missing from the prepared cache.")
    yielded = 0
    with index_path.open("r", encoding="utf-8") as index_file:
        for line in index_file:
            line = line.strip()
            if not line:
                continue
            entry = json.loads(line)
            source = entry.get("source")
            record_number = entry.get("record_number")
            if not isinstance(source, str) or not isinstance(record_number, int):
                raise DatasetRecordError("Dataset sample index contains an invalid entry.")
            source_file = (source_root / source).resolve()
            if not source_file.is_relative_to(source_root.resolve()):
                raise DatasetRecordError("Dataset sample index references a file outside the prepared cache.")
            fields = _read_record(source_file, record_number)
            if fields is None:
                continue
            yielded += 1
            yield {"source": source, "record_number": record_number, "fields": fields}
            if limit is not None and yielded >= limit:
                return


def count_dataset_records(prepared_path: str, data_root: str, *, limit: int | None = None) -> int:
    """Count indexable records without materializing their field mappings."""

    return sum(1 for _ in iter_dataset_records(prepared_path, data_root, limit=limit))


def _prepared_root(prepared_path: str, data_root: str) -> Path:
    root = (Path(data_root).resolve() / "datasets").resolve()
    manifest = Path(prepared_path).resolve()
    if not manifest.is_relative_to(root) or manifest.name != "manifest.json" or manifest.parent.name != "prepared":
        raise DatasetRecordError("Dataset prepared cache is missing or outside the configured dataset root.")
    return manifest.parent


def _read_record(source_file: Path, record_number: int) -> dict[str, object] | None:
    suffix = source_file.suffix.lower()
    if suffix == ".jsonl":
        return _read_jsonl_record(source_file, record_number)
    if suffix == ".json":
        return _read_json_record(source_file, record_number)
    if suffix in {".csv", ".tsv"}:
        return _read_delimited_record(source_file, record_number, delimiter="," if suffix == ".csv" else "\t")
    if suffix == ".txt":
        return _read_text_record(source_file, record_number)
    raise DatasetRecordError(
        f"Dataset format {suffix or '(none)'} is not supported for evaluation runs; "
        "use JSONL, JSON, CSV, TSV, or TXT."
    )


def _read_jsonl_record(source_file: Path, record_number: int) -> dict[str, object] | None:
    with source_file.open("r", encoding="utf-8", errors="replace") as source:
        current = 0
        for line in source:
            line = line.strip()
            if not line:
                continue
            current += 1
            if current != record_number:
                continue
            value = json.loads(line)
            if not isinstance(value, dict):
                raise DatasetRecordError("Dataset JSONL records must be JSON objects.")
            return value
    return None


def _read_json_record(source_file: Path, record_number: int) -> dict[str, object] | None:
    value = json.loads(source_file.read_text(encoding="utf-8", errors="replace"))
    if isinstance(value, dict):
        return value
    if not isinstance(value, list):
        raise DatasetRecordError("Dataset JSON sources must be an object or an array of objects.")
    index = record_number - 1
    if not 0 <= index < len(value):
        return None
    record = value[index]
    if not isinstance(record, dict):
        raise DatasetRecordError("Dataset JSON records must be objects.")
    return record


def _read_delimited_record(source_file: Path, record_number: int, *, delimiter: str) -> dict[str, object] | None:
    with source_file.open("r", encoding="utf-8", errors="replace", newline="") as source:
        reader = csv.DictReader(io.StringIO(source.read()), delimiter=delimiter)
        rows = list(reader)
    if not 1 <= record_number <= len(rows):
        return None
    return dict(rows[record_number - 1])


def _read_text_record(source_file: Path, record_number: int) -> dict[str, object] | None:
    with source_file.open("r", encoding="utf-8", errors="replace") as source:
        current = 0
        for line in source:
            line = line.rstrip("\n").rstrip("\r")
            if not line.strip():
                continue
            current += 1
            if current == record_number:
                return {"text": line}
    return None
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `python -m pytest tests/test_dataset_records.py -q`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/dataset_records.py tests/test_dataset_records.py
git commit -m "feat: add prepared dataset record reader"
```

---

### Task 4: Allow record fields in prompt templates

**Files:**
- Modify: `backend/app/services/prompt_templates.py:19-39`
- Test: `tests/test_prompt_templates.py`

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_prompt_templates.py`:

```python
def test_render_template_accepts_extra_variables() -> None:
    rendered = render_template("Rate: {{star}}/5", {"star": "4"}, extra_variables=frozenset({"star"}))
    assert rendered == "Rate: 4/5"


def test_render_template_still_rejects_unknown_variables_without_extra_variables() -> None:
    with pytest.raises(PromptTemplateError, match="star"):
        render_template("Rate: {{star}}/5", {"star": "4"})
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `python -m pytest tests/test_prompt_templates.py -q`
Expected: FAIL — `TypeError: render_template() got an unexpected keyword argument 'extra_variables'`

- [ ] **Step 3: Extend the template functions**

In `backend/app/services/prompt_templates.py`, replace `validate_template` and `render_template` (lines 19-39) with:

```python
def validate_template(template: str, *, extra_variables: frozenset[str] = frozenset()) -> set[str]:
    """Reject unsupported interpolation variables at package-registration time.

    ``extra_variables`` allows caller-known variables (for example dataset
    record field names) without relaxing the allowlist for other callers.
    """

    variables = set(_VARIABLE.findall(template))
    unsupported = sorted(variables - (ALLOWED_TEMPLATE_VARIABLES | extra_variables))
    if unsupported:
        raise PromptTemplateError("Unsupported template variable(s): " + ", ".join(unsupported))
    return variables


def render_template(
    template: str,
    values: Mapping[str, object],
    *,
    extra_variables: frozenset[str] = frozenset(),
) -> str:
    """Render only the explicitly supported variables with deterministic values."""

    validate_template(template, extra_variables=extra_variables)

    def substitute(match: re.Match[str]) -> str:
        name = match.group(1)
        value = values.get(name, "")
        return str(value)

    return _VARIABLE.sub(substitute, template)
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `python -m pytest tests/test_prompt_templates.py -q`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/prompt_templates.py tests/test_prompt_templates.py
git commit -m "feat: support record-field variables in prompt templates"
```

---

### Task 5: Dataset run service (SQLAlchemy)

**Files:**
- Create: `backend/app/services/dataset_runs.py`
- Test: `tests/test_dataset_runs.py` (part 1 — service-level)

- [ ] **Step 1: Write the failing service tests**

Create `tests/test_dataset_runs.py` (part 1; Task 6 appends the API tests):

```python
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.core.config import Settings
from app.main import create_app


def _register_ready_dataset(client: TestClient, dataset_id: str = "demo") -> dict[str, object]:
    created = client.post(
        "/api/v1/datasets",
        json={"dataset_id": dataset_id, "version": "1", "revision": "main"},
    )
    assert created.status_code == 201
    version_id = created.json()["id"]
    content = b'{"question":"what is 2+2?","answer":"4"}\n{"question":"what is 3+3?","answer":"6"}\n'
    uploaded = client.post(
        f"/api/v1/datasets/{version_id}/upload",
        json={"filename": "examples.jsonl", "base64_data": __import__("base64").b64encode(content).decode("ascii")},
    )
    assert uploaded.status_code == 200
    assert uploaded.json()["status"] == "ready"
    return uploaded.json()


def _available_endpoint(client: TestClient) -> str:
    endpoints = client.get("/api/v1/model-endpoints").json()
    return next(item["id"] for item in endpoints if item["status"] == "available")
```

- [ ] **Step 2: Implement the service**

Create `backend/app/services/dataset_runs.py`:

```python
from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.benchmarks.registry import BenchmarkSample
from app.db.models import (
    DatasetStatus,
    DatasetVersion,
    EndpointStatus,
    EvaluationRun,
    ModelEndpoint,
    PromptPackage,
    RunStatus,
    SampleAttempt,
    TaskStatus,
    TaskType,
    TaskUnit,
)
from app.services.dataset_records import DatasetRecordError, iter_dataset_records
from app.services.evaluation_runs import (
    RunCreationError,
    _build_sample_messages,
    _capability_compatibility,
    _estimate_sample_tokens,
    _request_body_evidence,
    _split_samples_for_endpoint_budget,
)
from app.services.prompt_templates import PromptTemplateError, render_template
from app.services.scoring import ScoringError, validate_scoring_rule


class DatasetRunError(ValueError):
    pass


DATASET_RUN_BENCHMARK_ID = "dataset-evaluation"
DATASET_RUN_BENCHMARK_VERSION = "1.0.0"
DATASET_RUN_DEFAULT_SAMPLE_LIMIT = 100

_FIXED_TEMPLATE_KEYS = {
    "question": "",
    "choices": "",
    "context": "",
    "image": "",
    "audio": "",
    "video": "",
    "language": "",
    "output_schema": "",
}

_DATASET_RUN_MANIFEST: dict[str, object] = {
    "benchmark_id": DATASET_RUN_BENCHMARK_ID,
    "version": DATASET_RUN_BENCHMARK_VERSION,
    "display_name": "Dataset Evaluation",
    "description": "Records of a registered dataset evaluated through a prompt template.",
    "pack": "user",
    "modalities": ["text"],
    "input_modalities": ["text"],
    "output_modality": "text",
    "required_capabilities": ["text_input"],
    "recommended_capabilities": ["text_input"],
    "capability_categories": ["text_input"],
    "datasets": [],
    "license": "User-registered dataset; license state recorded on the dataset version.",
    "estimated_download_bytes": 0,
    "sample_count": 0,
    "prompt_version": "dataset/1.0.0",
    "scorer_type": "exact_match",
    "scoring": {"type": "exact_match"},
    "languages": ["en"],
    "shard_size": 50,
    "analysis_schema": {"dimensions": ["capability", "language", "difficulty", "modality"], "version": "1.0.0"},
}


def create_dataset_run(
    session: Session,
    *,
    model_endpoint_id: str,
    dataset_version_id: str,
    prompt_package_id: str | None,
    reference_field: str,
    sample_limit: int,
    request_body_override: dict[str, object] | None = None,
    created_by: str | None = None,
    max_concurrency: int | None = None,
    data_root: str,
) -> EvaluationRun:
    endpoint = session.get(ModelEndpoint, model_endpoint_id)
    if endpoint is None:
        raise DatasetRunError("Model endpoint not found.")
    if endpoint.status != EndpointStatus.AVAILABLE.value:
        raise DatasetRunError("Model endpoint must pass a connection test before scheduling a run.")
    dataset = session.get(DatasetVersion, dataset_version_id)
    if dataset is None:
        raise DatasetRunError("Dataset version not found.")
    if dataset.status != DatasetStatus.READY.value or not dataset.prepared_path:
        raise DatasetRunError(
            f"Dataset {dataset.dataset_id} v{dataset.version} is not ready; download and verify it before running."
        )
    prompt_package = session.get(PromptPackage, prompt_package_id) if prompt_package_id else None
    if prompt_package_id and prompt_package is None:
        raise DatasetRunError("Prompt package not found.")
    if not reference_field.strip():
        raise DatasetRunError("A reference field is required.")
    try:
        samples, skipped = _build_dataset_samples(
            prepared_path=dataset.prepared_path,
            data_root=data_root,
            sample_limit=sample_limit,
            reference_field=reference_field.strip(),
            prompt_package=prompt_package,
            dataset_id=dataset.dataset_id,
            dataset_version=dataset.version,
        )
    except DatasetRecordError as error:
        raise DatasetRunError(str(error)) from error
    if not samples:
        raise DatasetRunError(
            f"None of the first {sample_limit} records contain the reference field {reference_field!r}; "
            "check the field name or register a different dataset."
        )
    compatibility = _capability_compatibility(session, endpoint.id, _DATASET_RUN_MANIFEST)
    if compatibility["unsupported"]:
        raise DatasetRunError(
            "Model endpoint is incompatible with dataset evaluation: " + ", ".join(compatibility["unsupported"])
        )
    scoring_rule = dict(prompt_package.scoring_rule) if prompt_package and isinstance(prompt_package.scoring_rule, dict) and prompt_package.scoring_rule else {"type": "exact_match"}
    try:
        validate_scoring_rule(scoring_rule)
    except ScoringError as error:
        raise DatasetRunError(f"Scoring rule is invalid: {error}") from error
    request_body_evidence = _request_body_evidence(
        endpoint=endpoint,
        benchmark_manifest=_DATASET_RUN_MANIFEST,
        suite_snapshot=None,
        request_body_override=request_body_override,
    )
    frozen_datasets = [{
        "dataset_id": dataset.dataset_id,
        "version": dataset.version,
        "revision": dataset.revision,
        "dataset_version_id": dataset.id,
    }]
    snapshot = {
        "benchmark": {"id": DATASET_RUN_BENCHMARK_ID, "version": DATASET_RUN_BENCHMARK_VERSION, "source": "user", "manifest": _DATASET_RUN_MANIFEST},
        "endpoint": {
            "id": endpoint.id,
            "base_url": endpoint.base_url,
            "model_name": endpoint.model_name,
            "protocol_profile": endpoint.protocol_profile,
            "default_request_body": endpoint.default_request_body,
            "timeout_seconds": endpoint.timeout_seconds,
            "custom_headers": endpoint.custom_headers,
            "input_cost_per_million": endpoint.input_cost_per_million,
            "output_cost_per_million": endpoint.output_cost_per_million,
        },
        "datasets": frozen_datasets,
        "dataset_version": {"id": dataset.id, "dataset_id": dataset.dataset_id, "version": dataset.version, "revision": dataset.revision},
        "reference_field": reference_field.strip(),
        "sample_limit": sample_limit,
        "skipped_records": skipped,
        "sample_ids": [sample.sample_id for sample in samples],
        "capability_compatibility": compatibility,
        "prompt_package": (
            {"id": prompt_package.id, "name": prompt_package.name, "version": prompt_package.version,
             "system_message": prompt_package.system_message, "user_template": prompt_package.user_template,
             "few_shot_examples": prompt_package.few_shot_examples, "scoring_rule": prompt_package.scoring_rule}
            if prompt_package else None
        ),
        "request_body_evidence": request_body_evidence,
    }
    run = EvaluationRun(
        model_endpoint_id=endpoint.id,
        prompt_package_id=prompt_package.id if prompt_package else None,
        created_by=created_by,
        max_concurrency=max_concurrency,
        benchmark_id=DATASET_RUN_BENCHMARK_ID,
        benchmark_version=DATASET_RUN_BENCHMARK_VERSION,
        configuration_snapshot=snapshot,
        status=RunStatus.QUEUED.value,
        total_samples=len(samples),
    )
    session.add(run)
    session.flush()
    dataset_task = TaskUnit(
        run_id=run.id,
        task_type=TaskType.DATASET_PREPARATION.value,
        payload={"datasets": frozen_datasets, "prepared_inline": False},
        status=TaskStatus.PENDING.value,
    )
    session.add(dataset_task)
    session.flush()
    benchmark_task = TaskUnit(
        run_id=run.id,
        parent_task_id=dataset_task.id,
        task_type=TaskType.BENCHMARK.value,
        payload={"benchmark_id": DATASET_RUN_BENCHMARK_ID, "benchmark_version": DATASET_RUN_BENCHMARK_VERSION, "planned_samples": len(samples)},
        status=TaskStatus.PENDING.value,
    )
    session.add(benchmark_task)
    session.flush()
    shards = _split_samples_for_endpoint_budget(tuple(samples), _DATASET_RUN_MANIFEST, endpoint)
    for shard_index, shard_samples in enumerate(shards, start=1):
        task = TaskUnit(
            run_id=run.id,
            parent_task_id=benchmark_task.id,
            task_type=TaskType.EVALUATION_SHARD.value,
            payload={
                "sample_ids": [sample.sample_id for sample in shard_samples],
                "estimated_request_count": len(shard_samples),
                "estimated_token_count": sum(_estimate_sample_tokens(sample) for sample in shard_samples),
                "sample_token_estimates": {sample.sample_id: _estimate_sample_tokens(sample) for sample in shard_samples},
                "shard_index": shard_index,
                "shard_count": len(shards),
                "retry_policy": {"max_attempts": 3, "base_delay_seconds": 2, "max_delay_seconds": 60},
            },
            status=TaskStatus.PENDING.value,
        )
        session.add(task)
        session.flush()
        session.add_all(
            [
                SampleAttempt(
                    run_id=run.id,
                    task_id=task.id,
                    sample_id=sample.sample_id,
                    input_snapshot={
                        "messages": _build_sample_messages(sample, None),
                        "modality": "text",
                        "metadata": dict(sample.metadata),
                        "request_body_evidence": request_body_evidence,
                    },
                    reference_snapshot={"type": str(scoring_rule.get("type", "exact_match")), "answer": sample.reference_answer, "scoring": scoring_rule},
                )
                for sample in shard_samples
            ]
        )
    session.commit()
    session.refresh(run)
    return run


def preflight_dataset_run(
    session: Session,
    *,
    model_endpoint_id: str,
    dataset_version_id: str,
    prompt_package_id: str | None,
    reference_field: str,
    sample_limit: int,
    request_body_override: dict[str, object] | None = None,
    data_root: str,
) -> dict[str, object]:
    """Preview dataset-run readiness and cost without persisting anything."""

    issues: list[str] = []
    endpoint = session.get(ModelEndpoint, model_endpoint_id)
    if endpoint is None:
        issues.append("Model endpoint not found.")
    elif endpoint.status != EndpointStatus.AVAILABLE.value:
        issues.append("Model endpoint must pass a connection test before scheduling a run.")
    dataset = session.get(DatasetVersion, dataset_version_id)
    if dataset is None:
        issues.append("Dataset version not found.")
    elif dataset.status != DatasetStatus.READY.value or not dataset.prepared_path:
        issues.append(f"Dataset {dataset.dataset_id} v{dataset.version} is not ready; download and verify it first.")
    if prompt_package_id and session.get(PromptPackage, prompt_package_id) is None:
        issues.append("Prompt package not found.")
    if not reference_field.strip():
        issues.append("A reference field is required.")
    samples: list[BenchmarkSample] = []
    datasets: list[dict[str, object]] = []
    if dataset is not None and dataset.status == DatasetStatus.READY.value and dataset.prepared_path:
        datasets.append({"id": dataset.id, "dataset_id": dataset.dataset_id, "version": dataset.version, "revision": dataset.revision, "status": dataset.status, "will_prepare": False})
        try:
            samples, skipped = _build_dataset_samples(
                prepared_path=dataset.prepared_path,
                data_root=data_root,
                sample_limit=sample_limit,
                reference_field=reference_field.strip(),
                prompt_package=session.get(PromptPackage, prompt_package_id) if prompt_package_id else None,
                dataset_id=dataset.dataset_id,
                dataset_version=dataset.version,
            )
            if not samples:
                issues.append(f"None of the first {sample_limit} records contain the reference field {reference_field!r}.")
        except DatasetRecordError as error:
            issues.append(str(error))
    if endpoint is not None and endpoint.status == EndpointStatus.AVAILABLE.value:
        compatibility = _capability_compatibility(session, endpoint.id, _DATASET_RUN_MANIFEST)
        if compatibility["unsupported"]:
            issues.append("Model endpoint is incompatible with dataset evaluation: " + ", ".join(compatibility["unsupported"]))
    else:
        compatibility = {"required": ["text_input"], "unsupported": [], "unverified": []}
    estimated_input_tokens = sum(_estimate_sample_tokens(sample) for sample in samples)
    estimated_output_tokens = len(samples) * 64
    estimated_cost = (
        ((estimated_input_tokens * endpoint.input_cost_per_million) + (estimated_output_tokens * endpoint.output_cost_per_million)) / 1_000_000
        if endpoint is not None and endpoint.input_cost_per_million is not None and endpoint.output_cost_per_million is not None
        else None
    )
    return {
        "can_queue": not issues,
        "issues": issues,
        "sample_count": len(samples),
        "estimated_requests": len(samples),
        "estimated_input_tokens": estimated_input_tokens,
        "estimated_output_tokens": estimated_output_tokens,
        "estimated_cost": estimated_cost,
        "currency": endpoint.currency if endpoint is not None else None,
        "compatibility": compatibility,
        "datasets": datasets,
        "request_body_evidence": (
            _request_body_evidence(endpoint=endpoint, benchmark_manifest=_DATASET_RUN_MANIFEST, suite_snapshot=None, request_body_override=request_body_override)
            if endpoint is not None else None
        ),
    }


def _build_dataset_samples(
    *,
    prepared_path: str,
    data_root: str,
    sample_limit: int,
    reference_field: str,
    prompt_package: PromptPackage | None,
    dataset_id: str,
    dataset_version: str,
) -> tuple[list[BenchmarkSample], int]:
    """Materialize up to ``sample_limit`` usable records as benchmark samples.

    Records missing the reference field, or that render no prompt, are counted
    as skipped.  The prompt is fully rendered here (template applied with the
    record fields), so callers must pass ``None`` as the prompt package when
    building attempt messages to avoid double rendering.
    """

    samples: list[BenchmarkSample] = []
    skipped = 0
    for entry in iter_dataset_records(prepared_path, data_root, limit=sample_limit):
        fields = {str(key): value for key, value in entry["fields"].items()}
        reference = fields.get(reference_field)
        prompt = _render_record_prompt(fields, prompt_package)
        if reference is None or prompt is None:
            skipped += 1
            continue
        samples.append(
            BenchmarkSample(
                sample_id=f"{dataset_id}:{dataset_version}:{entry['source']}#{entry['record_number']}",
                prompt=prompt,
                reference_answer=str(reference),
                metadata={"source": entry["source"], "record_number": str(entry["record_number"]), "dataset": dataset_id},
                messages=({"role": "user", "content": prompt},),
            )
        )
    return samples, skipped


def _render_record_prompt(fields: dict[str, object], prompt_package: PromptPackage | None) -> str | None:
    if prompt_package is not None:
        try:
            return render_template(
                prompt_package.user_template,
                {**_FIXED_TEMPLATE_KEYS, **fields},
                extra_variables=frozenset(fields),
            )
        except PromptTemplateError as error:
            raise DatasetRunError(str(error)) from error
    for value in fields.values():
        if isinstance(value, str) and value:
            return value
    return None
```

Note: `_build_dataset_samples` and `_render_record_prompt` are intentionally module-level so the Mongo variant in Task 6 reuses them.

- [ ] **Step 3: Run a smoke import check**

Run: `python -m pytest tests/test_dataset_runs.py -q`
Expected: PASS (the file currently only defines helpers; no test functions yet — Task 6 adds the API tests)

- [ ] **Step 4: Commit**

```bash
git add backend/app/services/dataset_runs.py tests/test_dataset_runs.py
git commit -m "feat: add dataset evaluation run service"
```

---

### Task 6: Dataset run API endpoints (SQL + Mongo)

**Files:**
- Modify: `backend/app/api/evaluation_runs.py:19-36` (imports), `:53-105` (models), after `:291` (endpoints)
- Modify: `backend/app/services/mongo_run_executor.py` (imports + two functions)
- Test: `tests/test_dataset_runs.py` (append)

- [ ] **Step 1: Write the failing API tests**

Append to `tests/test_dataset_runs.py`:

```python
def _prompt_package(client: TestClient) -> str:
    created = client.post(
        "/api/v1/prompt-packages",
        json={"name": "record-template", "version": "1.0.0", "prompt_type": "user_custom", "user_template": "Q: {{question}}\nA:", "scoring_rule": {"type": "exact_match"}},
    )
    assert created.status_code == 201
    return created.json()["id"]


def test_dataset_run_end_to_end(tmp_path: Path) -> None:
    app = create_app(Settings.local_development(database_url=f"sqlite:///{tmp_path / 'db.sqlite'}", data_root=str(tmp_path / "data")))
    with TestClient(app) as client:
        dataset = _register_ready_dataset(client)
        endpoint_id = _available_endpoint(client)
        package_id = _prompt_package(client)
        created = client.post(
            "/api/v1/evaluation-runs/dataset",
            json={
                "model_endpoint_id": endpoint_id,
                "dataset_version_id": dataset["id"],
                "prompt_package_id": package_id,
                "reference_field": "answer",
                "sample_limit": 10,
            },
        )
        assert created.status_code == 201
        run = created.json()
        assert run["benchmark_id"] == "dataset-evaluation"
        assert run["total_samples"] == 2
        assert run["configuration_snapshot"]["reference_field"] == "answer"
        executed = client.post(f"/api/v1/evaluation-runs/{run['id']}/execute")
        assert executed.status_code == 200
        attempts = client.get(f"/api/v1/evaluation-runs/{run['id']}/attempts").json()
        assert len(attempts) == 2
        contents = {attempt["input_snapshot"]["messages"][0]["content"] for attempt in attempts}
        assert contents == {"Q: what is 2+2?\nA:", "Q: what is 3+3?\nA:"}
        assert {attempt["reference_snapshot"]["answer"] for attempt in attempts} == {"4", "6"}


def test_dataset_run_preflight_and_validation_errors(tmp_path: Path) -> None:
    app = create_app(Settings.local_development(database_url=f"sqlite:///{tmp_path / 'db.sqlite'}", data_root=str(tmp_path / "data")))
    with TestClient(app) as client:
        dataset = _register_ready_dataset(client)
        endpoint_id = _available_endpoint(client)
        preflight = client.post(
            "/api/v1/evaluation-runs/dataset/preflight",
            json={"model_endpoint_id": endpoint_id, "dataset_version_id": dataset["id"], "reference_field": "answer", "sample_limit": 10},
        )
        assert preflight.status_code == 200
        assert preflight.json()["can_queue"] is True
        assert preflight.json()["sample_count"] == 2
        bad_field = client.post(
            "/api/v1/evaluation-runs/dataset",
            json={"model_endpoint_id": endpoint_id, "dataset_version_id": dataset["id"], "reference_field": "nope", "sample_limit": 10},
        )
        assert bad_field.status_code == 409
        assert "reference field" in bad_field.json()["detail"]
        not_ready = client.post(
            "/api/v1/evaluation-runs/dataset",
            json={"model_endpoint_id": endpoint_id, "dataset_version_id": "missing", "reference_field": "answer", "sample_limit": 10},
        )
        assert not_ready.status_code == 404
        missing_field = client.post(
            "/api/v1/evaluation-runs/dataset",
            json={"model_endpoint_id": endpoint_id, "dataset_version_id": dataset["id"], "reference_field": "", "sample_limit": 10},
        )
        assert missing_field.status_code == 422
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `python -m pytest tests/test_dataset_runs.py -q`
Expected: FAIL — 404 on `POST /api/v1/evaluation-runs/dataset` (route does not exist)

- [ ] **Step 3: Add the API models and endpoints**

In `backend/app/api/evaluation_runs.py`:

1. Add to the imports (after line 20):

```python
from app.services.dataset_runs import DatasetRunError, create_dataset_run, preflight_dataset_run
```

2. Add to the Mongo import block (lines 26-36):

```python
    create_mongo_dataset_run,
    preflight_mongo_dataset_run,
```

3. Add the request model after `CustomMultimodalRunCreate` (line 69):

```python
class DatasetRunCreate(BaseModel):
    model_endpoint_id: str
    dataset_version_id: str
    prompt_package_id: str | None = None
    reference_field: Annotated[str, Field(min_length=1, max_length=255)]
    sample_limit: Annotated[int, Field(ge=1, le=10_000)] = 100
    max_concurrency: Annotated[int | None, Field(ge=1, le=1000)] = None
    request_body_override: dict[str, Any] = Field(default_factory=dict)
```

4. Add the two endpoints after `create_custom_run` (after line 291):

```python
@router.post("/dataset", response_model=EvaluationRunResponse, status_code=status.HTTP_201_CREATED)
def create_dataset_evaluation_run(
    payload: DatasetRunCreate,
    request: Request,
    session: SessionDependency,
) -> EvaluationRun | dict[str, Any]:
    store = get_document_store(request)
    if store is not None:
        try:
            return create_mongo_dataset_run(
                store,
                data_root=request.app.state.settings.data_root,
                model_endpoint_id=payload.model_endpoint_id,
                dataset_version_id=payload.dataset_version_id,
                prompt_package_id=payload.prompt_package_id,
                reference_field=payload.reference_field,
                sample_limit=payload.sample_limit,
                request_body_override=payload.request_body_override,
                created_by=getattr(request.state, "actor_id", None),
                max_concurrency=payload.max_concurrency,
            )
        except MongoRunExecutionError as error:
            status_code = status.HTTP_404_NOT_FOUND if str(error) in {"Model endpoint not found.", "Dataset version not found.", "Prompt package not found."} else status.HTTP_409_CONFLICT
            raise HTTPException(status_code=status_code, detail=str(error)) from error
    assert session is not None
    try:
        return create_dataset_run(
            session,
            data_root=request.app.state.settings.data_root,
            model_endpoint_id=payload.model_endpoint_id,
            dataset_version_id=payload.dataset_version_id,
            prompt_package_id=payload.prompt_package_id,
            reference_field=payload.reference_field,
            sample_limit=payload.sample_limit,
            request_body_override=payload.request_body_override,
            created_by=getattr(request.state, "actor_id", None),
            max_concurrency=payload.max_concurrency,
        )
    except DatasetRunError as error:
        status_code = status.HTTP_404_NOT_FOUND if str(error) in {"Model endpoint not found.", "Dataset version not found.", "Prompt package not found."} else status.HTTP_409_CONFLICT
        raise HTTPException(status_code=status_code, detail=str(error)) from error


@router.post("/dataset/preflight", response_model=EvaluationRunPreflightResponse)
def preflight_dataset_evaluation_run(
    payload: DatasetRunCreate,
    request: Request,
    session: SessionDependency,
) -> dict[str, object]:
    store = get_document_store(request)
    if store is not None:
        return preflight_mongo_dataset_run(
            store,
            data_root=request.app.state.settings.data_root,
            model_endpoint_id=payload.model_endpoint_id,
            dataset_version_id=payload.dataset_version_id,
            prompt_package_id=payload.prompt_package_id,
            reference_field=payload.reference_field,
            sample_limit=payload.sample_limit,
            request_body_override=payload.request_body_override,
        )
    assert session is not None
    return preflight_dataset_run(
        session,
        data_root=request.app.state.settings.data_root,
        model_endpoint_id=payload.model_endpoint_id,
        dataset_version_id=payload.dataset_version_id,
        prompt_package_id=payload.prompt_package_id,
        reference_field=payload.reference_field,
        sample_limit=payload.sample_limit,
        request_body_override=payload.request_body_override,
    )
```

- [ ] **Step 4: Add the Mongo variants**

In `backend/app/services/mongo_run_executor.py`:

1. Add to the imports:

```python
from app.benchmarks.registry import BenchmarkSample
from app.services.dataset_runs import (
    DATASET_RUN_BENCHMARK_ID,
    DATASET_RUN_BENCHMARK_VERSION,
    DatasetRunError,
    _build_dataset_samples,
)
from app.services.dataset_records import DatasetRecordError
```

2. Add `_mongo_dataset_run_preflight` helpers and the two public functions (place them after `create_mongo_benchmark_run`, i.e. after line 330):

```python
def create_mongo_dataset_run(
    store: MongoDocumentStore,
    *,
    data_root: str,
    model_endpoint_id: str,
    dataset_version_id: str,
    prompt_package_id: str | None,
    reference_field: str,
    sample_limit: int,
    request_body_override: dict[str, object] | None = None,
    created_by: str | None = None,
    max_concurrency: int | None = None,
) -> dict[str, Any]:
    endpoint = store.get_document("model_endpoints", model_endpoint_id)
    if endpoint is None:
        raise MongoRunExecutionError("Model endpoint not found.")
    if endpoint.get("status") != "available":
        raise MongoRunExecutionError("Model endpoint must pass a connection test before scheduling a run.")
    dataset = store.get_document("dataset_versions", dataset_version_id)
    if dataset is None:
        raise MongoRunExecutionError("Dataset version not found.")
    if dataset.get("status") != "ready" or not dataset.get("prepared_path"):
        raise MongoRunExecutionError(f"Dataset {dataset['dataset_id']} v{dataset['version']} is not ready; download and verify it before running.")
    prompt_package = store.get_document("prompt_packages", prompt_package_id) if prompt_package_id else None
    if prompt_package_id and prompt_package is None:
        raise MongoRunExecutionError("Prompt package not found.")
    if not reference_field.strip():
        raise MongoRunExecutionError("A reference field is required.")
    try:
        samples, skipped = _build_dataset_samples(
            prepared_path=dataset["prepared_path"],
            data_root=data_root,
            sample_limit=sample_limit,
            reference_field=reference_field.strip(),
            prompt_package=_proxy(prompt_package) if prompt_package else None,
            dataset_id=dataset["dataset_id"],
            dataset_version=dataset["version"],
        )
    except (DatasetRecordError, DatasetRunError) as error:
        raise MongoRunExecutionError(str(error)) from error
    if not samples:
        raise MongoRunExecutionError(
            f"None of the first {sample_limit} records contain the reference field {reference_field!r}; "
            "check the field name or register a different dataset."
        )
    compatibility = _capability_compatibility(store, model_endpoint_id, _dataset_run_manifest())
    if compatibility["unsupported"]:
        raise MongoRunExecutionError(
            "Model endpoint is incompatible with dataset evaluation: " + ", ".join(compatibility["unsupported"])
        )
    scoring_rule = dict(prompt_package.get("scoring_rule")) if prompt_package and isinstance(prompt_package.get("scoring_rule"), dict) and prompt_package.get("scoring_rule") else {"type": "exact_match"}
    try:
        validate_scoring_rule(scoring_rule)
    except ScoringError as error:
        raise MongoRunExecutionError(f"Scoring rule is invalid: {error}") from error
    request_body_evidence = _mongo_request_body_evidence(
        endpoint=endpoint,
        benchmark_manifest=_dataset_run_manifest(),
        suite_snapshot=None,
        request_body_override=request_body_override,
    )
    frozen_datasets = [{
        "dataset_id": dataset["dataset_id"],
        "version": dataset["version"],
        "revision": dataset.get("revision", "default"),
        "dataset_version_id": dataset["id"],
    }]
    now = _utc_now()
    snapshot = {
        "benchmark": {"id": DATASET_RUN_BENCHMARK_ID, "version": DATASET_RUN_BENCHMARK_VERSION, "source": "user", "manifest": _dataset_run_manifest()},
        "endpoint": {
            "id": endpoint["id"],
            "base_url": endpoint["base_url"],
            "model_name": endpoint["model_name"],
            "protocol_profile": endpoint.get("protocol_profile", "openai_chat_completions"),
            "default_request_body": endpoint.get("default_request_body", {}),
            "timeout_seconds": endpoint.get("timeout_seconds", 60),
            "custom_headers": endpoint.get("custom_headers", {}),
            "input_cost_per_million": endpoint.get("input_cost_per_million"),
            "output_cost_per_million": endpoint.get("output_cost_per_million"),
        },
        "datasets": frozen_datasets,
        "dataset_version": {"id": dataset["id"], "dataset_id": dataset["dataset_id"], "version": dataset["version"], "revision": dataset.get("revision", "default")},
        "reference_field": reference_field.strip(),
        "sample_limit": sample_limit,
        "skipped_records": skipped,
        "sample_ids": [sample.sample_id for sample in samples],
        "capability_compatibility": compatibility,
        "prompt_package": (
            {"id": prompt_package["id"], "name": prompt_package["name"], "version": prompt_package["version"],
             "system_message": prompt_package.get("system_message"), "user_template": prompt_package["user_template"],
             "few_shot_examples": prompt_package.get("few_shot_examples", []), "scoring_rule": prompt_package.get("scoring_rule")}
            if prompt_package else None
        ),
        "request_body_evidence": request_body_evidence,
    }
    run = store.insert_document(
        "evaluation_runs",
        {
            "model_endpoint_id": model_endpoint_id,
            "prompt_package_id": prompt_package_id,
            "suite_id": None,
            "created_by": created_by,
            "max_concurrency": max_concurrency,
            "benchmark_id": DATASET_RUN_BENCHMARK_ID,
            "benchmark_version": DATASET_RUN_BENCHMARK_VERSION,
            "configuration_snapshot": snapshot,
            "status": "queued",
            "total_samples": len(samples),
            "completed_samples": 0,
            "successful_samples": 0,
            "failed_samples": 0,
            "created_at": now,
            "started_at": None,
            "completed_at": None,
            "archived_at": None,
        },
    )
    dataset_task = store.insert_document(
        "task_units",
        {
            "run_id": run["id"],
            "parent_task_id": None,
            "task_type": "dataset_preparation",
            "payload": {"datasets": frozen_datasets, "prepared_inline": False},
            "status": "pending",
            "priority": 0,
            "attempt_count": 0,
            "leased_by": None,
            "lease_token": None,
            "lease_expires_at": None,
            "next_retry_at": None,
            "heartbeat_at": None,
            "created_at": now,
            "updated_at": now,
        },
    )
    benchmark_task = store.insert_document(
        "task_units",
        {
            "run_id": run["id"],
            "parent_task_id": dataset_task["id"],
            "task_type": "benchmark",
            "payload": {"benchmark_id": DATASET_RUN_BENCHMARK_ID, "benchmark_version": DATASET_RUN_BENCHMARK_VERSION, "planned_samples": len(samples)},
            "status": "pending",
            "priority": 0,
            "attempt_count": 0,
            "leased_by": None,
            "lease_token": None,
            "lease_expires_at": None,
            "next_retry_at": None,
            "heartbeat_at": None,
            "created_at": now,
            "updated_at": now,
        },
    )
    try:
        shards = _split_samples_for_endpoint_budget(tuple(samples), _dataset_run_manifest(), endpoint)
    except RunCreationError as error:
        raise MongoRunExecutionError(str(error)) from error
    for shard_index, shard_samples in enumerate(shards, start=1):
        task = store.insert_document(
            "task_units",
            {
                "run_id": run["id"],
                "parent_task_id": benchmark_task["id"],
                "task_type": "evaluation_shard",
                "payload": {
                    "sample_ids": [sample.sample_id for sample in shard_samples],
                    "estimated_request_count": len(shard_samples),
                    "estimated_token_count": sum(_estimate_sample_tokens(sample) for sample in shard_samples),
                    "sample_token_estimates": {sample.sample_id: _estimate_sample_tokens(sample) for sample in shard_samples},
                    "shard_index": shard_index,
                    "shard_count": len(shards),
                    "retry_policy": {"max_attempts": 3, "base_delay_seconds": 2, "max_delay_seconds": 60},
                },
                "status": "pending",
                "priority": 0,
                "attempt_count": 0,
                "leased_by": None,
                "lease_token": None,
                "lease_expires_at": None,
                "next_retry_at": None,
                "heartbeat_at": None,
                "created_at": now,
                "updated_at": now,
            },
        )
        for sample in shard_samples:
            store.insert_document(
                "sample_attempts",
                {
                    "run_id": run["id"],
                    "task_id": task["id"],
                    "sample_id": sample.sample_id,
                    "attempt_number": 1,
                    "input_snapshot": {"messages": _build_sample_messages(sample, None), "modality": "text", "metadata": dict(sample.metadata), "request_body_evidence": request_body_evidence},
                    "reference_snapshot": {"type": str(scoring_rule.get("type", "exact_match")), "answer": sample.reference_answer, "scoring": scoring_rule},
                    "request_snapshot": None,
                    "raw_response": None,
                    "parsed_prediction": None,
                    "score": None,
                    "latency_ms": None,
                    "input_tokens": None,
                    "output_tokens": None,
                    "estimated_cost": None,
                    "error_type": None,
                    "error_message": None,
                    "status": "pending",
                    "created_at": now,
                    "started_at": None,
                    "completed_at": None,
                },
            )
    return run


def preflight_mongo_dataset_run(
    store: MongoDocumentStore,
    *,
    data_root: str,
    model_endpoint_id: str,
    dataset_version_id: str,
    prompt_package_id: str | None,
    reference_field: str,
    sample_limit: int,
    request_body_override: dict[str, object] | None = None,
) -> dict[str, object]:
    issues: list[str] = []
    endpoint = store.get_document("model_endpoints", model_endpoint_id)
    if endpoint is None:
        issues.append("Model endpoint not found.")
    elif endpoint.get("status") != "available":
        issues.append("Model endpoint must pass a connection test before scheduling a run.")
    dataset = store.get_document("dataset_versions", dataset_version_id)
    if dataset is None:
        issues.append("Dataset version not found.")
    elif dataset.get("status") != "ready" or not dataset.get("prepared_path"):
        issues.append(f"Dataset {dataset['dataset_id']} v{dataset['version']} is not ready; download and verify it first.")
    if prompt_package_id and store.get_document("prompt_packages", prompt_package_id) is None:
        issues.append("Prompt package not found.")
    if not reference_field.strip():
        issues.append("A reference field is required.")
    samples: list[BenchmarkSample] = []
    datasets: list[dict[str, object]] = []
    if dataset is not None and dataset.get("status") == "ready" and dataset.get("prepared_path"):
        datasets.append({"id": dataset["id"], "dataset_id": dataset["dataset_id"], "version": dataset["version"], "revision": dataset.get("revision", "default"), "status": dataset["status"], "will_prepare": False})
        try:
            samples, _skipped = _build_dataset_samples(
                prepared_path=dataset["prepared_path"],
                data_root=data_root,
                sample_limit=sample_limit,
                reference_field=reference_field.strip(),
                prompt_package=_proxy(store.get_document("prompt_packages", prompt_package_id)) if prompt_package_id else None,
                dataset_id=dataset["dataset_id"],
                dataset_version=dataset["version"],
            )
            if not samples:
                issues.append(f"None of the first {sample_limit} records contain the reference field {reference_field!r}.")
        except (DatasetRecordError, DatasetRunError) as error:
            issues.append(str(error))
    if endpoint is not None and endpoint.get("status") == "available":
        compatibility = _capability_compatibility(store, model_endpoint_id, _dataset_run_manifest())
        if compatibility["unsupported"]:
            issues.append("Model endpoint is incompatible with dataset evaluation: " + ", ".join(compatibility["unsupported"]))
    else:
        compatibility = {"required": ["text_input"], "unsupported": [], "unverified": []}
    estimated_input_tokens = sum(_estimate_sample_tokens(sample) for sample in samples)
    estimated_output_tokens = len(samples) * 64
    estimated_cost = (
        ((estimated_input_tokens * endpoint.get("input_cost_per_million")) + (estimated_output_tokens * endpoint.get("output_cost_per_million"))) / 1_000_000
        if endpoint is not None and endpoint.get("input_cost_per_million") is not None and endpoint.get("output_cost_per_million") is not None
        else None
    )
    return {
        "can_queue": not issues,
        "issues": issues,
        "sample_count": len(samples),
        "estimated_requests": len(samples),
        "estimated_input_tokens": estimated_input_tokens,
        "estimated_output_tokens": estimated_output_tokens,
        "estimated_cost": estimated_cost,
        "currency": endpoint.get("currency") if endpoint is not None else None,
        "compatibility": compatibility,
        "datasets": datasets,
        "request_body_evidence": (
            _mongo_request_body_evidence(endpoint=endpoint, benchmark_manifest=_dataset_run_manifest(), suite_snapshot=None, request_body_override=request_body_override)
            if endpoint is not None else None
        ),
    }


def _dataset_run_manifest() -> dict[str, object]:
    from app.services.dataset_runs import _DATASET_RUN_MANIFEST

    return dict(_DATASET_RUN_MANIFEST)
```

- [ ] **Step 5: Run the tests to verify they pass**

Run: `python -m pytest tests/test_dataset_runs.py -q`
Expected: PASS

- [ ] **Step 6: Run the neighboring suites to catch regressions**

Run: `python -m pytest tests/test_evaluation_runs.py tests/test_custom_multimodal_runs.py tests/test_datasets.py -q`
Expected: PASS

- [ ] **Step 7: Commit**

```bash
git add backend/app/api/evaluation_runs.py backend/app/services/mongo_run_executor.py tests/test_dataset_runs.py
git commit -m "feat: add dataset evaluation run API endpoints"
```

---

### Task 7: Frontend dataset evaluation form

**Files:**
- Modify: `frontend/src/api.ts` (after line 271)
- Modify: `frontend/src/i18n/catalog.ts` (8 new keys × 8 locales)
- Modify: `frontend/src/App.tsx` (runs view, around line 719)
- Test: `frontend/src/dataset-run.test.tsx`

- [ ] **Step 1: Write the failing API-client test**

Append to `frontend/src/api.test.ts` (follow its existing mocking style):

```ts
it("creates a dataset evaluation run", async () => {
  const body = { model_endpoint_id: "ep-1", dataset_version_id: "ds-1", reference_field: "answer", sample_limit: 100 };
  fetchMock.mockResponseOnce(JSON.stringify({ id: "run-1", benchmark_id: "dataset-evaluation", total_samples: 2 }), { status: 201 });
  const run = await api.createDatasetRun(body);
  expect(run.id).toBe("run-1");
  const [url, init] = fetchMock.mock.calls[0];
  expect(String(url)).toContain("/evaluation-runs/dataset");
  expect(JSON.parse(String(init?.body))).toEqual(body);
});
```

(If `api.test.ts` does not use `fetch-mock`, mirror whatever fetch-stubbing helper it already uses.)

- [ ] **Step 2: Add the client functions**

In `frontend/src/api.ts`, after the `createCustomMultimodalRun` line (271), add:

```ts
  createDatasetRun: (body: Record<string, unknown>) => request<EvaluationRun>("/evaluation-runs/dataset", { method: "POST", body: JSON.stringify(body) }),
  validateDatasetRun: (body: Record<string, unknown>) => request<RunPreflight>("/evaluation-runs/dataset/preflight", { method: "POST", body: JSON.stringify(body) }),
```

- [ ] **Step 3: Add the catalog keys**

In `frontend/src/i18n/catalog.ts`, add these 8 keys to the `en` catalog and every other locale catalog (`zh-CN`, `fr`, `de`, `ru`, `ja`, `ko`, `ms`). The `TranslationCatalog` type requires every locale to define every key; translate the `en` strings faithfully into the other 7 locales, matching the existing style of each catalog.

```ts
  "datasetRun.title": "Dataset evaluation",
  "datasetRun.dataset": "Dataset",
  "datasetRun.promptPackage": "Prompt package (optional)",
  "datasetRun.referenceField": "Reference field",
  "datasetRun.referenceFieldHint": "Record field holding the expected answer",
  "datasetRun.sampleLimit": "Sample limit",
  "datasetRun.queue": "Queue dataset run",
  "datasetRun.queued": "Dataset evaluation run queued.",
```

- [ ] **Step 4: Add the run form and handler**

In `frontend/src/App.tsx`:

1. Add form state next to the other form states (near `initialSuite`, line 65):

```ts
const initialDatasetRun = { dataset_version_id: "", prompt_package_id: "", reference_field: "", sample_limit: "100", model_endpoint_id: "" };
```

2. Add state near the other `useState` calls (line ~178):

```ts
  const [datasetRunForm, setDatasetRunForm] = useState(initialDatasetRun);
```

3. Add the queue handler near `createSuite`:

```ts
  async function queueDatasetRun() {
    setBusy("dataset-run");
    try {
      await api.createDatasetRun({
        model_endpoint_id: datasetRunForm.model_endpoint_id,
        dataset_version_id: datasetRunForm.dataset_version_id,
        prompt_package_id: datasetRunForm.prompt_package_id || null,
        reference_field: datasetRunForm.reference_field,
        sample_limit: Number(datasetRunForm.sample_limit) || 100,
      });
      showNotice(translateStaticTemplate(locale, "datasetRun.queued"));
      setDatasetRunForm(initialDatasetRun);
      await refresh();
    } catch (error) {
      showNotice(error instanceof Error ? error.message : "Dataset run failed.");
    } finally {
      setBusy(null);
    }
  }
```

4. In the runs view (the section starting around line 719 that renders the "Benchmark pack" select), add a second panel. `App.tsx` does not currently load prompt packages, so first add that state and loading:

```ts
  const [promptPackages, setPromptPackages] = useState<PromptPackage[]>([]);
```

(import `type PromptPackage` from `./api`), and inside the existing `refresh()` function add:

```ts
      setPromptPackages(await api.listPromptPackages());
```

Then add the panel:

```tsx
      <article className="panel"><h2>{translateStaticTemplate(locale, "datasetRun.title")}</h2><form onSubmit={(event) => { event.preventDefault(); void queueDatasetRun(); }} className="form"><label>{translateStaticTemplate(locale, "datasetRun.dataset")}<select required value={datasetRunForm.dataset_version_id} onChange={(event) => setDatasetRunForm({ ...datasetRunForm, dataset_version_id: event.target.value })}>{datasets.filter((dataset) => dataset.status === "ready").map((dataset) => <option data-i18n-preserve key={dataset.id} value={dataset.id}>{dataset.dataset_id} v{dataset.version}</option>)}</select>{datasets.some((dataset) => dataset.status !== "ready") && <p className="muted">{translateStaticTemplate(locale, "datasetRun.referenceFieldHint")}</p>}</label><label>{translateStaticTemplate(locale, "datasetRun.promptPackage")}<select value={datasetRunForm.prompt_package_id} onChange={(event) => setDatasetRunForm({ ...datasetRunForm, prompt_package_id: event.target.value })}><option value="">—</option>{promptPackages.map((packageItem) => <option data-i18n-preserve key={packageItem.id} value={packageItem.id}>{packageItem.name} v{packageItem.version}</option>)}</select></label><label>{translateStaticTemplate(locale, "datasetRun.referenceField")}<input required value={datasetRunForm.reference_field} onChange={(event) => setDatasetRunForm({ ...datasetRunForm, reference_field: event.target.value })} placeholder={translateStaticTemplate(locale, "datasetRun.referenceFieldHint")} /></label><label>{translateStaticTemplate(locale, "datasetRun.sampleLimit")}<input required type="number" min={1} value={datasetRunForm.sample_limit} onChange={(event) => setDatasetRunForm({ ...datasetRunForm, sample_limit: event.target.value })} /></label><label>Endpoint<select required value={datasetRunForm.model_endpoint_id} onChange={(event) => setDatasetRunForm({ ...datasetRunForm, model_endpoint_id: event.target.value })}>{endpoints.filter((endpoint) => endpoint.status === "available").map((endpoint) => <option data-i18n-preserve key={endpoint.id} value={endpoint.id}>{endpoint.display_name}</option>)}</select></label><button className="primary" disabled={busy === "dataset-run"}>{translateStaticTemplate(locale, "datasetRun.queue")}</button></form></article>
```

- [ ] **Step 5: Add the form behavior test**

Create `frontend/src/dataset-run.test.tsx` mirroring the mocking style of `frontend/src/dataset-registration.test.tsx` (mock `./api` with `vi.mock`, render `<App />`, and drive the form):

```tsx
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import App from "./App";

vi.mock("./api", () => ({
  api: {
    createDatasetRun: vi.fn().mockResolvedValue({ id: "run-1", benchmark_id: "dataset-evaluation", total_samples: 1, status: "queued" }),
    listDatasets: vi.fn().mockResolvedValue([{ id: "ds-1", dataset_id: "demo", version: "1", status: "ready" }]),
    listEndpoints: vi.fn().mockResolvedValue([]),
    listPromptPackages: vi.fn().mockResolvedValue([]),
    listRuns: vi.fn().mockResolvedValue([]),
  },
}));

describe("dataset evaluation run form", () => {
  it("queues a run with the chosen dataset and reference field", async () => {
    render(<App />);
    await userEvent.click(screen.getByText("Runs"));
    await userEvent.selectOptions(screen.getByLabelText("Dataset"), "ds-1");
    await userEvent.type(screen.getByLabelText("Reference field"), "answer");
    await userEvent.click(screen.getByRole("button", { name: "Queue dataset run" }));
    await waitFor(() => expect(vi.mocked(api.createDatasetRun)).toHaveBeenCalledWith(expect.objectContaining({ dataset_version_id: "ds-1", reference_field: "answer" })));
  });
});
```

If App's exact nav label differs (the app is localized — check the "Runs" navigation label in `frontend/src/i18n/catalog.ts` and the shell test helpers in `frontend/src/app-shell.test.tsx`), use the same label/helpers those tests use.

- [ ] **Step 6: Run the frontend checks**

Run: `node --check frontend/src/api.ts` and `node --check frontend/src/App.tsx` and `node --check frontend/src/dataset-run.test.tsx`
Expected: no output (syntax OK)

Run: `npm test -- --run` (from `frontend/`)
Expected: all tests pass

Run: `npx tsc -b` (from `frontend/`)
Expected: no type errors

- [ ] **Step 7: Commit**

```bash
git add frontend/src/api.ts frontend/src/i18n/catalog.ts frontend/src/App.tsx frontend/src/api.test.ts frontend/src/dataset-run.test.tsx
git commit -m "feat: add dataset evaluation run form to the workspace"
```

---

### Task 8: Workflow documentation

**Files:**
- Create: `docs/evaluation-workflow.md`
- Modify: `README.md` (pointer section after "Database operations", line 47)

- [ ] **Step 1: Write the guide**

Create `docs/evaluation-workflow.md` covering, in order, with the `hf://lhoestq/demo1/data/train.csv` example:

1. **Register a model endpoint** — models view, connection test, `available` status.
2. **Register a dataset version** — `dataset_id`, `version`, `revision` (e.g. `main`), source `hf://lhoestq/demo1/data/train.csv` (explain: `hf://` means a Hugging Face **dataset** repo; no `resolve/` segment; revision selects the branch/tag/commit).
3. **Accept the license** (if `license_required`) and **Download and verify** — status flow `not_downloaded` → `downloading` → `verifying` → `preparing` → `ready`; checksum recorded on first verified download; optional upload action for local files.
4. **(Optional) Create a prompt package** — template with `{{field}}` placeholders (record fields), e.g. `Rate this review: {{review}}\nReturn only the star count.`.
5. **Queue a dataset evaluation run** — dataset, prompt package (optional), reference field (e.g. `star`), sample limit, endpoint; preflight shows record count and cost.
6. **Watch and inspect** — runs view status, sample attempts with rendered prompts and scores, report generation.
7. **Troubleshooting** table:
   - `401 Unauthorized` / `credential_required` → private or gated repository; configure a credential binding (`LLE_DATASET_CREDENTIAL_BINDINGS_JSON` + token env var), or fix the owner/repository name.
   - `404` on download → repository or file does not exist; check name and revision.
   - Checksum mismatch → corrupted download; use Validate or clear cache and re-download.
   - `not supported for evaluation runs` → use JSONL/JSON/CSV/TSV/TXT (Parquet/zip are cached but not runnable).
   - No usable records → reference field name does not match any record field; check the dataset preview.

- [ ] **Step 2: Add the README pointer**

In `README.md`, after the "Database operations" section (after line 47), add:

```markdown
## Evaluation workflow

A step-by-step guide from dataset registration through scored evaluation runs
(including Hugging Face `hf://` sources) lives in
[docs/evaluation-workflow.md](docs/evaluation-workflow.md).
```

- [ ] **Step 3: Verify links and content**

Run: `git diff --check`
Expected: clean

- [ ] **Step 4: Commit**

```bash
git add docs/evaluation-workflow.md README.md
git commit -m "docs: add end-to-end evaluation workflow guide"
```

(`docs/` is git-ignored; tracked docs exist, so use `git add -f docs/evaluation-workflow.md` if plain `git add` refuses.)

---

### Task 9: Full verification and manual end-to-end check

**Files:** none (verification only)

- [ ] **Step 1: Run the full backend suite**

Run: `python -m pytest tests/ -q`
Expected: all tests pass

- [ ] **Step 2: Run the full frontend checks**

Run (from `frontend/`): `npm test -- --run` then `npx tsc -b`
Expected: all tests pass, no type errors

- [ ] **Step 3: Live download check against Hugging Face**

Start the app (`uvicorn app.main:app --app-dir backend` with `LLE_ALLOW_INSECURE_LOCAL_AUTH=true`), register `hf://lhoestq/demo1/data/train.csv` (revision `main`), trigger download, and confirm status `ready` with a recorded `checksum` and `size_bytes`. If the machine has no network access to `huggingface.co`, record that the automated suite already covers resolution and redirect handling and note the manual check as pending.

- [ ] **Step 4: Review the branch diff**

Run: `git diff --check master...HEAD` and `git status --short`
Expected: clean diff; only the planned files changed

- [ ] **Step 5: Commit any remaining verification fixes**

If the full suite found issues, fix them in focused commits following the same TDD pattern, then re-run Steps 1-2.

---

## Self-review notes

- Spec section 1 (namespace fix) → Task 1; section 2 (redirects + error hints) → Task 2; section 3 (record reader) → Task 3; section 4 (run mode, API) → Tasks 4-6; section 5 (frontend + i18n) → Task 7; section 6 (docs) → Task 8; section 7 (tests) → Tasks 1-7, 9; acceptance criteria AC1-AC6 → Tasks 1, 2, 5, 6, 7, 9.
- `_build_sample_messages(sample, None)` is used for dataset attempts because the prompt is fully rendered at sample-build time (record fields applied); passing the package again would double-render.
- `render_template` gains `extra_variables` (Task 4) so record fields like `{{review}}` pass validation without relaxing the global allowlist.
- Mongo variant reuses `_build_dataset_samples`/`_render_record_prompt` from `dataset_runs.py` so the record-reading logic has exactly one implementation.
