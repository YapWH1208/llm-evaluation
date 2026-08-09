# Implementation goal: redesign remaining evaluation workspace views

## Objective

Implement the approved frontend workspace redesign so every non-Dashboard
frontend view shares the current Dashboard’s developer-tool design language,
while preserving existing API behavior, state flows, localization, themes,
forms, configuration options, and workflows.

## Source of truth

- Requirements: `docs/frontend-workspace-redesign/requirements.md`
- Approved visual specification:
  `docs/superpowers/specs/2026-08-08-frontend-workspace-redesign-design.md`
- Detailed execution plan:
  `docs/superpowers/plans/2026-08-08-frontend-workspace-redesign.md`
- Lifecycle plan: `docs/frontend-workspace-redesign/implementation-plan.md`

## Execution constraints

1. Read the execution-phase workflow and use test-driven development before
   each production-code change.
2. Work on `agent/frontend-workspace-redesign`; do not push, open a pull
   request, merge, or alter remotes without new user authorization.
3. Preserve the uncommitted `.gitignore` change as user-owned. Do not stage it.
4. Keep `App.tsx` as controller and move only view presentation into typed,
   focused components. Do not change backend APIs, data models, request
   payloads, localization behavior, or persisted configuration semantics.
5. Treat the existing Dashboard as a protected visual reference. New CSS must
   be scoped so Dashboard appearance remains unchanged.
6. Follow the detailed checkbox plan in order. Make the specified small,
   validated local commits; do not combine page groups without a documented
   reason.
7. After each logical group, run the frontend test suite and build, then use
   the in-app browser to inspect the appropriate views in light and dark
   themes. Retry the browser responsive-viewport capability and document a
   substitute check if it remains unavailable.
8. Before completion, run the full frontend suite/build, backend suite,
   final Code Review Graph checks, complete-diff review, staged secret scan,
   and final git-status review. Update `CHANGELOG.md` under `Unreleased` for
   the user-visible workspace redesign.
9. Stop and ask for direction if a required design choice materially conflicts
   with a preserved workflow or requires backend/API changes.

## Completion evidence

Report the requirement and lifecycle phase, skill references used, goal status,
branch, Code Review Graph findings (including manual fallback only if necessary),
commits, changed components, browser/theme validation, automated validation,
unrun checks and risks, and confirmation that no user-owned files were committed.
