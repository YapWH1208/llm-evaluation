import { cleanup, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import { AuditEvent, EvaluationRun, SampleAttempt, SystemHealth, User } from "./api";
import { ReportsPage, ReviewsPage, SettingsPage, UsersPage } from "./components/pages/SystemPages";
import { LocaleProvider } from "./i18n/LocaleProvider";

afterEach(cleanup);

const run = {
  id: "run-alpha-1234",
  benchmark_id: "math-check",
  benchmark_version: "1",
  status: "completed",
  completed_at: "2026-08-08T12:00:00Z",
} as EvaluationRun;

const secondRun = { ...run, id: "run-beta-5678", benchmark_id: "science-check" } as EvaluationRun;

const attempt = { id: "attempt-1", sample_id: "sample-7", attempt_number: 1, status: "succeeded" } as SampleAttempt;

function renderPage(page: React.ReactNode) {
  return render(<LocaleProvider>{page}</LocaleProvider>);
}

describe("system workspace pages", () => {
  it("keeps report generation and the artifact table beneath a visible source-run selector", async () => {
    const user = userEvent.setup();
    const onSelectRun = vi.fn();
    const onGenerateReport = vi.fn();
    renderPage(<ReportsPage completedRuns={[run, secondRun]} onGenerateReport={onGenerateReport} onRelatedRunChange={vi.fn()} onReportTypeChange={vi.fn()} onSelectRun={onSelectRun} relatedRunId="" reportArtifacts={<div>Report artifact inventory</div>} reportType="single_model" runs={[run, secondRun]} selectedRun={run} />);

    await user.selectOptions(screen.getByLabelText("Report source run"), secondRun.id);
    await user.click(screen.getByRole("button", { name: "Generate HTML" }));

    expect(onSelectRun).toHaveBeenCalledWith(secondRun.id);
    expect(onGenerateReport).toHaveBeenCalledWith(run.id, "html");
    expect(screen.getByText("Report artifact inventory")).toBeVisible();
  });

  it("keeps review run and sample selection in the workflow context bar", async () => {
    const user = userEvent.setup();
    const onSelectRun = vi.fn();
    const onSelectAttempt = vi.fn();
    renderPage(<ReviewsPage attempts={[attempt]} onSelectAttempt={onSelectAttempt} onSelectRun={onSelectRun} reviewDetail={<div>Judge and review workflow</div>} runs={[run, secondRun]} selectedAttempt={attempt} selectedRun={run} />);

    await user.selectOptions(screen.getByLabelText("Review run"), secondRun.id);
    await user.selectOptions(screen.getByLabelText("Review sample"), attempt.id);

    expect(onSelectRun).toHaveBeenCalledWith(secondRun.id);
    expect(onSelectAttempt).toHaveBeenCalledWith(attempt);
    expect(screen.getByText("Judge and review workflow")).toBeVisible();
  });

  it("keeps the user creation form, role choices, inventory, and audit evidence together", () => {
    const user = { id: "user-1", display_name: "Ada", email: "ada@example.test", role: "reviewer", status: "active", max_concurrency: 4, created_at: "2026-08-08T12:00:00Z" } as User;
    const audit = { id: "audit-1", action: "user.created", entity_type: "user", entity_id: user.id, actor_id: "admin", details: null, created_at: "2026-08-08T12:00:00Z" } as AuditEvent;
    renderPage(<UsersPage auditEvents={[audit]} busy={null} form={{ email: "", display_name: "", role: "viewer", max_concurrency: "" }} onFormChange={vi.fn()} onSubmit={vi.fn()} users={[user]} />);

    expect(screen.getByRole("heading", { name: "Create user" })).toBeVisible();
    expect(screen.getByRole("option", { name: "Reviewer" })).toBeVisible();
    expect(screen.getByText("Ada")).toBeVisible();
    expect(screen.getByText("user.created")).toBeVisible();
  });

  it("keeps settings categories, masked token controls, and save/reset actions visible", async () => {
    const user = userEvent.setup();
    const health = { status: "ok", database: "sqlite", schema_version: 3, database_connected: true, disk: { available_bytes: 30, total_bytes: 100 }, queue: { pending: 2, active: 1 } } as SystemHealth;
    const onSaveToken = vi.fn();
    const onClearToken = vi.fn();
    const onToggleTheme = vi.fn();
    renderPage(<SettingsPage apiToken="" locale="en" onApiTokenChange={vi.fn()} onClearToken={onClearToken} onLocaleChange={vi.fn()} onSaveToken={onSaveToken} onToggleTheme={onToggleTheme} systemHealth={health} theme="dark" />);

    expect(screen.getByRole("heading", { name: "System settings" })).toBeVisible();
    expect(screen.getByLabelText("Administrator or user bearer token")).toHaveAttribute("type", "password");
    await user.click(screen.getByRole("button", { name: "Save token" }));
    await user.click(screen.getByRole("button", { name: "Clear token" }));
    await user.click(screen.getByRole("button", { name: "Switch to light mode" }));

    expect(onSaveToken).toHaveBeenCalledOnce();
    expect(onClearToken).toHaveBeenCalledOnce();
    expect(onToggleTheme).toHaveBeenCalledOnce();
  });
});
