import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { EvaluationRun, Task } from "./api";
import { QueuePage, RunsPage, WorkersPage } from "./components/pages/OperationsPages";
import { LocaleProvider } from "./i18n/LocaleProvider";

const firstRun = {
  id: "run-1",
  benchmark_id: "math-check",
  benchmark_version: "1",
  completed_samples: 4,
  total_samples: 10,
  status: "running",
  created_at: "2026-08-08T12:00:00Z",
} as EvaluationRun;

const secondRun = {
  ...firstRun,
  id: "run-2",
  benchmark_id: "code-check",
  status: "completed",
} as EvaluationRun;

const pendingTask = {
  id: "task-1",
  task_type: "evaluate_sample",
  run_id: "run-1",
  parent_task_id: null,
  status: "pending",
  priority: 100,
  attempt_count: 0,
  leased_by: null,
  lease_expires_at: null,
  next_retry_at: null,
  heartbeat_at: null,
  created_at: "2026-08-08T12:00:00Z",
  updated_at: "2026-08-08T12:00:00Z",
  payload: {},
} as Task;

const runningTask = {
  ...pendingTask,
  id: "task-2",
  status: "running",
  leased_by: "worker-alpha",
} as Task;

function renderOperationsPage(page: React.ReactNode) {
  return render(<LocaleProvider>{page}</LocaleProvider>);
}

describe("operations workspace pages", () => {
  it("keeps the selected run visible in the inventory and routes a new selection to the existing controller", async () => {
    const user = userEvent.setup();
    const onSelect = vi.fn();
    renderOperationsPage(<RunsPage inspector={<p>Run inspector evidence</p>} launcher={<p>Launch controls</p>} onSelect={onSelect} preflight={<p>Preflight controls</p>} renderActions={() => <button type="button">Run action</button>} runs={[firstRun, secondRun]} selectedRunId={firstRun.id} />);

    expect(screen.getByRole("button", { name: /math-check v1/i })).toHaveAttribute("aria-pressed", "true");
    await user.click(screen.getByRole("button", { name: /code-check v1/i }));

    expect(onSelect).toHaveBeenCalledWith(secondRun.id);
    expect(screen.getByText("Run inspector evidence")).toBeVisible();
  });

  it("filters the virtual task queue locally while retaining editable priority controls", async () => {
    const user = userEvent.setup();
    const onPriority = vi.fn().mockResolvedValue(undefined);
    renderOperationsPage(<QueuePage busy={null} onPriority={onPriority} tasks={[pendingTask, runningTask]} />);

    await user.selectOptions(screen.getByLabelText("Task status"), "pending");

    expect(screen.getByText("evaluate_sample")).toBeVisible();
    expect(screen.queryByText("worker-alpha")).not.toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Raise priority for evaluate_sample" }));
    expect(onPriority).toHaveBeenCalledWith(pendingTask, 110);
  });

  it("shows active worker leases and offers queue diagnostics when no lease is active", async () => {
    const user = userEvent.setup();
    const onOpenQueue = vi.fn();
    const { rerender } = renderOperationsPage(<WorkersPage onOpenQueue={onOpenQueue} systemHealth={null} tasks={[runningTask]} />);

    expect(screen.getByText("worker-alpha")).toBeVisible();
    expect(screen.getByText("1 active lease")).toBeVisible();

    rerender(<LocaleProvider><WorkersPage onOpenQueue={onOpenQueue} systemHealth={{ queue: { active: 0, pending: 3 } } as never} tasks={[pendingTask]} /></LocaleProvider>);
    expect(screen.getByText("No active worker leases")).toBeVisible();
    expect(screen.getByText("3 pending tasks · 0 active tasks")).toBeVisible();
    await user.click(screen.getByRole("button", { name: "Open task queue" }));
    expect(onOpenQueue).toHaveBeenCalledTimes(1);
  });
});
