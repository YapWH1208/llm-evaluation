import json
from pathlib import Path

import pytest

from app.services.dataset_records import DatasetRecordError, count_dataset_records, iter_dataset_records


def _write_prepared(tmp_path: Path, source_name: str, source_bytes: bytes, index_entries: list[dict[str, object]]) -> str:
    prepared = tmp_path / "data" / "datasets" / "demo" / "1" / "main" / "prepared"
    source_root = prepared / "source"
    source_root.mkdir(parents=True, exist_ok=True)
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
