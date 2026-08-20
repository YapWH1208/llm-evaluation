import { cleanup, render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import type { AnalyticsMatrix, Dashboard, Endpoint, EvaluationRun, SystemHealth, Task } from "./shared/api";
import { OverviewDashboard } from "./components/OverviewDashboard";
import { LocaleProvider } from "./i18n/LocaleProvider";

afterEach(cleanup);

const dashboard: Dashboard = {
  runs: { active: 1, completed: 3, recent_completed: [{ id: "completed-run", display_name: "evaluation-model_release-check_20260730T090000Z", benchmark_id: "release-check", status: "completed", completed_samples: 12, total_samples: 12, completed_at: "2026-07-30T09:00:00Z" }] },
  queue: { pending: 2, leased: 1 },
  workers: { active: 2 },
  endpoints: { available: 1, unavailable: 0, total: 1 },
  datasets: { ready: 1, blocked: 0 },
  quality: {
    samples: { accuracy: .91, successful: 11, total: 12, completed: 12, failed: 1, completion_rate: 1, success_rate: .92 },
    errors: { total: 1, rate: .08, api_errors: 1, api_error_rate: .02, parser_errors: 0, parser_error_rate: 0, by_type: {} },
    latency_ms: { p95: 320, measured_samples: 12, average: 288, p50: 280, p99: 340 },
    tokens: { total: 2100, input: 1000, output: 1100, measured_samples: 12 },
    cost: { measured_samples: 12, estimated: .1234, actual: null, currency: "USD" },
    insights: { capabilities: [], strongest_capability: null, weakest_capability: null, significant_anomalies: [], major_regressions: [] },
  },
  api: { request_error_rate: .02, estimated_cost_by_currency: { USD: .1234 } },
  reports: 0,
};

const endpoint: Endpoint = {
  id: "endpoint-id",
  display_name: "Production evaluator",
  base_url: "https://models.example.test/v1",
  model_name: "evaluation-model",
  protocol_profile: "openai_chat_completions",
  api_key_mask: "****",
  custom_headers: {},
  default_request_body: {},
  timeout_seconds: 60,
  status: "available",
  max_concurrency: 2,
  requests_per_second: null,
  requests_per_minute: null,
  tokens_per_minute: null,
  input_tokens_per_minute: null,
  output_tokens_per_minute: null,
  input_cost_per_million: null,
  output_cost_per_million: null,
  currency: "USD",
  tags: [],
  notes: null,
  last_connection_error: null,
  api_key_max_concurrency: null,
};

const activeRun: EvaluationRun = {
  id: "active-run",
  display_name: "evaluation-model_release-check_20260802T090000Z",
  model_endpoint_id: "endpoint-id",
  created_by: null,
  max_concurrency: null,
  benchmark_id: "release-check",
  benchmark_version: "1.0",
  status: "running",
  total_samples: 12,
  completed_samples: 4,
  successful_samples: 4,
  failed_samples: 0,
  created_at: "2026-08-02T09:00:00Z",
  started_at: "2026-08-02T09:01:00Z",
  completed_at: null,
  archived_at: null,
};

const completedRun: EvaluationRun = {
  ...activeRun,
  id: "completed-run",
  display_name: "evaluation-model_release-check_20260801T090000Z",
  status: "completed",
  completed_samples: 12,
  successful_samples: 11,
  failed_samples: 1,
  created_at: "2026-08-01T09:00:00Z",
  started_at: "2026-08-01T09:01:00Z",
  completed_at: "2026-08-01T09:03:00Z",
};

const olderRun: EvaluationRun = {
  ...completedRun,
  id: "older-run",
  display_name: "evaluation-model_release-check_20260731T090000Z",
  created_at: "2026-07-31T09:00:00Z",
  started_at: "2026-07-31T09:01:00Z",
  completed_at: "2026-07-31T09:03:00Z",
};

const analytics: AnalyticsMatrix = {
  baseline_run_id: null,
  heatmap: [
    {
      run_id: "completed-run",
      model_endpoint_id: "endpoint-id",
      model_name: "Evaluation model",
      benchmark_id: "release-check",
      benchmark_version: "1.0",
      accuracy: .91,
      success_rate: .92,
      error_rate: .08,
      average_latency_ms: 320,
      estimated_cost: .1234,
      currency: "USD",
      required_capabilities: [],
      sample_count: 12,
      confidence_interval: null,
    },
    {
      run_id: "older-run",
      model_endpoint_id: "endpoint-id",
      model_name: "Evaluation model",
      benchmark_id: "release-check",
      benchmark_version: "1.0",
      accuracy: .8,
      success_rate: .83,
      error_rate: .17,
      average_latency_ms: 410,
      estimated_cost: .2,
      currency: "USD",
      required_capabilities: [],
      sample_count: 12,
      confidence_interval: null,
    },
  ],
  capability_matrix: [],
  heatmaps: { model_benchmark: [], model_capability: [], model_language: [], model_difficulty: [], prompt_benchmark: [], model_modality: [] },
};

const systemHealth: SystemHealth = {
  status: "ok",
  database: "sqlite",
  schema_version: 1,
  database_connected: true,
  disk: { available_bytes: 1024, total_bytes: 2048 },
  queue: { pending: 2, active: 1 },
};

const task: Task = {
  id: "task-id",
  run_id: "active-run",
  parent_task_id: null,
  task_type: "evaluate",
  payload: {},
  status: "running",
  priority: 0,
  attempt_count: 1,
  leased_by: "worker-1",
  lease_expires_at: null,
  next_retry_at: null,
  heartbeat_at: null,
  created_at: "2026-08-02T09:00:00Z",
  updated_at: "2026-08-02T09:01:00Z",
};

function renderOverview(overrides: Partial<React.ComponentProps<typeof OverviewDashboard>> = {}) {
  const props = {
    activeTab: "summary" as const,
    dashboard,
    analytics,
    systemHealth,
    endpoints: [endpoint],
    runs: [activeRun, completedRun, olderRun],
    tasks: [task],
    onInspectRun: vi.fn(),
    onOpenView: vi.fn(),
    onOpenSetup: vi.fn(),
    onTabChange: vi.fn(),
    ...overrides,
  };
  render(<LocaleProvider><OverviewDashboard {...props} /></LocaleProvider>);
  return props;
}

describe("OverviewDashboard", () => {
  it("retains the protected Overview structure instead of adopting a generic workspace-page wrapper", () => {
    renderOverview();

    expect(document.querySelector(".overview-dashboard")).toBeInTheDocument();
    expect(document.querySelector(".overview-dashboard.workspace-page")).not.toBeInTheDocument();
    expect(screen.getByRole("tabpanel")).toHaveClass("dashboard-tabpanel");
  });

  it("shows performance evidence only on the summary tab", async () => {
    const user = userEvent.setup();
    const props = renderOverview();

    expect(screen.getByRole("heading", { level: 1, name: "Dashboard" })).toBeVisible();
    expect(screen.getByRole("tab", { name: "Summary" })).toHaveAttribute("aria-selected", "true");
    expect(screen.queryByText("Keep every evaluation moving")).not.toBeInTheDocument();
    expect(screen.getAllByText("Accuracy").length).toBeGreaterThan(0);
    expect(screen.getAllByText("Success rate").length).toBeGreaterThan(0);
    expect(screen.getAllByText("P95 latency").length).toBeGreaterThan(0);
    expect(screen.getByText("API errors")).toBeVisible();
    expect(screen.getByRole("img", { name: "Evaluation trend" })).toBeVisible();
    expect(screen.getByText("Model / benchmark comparison")).toBeVisible();
    expect(screen.getAllByText("Evaluation model").length).toBeGreaterThan(0);
    expect(screen.getByText("Latency, cost & errors")).toBeVisible();
    expect(screen.queryByRole("heading", { level: 2, name: "Recent evaluations" })).not.toBeInTheDocument();
    expect(screen.queryByRole("heading", { level: 2, name: "System readiness" })).not.toBeInTheDocument();

    await user.click(screen.getAllByRole("button", { name: "Open analysis" })[0]);
    await user.click(screen.getByRole("tab", { name: "Evaluations" }));

    expect(props.onOpenView).toHaveBeenCalledWith("analysis");
    expect(props.onTabChange).toHaveBeenCalledWith("evaluations");
  });

  it("shows recent evaluations only on the evaluations tab", async () => {
    const user = userEvent.setup();
    const props = renderOverview({ activeTab: "evaluations" });

    expect(screen.getByRole("tab", { name: "Evaluations" })).toHaveAttribute("aria-selected", "true");
    expect(screen.getByRole("heading", { level: 2, name: "Recent evaluations" })).toBeVisible();
    expect(document.querySelector(".dashboard-status-badge.completed")).toBeInTheDocument();
    expect(screen.getByText("evaluation-model_release-check_20260802T090000Z")).toBeVisible();
    expect(screen.getByText("evaluation-model_release-check_20260801T090000Z")).toBeVisible();
    expect(screen.queryByRole("img", { name: "Evaluation trend" })).not.toBeInTheDocument();
    expect(screen.queryByRole("heading", { level: 2, name: "System readiness" })).not.toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "Inspect active-run" }));
    expect(props.onInspectRun).toHaveBeenCalledWith("active-run");
  });

  it("shows operational readiness only on the readiness tab", async () => {
    const user = userEvent.setup();
    const props = renderOverview({ activeTab: "readiness" });

    expect(screen.getByRole("tab", { name: "Readiness" })).toHaveAttribute("aria-selected", "true");
    expect(screen.getByRole("heading", { level: 2, name: "System readiness" })).toBeVisible();
    expect(screen.queryByRole("heading", { level: 2, name: "Recent evaluations" })).not.toBeInTheDocument();
    expect(screen.queryByRole("img", { name: "Evaluation trend" })).not.toBeInTheDocument();

    const queue = screen.getByText("Queue pressure").closest("article");
    const workers = screen.getByText("Workers").closest("article");
    await user.click(within(queue as HTMLElement).getByRole("button", { name: "Manage" }));
    await user.click(within(workers as HTMLElement).getByRole("button", { name: "Manage" }));
    expect(props.onOpenView).toHaveBeenNthCalledWith(1, "runs");
    expect(props.onOpenView).toHaveBeenNthCalledWith(2, "runs");
  });

  it("keeps sparse analytics honest on the summary tab", () => {
    renderOverview({ analytics: { ...analytics, heatmap: [] } });

    expect(screen.getAllByText("Evaluation history is not available yet.").length).toBeGreaterThan(0);
    expect(screen.queryByRole("heading", { level: 2, name: "Recent evaluations" })).not.toBeInTheDocument();
    expect(screen.queryByRole("heading", { level: 2, name: "System readiness" })).not.toBeInTheDocument();
  });

  it("guides an empty workspace to add its first model endpoint", async () => {
    const user = userEvent.setup();
    const props = renderOverview({
      analytics: null,
      endpoints: [],
      runs: [],
      dashboard: { ...dashboard, runs: { active: 0, completed: 0, recent_completed: [] }, endpoints: { available: 0, unavailable: 0, total: 0 } },
    });

    expect(screen.getByRole("heading", { name: "Set up your first evaluation" })).toBeVisible();
    expect(screen.queryByRole("img", { name: "Evaluation trend" })).not.toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Add model endpoint" }));

    expect(props.onOpenView).toHaveBeenCalledWith("models", { tab: "add-endpoint" });
  });

  it("guides an unverified model to connection testing", async () => {
    const user = userEvent.setup();
    const props = renderOverview({
      analytics: null,
      endpoints: [{ ...endpoint, status: "unverified" }],
      runs: [],
      dashboard: { ...dashboard, runs: { active: 0, completed: 0, recent_completed: [] }, endpoints: { available: 0, unavailable: 0, total: 1 } },
    });

    await user.click(screen.getByRole("button", { name: "Test model connection" }));

    expect(props.onOpenView).toHaveBeenCalledWith("models", { tab: "model-inventory" });
  });

  it("guides a ready model to the built-in Quick start", async () => {
    const user = userEvent.setup();
    const props = renderOverview({
      analytics: null,
      endpoints: [endpoint],
      runs: [],
      dashboard: { ...dashboard, runs: { active: 0, completed: 0, recent_completed: [] } },
    });

    await user.click(screen.getByRole("button", { name: "Start Quick start" }));

    expect(props.onOpenView).toHaveBeenCalledWith("runs", { tab: "quick-start" });
  });

  it("keeps the first-evaluation checklist on the summary tab for an empty workspace", () => {
    renderOverview({
      analytics: null,
      endpoints: [],
      runs: [],
      dashboard: { ...dashboard, runs: { active: 0, completed: 0, recent_completed: [] }, endpoints: { available: 0, unavailable: 0, total: 0 } },
    });

    expect(screen.getByRole("heading", { name: "Set up your first evaluation" })).toBeVisible();
    expect(screen.getByText("1. Connect a model")).toBeVisible();
    expect(screen.getByText("2. Run Quick start")).toBeVisible();
    expect(screen.getByText("3. Inspect the result")).toBeVisible();
    expect(screen.queryByRole("heading", { level: 2, name: "Recent evaluations" })).not.toBeInTheDocument();
    expect(screen.queryByRole("heading", { level: 2, name: "System readiness" })).not.toBeInTheDocument();
  });

  it("shows an empty recent-evaluations state on the evaluations tab for an empty workspace", () => {
    renderOverview({
      activeTab: "evaluations",
      analytics: null,
      endpoints: [endpoint],
      runs: [],
      dashboard: { ...dashboard, runs: { active: 0, completed: 0, recent_completed: [] } },
    });

    expect(screen.getByRole("tab", { name: "Evaluations" })).toHaveAttribute("aria-selected", "true");
    expect(screen.getByRole("heading", { level: 2, name: "Recent evaluations" })).toBeVisible();
    expect(screen.getByText("Evaluation history is not available yet.")).toBeVisible();
    expect(screen.queryByRole("heading", { name: "Set up your first evaluation" })).not.toBeInTheDocument();
  });

  it("keeps operational readiness reachable on the readiness tab for an empty workspace", () => {
    renderOverview({
      activeTab: "readiness",
      analytics: null,
      endpoints: [endpoint],
      runs: [],
      dashboard: { ...dashboard, runs: { active: 0, completed: 0, recent_completed: [] } },
    });

    expect(screen.getByRole("tab", { name: "Readiness" })).toHaveAttribute("aria-selected", "true");
    expect(screen.getByRole("heading", { level: 2, name: "System readiness" })).toBeVisible();
    const grid = document.querySelector(".readiness-grid");
    expect(grid).not.toBeNull();
    const systemItem = within(grid as HTMLElement).getByText("Operational").closest("article");
    expect(systemItem).not.toBeNull();
    expect(screen.queryByRole("heading", { name: "Set up your first evaluation" })).not.toBeInTheDocument();
  });

  it("routes setup through dataset registration and comparison through analysis", async () => {
    const user = userEvent.setup();
    const props = renderOverview();

    const comparison = screen.getByRole("heading", { name: "Model / benchmark comparison" }).closest("section");
    await user.click(within(comparison as HTMLElement).getByRole("button", { name: "Open analysis" }));
    await user.click(screen.getByRole("button", { name: "Set up an evaluation" }));

    expect(props.onOpenView).toHaveBeenCalledTimes(1);
    expect(props.onOpenView).toHaveBeenCalledWith("analysis");
    expect(props.onOpenSetup).toHaveBeenCalledTimes(1);
  });

  it("keeps localized recovery actions available when the live dashboard summary is unavailable", async () => {
    const user = userEvent.setup();
    const props = renderOverview({ dashboard: null });

    expect(screen.getByRole("heading", { level: 1, name: "Dashboard" })).toBeVisible();
    expect(screen.getByRole("heading", { name: "Operational signals are loading" })).toBeVisible();

    await user.click(screen.getByRole("button", { name: "Configure a model" }));
    await user.click(screen.getByRole("button", { name: "Open runs" }));

    expect(props.onOpenView).toHaveBeenNthCalledWith(1, "models");
    expect(props.onOpenView).toHaveBeenNthCalledWith(2, "runs");
  });

  it("keeps system readiness neutral while health is unknown", () => {
    renderOverview({ activeTab: "readiness", systemHealth: null });

    const grid = document.querySelector(".readiness-grid");
    expect(grid).not.toBeNull();
    const systemItem = within(grid as HTMLElement).getByText("Not available").closest("article");

    expect(systemItem).not.toBeNull();
    expect(systemItem).not.toHaveClass("is-attention");
    expect(screen.queryByText("Attention needed")).not.toBeInTheDocument();
  });

  it("flags degraded system health for attention instead of leaving it neutral", () => {
    renderOverview({ activeTab: "readiness", systemHealth: { ...systemHealth, status: "degraded", database_connected: false } });

    const systemItem = screen.getByText("Attention needed").closest("article");

    expect(systemItem).not.toBeNull();
    expect(systemItem).toHaveClass("is-attention");
  });

  it("reports an operational system without raising attention", () => {
    renderOverview({ activeTab: "readiness" });

    const grid = document.querySelector(".readiness-grid");
    const systemItem = within(grid as HTMLElement).getByText("Operational").closest("article");

    expect(systemItem).not.toBeNull();
    expect(systemItem).not.toHaveClass("is-attention");
  });
});
