import { cleanup, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import type { Dashboard, Endpoint, EvaluationRun, Task } from "./api";
import { OverviewDashboard } from "./components/OverviewDashboard";
import { LocaleProvider } from "./i18n/LocaleProvider";

afterEach(cleanup);

const dashboard = {
  runs: { active: 1, completed: 3, recent_completed: [{ id: "completed-run", benchmark_id: "release-check", status: "completed", completed_samples: 12, total_samples: 12, completed_at: "2026-07-30T09:00:00Z" }] },
  queue: { pending: 2, leased: 1 },
  workers: { active: 2 },
  endpoints: { available: 1, unavailable: 0, total: 1 },
  datasets: { ready: 1, blocked: 0 },
  quality: { samples: { accuracy: .91, successful: 11, total: 12 }, errors: { api_errors: 1 }, latency_ms: { p95: 320, measured_samples: 12 }, tokens: { total: 2100, input: 1000, output: 1100 } },
  api: { request_error_rate: .02, estimated_cost_by_currency: { USD: .1234 } },
} as unknown as Dashboard;

const activeRun = { id: "active-run", benchmark_id: "release-check", benchmark_version: "1.0", status: "running", completed_samples: 4, total_samples: 12 } as EvaluationRun;
const endpoint = { id: "endpoint-id", status: "available" } as Endpoint;
const task = { id: "task-id", status: "running" } as Task;

function renderOverview(overrides: Partial<React.ComponentProps<typeof OverviewDashboard>> = {}) {
  const props = {
    dashboard,
    endpoints: [endpoint],
    runs: [activeRun],
    tasks: [task],
    onInspectRun: vi.fn(),
    onOpenView: vi.fn(),
    ...overrides,
  };
  render(<LocaleProvider><OverviewDashboard {...props} /></LocaleProvider>);
  return props;
}

describe("OverviewDashboard", () => {
  it("turns current dashboard signals into inspect and navigation actions", async () => {
    const user = userEvent.setup();
    const props = renderOverview();

    expect(screen.getByRole("heading", { name: "Keep every evaluation moving" })).toBeVisible();
    expect(screen.getByText("Active runs")).toBeVisible();
    expect(screen.getByText("Quality at a glance")).toBeVisible();
    expect(screen.getByText("1 verified")).toBeVisible();

    await user.click(screen.getByRole("button", { name: /running release-check/i }));
    await user.click(screen.getAllByRole("button", { name: "Open runs" })[0]);
    await user.click(screen.getByRole("button", { name: "Manage" }));

    expect(props.onInspectRun).toHaveBeenCalledWith("active-run");
    expect(props.onOpenView).toHaveBeenCalledWith("runs");
    expect(props.onOpenView).toHaveBeenCalledWith("models");
  });

  it("keeps the unavailable dashboard state actionable", async () => {
    const user = userEvent.setup();
    const props = renderOverview({ dashboard: null, endpoints: [], runs: [], tasks: [] });

    expect(screen.getByRole("heading", { name: "Operational signals are loading" })).toBeVisible();
    await user.click(screen.getByRole("button", { name: "Configure a model" }));
    await user.click(screen.getByRole("button", { name: "Open runs" }));

    expect(props.onOpenView).toHaveBeenNthCalledWith(1, "models");
    expect(props.onOpenView).toHaveBeenNthCalledWith(2, "runs");
  });
});
