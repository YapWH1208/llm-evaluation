# Changelog

All notable changes to the LLM/SLM Evaluation Platform are documented in this file.
The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this
project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## Unreleased

### Added

- Initial release of the platform (version `0.1.0`).

## 0.1.0 — 2026-08-05

### Added

- **Evaluation core**: SQLite-first evaluation service with encrypted model endpoints,
  OpenAI-compatible connection testing, declared capability detection/probing, versioned
  prompt packages, and queued text evaluation runs with worker leases, retry recovery, and
  run lifecycle controls (clone, retry failed samples, archive before deletion).
- **Scoring and judging**: versioned deterministic scoring rules, LLM judge assessments,
  blinded pairwise judge comparisons, human sample reviews with structured adjudication,
  and safeguards preventing target models from self-judging.
- **Datasets**: versioned dataset lifecycle with verified uploads, credentialed and
  local sources, Hugging Face `hf://` sources, host allowlisting, manifest-driven
  dataset preparation, frozen dataset revisions per run, and dataset evaluation runs
  with record-field prompt variables and sharding.
- **Benchmarks and suites**: versioned benchmark plugins with capability compatibility
  validation, evaluation suites with scheduling, runnable multimodal benchmark packs,
  and builtin benchmark registry (`text_quick_check`).
- **Reports and analysis**: report artifact generation through the task pipeline, PDF
  exports, expiring read-only share links, Parquet evidence exports, comparisons,
  capability matrix/heatmap analysis, baselines, and a filtered progressive sample
  evidence browser with secure media previews.
- **Multimodal support**: custom multimodal checks (image/audio/video), OpenAI-compatible
  Responses endpoints, and content translation for OpenAI endpoints.
- **MongoDB document store**: full feature-parity persistence layer for endpoints,
  capabilities, runs, dashboards, judge assessments, reports, sharing, analysis, and
  the task queue.
- **Operational controls**: task priorities and evidence filters, RPS/token limits,
  system and worker concurrency ceilings, hierarchical scheduling limits, rate-limit
  honoring with bounded backoff, operational dashboards, request/health telemetry,
  audit events, and durable run lifecycle logs.
- **Security**: admin bearer tokens with scoped user roles, Fernet-encrypted endpoint
  credentials, request-body redaction of sensitive keys, outbound host fencing,
  loopback endpoint restrictions (local `ollama` only), and immutable report sharing.
- **Web workspace**: React 19 evaluation workspace with responsive dashboard shell,
  unified visual system, persistent light/dark themes, localization across eight
  locales via a typed i18n catalog, dataset evaluation run form, and complete
  interactive accessibility.
- **Operations**: cross-platform `quick-launch` scripts, Docker image and compose
  setup, forward-only database migrations with controlled initialization modes
  (`auto_migrate` / `preview` / `validate`) and SQLite backups, PostgreSQL deployment
  runbook, and GitHub Actions CI for backend tests and frontend test/build.

### Fixed

- Dataset download redirects now validate each hop and surface failures clearly.
- Malformed CSV/TSV and JSON parse errors surface as dataset errors instead of 500s;
  CSV/TSV numbering is per logical row.
- Mongo dataset downloads respect the host allowlist and confine the index path.
- Sharding and template errors surface as conflict responses in dataset runs.
- Sensitive body keys are redacted from real run requests and previews.
- Rate-window tests were made deterministic instead of wall-clock racy.
- PyMongo return-document import issue on newer driver versions.
- Legacy database migration ledger backfill and compatibility preserved.
- Backend package discovery and secure authenticated deployment defaults fixed.
- Evaluation execution is resumable, reproducible, and preserves results on report
  failure.

### Docs

- End-to-end evaluation workflow guide (`docs/evaluation-workflow.md`), PostgreSQL
  deployment runbook (`docs/deployment.md`), requirements traceability map, and
  design spec/implementation plan for HF datasets and dataset evaluation runs.
