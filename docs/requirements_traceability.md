# Requirements traceability and verification

This matrix maps the version-1 requirements specification to the current
implementation and its automated evidence. It is intentionally grouped by
requirement section so future changes can preserve the same product contract.

| Requirement sections | Implementation evidence | Verification evidence |
| --- | --- | --- |
| 1–5: product goals, users, and core workflows | React workspace, FastAPI service, endpoint-to-run workflow in `frontend/src/App.tsx` and `backend/app/api/` | `tests/test_model_endpoints.py`, `tests/test_evaluation_runs.py`, `tests/test_evaluation_suites.py` |
| 6: endpoint management and credential protection | `api/model_endpoints.py`, encrypted secret service, provider adapters and request preview | `tests/test_model_endpoints.py`, `tests/test_connection_tester.py`, `tests/test_model_executor.py` |
| 7: declarations, detection, conflicts, and safe probe evidence | `api/capabilities.py`, `services/capability_detector.py`, capability workspace | `tests/test_capabilities.py`, including multi-input, SSE, conflict, and evidence checks |
| 8–9: request-body hierarchy and versioned prompts | `services/request_body.py`, `api/prompt_packages.py`, immutable run snapshots | `tests/test_prompt_templates.py`, `tests/test_evaluation_runs.py`, `tests/test_model_executor.py` |
| 10–11: normalized multimodal samples and evaluation categories | content IR, media assets, built-in text, vision, audio, video, multimodal, coding, instruction, and safety packs | `tests/test_custom_multimodal_runs.py`, `tests/test_media_assets.py`, `tests/test_benchmarks.py` |
| 12: plugin and pack lifecycle | benchmark registry, manifest validation, dynamic persisted inline plugins, pack APIs | `tests/test_benchmark_management.py`, `tests/test_benchmarks.py` |
| 13: versioned dataset sources, license, credentials, cache, checksum, and preparation | `api/datasets.py`, relational and Mongo dataset services | `tests/test_datasets.py`, `tests/test_mongo_document_store.py` |
| 14–15: durable runs, queue controls, leasing, limits, retries, and resume | `api/evaluation_runs.py`, `services/task_queue.py`, `services/run_executor.py` | `tests/test_evaluation_runs.py`, `tests/test_task_queue_api.py`, `tests/test_operational_events.py` |
| 16–18: SQLite/PostgreSQL/Mongo initialization, migrations, workers, and shards | database/migration services, Mongo document store, worker APIs, sharded executor | `tests/test_database_initialization.py`, `tests/test_migrations.py`, `tests/test_mongo_document_store.py` |
| 19: deterministic, judge, and human scoring | scoring, judge-assessment, and review services/APIs | `tests/test_scoring.py`, `tests/test_judge_assessments.py`, `tests/test_human_reviews.py` |
| 20–21: dashboard, evidence, analysis, comparison, reports, exports, and sharing | dashboard/analytics/comparison/report APIs and React evidence/analysis views | `tests/test_analysis_and_reports.py`, `tests/test_evaluation_runs.py` |
| 22–23: responsive React/Vite workspace, live updates, virtual queue, interactive chart, theme, locale extension | `frontend/src/App.tsx`, `styles.css`, `evidence.css`, Vite configuration | production `npm.cmd run build`; browser verification against local SQLite |
| 24: model, benchmark, dataset, run, and report APIs | routers under `backend/app/api/`, including explicit conflict, progress, logs, and result routes | endpoint-focused tests listed above plus Mongo route coverage |
| 25: roles and metadata-only auditing | authentication/audit middleware and administration API | `tests/test_admin.py`, `tests/test_mongo_document_store.py` |
| 26: reliability, observability, and security controls | leases/retries, request IDs, health, encrypted keys, SSRF/file checks, report-share policy | `tests/test_operational_events.py`, `tests/test_health.py`, `tests/test_media_assets.py`, `tests/test_model_endpoints.py` |
| 27: local, team, and distributed deployment modes | `README.md`, `docs/deployment.md`, Docker files, database CLI | `tests/test_database_initialization.py`, `tests/test_migrations.py` |
| 28–31: MVP scope, phase outcomes, acceptance criteria, and final product definition | the integrated platform above, with the explicit acceptance surfaces retained as regression tests | complete backend suite and production frontend build |

## Completion checks

Run from the repository root:

```powershell
python -m pytest -q --basetemp .tmp-pytest-final-acceptance
Set-Location frontend
npm.cmd run build
```

The test base directory is intentionally disposable and must not be committed.
