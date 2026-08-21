from __future__ import annotations

from app.core.config import Settings
from app.main import create_app


EXPECTED_ROUTES: dict[str, frozenset[str]] = {
    "/api/v1/analytics/matrix": frozenset({"GET"}),
    "/api/v1/analytics/runs/{run_id}/metrics": frozenset({"GET"}),
    "/api/v1/analytics/runs/{run_id}/metrics/recompute": frozenset({"POST"}),
    "/api/v1/analytics/scatter": frozenset({"GET"}),
    "/api/v1/assets": frozenset({"POST"}),
    "/api/v1/assets/{asset_id}": frozenset({"GET"}),
    "/api/v1/assets/{asset_id}/content-part": frozenset({"GET"}),
    "/api/v1/assets/{asset_id}/download": frozenset({"GET"}),
    "/api/v1/benchmarks": frozenset({"GET", "POST"}),
    "/api/v1/benchmarks/packs": frozenset({"POST"}),
    "/api/v1/benchmarks/{benchmark_definition_id}": frozenset({"GET", "PATCH"}),
    "/api/v1/benchmarks/{benchmark_definition_id}/dataset-status": frozenset({"GET"}),
    "/api/v1/benchmarks/{benchmark_definition_id}/prompt": frozenset({"GET"}),
    "/api/v1/benchmarks/{benchmark_definition_id}/versions": frozenset({"POST"}),
    "/api/v1/comparisons": frozenset({"GET"}),
    "/api/v1/dashboard": frozenset({"GET"}),
    "/api/v1/datasets": frozenset({"GET", "POST"}),
    "/api/v1/datasets/disk-usage": frozenset({"GET"}),
    "/api/v1/datasets/{dataset_version_id}": frozenset({"DELETE", "PUT"}),
    "/api/v1/datasets/{dataset_version_id}/accept-license": frozenset({"POST"}),
    "/api/v1/datasets/{dataset_version_id}/cache": frozenset({"DELETE"}),
    "/api/v1/datasets/{dataset_version_id}/credential-reference": frozenset({"PUT"}),
    "/api/v1/datasets/{dataset_version_id}/download": frozenset({"POST"}),
    "/api/v1/datasets/{dataset_version_id}/pause": frozenset({"POST"}),
    "/api/v1/datasets/{dataset_version_id}/preview": frozenset({"GET"}),
    "/api/v1/datasets/{dataset_version_id}/retry": frozenset({"POST"}),
    "/api/v1/datasets/{dataset_version_id}/upload": frozenset({"POST"}),
    "/api/v1/datasets/{dataset_version_id}/validate": frozenset({"POST"}),
    "/api/v1/evaluation-runs": frozenset({"GET", "POST"}),
    "/api/v1/evaluation-runs/custom-multimodal": frozenset({"POST"}),
    "/api/v1/evaluation-runs/dataset": frozenset({"POST"}),
    "/api/v1/evaluation-runs/dataset/preflight": frozenset({"POST"}),
    "/api/v1/evaluation-runs/validate": frozenset({"POST"}),
    "/api/v1/evaluation-runs/{run_id}": frozenset({"DELETE", "GET"}),
    "/api/v1/evaluation-runs/{run_id}/archive": frozenset({"POST"}),
    "/api/v1/evaluation-runs/{run_id}/attempts": frozenset({"GET"}),
    "/api/v1/evaluation-runs/{run_id}/cancel": frozenset({"POST"}),
    "/api/v1/evaluation-runs/{run_id}/clone": frozenset({"POST"}),
    "/api/v1/evaluation-runs/{run_id}/events": frozenset({"GET"}),
    "/api/v1/evaluation-runs/{run_id}/execute": frozenset({"POST"}),
    "/api/v1/evaluation-runs/{run_id}/logs": frozenset({"GET"}),
    "/api/v1/evaluation-runs/{run_id}/pause": frozenset({"POST"}),
    "/api/v1/evaluation-runs/{run_id}/progress": frozenset({"GET"}),
    "/api/v1/evaluation-runs/{run_id}/rerun-benchmark": frozenset({"POST"}),
    "/api/v1/evaluation-runs/{run_id}/resume": frozenset({"POST"}),
    "/api/v1/evaluation-runs/{run_id}/retry-failed": frozenset({"POST"}),
    "/api/v1/evaluation-runs/{run_id}/scheduling": frozenset({"PATCH"}),
    "/api/v1/evaluation-runs/{run_id}/summary": frozenset({"GET"}),
    "/api/v1/evaluation-suites": frozenset({"GET", "POST"}),
    "/api/v1/evaluation-suites/{suite_id}": frozenset({"GET", "PATCH"}),
    "/api/v1/evaluation-suites/{suite_id}/runs": frozenset({"POST"}),
    "/api/v1/judge-assessments": frozenset({"POST"}),
    "/api/v1/judge-assessments/compare": frozenset({"POST"}),
    "/api/v1/judge-assessments/sample/{sample_attempt_id}": frozenset({"GET"}),
    "/api/v1/judge-assessments/sample/{sample_attempt_id}/agreement": frozenset({"GET"}),
    "/api/v1/leaderboard": frozenset({"GET"}),
    "/api/v1/model-endpoints": frozenset({"GET", "POST"}),
    "/api/v1/model-endpoints/{endpoint_id}": frozenset({"DELETE", "GET", "PATCH"}),
    "/api/v1/model-endpoints/{endpoint_id}/capabilities": frozenset({"GET", "PUT"}),
    "/api/v1/model-endpoints/{endpoint_id}/capabilities/conflicts": frozenset({"GET"}),
    "/api/v1/model-endpoints/{endpoint_id}/capabilities/detect": frozenset({"POST"}),
    "/api/v1/model-endpoints/{endpoint_id}/connection-test": frozenset({"POST"}),
    "/api/v1/model-endpoints/{endpoint_id}/request-preview": frozenset({"POST"}),
    "/api/v1/prompt-packages": frozenset({"GET", "POST"}),
    "/api/v1/prompt-packages/{prompt_package_id}": frozenset({"DELETE", "PUT"}),
    "/api/v1/reports": frozenset({"POST"}),
    "/api/v1/reports/run/{run_id}": frozenset({"GET"}),
    "/api/v1/reports/{report_id}": frozenset({"DELETE"}),
    "/api/v1/reports/{report_id}/download": frozenset({"GET"}),
    "/api/v1/reports/{report_id}/shares": frozenset({"GET", "POST"}),
    "/api/v1/reports/{report_id}/shares/{share_id}/revoke": frozenset({"POST"}),
    "/api/v1/reviews": frozenset({"POST"}),
    "/api/v1/reviews/sample/{sample_attempt_id}": frozenset({"GET"}),
    "/api/v1/reviews/sample/{sample_attempt_id}/agreement": frozenset({"GET"}),
    "/api/v1/tasks": frozenset({"GET"}),
    "/api/v1/tasks/{task_id}": frozenset({"PATCH"}),
    "/api/v1/workers/claim": frozenset({"POST"}),
    "/api/v1/workers/events": frozenset({"GET"}),
    "/api/v1/workers/reclaim-expired": frozenset({"POST"}),
    "/api/v1/workers/tasks/{task_id}/execute": frozenset({"POST"}),
    "/api/v1/workers/tasks/{task_id}/heartbeat": frozenset({"POST"}),
    "/health": frozenset({"GET"}),
    "/shared-reports/{token}": frozenset({"GET"}),
}


def _openapi_methods(operation_map: dict[str, object]) -> frozenset[str]:
    return frozenset(
        method.upper()
        for method in operation_map
        if method.lower() in {"get", "post", "put", "patch", "delete", "head", "options"}
    )


def test_public_http_route_contract_is_stable() -> None:
    app = create_app(
        Settings.local_development(
            database_url="sqlite:///:memory:",
            secret_encryption_key="test-secret-key",
        )
    )
    paths = app.openapi()["paths"]
    actual = {path: _openapi_methods(operation_map) for path, operation_map in paths.items()}

    assert actual == EXPECTED_ROUTES


def test_public_http_response_contract_keeps_lifecycle_statuses() -> None:
    app = create_app(
        Settings.local_development(
            database_url="sqlite:///:memory:",
            secret_encryption_key="test-secret-key",
        )
    )
    responses = app.openapi()["paths"]

    assert "201" in responses["/api/v1/model-endpoints"]["post"]["responses"]
    assert "204" in responses["/api/v1/evaluation-runs/{run_id}"]["delete"]["responses"]
    assert "204" in responses["/api/v1/reports/{report_id}"]["delete"]["responses"]
    assert "200" in responses["/health"]["get"]["responses"]
