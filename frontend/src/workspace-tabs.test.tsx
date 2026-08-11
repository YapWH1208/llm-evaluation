import { cleanup, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import App from "./App";
import { api, type Endpoint, type EvaluationRun } from "./api";
import { LocaleProvider } from "./i18n/LocaleProvider";

const endpoint: Endpoint = {
  api_key_mask: "••••1234",
  api_key_max_concurrency: null,
  base_url: "https://provider.example/v1",
  currency: "USD",
  custom_headers: {},
  default_request_body: {},
  display_name: "Production model",
  id: "endpoint-1",
  input_cost_per_million: 1.5,
  input_tokens_per_minute: null,
  last_connection_error: null,
  max_concurrency: 2,
  model_name: "example-model",
  notes: null,
  output_cost_per_million: 3,
  output_tokens_per_minute: null,
  protocol_profile: "openai_chat_completions",
  requests_per_minute: null,
  requests_per_second: null,
  status: "available",
  tags: ["production"],
  timeout_seconds: 60,
  tokens_per_minute: null,
};

const run: EvaluationRun = {
  archived_at: null,
  benchmark_id: "math-check",
  benchmark_version: "1",
  completed_at: "2026-08-08T12:05:00Z",
  completed_samples: 1,
  created_at: "2026-08-08T12:00:00Z",
  created_by: null,
  failed_samples: 0,
  id: "run-1",
  display_name: "example-model_math-check_20260808T120000Z",
  max_concurrency: null,
  model_endpoint_id: endpoint.id,
  started_at: "2026-08-08T12:00:01Z",
  status: "completed",
  successful_samples: 1,
  total_samples: 1,
};

function mockWorkspace({ runs = [] }: { runs?: EvaluationRun[] } = {}) {
  vi.spyOn(api, "listEndpoints").mockResolvedValue([endpoint]);
  vi.spyOn(api, "listRuns").mockResolvedValue(runs);
  vi.spyOn(api, "dashboard").mockResolvedValue(null as never);
  vi.spyOn(api, "listPromptPackages").mockResolvedValue([]);
  vi.spyOn(api, "listDatasets").mockResolvedValue([]);
  vi.spyOn(api, "listBenchmarks").mockResolvedValue([]);
  vi.spyOn(api, "listTasks").mockResolvedValue([]);
  vi.spyOn(api, "analyticsMatrix").mockResolvedValue(null as never);
  vi.spyOn(api, "leaderboard").mockResolvedValue({
    items: runs.map((item) => ({
      run_id: item.id,
      display_name: item.display_name,
      model_endpoint_id: item.model_endpoint_id,
      model_name: endpoint.model_name,
      dataset: item.benchmark_id,
      benchmark_id: item.benchmark_id,
      benchmark_version: item.benchmark_version,
      status: item.status,
      created_at: item.created_at,
      completed_at: item.completed_at,
      capabilities: [],
      languages: [],
      evaluation_type: "custom",
      score: 1,
      primary_metric: "score",
      average_latency_ms: 120,
      p95_latency_ms: 180,
      estimated_cost: .01,
      sample_count: item.total_samples,
      completed_samples: item.completed_samples,
      successful_samples: item.successful_samples,
      failed_samples: item.failed_samples,
      available_metrics: ["score"],
      named_metrics: {},
    })),
    total: runs.length,
    page: 1,
    page_size: 50,
    total_pages: runs.length ? 1 : 0,
    sort: "default",
    direction: "desc",
  });
  vi.spyOn(api, "systemHealth").mockResolvedValue(null as never);
  vi.spyOn(api, "datasetDiskUsage").mockResolvedValue({ available_bytes: 1000, cache_bytes: 0, root: "/data", total_bytes: 2000 });
  vi.spyOn(api, "listAttempts").mockResolvedValue([]);
  vi.spyOn(api, "getRunSummary").mockResolvedValue(null as never);
  vi.spyOn(api, "listReports").mockResolvedValue([]);
  vi.spyOn(api, "listRunLogs").mockResolvedValue([]);
  vi.spyOn(api, "listRunMetrics").mockResolvedValue([]);
}

afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
  window.history.replaceState(null, "", "/dashboard");
});

describe("workspace tab routing", () => {
  it("moves an endpoint edit from inventory to its URL-backed form tab", async () => {
    mockWorkspace();
    window.history.replaceState(null, "", "/models");
    const user = userEvent.setup();
    render(<LocaleProvider><App /></LocaleProvider>);

    await user.click(await screen.findByRole("button", { name: "Edit configuration" }));

    await waitFor(() => expect(window.location.pathname).toBe("/models"));
    expect(window.location.search).toBe("?tab=add-endpoint");
    expect(screen.getByRole("tab", { name: "Add endpoint" })).toHaveAttribute("aria-selected", "true");
    expect(screen.getByRole("heading", { name: "Edit model endpoint" })).toBeVisible();
    expect(screen.getByLabelText("Display name")).toHaveValue("Production model");
  });

  it("opens dataset registration as an exclusive URL-backed tab", async () => {
    mockWorkspace();
    window.history.replaceState(null, "", "/datasets");
    const user = userEvent.setup();
    render(<LocaleProvider><App /></LocaleProvider>);

    await user.click(screen.getByRole("tab", { name: "Register dataset" }));

    expect(window.location.pathname).toBe("/datasets");
    expect(window.location.search).toBe("?tab=register-dataset");
    expect(screen.getByRole("heading", { name: "Register dataset version" })).toBeVisible();
    expect(screen.queryByRole("heading", { name: "No dataset versions" })).not.toBeInTheDocument();
  });

  it("opens a selected run in its URL-backed detail tab", async () => {
    mockWorkspace({ runs: [run] });
    window.history.replaceState(null, "", "/runs");
    const user = userEvent.setup();
    render(<LocaleProvider><App /></LocaleProvider>);

    await user.click(await screen.findByRole("button", { name: /math-check v1/i }));

    expect(window.location.pathname).toBe("/runs");
    expect(window.location.search).toBe("?tab=run-details&run=run-1");
    expect(screen.getByRole("tab", { name: "Run details" })).toHaveAttribute("aria-selected", "true");
    const inspector = screen.getByRole("region", { name: "Selected run inspector" });
    expect(inspector).toBeVisible();
    expect(within(inspector).getByRole("heading", { name: run.display_name })).toBeVisible();
    expect(within(inspector).getByRole("tab", { name: "Overview" })).toHaveAttribute("aria-selected", "true");
    expect(within(inspector).getByRole("button", { name: "Clone" })).toBeVisible();
    expect(within(inspector).getByRole("button", { name: "Rerun benchmark" })).toBeVisible();
    expect(api.listRunMetrics).toHaveBeenCalledWith(run.id);
  });

  it("opens a leaderboard row at a restorable run-detail URL", async () => {
    mockWorkspace({ runs: [run] });
    window.history.replaceState(null, "", "/leaderboard");
    const user = userEvent.setup();
    render(<LocaleProvider><App /></LocaleProvider>);

    expect(await screen.findByRole("heading", { level: 1, name: "Leaderboard" })).toBeVisible();
    expect(screen.getByRole("link", { name: "Leaderboard" })).toHaveAttribute("aria-current", "page");
    await user.click(await screen.findByRole("link", { name: `Inspect ${run.display_name}` }));

    await waitFor(() => expect(window.location.search).toBe("?tab=run-details&run=run-1"));
    expect(window.location.pathname).toBe("/runs");
    expect(screen.getByRole("region", { name: "Selected run inspector" })).toBeVisible();
  });

  it("shows run-detail guidance when a deep link has no selected run", () => {
    mockWorkspace();
    window.history.replaceState(null, "", "/runs?tab=run-details");
    render(<LocaleProvider><App /></LocaleProvider>);

    expect(screen.getByRole("tab", { name: "Run details" })).toHaveAttribute("aria-selected", "true");
    expect(screen.getByRole("heading", { name: "Select a run" })).toBeVisible();
  });

  it("canonicalizes the legacy launcher and keeps both launch tabs isolated", async () => {
    mockWorkspace();
    window.history.replaceState(null, "", "/runs?tab=launch-evaluation");
    const user = userEvent.setup();
    render(<LocaleProvider><App /></LocaleProvider>);

    await waitFor(() => expect(window.location.search).toBe("?tab=quick-start"));
    expect(screen.getByRole("tab", { name: "Quick start" })).toHaveAttribute("aria-selected", "true");
    expect(screen.getByLabelText("Quick-start benchmark")).toBeVisible();
    expect(screen.queryByLabelText("Dataset")).not.toBeInTheDocument();

    await user.click(screen.getByRole("tab", { name: "Dataset evaluation" }));
    expect(window.location.search).toBe("?tab=dataset-evaluation");
    expect(screen.getByLabelText("Dataset")).toBeVisible();
    expect(screen.queryByLabelText("Quick-start benchmark")).not.toBeInTheDocument();
  });

  it("direct-loads a lower-density Guide section from the URL", () => {
    mockWorkspace();
    window.history.replaceState(null, "", "/guide?tab=prepare-data");
    render(<LocaleProvider><App /></LocaleProvider>);

    expect(screen.getByRole("tab", { name: "Prepare data" })).toHaveAttribute("aria-selected", "true");
    expect(screen.getByText(/2\. Register a dataset/i)).toBeVisible();
    expect(screen.queryByText(/1\. Add a model endpoint/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/4\. Queue a dataset run/i)).not.toBeInTheDocument();
  });

  it("direct-loads the Dashboard readiness tab", () => {
    mockWorkspace();
    window.history.replaceState(null, "", "/dashboard?tab=readiness");
    render(<LocaleProvider><App /></LocaleProvider>);

    expect(screen.getByRole("tab", { name: "Readiness" })).toHaveAttribute("aria-selected", "true");
  });

  it("links aria-controls only from the active tab to its rendered panel", () => {
    mockWorkspace();
    window.history.replaceState(null, "", "/dashboard");
    render(<LocaleProvider><App /></LocaleProvider>);

    expect(screen.getByRole("tab", { name: "Summary" })).toHaveAttribute("aria-controls", "dashboard-tabpanel-summary");
    expect(screen.getByRole("tab", { name: "Evaluations" })).not.toHaveAttribute("aria-controls");
    expect(screen.getByRole("tab", { name: "Readiness" })).not.toHaveAttribute("aria-controls");
  });

  it("direct-loads Analysis comparison and Settings preferences", async () => {
    mockWorkspace();
    window.history.replaceState(null, "", "/analysis?tab=compare-runs");
    render(<LocaleProvider><App /></LocaleProvider>);

    expect(screen.getByRole("tab", { name: "Compare runs" })).toHaveAttribute("aria-selected", "true");
    expect(screen.getByLabelText("Run A")).toBeVisible();

    window.history.pushState(null, "", "/settings?tab=preferences");
    window.dispatchEvent(new PopStateEvent("popstate"));

    await waitFor(() => expect(screen.getByRole("tab", { name: "Preferences" })).toHaveAttribute("aria-selected", "true"));
    expect(within(screen.getByRole("tabpanel", { name: "Preferences" })).getByLabelText("Workspace language")).toBeVisible();
  });
});
