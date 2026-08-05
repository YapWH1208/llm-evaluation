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


def test_dataset_run_service_manifest_identity() -> None:
    from app.services.dataset_runs import (
        DATASET_RUN_BENCHMARK_ID,
        DATASET_RUN_BENCHMARK_VERSION,
        DATASET_RUN_DEFAULT_SAMPLE_LIMIT,
        _DATASET_RUN_MANIFEST,
    )

    assert DATASET_RUN_BENCHMARK_ID == "dataset-evaluation"
    assert DATASET_RUN_BENCHMARK_VERSION == "1.0.0"
    assert DATASET_RUN_DEFAULT_SAMPLE_LIMIT == 100
    assert _DATASET_RUN_MANIFEST["benchmark_id"] == DATASET_RUN_BENCHMARK_ID
    assert _DATASET_RUN_MANIFEST["shard_size"] == 50
