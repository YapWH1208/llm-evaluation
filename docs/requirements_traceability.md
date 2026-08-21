# Requirements traceability and verification

This matrix maps the version-1 requirements specification to the current
implementation and its automated evidence. It is intentionally grouped by
requirement section so future changes can preserve the same product contract.

| Requirement sections | Implementation evidence | Verification evidence |
| --- | --- | --- |
| 1–5: product goals, users, and core workflows | React workspace, FastAPI service, and feature-owned endpoint-to-run workflow in `frontend/src/components/` and `backend/app/modules/` | `tests/test_model_endpoints.py`, `tests/test_evaluation_runs.py`, `tests/test_evaluation_suites.py` |
| 6: endpoint management and credential protection | `backend/app/modules/endpoints/`, encrypted secret service, provider adapters, and request preview | `tests/test_model_endpoints.py`, `tests/test_connection_tester.py`, `tests/test_model_executor.py` |
| 7: declarations, detection, conflicts, and safe probe evidence | `backend/app/modules/endpoints/` capability service and provider capability adapter | `tests/test_capabilities.py`, including multi-input, SSE, conflict, and evidence checks |
| 8–9: request-body hierarchy and versioned prompts | provider request contracts, `backend/app/modules/benchmarks/prompts.py`, and immutable run snapshots | `tests/test_prompt_templates.py`, `tests/test_evaluation_runs.py`, `tests/test_model_executor.py` |
| 10–11: normalized multimodal samples and evaluation categories | content IR, media assets, built-in text, vision, audio, video, multimodal, coding, instruction, and safety packs | `tests/test_custom_multimodal_runs.py`, `tests/test_media_assets.py`, `tests/test_benchmarks.py` |
| 12: plugin and pack lifecycle | `backend/app/benchmarks/` plugin registry plus `backend/app/modules/benchmarks/` catalog service and repositories | `tests/test_benchmark_management.py`, `tests/test_benchmarks.py` |
| 13: versioned dataset sources, license, credentials, cache, checksum, and preparation | `backend/app/modules/datasets/` service, preparation workflow, and SQLite/Mongo repositories | `tests/test_datasets.py`, `tests/test_mongo_document_store.py` |
| 14–15: durable runs, queue controls, leasing, limits, retries, and resume | `backend/app/modules/evaluations/` lifecycle, execution, operations, and queue integrations | `tests/test_evaluation_runs.py`, `tests/test_task_queue_api.py`, `tests/test_operational_events.py` |
| 16–18: SQLite/Mongo initialization, migrations, workers, and shards | database/migration infrastructure, shared evaluation execution service, queue ports, and SQLite/Mongo adapters | `tests/test_database_initialization.py`, `tests/test_migrations.py`, `tests/test_mongo_document_store.py`, `tests/contracts/test_evaluation_adapter_contract.py` |
| 19: deterministic, judge, and human scoring | `backend/app/modules/benchmarks/scoring.py` and `backend/app/modules/reviews/` judge/review services and APIs | `tests/test_scoring.py`, `tests/test_judge_assessments.py`, `tests/test_human_reviews.py` |
| 20–21: dashboard, evidence, analysis, comparison, reports, exports, and sharing | application services under `backend/app/modules/analytics/`, `reports/`, and `reviews/`, plus feature-owned React routes | `tests/test_analysis_and_reports.py`, `tests/test_evaluation_runs.py` |
| 22–23: responsive React/Vite workspace, live updates, virtual queue, interactive chart, theme, locale extension | shell composition under `frontend/src/app/` and state/API/DTO ownership under `frontend/src/features/` | frontend ESLint, Vitest, and production build |
| 24: model, benchmark, dataset, run, and report APIs | feature routers under `backend/app/modules/`, including explicit conflict, progress, logs, and result routes | endpoint-focused tests listed above plus Mongo route coverage |
| 25: deployment access boundary | intentionally unauthenticated trusted-network deployment with encrypted provider credentials and no obsolete role/audit subsystem | `tests/test_deployment_security.py`, `tests/test_model_endpoints.py` |
| 26: reliability, observability, and security controls | leases/retries, request IDs, health, encrypted keys, SSRF/file checks, report-share policy | `tests/test_operational_events.py`, `tests/test_health.py`, `tests/test_media_assets.py`, `tests/test_model_endpoints.py` |
| 27: local, team, and distributed deployment modes | `README.md`, `docs/deployment.md`, Docker files, database CLI | `tests/test_database_initialization.py`, `tests/test_migrations.py` |
| 28–31: MVP scope, phase outcomes, acceptance criteria, and final product definition | the integrated platform above, with the explicit acceptance surfaces retained as regression tests | complete backend suite and production frontend build |

## Completion checks

Run from the repository root:

```bash
python -m pytest -q --basetemp .tmp-pytest-final-acceptance
python -m ruff check backend tests
python -m ruff format --check backend tests
cd frontend
npm ci
npm run lint
npm test -- --run
npm run build
```

The test base directory is intentionally disposable and must not be committed.
