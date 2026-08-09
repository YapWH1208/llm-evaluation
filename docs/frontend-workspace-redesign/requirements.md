# Frontend workspace redesign requirements

## 1. Document control

- Status: Draft awaiting written-spec review
- Version: 1.0
- Owner: YapWH1208
- Last updated: 2026-08-08
- Target branch: `agent/frontend-workspace-redesign`
- Design direction: approved 2026-08-08
- Design specification: `docs/superpowers/specs/2026-08-08-frontend-workspace-redesign-design.md`
- Artifact path note: existing root and Dashboard workflow requirements are preserved; this requirement uses a scoped path.

## 2. Problem statement

The redesigned Dashboard and compact application shell now establish a restrained, information-dense developer-tool aesthetic, but every other frontend view still relies on the older generic panel/card/form presentation. Those views frequently duplicate shell context, use long undifferentiated forms, underuse available space in sparse states, and present related lists, configuration, evidence, and actions as disconnected vertical panels. The result is inconsistent visual quality and weaker task hierarchy across the evaluation workflow.

The remaining workspace and shared-report views must be redesigned to the Dashboard's visual and interaction standard without changing backend behavior or removing any capability.

## 3. Goals and success metrics

- Bring every non-Dashboard frontend view to the Dashboard's visual quality, density, spacing, typography, component language, and theme treatment.
- Give each page a purpose-specific information architecture using appropriate lists, tables, split panes, inspectors, forms, charts, toolbars, tabs, and empty states.
- Reduce the presentation coupling in `App.tsx` while keeping it as the application controller.
- Preserve every current workflow, field, action, API call, state transition, locale, theme, and accessibility behavior.
- Complete with all frontend and backend CI-equivalent checks passing, Code Review Graph review, and view-by-view browser inspection in dark and light themes.

## 4. Users and stakeholders

- Primary: ML engineers, LLM evaluation engineers, researchers, and platform operators.
- Secondary: reviewers, administrators, and read-only report consumers.
- Maintainers: repository owner and frontend/backend contributors.

## 5. Scope

### 5.1 In scope

- Guide, Models, Capabilities, Workspace, Benchmarks, Datasets, Suites, Runs, Task queue, Workers, Analysis, Compare, Reports, Human review, Users, Settings, and `/shared-reports/:token`.
- Page-owned compact headers for every non-Dashboard workspace view.
- Reusable dependency-free workspace presentation primitives derived from Dashboard.
- Purpose-specific page layout and responsive structure.
- Incremental extraction of inline page presentation from `App.tsx` while retaining controller behavior there.
- Local-only search/filter/tab/selection UI over existing in-memory data where it improves page use.
- Dark/light, responsive, localization, accessibility, tests, visual QA, and changelog work.

### 5.2 Out of scope

- Redesigning Dashboard composition or changing Dashboard analytics behavior.
- Backend, API, database, migration, authentication, authorization, deployment, or request-cadence changes.
- Removing or renaming existing views, fields, forms, actions, statuses, configuration options, or workflows.
- New UI/chart/icon/router/state/i18n dependencies or CSS-framework migration.
- Fabricated data, seeded production content, telemetry, or third-party runtime assets.
- Unrelated refactors or dependency upgrades.

## 6. User journeys

1. An engineer navigates from Dashboard into any workspace page and experiences the same compact hierarchy, visual language, navigation behavior, and theme quality.
2. An engineer manages model endpoints through an inventory and structured editor without losing advanced configuration.
3. An engineer creates prompts, registers datasets, builds suites, and prepares multimodal checks through a tabbed setup workbench rather than a single multi-thousand-pixel form wall.
4. An operator scans benchmarks, datasets, suites, queue tasks, and workers through dense task-appropriate tables or list/inspector views.
5. An engineer launches, selects, manages, and inspects runs without losing access to evidence, logs, reviews, judge results, or reports.
6. An analyst selects one analysis dimension or two compatible runs and receives a focused visualization/table workspace.
7. A reporter or reviewer selects the necessary run/sample on the current page instead of depending on hidden prior navigation state.
8. An administrator manages users, audits, access tokens, locale, theme, and runtime diagnostics through clearly categorized sections.
9. A shared-report consumer opens a read-only report through the existing password-safe flow in a visually consistent standalone page.
10. A keyboard, mobile, light-theme, dark-theme, or non-English user completes the same workflows without clipping, inaccessible controls, or missing copy.

## 7. Functional requirements

| ID | Requirement | Priority | Acceptance criteria |
|---|---|---|---|
| FR-001 | The existing Dashboard composition and analytics behavior MUST remain the visual and functional reference and MUST NOT be redesigned. | MUST | AC-001 |
| FR-002 | `AppShell` MUST retain all navigation groups, destinations, icons, drawer behavior, locale/theme controls, notices, completed count, and health state. | MUST | AC-002 |
| FR-003 | Every non-Dashboard workspace view MUST render one page-owned compact header with contextual description, status/counts, and relevant actions; the shell MUST NOT render a duplicate generic page heading. | MUST | AC-003 |
| FR-004 | Shared workspace primitives MUST provide consistent compact panels, toolbars, tabs, split panes, inspectors, tables, status indicators, empty states, form sections, and metric strips without a new runtime dependency. | MUST | AC-004 |
| FR-005 | Models MUST use an endpoint inventory and structured create/edit inspector while preserving all current endpoint fields and endpoint/run actions. | MUST | AC-005 |
| FR-006 | Capabilities MUST use endpoint selection and a capability inspector that keeps detected, declared, and effective status distinct. | MUST | AC-006 |
| FR-007 | Workspace MUST organize prompt, dataset-registration, suite, and multimodal workflows into switchable workbench modes while preserving every field and action. | MUST | AC-007 |
| FR-008 | Benchmarks MUST use a compact registry with local search/filter controls and preserve status operations and pack-managed semantics. | MUST | AC-008 |
| FR-009 | Datasets MUST use an inventory and selected-dataset inspector while preserving preparation, pause/retry, validation, upload, preview, edit, delete, license, and cache-clear workflows. | MUST | AC-009 |
| FR-010 | Suites MUST show versioned composition and endpoint queue actions and provide a direct existing workflow action from its empty state. | MUST | AC-010 |
| FR-011 | Runs MUST present launch/preflight controls, a persistent run list, and an organized selected-run inspector without removing any lifecycle, concurrency, evidence, review, judge, report, or pagination action. | MUST | AC-011 |
| FR-012 | Task queue MUST preserve virtualization and priority updates while adding compact status context and local filtering. | MUST | AC-012 |
| FR-013 | Workers MUST show active lease data when present and a diagnostic empty state with existing queue/health context when absent. | MUST | AC-013 |
| FR-014 | Analysis MUST provide a dimension switcher, global baseline selection, one primary visualization, and synchronized evidence table for every current heatmap dimension. | MUST | AC-014 |
| FR-015 | Compare MUST preserve compatibility validation and API semantics while presenting selectors, run context, KPI differences, and detailed comparison evidence. | MUST | AC-015 |
| FR-016 | Reports MUST allow completed-run selection on the page and preserve report type, related-run, generation, artifact, download, and sharing workflows. | MUST | AC-016 |
| FR-017 | Human review MUST allow run/sample selection on the page and preserve review, adjudication, agreement, judge, blinded comparison, swap-test, evidence, and pagination workflows. | MUST | AC-017 |
| FR-018 | Guide MUST preserve all seven workflow steps and add direct actions to the corresponding existing destinations. | MUST | AC-018 |
| FR-019 | Users MUST preserve creation, role, concurrency, one-time token notice, authentication behavior, user inventory, and audit data in a clearer administration layout. | MUST | AC-019 |
| FR-020 | Settings MUST clearly distinguish read-only runtime values, browser preferences, secret token entry, and deployment guidance while preserving save/clear/refresh behavior. | MUST | AC-020 |
| FR-021 | The standalone shared-report page MUST preserve password safety, object-URL lifecycle, read-only semantics, open, and download behavior. | MUST | AC-021 |
| FR-022 | Local search, filters, tabs, and selection state MUST operate only on existing frontend state and MUST NOT change API request cadence or persisted data. | MUST | AC-022 |
| FR-023 | Loading, empty, sparse, permission, error, and populated states MUST remain distinguishable and actionable wherever the current API state supports the distinction. | MUST | AC-023 |
| FR-024 | Unknown values MUST render as `--`, measured zero MUST remain zero, long identifiers MUST not cause page overflow, and dynamic/user/API values MUST remain untranslated. | MUST | AC-024 |
| FR-025 | All current view-changing, form-submission, confirmation, upload, download, mutation, and notice workflows MUST remain functional. | MUST | AC-025 |

## 8. Non-functional requirements

| ID | Category | Requirement | Target |
|---|---|---|---|
| NFR-001 | Visual consistency | Every in-scope page MUST use Dashboard-derived tokens, compact hierarchy, flat borders, 6–8px radii, sparse semantic color, and restrained motion. | Dark/light browser review passes for every view |
| NFR-002 | Information density | Pages MUST avoid unnecessary vertical card walls and unused canvases while maintaining readable grouping. | Purpose-specific layouts documented and visually verified |
| NFR-003 | Performance | The redesign MUST add no external asset request, runtime dependency, or API request and SHOULD avoid unnecessary rerenders for local filtering. | No manifest dependency change; request cadence unchanged |
| NFR-004 | Accessibility | All controls MUST remain keyboard-operable with visible focus, accessible names, semantic headings/tables/tabs, selected state, live messaging, and non-color status cues. | Automated assertions and manual review |
| NFR-005 | Responsiveness | Every page MUST avoid page-level horizontal overflow at approximately 320px and 390px; dense regions MAY scroll within labeled containers. | Responsive assertions and mobile visual review |
| NFR-006 | Theme parity | Dark and light themes MUST use semantic tokens and retain readable contrast and complete interaction states. | Both themes inspected for every logical page group |
| NFR-007 | Localization | New or reorganized static copy MUST remain available in all eight shipped locales through the existing catalog/bridge, with protected dynamic content unchanged. | Locale tests pass and representative browser review succeeds |
| NFR-008 | Maintainability | API/state ownership MUST remain in `App.tsx`; extracted presentation MUST use focused typed props and reusable bounded primitives. | `App.tsx` presentation shrinks without a replacement mega-component |
| NFR-009 | Compatibility | React 19, TypeScript, Vite, Vitest, vanilla CSS, current storage keys, view identifiers, API types, and backend contracts MUST remain compatible. | Existing and new tests/build pass |
| NFR-010 | Security/privacy | The redesign MUST NOT expose credentials, bearer tokens, hidden evidence, share passwords, or new personal data, and MUST NOT weaken confirmation/access behavior. | Security/diff review finds no sensitive behavior regression |
| NFR-011 | Reliability | Page-level state organization MUST not lose current form values, selected data, mutation results, object URLs, or notices during normal workflows. | Integration tests cover preserved state transitions |
| NFR-012 | Scope | Dashboard, backend, dependencies, and unrelated code MUST remain unchanged except narrow compatibility fixes justified by shared primitives. | Final diff and graph review show requirement traceability |

## 9. Interfaces and integrations

- Existing API client/types in `frontend/src/api.ts`.
- Existing `App.tsx` state, refresh cycle, handlers, confirmations, and cross-view callbacks.
- Existing `AppShell`, navigation configuration, `StaticCopy`, locale provider/catalog, theme storage, and CSS imports.
- Existing Dashboard components and analytics projections.
- Existing browser routes `/` and `/shared-reports/:token`.

No new external integration is authorized.

## 10. Data model and lifecycle

- No persistent model or API response changes.
- Local filters and tabs derive transient UI state from existing arrays and selected entities.
- Run/report/review page selectors reuse the existing run selection/loading workflow.
- Unknown/null values remain distinct from numeric zero.
- Object URLs continue to be revoked according to existing asset/report lifecycle behavior.
- No UI-only derived data is persisted outside existing theme, locale, and bearer-token mechanisms.

## 11. Security and privacy

- Preserve encrypted endpoint-key behavior and masked/non-returned credentials.
- Preserve session-only bearer-token handling and save/clear semantics.
- Preserve report share password non-persistence and read-only policy.
- Preserve destructive confirmation prompts and dataset/run guards.
- Do not log or render raw secrets, hidden evidence, or new personal data.

## 12. Reliability, recovery, and failure behavior

- Existing API failures continue through the current notice/error path.
- Page presentation may reorganize state but must not swallow exceptions or fabricate success.
- Sparse lists/matrices render direct empty states without breaking sibling sections.
- Rollback is the set of atomic frontend commits; no data recovery or migration is required.

## 13. Observability and operations

- Continue displaying current system, database, disk, queue, run, worker, endpoint, dataset, task, error, latency, cost, and audit signals.
- Do not add telemetry or change backend health semantics.
- Inspect browser console output during each visual checkpoint.

## 14. Compatibility and migration

- No backend, database, schema, environment, deployment, or stored-data migration.
- Preserve theme key `lle-theme`, bearer-token key `lle-api-token`, locale persistence, and state-driven workspace view identifiers.
- Preserve current responsive drawer behavior and standalone shared-report routing.

## 15. Testing requirements

- TDD for shared primitives and each logical page group.
- Integration tests for page navigation, headers, local tabs/filters/selection, preserved forms/actions, sparse states, and accessible semantics.
- Expand current shell, Guide, dataset, run, localization, analysis/comparison/report/review, user/settings, and shared-report coverage as needed.
- Keep all Dashboard tests green and add a compatibility assertion that Dashboard hierarchy remains unchanged.
- Per coherent step: focused tests, `npm run build` when types/components change, `git diff --check`, ownership/security review, and atomic commit.
- Final: `npm test -- --run`, `npm run build`, `python3 -m pytest -q`, final Code Review Graph, full diff, secret scan, and view-by-view browser audit.

## 16. Deployment and rollout

- Existing Vite asset build and deployment path.
- No feature flag or backend rollout.
- Update `CHANGELOG.md` under `Unreleased`.
- Current authorization covers local implementation and commits only; no push or pull request is authorized.

## 17. Dependencies

- Existing React, TypeScript, Vite, Vitest, Testing Library, API client, locale system, and vanilla CSS.
- No new runtime or development dependency is planned.

## 18. Risks and mitigations

- `App.tsx` coupling: extract presentation incrementally while keeping controller behavior and focused integration tests.
- Workflow loss during layout changes: inventory every current field/action and verify callbacks per page group.
- Cross-page selection changes: reuse current selection/loading functions and test Reports/Reviews direct selection.
- CSS regression: scope new primitives, retain Dashboard selectors, and visually inspect both themes after each group.
- Localization drift: keep static source text in the existing catalog/bridge and run parity tests.
- Responsive clipping: use scoped table/tab overflow, responsive split-pane stacking, explicit scroll-width assertions, and mobile screenshots when the browser capability works.
- Browser tooling limitation: retry viewport capability during implementation; document substitute validation and remaining risk if unavailable.
- Superdesign unavailability: use the approved source/browser-grounded design specification and do not claim a canvas draft was produced.

## 19. Assumptions

- The current Dashboard branch commits are the authoritative visual baseline and the new branch correctly builds on them.
- Existing API data is sufficient for every proposed presentation; no new server field is required.
- Local filtering and view-mode state are acceptable frontend-only enhancements because they do not change persisted data or API semantics.
- The uncommitted `.gitignore` change predates this requirement and remains user-owned, unstaged, and unmodified.

## 20. Decision log

| Decision | Recommended choice | Alternatives | Rationale | User confirmation |
|---|---|---|---|---|
| Page heading ownership | Page-owned compact headers for all views | Retain generic shell heading | Matches Dashboard and enables contextual hierarchy/actions | Approved 2026-08-08 |
| Architecture | Typed page components plus bounded shared primitives; `App.tsx` remains controller | Inline-only restyle; full re-platform | Balances visual depth, testability, and behavior preservation | Approved 2026-08-08 |
| Page IA | Purpose-specific list/table/split/inspector/tab structures | Uniform cards/panels | Fits each workflow and avoids superficial CSS-only redesign | Approved 2026-08-08 |
| Visual system | Reuse Dashboard tokens and component language | New style direction | Dashboard is the user's explicit source of truth | Approved 2026-08-08 |
| Dashboard scope | Preserve current Dashboard | Redesign Dashboard with other pages | Explicit user requirement | Approved 2026-08-08 |
| Dependencies | Dependency-free React/CSS/inline SVG | Add component/chart library | Avoids churn and preserves current stack | Approved 2026-08-08 |
| Delivery | Logical page groups with tests and browser checkpoints | One large rewrite | Reduces regression and review risk | Approved 2026-08-08 |

## 21. Open questions

None. Implementation remains gated on written-spec review, implementation-plan approval, and `/goal` activation.

## 22. Acceptance criteria index

| ID | Requirement IDs | Verification method |
|---|---|---|
| AC-001 | FR-001, NFR-012 | Dashboard tests remain green and browser comparison confirms unchanged hierarchy/analytics behavior. |
| AC-002 | FR-002 | Shell tests enumerate every destination and verify drawer, theme, locale, notices, counts, health, and icons. |
| AC-003 | FR-003 | Every workspace page has exactly one page-level heading and no shell duplicate. |
| AC-004 | FR-004, NFR-001, NFR-008 | Primitive tests and source review cover panels, toolbars, tabs, split panes, inspectors, tables, statuses, empty states, and forms. |
| AC-005 | FR-005 | Models integration tests exercise create/edit fields and representative endpoint actions in the new layout. |
| AC-006 | FR-006 | Capability tests verify endpoint selection, probe action, and detected/declared/effective status separation. |
| AC-007 | FR-007 | Workspace tests open all four modes and exercise existing prompt, dataset, suite, and multimodal forms. |
| AC-008 | FR-008 | Benchmark tests verify local filters and existing status/managed operations. |
| AC-009 | FR-009 | Existing dataset tests plus new selection/inspector tests pass for preview/edit/delete/upload/cache states. |
| AC-010 | FR-010 | Suite populated and empty states expose composition, endpoint queue actions, and Workspace navigation. |
| AC-011 | FR-011 | Run tests cover launch/preflight, selection, lifecycle actions, evidence/log/review/judge/report modes, and pagination. |
| AC-012 | FR-012 | Queue tests verify virtualization, local filtering, and priority updates. |
| AC-013 | FR-013 | Worker populated/empty fixtures render diagnostic context and lease table appropriately. |
| AC-014 | FR-014 | Analysis tests switch every dimension, baseline, chart/table evidence, and sparse state. |
| AC-015 | FR-015 | Comparison tests verify selection validation, API call, KPI outcomes, and A/B/difference table. |
| AC-016 | FR-016 | Report tests select a run, generate formats, download, share, and retain password policy. |
| AC-017 | FR-017 | Review tests select run/sample and preserve review, judge, adjudication, comparison, agreement, and pagination actions. |
| AC-018 | FR-018 | Guide test verifies all seven steps and direct navigation actions. |
| AC-019 | FR-019 | User tests cover create form, roles/caps, auth empty state, inventory, audit data, and token notice. |
| AC-020 | FR-020 | Settings tests cover runtime values, locale/theme, token save/clear, refresh, and read-only guidance. |
| AC-021 | FR-021 | Existing shared-report tests remain green and browser review confirms Dashboard-derived styling. |
| AC-022 | FR-022, NFR-003 | Network/API mocks confirm local controls add no API requests or persistence. |
| AC-023 | FR-023 | Group tests cover loading/empty/permission/error/populated states where applicable. |
| AC-024 | FR-024, NFR-005, NFR-007 | Unknown/zero/long-ID fixtures, locale tests, overflow assertions, and representative non-English browser checks pass. |
| AC-025 | FR-025, NFR-004, NFR-009, NFR-010, NFR-011 | Existing interaction suites and targeted new tests pass without accessibility, security, or workflow regressions. |
| AC-026 | NFR-001, NFR-002, NFR-005, NFR-006 | Every view is inspected in dark/light desktop and responsive layouts after its group; defects are iterated before completion. |
| AC-027 | All MUST requirements | Frontend tests/build, backend tests, `git diff --check`, final Code Review Graph, full diff/secret/ownership review, and changelog validation succeed or are explicitly reported. |
