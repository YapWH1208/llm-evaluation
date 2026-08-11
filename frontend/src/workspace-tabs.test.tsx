import { cleanup, render, screen, waitFor } from "@testing-library/react";
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
  vi.spyOn(api, "systemHealth").mockResolvedValue(null as never);
  vi.spyOn(api, "datasetDiskUsage").mockResolvedValue({ available_bytes: 1000, cache_bytes: 0, root: "/data", total_bytes: 2000 });
  vi.spyOn(api, "listAttempts").mockResolvedValue([]);
  vi.spyOn(api, "getRunSummary").mockResolvedValue(null as never);
  vi.spyOn(api, "listReports").mockResolvedValue([]);
  vi.spyOn(api, "listRunLogs").mockResolvedValue([]);
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
    expect(window.location.search).toBe("?tab=run-details");
    expect(screen.getByRole("tab", { name: "Run details" })).toHaveAttribute("aria-selected", "true");
    expect(screen.getByRole("region", { name: "Selected run inspector" })).toBeVisible();
  });

  it("shows run-detail guidance when a deep link has no selected run", () => {
    mockWorkspace();
    window.history.replaceState(null, "", "/runs?tab=run-details");
    render(<LocaleProvider><App /></LocaleProvider>);

    expect(screen.getByRole("tab", { name: "Run details" })).toHaveAttribute("aria-selected", "true");
    expect(screen.getByRole("heading", { name: "Select a run" })).toBeVisible();
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
});
