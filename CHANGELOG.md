# Changelog

All notable changes to the LLM/SLM Evaluation Platform are documented in this file.
The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this
project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## Unreleased

### Added

- The Configure navigation now includes a `/prompts` page that lists existing
  versioned prompt packages and creates new versions through the existing API.
- Every newly created evaluation run receives an immutable, URL-safe display name in
  `<model_name>_<dataset_or_benchmark_name>_<UTC_datetime>` form. Existing runs derive
  the same deterministic label without a destructive backfill.
- Dataset registration and editing now support multi-select capabilities and
  languages, a task-oriented evaluation type, and prepared-schema input/output field
  selectors with custom values and validation.
- Task-aware aggregate results now expose named metrics—including accuracy,
  precision, recall, F1, pass@1, perplexity, BLEU, ROUGE-L, latency, token use, and
  cost—with sample counts, confidence intervals, and explicit unavailable reasons.
- A server-backed `/leaderboard` workspace lists every non-archived run with combined
  dataset/model/status/capability/language/evaluation-type/date/quality filters,
  sortable columns, pagination, and direct handoff to the selected run details.
- Dataset evaluation runs can select Default, exact match, normalized exact
  match, token F1, BLEU, or ROUGE-L. Explicit selections override the prompt
  package rule; Default defers to the package and then exact match. The run
  launcher now shows a hint when a chosen metric overrides the selected prompt
  package's scoring rule.
- Dataset evaluation runs can now use LLM-as-judge scoring with a separately
  tested judge endpoint, frozen judge system message, and per-record reference
  field. Successful assessments materialize an `llm_judge` metric with coverage
  and confidence intervals; safe assessment evidence remains available when a
  judge fails without failing the target response.
- The retained workspace pages have stable direct URLs: `/dashboard`, `/guide`,
  `/models`, `/datasets`, `/runs`, `/analysis`, and `/settings`.
- Every retained page now exposes URL-backed task tabs so inventory, creation,
  launch, evidence, analysis, health, access, and preference workflows can be
  opened directly without rendering unrelated page content alongside them.

### Changed

- Analysis now uses an independent-axis evidence scatter plot with all eligible runs
  selected by default, broad contextual and numeric filters, linked exact-value
  evidence, bounded loading states, and accessible point inspection.
- Two-run comparisons now visualize every compatible named metric in unit-aware bars,
  preserve exact values and sample counts in a semantic table, and show outcome
  distributions plus explicit missing-evidence reasons.
- Dashboard charts now use honest metric domains, labeled axes, exact-value tooltips,
  and unit-safe scaling. Recent evaluations and run inventory consistently show the
  immutable run name.
- Run details now use a responsive six-section hierarchy—Overview, Metrics, Evidence,
  Lifecycle, Reports, and Reviews—while retaining all lifecycle, concurrency, retry,
  evidence, judge, review, report, download, and sharing controls.
- Quick start and Dataset evaluation are separate URL-backed Runs tabs with independent
  preflight state, while legacy launch links continue to resolve to Quick start.
- Scan-oriented result and inventory cards use left/right desktop rows and intentional
  mobile stacking, with wide data confined to internal scroll regions.
- The browser workspace is reduced to its essential evaluation workflow while
  keeping Dashboard and Guide. Endpoint capabilities live under Models,
  registration lives under Datasets, run review/report evidence stays under
  Runs, and comparisons live under Analysis. Backend APIs remain available.
- Model inventory uses a compact selector with one detailed endpoint inspector;
  run selection and dataset-to-run handoffs open the relevant detail or launch
  tab while preserving browser back/forward history.
- The Dashboard guide and retained page headers are localized: the guide
  describes the queue, inspect, and analysis stages, and the Runs, Datasets,
  and Analysis page titles translate in every supported locale.
- The Dashboard guide now counts six stages and renames the run queue and
  evidence steps so each stage opens an essential evaluation destination.
- The guide renders as one continuous evaluation workflow instead of tabbed
  sections: all six stages are visible at once, and each stage opens the
  matching Models, Datasets, Runs, or Analysis task tab directly.

### Fixed

- Transient application notices dismiss automatically after five seconds; replacing
  a notice resets the timer, while manual dismissal and accessibility announcements
  remain available.
- New dataset registrations default their source revision to `main` without
  rewriting revision values already stored for existing datasets.
- Browser navigation now supports direct loads and back/forward history, with
  root and unknown workspace paths canonicalized to `/dashboard`.
- Queuing a quick-start run now refreshes the run inventory before navigating
  to run details, so the newly queued run no longer flashes away on arrival.
- The Dashboard "Set up an evaluation" action opens dataset registration
  directly instead of landing on the dataset inventory.
- Workspace tabs only link `aria-controls` from the active tab to its rendered
  panel, avoiding references to panels that are not in the document.

## 0.3.0 — 2026-08-09

### Added

- The Runs workspace now offers a compact shared endpoint/preflight context
  with separate quick-start and dataset launch cards. Quick start exposes the
  small deterministic built-in text, image, audio, video, and multimodal
  fixtures for offline smoke testing.
- Ready datasets can hand off directly from the catalog to the Runs workspace,
  where input and reference fields are selected from the prepared dataset
  schema before preflight or queueing.
- Dataset evaluation runs can explicitly select an input field; the chosen input
  and reference fields are frozen in the run snapshot, while clients that omit
  the input field retain the legacy first-string behavior. The input field only
  applies when no prompt package renders the prompt.
- The evaluation dashboard now surfaces live quality, model/benchmark comparisons,
  latency, cost, error signals, recent runs, and system readiness in a compact,
  responsive analytics workspace for light and dark themes.
- Every remaining workspace view now uses the same compact evaluation-tool visual
  language, including page-owned context selection for reports and reviews,
  dense operational inspectors, responsive administration panels, and standalone
  shared reports that honor the saved light/dark preference.

### Fixed

- Failed and other inactive, non-downloaded dataset registrations keep their
  Edit and Delete actions even when no cache exists, while active download,
  verification, preparation, and removal states suppress conflicting changes.
- Canonical Hugging Face dataset URIs such as
  `hf://datasets/hf-internal-testing/textfolder/hello.txt` now resolve correctly,
  while the existing `hf://owner/repository/path` shorthand remains supported,
  including owners named `datasets`, `models`, or `spaces`.
- Dataset evaluation runs reject identical input and reference fields instead of
  silently scoring model output against the input itself.
- Paused dataset downloads keep their paused state when a source correction is
  saved; the pause is released only by explicitly retrying the download.
- Material corrections to failed, non-cached dataset registrations clear stale
  failures consistently in relational and MongoDB stores and require acceptance
  again when license terms change.
- Catalog edits no longer fail with 422 when optional fields are left empty;
  they are sent as `null` like the registration form does.
- Switching datasets in the run form clears a stale reference field prefill
  instead of silently carrying the previous dataset's default.
- Dataset version update/delete on the MongoDB store return 404 for a missing
  version, matching the relational store.
- Dataset preview reports 409 instead of a 500 when the prepared cache is
  corrupt or incomplete.
- Dataset catalog preview and delete buttons are disabled while their request
  is in flight.
- New dataset catalog notices and the preview fallback copy are translated
  for non-English locales.
- Runs completed with errors now sort as finished work on the dashboard
  instead of appearing above cleanly completed runs.
- The virtualized task queue keeps rows rendered when a filter shrinks the
  list while it is scrolled deep.
- Switching review runs clears the previous run's sample list while the next
  run's attempts load, so stale samples can no longer be selected.
- Workspace filters, dataset lifecycle actions, suite queue controls, disk
  usage, and audit/compare states are translated for non-English locales.
- Selecting an analysis baseline no longer gets silently reset by background
  run-event refreshes, and a failed baseline request reverts the selector
  instead of leaving a stale choice.
- Report and review run selectors list only completed runs, so generating a
  report from an in-progress run is no longer offered.
- System readiness on the dashboard stays neutral while health is unknown
  instead of flashing "attention needed", and a healthy service is now
  recognized from the deployed health response.
- The dataset catalog refetches disk usage only when dataset cache state
  changes rather than on every background refresh.
- Workspace tabs expose their tab panels to assistive technology, and the
  setup workbench maps inputs, assets, suites, and catalog panes by name
  instead of by section position.

### Docs

- The end-to-end evaluation workflow guide covers dataset quick-start runs
  and handoff of prepared datasets from the catalog into the Runs workspace.

## 0.2.0 — 2026-08-07

### Added

- Dataset versions can declare optional input and reference field defaults,
  and the catalog gains preview, edit, and delete actions (delete is blocked
  while a run references the revision).
- New in-app usage guide view walking through the evaluation workflow.

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
