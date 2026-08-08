# Frontend workspace redesign implementation plan

## Purpose and approval boundary

This plan implements the approved requirements in
[`requirements.md`](requirements.md) and the approved visual direction in
[`../superpowers/specs/2026-08-08-frontend-workspace-redesign-design.md`](../superpowers/specs/2026-08-08-frontend-workspace-redesign-design.md).
It deliberately leaves the current Dashboard/Overview visual implementation as
the reference rather than replacing it.

Production implementation starts only after this plan is approved and the
prepared implementation goal is activated.  The work is local-only: it creates
tested local commits but does not push a branch or create a pull request.

## Starting state and constraints

- Branch: `agent/frontend-workspace-redesign`, based on the existing Dashboard
  redesign work.
- Existing user-owned change: `.gitignore` is modified and must remain outside
  every task commit.
- Frontend is React 19 + Vite + TypeScript. `App.tsx` owns routing-like view
  state, fetching, form state, callbacks, and the static-copy bridge.
- All UI copy must retain the typed catalog / `StaticCopy` localization model.
- No backend endpoints, API payloads, persistence, or workflow transitions may
  change.
- `AppShell`, `OverviewDashboard`, `workspace-theme.css`, and `dashboard.css`
  are the visual baseline.  Dashboard-specific structure and styles are not to
  be rebuilt.
- New page styling is scoped under workspace-page classes.  The legacy generic
  CSS is removed only after repository search demonstrates it has no remaining
  consumer.

## Architecture decision

`App.tsx` remains the stateful controller.  It continues to create the form
state and pass the existing callbacks, data, loading state, and error state.
The presentation branches are extracted to focused pages that receive typed
props.  This reduces the documented App controller blast radius without
introducing a second routing or data-fetching layer.

The reusable presentation layer is:

| Concern | Planned location | Responsibility |
| --- | --- | --- |
| Page title / action region | `components/workspace/PageHeader.tsx` | One compact header with title, contextual status, and primary/secondary actions. |
| Surface / panel layout | `components/workspace/WorkspacePanel.tsx` | Dashboard-aligned panel variants, headings, toolbars, and empty-state framing. |
| Local page tabs | `components/workspace/WorkspaceTabs.tsx` | Keyboard-accessible tabs using button semantics and `aria-selected`. |
| Page system styles | `components/workspace/workspace-pages.css` | Scoped grid, split-pane, table, inspector, form, responsive, and contrast rules. |
| Form types and defaults | `workspace/forms.ts` | Explicit form interfaces and initial-state factories extracted from App-only inferred state. |
| Domain pages | `components/pages/*.tsx` | Presentational page groups with typed, callback-based props. |

Each domain page can retain an existing specialized helper (`RunDetail`,
`JudgeWorkflow`, `AnalysisView`, `ReportsTable`, `SharedReportPage`, and
similar) while placing it in a clearer page-owned shell.  That preserves the
tested behavior of the existing workflow helpers.

## Requirement coverage and implementation order

| Work package | Views | Principal requirements |
| --- | --- | --- |
| 1. Foundation | App shell and shared primitives | FR-001–004, FR-022–025, NFR-001–012 |
| 2. Configure | Guide, Models, Capabilities | FR-005–007 |
| 3. Setup | Workspace | FR-008 |
| 4. Catalogs | Benchmarks, Datasets, Suites | FR-009–011 |
| 5. Operations | Runs, Queue, Workers | FR-012–014 |
| 6. Insights | Analysis, Compare | FR-015–016 |
| 7. Review and reports | Reports, Reviews | FR-017–018 |
| 8. Administration | Users, Settings, shared report | FR-019–021 |
| 9. Hardening | all non-Dashboard views | FR-001–025, NFR-001–012, AC-001–027 |

The detailed, task-by-task execution checklist is in
[`../superpowers/plans/2026-08-08-frontend-workspace-redesign.md`](../superpowers/plans/2026-08-08-frontend-workspace-redesign.md).

## Verification strategy

Every work package uses test-first page coverage where the extracted component
has deterministic behavior, followed by the existing frontend suite:

```bash
cd frontend
npm test -- --run
npm run build
```

The final validation also runs:

```bash
python3 -m pytest -q
code-review-graph update
code-review-graph detect-changes --brief
code-review-graph impact --files frontend/src/App.tsx --depth 3 --max-results 30
```

Browser validation will inspect the Dashboard baseline and each redesigned view
in both themes after each logical group.  The browser viewport override failed
in the discovery session; implementation will retry it.  If it remains
unavailable, the substituted evidence is browser desktop inspection plus
automated narrow-container overflow assertions and CSS media-query review; the
limitation will be recorded in the completion report.

## Risks and controls

| Risk | Control |
| --- | --- |
| Presentation extraction accidentally changes request behavior | Keep API calls, effects, mutable state, and action handlers in `App.tsx`; pass callbacks through unchanged; retain existing workflow helpers. |
| Static text breaks locale parity | Add new keys to every locale or route fixed copy through the established `StaticCopy` bridge; run `locales.test.ts`. |
| Dashboard styling regresses through global selectors | Scope all new selectors to `.workspace-page` / page-specific roots and inspect Overview in light and dark after each CSS package. |
| A very long Workspace page becomes hard to use | Use local tabs while preserving all form controls, defaults, and submit actions in the DOM of their tab pane. |
| Repeated old CSS cleanup reaches unrelated UI | Search before deletion; defer removal unless all consumers are proven migrated. |
| Responsive browser tooling remains constrained | Retry the browser viewport capability; add narrow-width test / review evidence and do not claim a device visual assertion that could not run. |

## Commit plan

1. `test: cover workspace presentation primitives`
2. `feat: add workspace page primitives`
3. `feat: redesign guide and endpoint configuration`
4. `feat: redesign workspace setup flow`
5. `feat: redesign benchmark dataset and suite catalogs`
6. `feat: redesign run operations workspace`
7. `feat: redesign analysis and comparison views`
8. `feat: redesign reporting review and administration views`
9. `fix: refine responsive workspace presentation`
10. `docs: document workspace redesign`

Commits are made only after their relevant test/build checks pass and only
intended files are selectively staged.  The pre-existing `.gitignore` change
will not be staged, restored, reformatted, or committed.
