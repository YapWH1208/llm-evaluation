# Frontend Workspace Redesign Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Bring every non-Dashboard frontend view to the current Dashboard’s compact, high-signal evaluation-workspace visual language without changing product behavior.

**Architecture:** Preserve `App.tsx` as the controller for API calls, data, state, side effects, and handlers. Extract reusable presentation primitives and focused domain pages with typed props. Page CSS is scoped to a new workspace-page layer that consumes the established theme tokens; the Dashboard remains a protected visual reference.

**Tech Stack:** React 19, TypeScript, Vite, Vitest, Testing Library, existing typed i18n catalog, existing browser automation, Code Review Graph.

## Global Constraints

- The existing Dashboard/Overview implementation is the visual source of truth; do not redesign its components or alter its layout deliberately.
- Preserve current API requests, callback wiring, local storage behavior, form fields/defaults, validation, data rendering, visibility conditions, and routing/view state.
- Keep `App.tsx` responsible for state and effects. Components created here are presentation-only and receive data/callbacks through typed props.
- Route static user-visible text through the existing typed catalog or `StaticCopy` bridge. Never send API/user/evidence values through static translation helpers.
- Do not stage or modify the pre-existing `.gitignore` change.
- Do not add dependencies, backend changes, database changes, CI changes, or remote Git operations.
- Make CSS opt-in and scoped. Search for usage before deleting legacy generic rules.
- Every task ends with its scoped test, the full frontend test suite, and a production build. Use browser inspection after each page group.

## Known starting evidence

- `npm test -- --run` passed: 14 files, 47 tests.
- `npm run build` passed at the start of planning.
- Initial Code Review Graph: 1,423 nodes, 18,722 edges, 120 files; `App.tsx` has a high downstream presentation blast radius (752 nodes at depth 3).
- In-app browser reviewed Dashboard and every target page in desktop light/dark. Viewport override did not take effect and must be retried during implementation.

---

### Task 1: Establish test seams and shared page primitives

**Requirements:** FR-001–004, FR-022–025; NFR-001–012; AC-001–004, AC-022–027.

**Files:**

- Create: `frontend/src/components/workspace/PageHeader.tsx`
- Create: `frontend/src/components/workspace/WorkspacePanel.tsx`
- Create: `frontend/src/components/workspace/WorkspaceTabs.tsx`
- Create: `frontend/src/components/workspace/workspace-pages.css`
- Create: `frontend/src/components/workspace/workspace-primitives.test.tsx`
- Modify: `frontend/src/components/AppShell.tsx`
- Modify: `frontend/src/components/app-shell.test.tsx`
- Modify: `frontend/src/App.tsx`

- [x] **Step 1: Write failing tests for the reusable primitives and page-owned heading contract.**

  Test one page header exposes the visible title plus its action region; test tab buttons advertise selection with `aria-selected` and invoke the supplied setter; test a panel’s label is programmatically associated with its content. Update the existing shell test to assert the non-Dashboard workspace no longer emits the generic duplicate heading.

  ```tsx
  it('marks the active workspace tab and reports changes', async () => {
    const onChange = vi.fn();
    render(<WorkspaceTabs value="inputs" onChange={onChange} tabs={[{ id: 'inputs', label: 'Inputs' }, { id: 'outputs', label: 'Outputs' }]} />);
    expect(screen.getByRole('tab', { name: 'Inputs' })).toHaveAttribute('aria-selected', 'true');
    await userEvent.click(screen.getByRole('tab', { name: 'Outputs' }));
    expect(onChange).toHaveBeenCalledWith('outputs');
  });
  ```

  Run: `cd frontend && npm test -- --run src/components/workspace/workspace-primitives.test.tsx src/components/app-shell.test.tsx`
  Expected: failure because the primitives and shell contract do not exist.

- [x] **Step 2: Implement accessible, narrow primitives that reuse Dashboard tokens.**

  Implement `PageHeader` with exactly one `h1`, optional eyebrow/status, and action slots. Implement `WorkspacePanel` with semantic heading markup and class variants (`default`, `muted`, `inset`). Implement `WorkspaceTabs` as a roving, button-based tab list with keyboard arrow/Home/End handling only if the component controls a visible pane; otherwise retain simple selected buttons and correct ARIA state. Add only scoped `.workspace-page` CSS, using `--surface`, `--raised`, `--border`, `--text`, `--muted`, `--primary`, the Dashboard radius, and its dense spacing rhythm.

  Update `AppShell` so non-Dashboard views rely on page-owned headings rather than its old generic heading. Keep the header/rail/navigation mechanics and Dashboard exception intact. Import page CSS once from the new primitive entry point or App, not from Dashboard CSS.

- [x] **Step 3: Verify primitives and protected Dashboard behavior.**

  Run:

  ```bash
  cd frontend
  npm test -- --run src/components/workspace/workspace-primitives.test.tsx src/components/app-shell.test.tsx
  npm test -- --run
  npm run build
  ```

  In the browser inspect Dashboard light and dark after navigating away and back. Confirm: one Dashboard heading, no header overlap, unchanged five-cell KPI cadence, panels retain their original border/radius behavior, and narrow rail CSS is not modified.

- [x] **Step 4: Review and commit the foundation.**

  Review `git diff --check`, `git diff -- frontend/src/App.tsx frontend/src/components/AppShell.tsx`, and selective status. Stage only Task 1 files. Commit:

  ```text
  test: cover workspace presentation primitives
  ```

  If tests and implementation are both included, use the single cohesive commit instead:

  ```text
  feat: add workspace page primitives
  ```

### Task 2: Redesign Guide, Models, and Capabilities

**Requirements:** FR-005–007; AC-005–007, AC-022–025.

**Files:**

- Create: `frontend/src/components/pages/GuidePage.tsx`
- Create: `frontend/src/components/pages/EndpointPages.tsx`
- Create: `frontend/src/configure-pages.test.tsx`
- Modify: `frontend/src/App.tsx`
- Modify: `frontend/src/i18n/operationalCopy.ts` or `frontend/src/i18n/catalog.ts` and all locale entries only if new fixed labels are needed

- [x] **Step 1: Capture the current workflows in failing render tests.**

  Test Guide renders its staged evaluation workflow and every existing route action. Test Models renders the existing endpoint inventory/form inputs, validation feedback, and save/cancel callback pathways. Test Capabilities keeps its model selector and rendered capability result state. Keep tests at the page boundary with mock props rather than mocking fetch inside the new components.

  ```tsx
  it('keeps model save wiring and endpoint fields available', async () => {
    const onSave = vi.fn((event) => event.preventDefault());
    render(<ModelsPage endpoint={endpoint} onChange={onChange} onSubmit={onSave} endpoints={[savedEndpoint]} />);
    await userEvent.type(screen.getByLabelText('Endpoint name'), ' staging');
    await userEvent.click(screen.getByRole('button', { name: /save endpoint/i }));
    expect(onChange).toHaveBeenCalled();
    expect(onSave).toHaveBeenCalled();
  });
  ```

  Run the focused test; expect it to fail before the extracted page exists.

- [x] **Step 2: Extract typed presentation pages without changing controller behavior.**

  Move inferred endpoint form shapes and initialization into `frontend/src/workspace/forms.ts` if this makes prop boundaries explicit; preserve property names and defaults. Build:

  - `GuidePage`: compact page header, a numbered workflow/timeline, outcome-oriented cards, direct actions that invoke the existing view setter.
  - `ModelsPage`: inventory plus editor split pane. Keep all endpoint provider/auth/options fields, errors, submit state, destructive controls, and no-data behavior.
  - `CapabilitiesPage`: selector on the left / result inspector on the right on wide screens; stacked responsive layout at small widths; retain every existing chart/table/content path.

  Use `PageHeader` + `WorkspacePanel` and descriptive page-root classes. Preserve `StaticCopy` treatment around existing static strings.

- [x] **Step 3: Verify both themes and visible workflow paths.**

  Run focused tests, full frontend tests, and build. Browser inspect Guide, Models (empty and configured state if available), and Capabilities in light/dark. Confirm endpoint form controls remain labeled, Guide action affordances are keyboard reachable, status/error messages remain visible, and no full-height blank panel displaces the active work.

- [x] **Step 4: Commit the configure group.**

  Selectively stage Task 2 production, test, and required locale files; inspect staged diff and secret scan. Commit:

  ```text
  feat: redesign guide and endpoint configuration
  ```

### Task 3: Redesign Workspace setup as a tabbed workbench

**Requirements:** FR-008; AC-008, AC-022–025.

**Files:**

- Create: `frontend/src/components/pages/WorkspaceSetupPage.tsx`
- Create: `frontend/src/workspace-setup.test.tsx`
- Modify: `frontend/src/App.tsx`
- Modify: `frontend/src/workspace/forms.ts`

- [x] **Step 1: Write failing tab/workflow preservation tests.**

  Cover inputs, judgments, multimodal setup, and catalog/launch states. Assert switching tabs does not reset a caller-owned form object and that submit controls still call the original handlers. Test validation/error summaries remain associated with their inputs.

- [x] **Step 2: Extract the Workspace page into four local workbench tabs.**

  Use stable IDs (`inputs`, `judgments`, `multimodal`, `catalog`) and the existing current view selection. Place each existing form and catalog workflow inside its relevant pane; do not omit a conditional section because it is less common. On desktop, place concise progress/status context beside tab controls and use a secondary inspector where existing contextual help/data exists. On narrow screens, stack form sections and let the tab strip scroll horizontally rather than clipping controls.

- [x] **Step 3: Validate long-form usability.**

  Run focused/full frontend tests and build. Browser inspect the full Workspace page in both themes: tab switch, each form’s primary action, catalogue transition, validation state, and scroll alignment. Retry mobile viewport control; if unavailable, assert the narrow breakpoint has no fixed width/overflow trap with a DOM/CSS test and record the evidence.

- [x] **Step 4: Commit the Workspace workbench.**

  Commit after review:

  ```text
  feat: redesign workspace setup flow
  ```

### Task 4: Redesign Benchmarks, Datasets, and Suites as catalog workspaces

**Requirements:** FR-009–011; AC-009–011, AC-022–025.

**Files:**

- Create: `frontend/src/components/pages/CatalogPages.tsx`
- Create: `frontend/src/catalog-pages.test.tsx`
- Modify: `frontend/src/App.tsx`
- Modify: `frontend/src/workspace/forms.ts` when existing inferred dataset/suite form shapes need types

- [x] **Step 1: Write failing inventory and action tests.**

  Test benchmark selection/filter controls retain the currently loaded data and action callbacks. Test Datasets exposes create/import/selection actions, preserves tags/metadata/evidence, and renders an inspector for the selected dataset without hiding the list. Test Suites offers a create action from its empty state and keeps any selected suite/run action.

- [x] **Step 2: Implement catalog-specific hierarchy.**

  - `BenchmarksPage`: page toolbar with current filters/actions, dense comparison table, visible loading/empty/error treatment, and drill-in link/button paths.
  - `DatasetsPage`: inventory list/table at left, selected dataset inspector at right, action bar above. Preserve current cards’ content and every import/edit/delete flow.
  - `SuitesPage`: dense suite inventory with run/readiness metadata, creation action in header and empty state, and a contextual inspector or run queue area where existing state supports it.

  Reuse semantic table markup where the content is tabular. Make long data cell values wrap or truncate with an accessible title/expanded inspector; do not rely on fixed-width overflow.

- [x] **Step 3: Browser-check dense data and empty states.**

  Run focused/full frontend tests and build. Inspect populated and empty paths where local data permits, light/dark themes, table header alignment, action priority, selection contrast, and narrow stacking. Verify no dataset metadata or suite action disappeared during extraction.

- [x] **Step 4: Commit catalog pages.**

  ```text
  feat: redesign benchmark dataset and suite catalogs
  ```

### Task 5: Redesign Runs, Queue, and Workers operations

**Requirements:** FR-012–014; AC-012–014, AC-022–025.

**Files:**

- Create: `frontend/src/components/pages/OperationsPages.tsx`
- Create: `frontend/src/operations-pages.test.tsx`
- Modify: `frontend/src/App.tsx`

- [x] **Step 1: Write failing tests for operation selection and actions.**

  Test Runs keeps selected-run state and invokes the existing refresh/cancel/retry/navigation callbacks through the new list/inspector layout. Test Queue preserves priority/status columns and operational controls. Test Workers retains all worker diagnostics and shows an explanatory diagnostic empty state when no worker is registered.

- [x] **Step 2: Implement the operations workspace.**

  - `RunsPage`: compact run list on the left and the existing `RunDetail` in an inspector on the right; responsive stack at small widths.
  - `QueuePage`: operational toolbar / quick filter region above the existing dense queue table. Preserve refresh, concurrency, cancellation, sorting, and status semantics.
  - `WorkersPage`: health-oriented table/cards with concise capacity/state cues and a diagnostic empty state that directs the user to the existing setup workflow without inventing a backend action.

  Ensure destructive/cancel controls retain their existing confirmation/disabled behavior and use visual danger treatment only as an additional cue.

- [x] **Step 3: Validate action safety and operations density.**

  Run focused/full tests and build. Browser inspect a live or seeded Runs state, Queue, and Workers in both themes. Verify run detail never appears without a corresponding selected list item, status colors have text/icon context, controls remain reachable by keyboard, and tables do not collapse into unreadable card walls.

- [ ] **Step 4: Commit operations.**

  ```text
  feat: redesign run operations workspace
  ```

### Task 6: Redesign Analysis and Compare as investigation workflows

**Requirements:** FR-015–016; AC-015–016, AC-022–025.

**Files:**

- Create: `frontend/src/components/pages/InsightsPages.tsx`
- Create: `frontend/src/insights-pages.test.tsx`
- Modify: `frontend/src/App.tsx`

- [ ] **Step 1: Write failing tests for dimension and comparison selection.**

  Test Analysis exposes all existing dimensions/statistical sections through tabs or a segmented control and preserves the current selected/available summary. Test Compare retains both source selections, validation/error behavior, submit callback, and result presentation states.

- [ ] **Step 2: Compose page-specific investigation layouts.**

  - `AnalysisPage`: page header and run context, local dimension switcher, summary metrics/plot section, and synchronized breakdown table. Existing analysis calculations and helper components remain unchanged.
  - `ComparePage`: side-by-side source selection surface with an explicit comparison action, followed by empty/loading/error/result states. Keep all existing comparison fields and result values; only restructure their framing and visual hierarchy.

  Do not introduce chart libraries or client-side derived calculations. Make every visual summary available in a textual/table representation already supplied by the app.

- [ ] **Step 3: Verify insights and comparable data states.**

  Run focused/full tests and build. Browser inspect Analysis and Compare in light/dark. Verify tab focus visibility, active-state contrast, result alignment, empty directions, and no visual-only information that lacks text context.

- [ ] **Step 4: Commit insights pages.**

  ```text
  feat: redesign analysis and comparison views
  ```

### Task 7: Redesign Reports, Human review, Users, Settings, and shared reports

**Requirements:** FR-017–021; AC-017–021, AC-022–025.

**Files:**

- Create: `frontend/src/components/pages/SystemPages.tsx`
- Create: `frontend/src/system-pages.test.tsx`
- Modify: `frontend/src/App.tsx`
- Modify: `frontend/src/shared-report.test.tsx`
- Modify: `frontend/src/i18n/operationalCopy.ts` or `frontend/src/i18n/catalog.ts` and all locale entries only when necessary

- [ ] **Step 1: Write failing context-selection and administration tests.**

  Test Reports exposes an on-page run selector then keeps `ReportsTable` export/share paths intact. Test Reviews has on-page run/sample selection and preserves `JudgeWorkflow` submissions/validation. Test Users retains user creation, roles, update/delete controls, and audit content. Test Settings keeps every configuration input, secret masking/help, save/reset behavior, and status message. Keep the shared-report discovery token flow and all loading/error/not-found/success states under test.

- [ ] **Step 2: Extract context-aware reporting/review pages.**

  - `ReportsPage`: run-context selector above the existing report table and share/export actions; clear no-run/no-report states.
  - `ReviewsPage`: run/sample context bar above existing review/editor workflow and evidence inspector.
  - `UsersPage`: user inventory, role/status summary, creator/editor side panel, and retained audit information.
  - `SettingsPage`: category navigation or groups (application, storage, execution, security) while retaining every existing option in its correct form/control.
  - `SharedReportPage`: retain standalone discovery-token behavior; refine panel density, headings, status hierarchy, and theme styling without bringing authenticated navigation into the public page.

- [ ] **Step 3: Run a complete administration/report workflow check.**

  Run focused/full frontend tests and build. Browser inspect Reports, Reviews, Users, Settings, and `/shared-reports/discovery-token` in both themes. Confirm hidden-prior-selection problems are resolved by visible selection controls, forms retain labels and help/error text, and shared report needs no authenticated shell.

- [ ] **Step 4: Commit the reporting and administration group.**

  ```text
  feat: redesign reporting review and administration views
  ```

### Task 8: Responsive, theme, accessibility, localization, and final cleanup

**Requirements:** FR-001–025; NFR-001–012; AC-001–027.

**Files:**

- Modify: `frontend/src/components/workspace/workspace-pages.css`
- Modify: `frontend/src/workspace-theme.css` only for missing reusable tokens
- Modify: `frontend/src/styles.css` only for proven-unused generic rules
- Modify: `frontend/src/i18n/catalog.ts`, locale files, and `frontend/src/i18n/locales.test.ts` if copy was added
- Modify: `frontend/src/CHANGELOG.md` or root `CHANGELOG.md` according to actual repository location
- Create or modify narrow/responsive tests adjacent to the affected page components

- [ ] **Step 1: Add failing regression tests for the final cross-cutting contract.**

  Add coverage for a narrow class/container or layout modifier where it prevents a specific fixed-width regression. Add locale-parity coverage only through the existing test conventions. Include one regression test that confirms Dashboard uses its protected Overview structure rather than the generic workspace root.

- [ ] **Step 2: Apply measured refinements.**

  Inspect browser findings and correct only observed spacing, alignment, density, contrast, horizontal overflow, focus visibility, and reduced-motion defects. Preserve the theme variable system; do not add hardcoded light/dark color duplicates when a semantic token works. Before removing old CSS, run `rg` for every candidate selector and leave it in place if any consumer remains.

- [ ] **Step 3: Run full technical and visual verification.**

  ```bash
  cd frontend
  npm test -- --run
  npm run build
  cd ..
  python3 -m pytest -q
  code-review-graph update
  code-review-graph detect-changes --brief
  code-review-graph impact --files frontend/src/App.tsx --depth 3 --max-results 30
  git diff --check
  git status --short --branch
  ```

  Browser-check every listed view plus the Dashboard reference in light/dark:

  `Overview, Guide, Models, Capabilities, Workspace, Benchmarks, Datasets, Suites, Runs, Queue, Workers, Analysis, Compare, Reports, Reviews, Users, Settings, Shared Report`.

  Retry the mobile viewport capability. If unavailable, document the concrete failed capability and substitute narrow-layout verification rather than claiming device screenshot coverage.

- [ ] **Step 4: Update user-facing change record and create final commits.**

  Add a concise Unreleased CHANGELOG entry covering the unified workspace visual redesign. Selectively stage only task-owned files, scan staged diffs for credentials/secrets, and commit:

  ```text
  fix: refine responsive workspace presentation
  docs: document workspace redesign
  ```

  Use two commits when the code refinement and documentation are separable. Do not commit `.gitignore`.

## Final handoff checklist

- [ ] Confirm every target view is represented by a page component or intentionally retained focused helper inside a redesigned page shell.
- [ ] Confirm Dashboard remains visually and structurally protected.
- [ ] Confirm API requests, callbacks, form fields/defaults, and localization behavior did not change.
- [ ] Confirm accessibility basics: one `h1` per page, semantic form labels, tab state/keyboard access, focus visibility, contextual status text, and non-color state cues.
- [ ] Confirm theme variables drive light/dark behavior and tables/forms/inspectors remain readable.
- [ ] Confirm browser theme inspection after every logical group and explicit responsive evidence or documented viewport limitation.
- [ ] Confirm frontend tests, build, backend tests, final Code Review Graph, diff check, and status review have actual recorded results.
- [ ] Confirm only intended files are committed; `.gitignore` remains user-owned and uncommitted.
- [ ] Prepare a concise completion report with lifecycle, plan/goal status, commit list, Code Review Graph findings, validation evidence, limitations, and no remote publication.
