import json
from pathlib import Path

import pytest

from app.modules.datasets.records import DatasetRecordError, count_dataset_records, iter_dataset_records


def _write_prepared(
    tmp_path: Path, source_name: str, source_bytes: bytes, index_entries: list[dict[str, object]]
) -> str:
    prepared = tmp_path / "data" / "datasets" / "demo" / "1" / "main" / "prepared"
    source_root = prepared / "source"
    source_root.mkdir(parents=True, exist_ok=True)
    (source_root / source_name).write_bytes(source_bytes)
    (prepared / "manifest.json").write_text(
        json.dumps(
            {
                "format": "lle.sample-index/v1",
                "source_files": [source_name],
                "record_count": len(index_entries),
                "index_path": "sample-index.jsonl",
            }
        ),
        encoding="utf-8",
    )
    (prepared / "sample-index.jsonl").write_text(
        "\n".join(json.dumps(entry) for entry in index_entries) + "\n", encoding="utf-8"
    )
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


def test_dataset_records_json_array_and_csv_through_preparation(tmp_path: Path) -> None:
    from app.modules.datasets.preparation import prepare_dataset_cache

    root = tmp_path / "datasets" / "demo" / "1" / "main"
    root.mkdir(parents=True)
    array_target = root / "array.json"
    array_target.write_text('[{"question":"q1","answer":"a1"},{"question":"q2","answer":"a2"}]', encoding="utf-8")
    prepared = prepare_dataset_cache(array_target)
    records = list(iter_dataset_records(str(prepared), str(tmp_path)))
    assert [record["fields"]["question"] for record in records] == ["q1", "q2"]
    csv_target = root / "rows.csv"
    csv_target.write_text("question,answer\nq1,a1\n\nq2,a2\n", encoding="utf-8")
    prepared = prepare_dataset_cache(csv_target)
    records = list(iter_dataset_records(str(prepared), str(tmp_path)))
    assert [record["fields"]["question"] for record in records] == ["q1", "q2"]


def test_dataset_records_csv_multiline_quoted_field_yields_one_record_per_row(tmp_path: Path) -> None:
    from app.modules.datasets.preparation import prepare_dataset_cache

    root = tmp_path / "datasets" / "demo" / "1" / "main"
    root.mkdir(parents=True)
    csv_target = root / "rows.csv"
    csv_target.write_text('question,answer\nq1,"line one\nline two"\nq2,a2\n', encoding="utf-8")
    prepared = prepare_dataset_cache(csv_target)
    records = list(iter_dataset_records(str(prepared), str(tmp_path)))
    assert len(records) == 2
    assert records[0]["fields"]["question"] == "q1"
    assert records[0]["fields"]["answer"].replace("\r\n", "\n") == "line one\nline two"
    assert records[1]["fields"]["question"] == "q2"


def test_dataset_preparation_rejects_malformed_json(tmp_path: Path) -> None:
    from app.core.errors import ConflictError
    from app.modules.datasets.preparation import prepare_dataset_cache

    root = tmp_path / "datasets" / "demo" / "1" / "main"
    root.mkdir(parents=True)
    bad = root / "broken.json"
    bad.write_text('{"question": "q1"', encoding="utf-8")
    with pytest.raises(ConflictError, match="could not be parsed"):
        prepare_dataset_cache(bad)


def test_dataset_records_rejects_malformed_jsonl(tmp_path: Path) -> None:
    prepared_path = _write_prepared(
        tmp_path,
        "dataset.jsonl",
        b"{not json}\n",
        [{"source": "dataset.jsonl", "record_number": 1}],
    )
    with pytest.raises(DatasetRecordError, match="could not be parsed"):
        list(iter_dataset_records(prepared_path, str(tmp_path / "data")))


def test_dataset_preparation_rejects_malformed_csv(tmp_path: Path) -> None:
    from app.core.errors import ConflictError
    from app.modules.datasets.preparation import prepare_dataset_cache

    root = tmp_path / "datasets" / "demo" / "1" / "main"
    root.mkdir(parents=True)
    bad = root / "broken.csv"
    bad.write_text('question,answer\nq1,"unclosed\n', encoding="utf-8")
    with pytest.raises(ConflictError, match="could not be parsed"):
        prepare_dataset_cache(bad)


def test_dataset_records_rejects_escaping_index_path(tmp_path: Path) -> None:
    prepared = tmp_path / "data" / "datasets" / "demo" / "1" / "main" / "prepared"
    source_root = prepared / "source"
    source_root.mkdir(parents=True)
    (source_root / "dataset.jsonl").write_bytes(b'{"question":"q1","answer":"a1"}\n')
    (prepared / "manifest.json").write_text(
        json.dumps(
            {
                "format": "lle.sample-index/v1",
                "source_files": ["dataset.jsonl"],
                "record_count": 1,
                "index_path": "../../../outside-index",
            }
        ),
        encoding="utf-8",
    )
    with pytest.raises(DatasetRecordError, match="escapes"):
        list(iter_dataset_records(str(prepared / "manifest.json"), str(tmp_path / "data")))
