from __future__ import annotations

import csv
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
        reader = csv.reader(source, delimiter=delimiter)
        header: list[str] | None = None
        previous_end = 0
        for raw_row in reader:
            if header is None:
                header = raw_row
                previous_end = reader.line_num
                continue
            row_start = previous_end + 1
            if row_start <= record_number <= reader.line_num:
                return dict(zip(header, raw_row)) if header else None
            previous_end = reader.line_num
    return None


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
