# Frontend workspace redesign

## Status

- Design direction: approved by the user on 2026-08-08
- Written specification: awaiting user review
- Branch: `agent/frontend-workspace-redesign`
- Scope: every workspace view except the already-redesigned Dashboard, plus the standalone shared-report route
- Backend behavior: unchanged

## Context and source of truth

The current Dashboard and application shell on the parent `agent/frontend-analytics-redesign` branch are the visual reference. The redesign must extend their developer-tool language to every remaining frontend view without reimagining the Dashboard.

Repository and browser discovery established the following facts:

- The frontend has 18 state-driven workspace views: Dashboard, Guide, Models, Capabilities, Workspace, Benchmarks, Datasets, Suites, Runs, Task queue, Workers, Analysis, Compare, Reports, Human review, Users, and Settings.
- `/shared-reports/:token` is a standalone additional view and is included in scope.
- Dashboard uses purpose-built compact sections, 8px panels, dense tables, tabular metrics, restrained status color, and page-owned hierarchy.
- Every other workspace view still uses the older generic `panel`, `card`, `form`, and `table` composition. Most presentation remains inline in the 1,022-line `App.tsx`.
- The initial Code Review Graph contains 1,423 nodes and 18,722 edges. `App.tsx` has a 752-node, 19-file blast radius at depth three, so presentation extraction is a risk-control measure rather than an unrelated refactor.
- The frontend baseline is green: 14 test files, 47 tests, TypeScript build, and Vite production build.
- Superdesign CLI preflight did not return its required authentication status after the permitted retry, so no canvas draft was generated. The design is grounded in the rendered application, current source, saved design-system context, and approved user decisions.
- Desktop light/dark browser inspection covered all workspace views and the shared-report route. The browser viewport override did not change the live viewport, so mobile visual verification must be retried during implementation and backed by responsive tests and overflow assertions.

## Design principles

1. Dashboard is the reference, not a redesign target.
2. Information architecture follows each page's job; shared CSS does not force every workflow into the same card grid.
3. Dense does not mean cramped: compact controls, deliberate grouping, readable tables, and predictable gutters replace oversized panels and long undifferentiated forms.
4. Lists, tables, split panes, inspectors, charts, forms, toolbars, tabs, and empty states are chosen by workflow rather than decoration.
5. API calls, data contracts, state ownership, persistence, confirmations, uploads, downloads, and authentication behavior remain unchanged.
6. Dark and light themes, all eight locales, keyboard use, and narrow layouts are first-class.
7. No new runtime UI, icon, chart, routing, state-management, or localization dependency is required.

## Visual system

### Tokens

Continue using `frontend/src/workspace-theme.css` as the semantic token source.

- Dark: canvas `#0d0f12`, soft canvas `#15191e`, surface `#121519`, raised surface `#181c21`, border `#2a3038`, text `#f1f3f5`, muted text `#a8b0bb`, accent `#5eead4`.
- Light: canvas `#f6f7f9`, soft canvas `#eef0f3`, surface `#ffffff`, border `#e2e5e9`, text `#17191c`, muted text `#5f6670`, accent `#0f766e`.
- Geometry: 6px compact controls, 8px panels, circular status dots, bounded pills only where run/task state benefits from rapid scanning.
- Spacing: 4, 8, 12, 16, 24, and 32px.
- Typography: Inter/system sans; 24–28px page titles, 14–16px section titles, 13–14px body, 11–12px labels/captions, tabular numerals for metrics and numeric cells.
- Borders: flat 1px semantic borders; no gradients or ambient panel shadows.
- Motion: 120–180ms interaction feedback, no ambient animation, and reduced-motion support.

### Shared primitives

Introduce a small dependency-free workspace UI layer that composes semantic HTML rather than wrapping every native element.

- `PageHeader`: eyebrow, title, concise description, contextual status, and page actions.
- `PageToolbar`: search/filter controls, counts, segmented actions, and responsive wrapping.
- `WorkspacePanel`: flat bordered region with compact heading, description, actions, and optional flush content.
- `Tabs`: keyboard-operable tab list and panels for page modes and inspectors.
- `SplitPane`: list/master region and flexible detail/inspector region with responsive stacking.
- `InspectorSection`: compact key-value, evidence, status, or form subsection.
- `DataTable`: scoped horizontal scrolling, compact header, row hover/selection, numeric alignment, and row actions.
- `StatusIndicator`: dot plus text by default; compact bordered state label when the bounded shape improves scanning.
- `EmptyState`: state explanation, prerequisite/context, and a direct existing workflow action.
- `FormSection`: titled field group, optional help text, responsive field grid, and deliberate advanced-field separation.
- `MetricStrip`: compact operational totals where counts help orient a page.

The primitives reuse current Dashboard tokens and do not change application data flow.

## Application shell and page hierarchy

`AppShell` remains responsible for the persistent navigation rail, responsive drawer state, top bar, locale, theme, notices, completed-run count, and system health.

- Keep the existing 232px desktop rail, five navigation groups, inline SVG icons, 960px drawer breakpoint, and current view identifiers.
- Remove the generic shell-owned page heading for all views, not only Dashboard.
- Every view supplies one page-owned `PageHeader`, following Dashboard's compact hierarchy and allowing contextual actions, filters, counts, and status.
- Keep the top bar as compact global context; page headers must not repeat the same sentence verbatim.
- Preserve notices, focus behavior, `aria-current`, close-on-navigation drawer behavior, theme persistence, and locale selection.

## Page information architecture

### Overview

#### Dashboard

Do not redesign its composition or change its analytics behavior. Compatibility changes are allowed only when a shared shell or token primitive must support every page, and must not reduce Dashboard visual fidelity or functionality.

#### Guide

Replace the flat seven-card wall with a compact workflow timeline/stepper. Each step has a number, outcome, concise instructions, and a direct action to the relevant existing destination. Preserve all seven current steps and localized content.

### Configure

#### Models

Use an endpoint inventory and detail/editor workbench.

- A compact summary shows total, available, unavailable, and unverified endpoints.
- The inventory supports selection and exposes identity, provider/protocol, status, and capacity at a glance.
- The editor groups fields into Connection, Capacity/rate limits, Pricing, and Metadata/advanced request configuration.
- Advanced JSON and secondary fields remain available without dominating the initial viewport.
- Preserve create, edit, cancel edit, connection test, capability probe, benchmark queue, saved encrypted-key behavior, confirmations, and all field values.

#### Capabilities

Use endpoint selection plus a capability inspector.

- Left region: model endpoints and probe status.
- Right region: detected evidence, user declaration, effective status, and per-capability controls.
- Preserve the explicit separation between automatic detection and user declaration.
- Empty states distinguish no endpoint, not yet probed, and no returned capability evidence.

#### Workspace

Replace the 3,967px aggregate page with a tabbed setup workbench:

1. Prompt packages
2. Dataset registration
3. Evaluation suites
4. Multimodal assets and quick checks

Each tab keeps the existing form, validation, help text, saved-resource context, and actions. Supporting catalogs become compact sidebars or in-tab summaries instead of four additional full-width panels.

#### Benchmarks

Use a compact registry table with local search, status/modality filters, totals, and clear managed-versus-actionable row operations. Preserve benchmark status updates and built-in pack semantics.

#### Datasets

Use a dataset inventory and selected-dataset inspector.

- Inventory rows/cards show version, revision, cache state, size, source, and failure/ready status.
- Inspector groups metadata, source/license, cache/download actions, preview, edit, upload, and destructive actions.
- Preserve checksum validation, pause/retry, preview, edit, upload, delete guards/confirmations, and cache clearing.

#### Suites

Use a suite inventory with benchmark composition, version, description, and endpoint queue actions. The empty state opens the existing Workspace suite builder. Preserve endpoint availability filtering and suite queue behavior.

### Operations

#### Runs

Use a persistent run list and selected-run inspector.

- A compact launch region contains preflight and dataset-run configuration without displacing run history.
- The run list shows state, benchmark/version, progress, timestamps, concurrency, and primary actions.
- The selected inspector organizes Summary, Evidence, Logs, Reviews, Judge, and Reports into tabs or clearly switchable modes.
- Preserve run selection, pagination, filtering, concurrency changes, execute/pause/resume/cancel/archive/clone/rerun/retry actions, media evidence, reviews, judge assessments, report generation, and all confirmations.

#### Task queue

Keep a dense virtualized table. Add local status/task/run filters, a compact task-status summary, clearer priority row controls, and selected/hover treatment. Preserve virtualization and priority update behavior.

#### Workers

Add queue/lease context, active-worker summary, and a diagnostic empty state. When workers are present, render worker, task, run, state, and heartbeat/lease timing in a compact table using existing data only.

### Insights

#### Analysis

Replace the vertical sequence of six heatmap panels with a dimension switcher.

- Baseline selection remains global.
- Dimension tabs select Model × benchmark, Model × capability, Model × language, Model × difficulty, Prompt × benchmark, or Model × modality.
- The primary visualization and synchronized evidence table show the selected dimension.
- Capability evidence remains keyboard-operable and exposes sample count, confidence interval, baseline/delta, errors, latency, and cost.
- Sparse dimensions render a useful empty state without hiding other dimensions.

#### Compare

Use a fixed comparison selector bar, selected-run context, compatibility guidance, KPI delta strip, and detailed A/B/difference table. Preserve same-benchmark validation, comparison API behavior, and outcome semantics.

#### Reports

Allow completed-run selection on the Reports page instead of requiring hidden prior navigation state. Then show report type/related-run configuration, generation actions, artifact table, sharing policy, download, and generated link state. Selection still calls the existing run-loading workflow and does not change backend behavior.

#### Human review

Allow run and sample selection on the page. Use a review queue/list and evidence inspector with Review and Judge modes. Preserve independent human-review and LLM-judge evidence, adjudication, agreement summaries, blinded comparisons, swap tests, and sample pagination.

### System

#### Users

Use a user inventory, contextual user-creation panel/drawer, and separate audit table/timeline. Preserve administrator-token behavior, roles, concurrency caps, created token notice, and all current audit data.

#### Settings

Use categorized sections for Runtime health, Access token, Localization, Appearance, and Database/deployment guidance. Clearly distinguish editable browser preferences, secret entry, and read-only server state. Preserve bearer-token handling, refresh behavior, theme, locale, and database guidance.

### Standalone shared report

Retain the focused password/access flow, but use the same typography, tokens, control density, status messaging, and responsive form treatment. Preserve password non-persistence, report object-URL lifecycle, download/open actions, and read-only access semantics.

## Component and data boundaries

`App.tsx` remains the controller for data fetching, state, API mutation handlers, notices, and cross-view navigation. Presentation moves into focused components under `frontend/src/components/pages/` and reusable primitives under `frontend/src/components/workspace/`.

```text
Existing API refresh and mutation handlers
  -> App-owned state and workflow callbacks
  -> typed page component props
  -> shared workspace primitives
  -> page-specific tables, forms, inspectors, and visualizations
```

Extraction rules:

- Do not duplicate or relocate API behavior into display primitives.
- Keep page props domain-focused and typed with existing API types.
- Extract complex existing pieces such as datasets, run evidence, reports, analysis, comparison, and review workflows incrementally with their tests.
- Avoid a single mega `WorkspaceViews` prop bag or speculative state abstraction.

## Failure and sparse-data behavior

- Every page must distinguish loading, empty, permission/authentication, failure, and populated states where the current data permits.
- Empty states include a direct existing workflow action when one can resolve the state.
- Unknown values display `--`; measured numeric zero remains zero.
- Long identifiers truncate visually with full values in accessible/title context and never widen the page.
- Network/API errors continue through the current notice/error mechanism.
- Destructive actions remain confirmed and visually separated.

## Responsive behavior

- Desktop: split panes and multi-column workbenches at widths where both regions remain legible.
- Tablet: inspectors move below inventories; toolbars and metric strips wrap without losing actions.
- Mobile: page headers stack, primary actions remain reachable, field grids collapse, tabs and dense tables scroll within scoped containers, and the existing navigation drawer remains authoritative.
- No page-level horizontal overflow at approximately 320px or 390px.
- Touch/narrow layouts keep destructive controls separated and maintain useful target sizes without inflating desktop density.

## Accessibility and localization

- Preserve semantic landmarks, one page-level heading, heading order, form labels, tables, buttons, `aria-current`, focus-visible behavior, and live notices.
- Tabs use proper tab/list semantics and keyboard operation; split-pane selections expose selected state.
- Charts include programmatic names and adjacent text/table equivalents; color is never the sole signal.
- New static copy must be translatable by the existing typed catalog or `StaticCopy` bridge and covered for English, Simplified Chinese, French, German, Russian, Japanese, Korean, and Malay.
- Provider/model/dataset/user data, raw evidence, statuses, and identifiers remain protected from accidental translation.

## Testing and visual verification

- Use test-driven development for each page group.
- Add primitive tests for tabs, selection, accessible names, and empty states.
- Add group-specific integration tests for navigation, forms, local filters, inspectors, and preserved callbacks.
- Retain and expand existing dataset, run, guide, shared-report, shell, localization, and Dashboard tests.
- Run focused tests and `npm run build` for every coherent commit.
- After each logical group, inspect populated and empty states in the running application, in dark and light themes. Retry mobile viewport inspection; if the browser capability remains unavailable, supplement source/tests with explicit overflow assertions and report the remaining visual risk.
- Final validation runs `npm test -- --run`, `npm run build`, `python3 -m pytest -q`, `git diff --check`, Code Review Graph update/detection, and a complete view-by-view browser audit.

## Delivery sequence

1. Shared workspace primitives and page-owned header shell.
2. Guide and Configure pages.
3. Operations pages and run inspector organization.
4. Insights pages and report/review selection workflows.
5. System pages and shared report.
6. Responsive/theme/localization refinement, changelog, final validation, and graph review.

Each coherent step is committed independently. No push or pull request is authorized by the current request.

## Rollout and rollback

The change is frontend-only and uses existing build/deployment behavior. It requires no feature flag, migration, or backend rollout. Atomic commits allow a page group or shared primitive layer to be reverted independently.

## Non-goals

- No Dashboard redesign or new Dashboard analytics behavior.
- No backend, API, schema, database, migration, authentication, authorization, or deployment behavior change.
- No new router, component library, CSS framework, chart library, icon package, state library, or i18n system.
- No removal of fields, actions, views, locales, workflows, or configuration options.
- No fabricated data, new telemetry, or third-party runtime assets.
- No unrelated backend or dependency refactor.
