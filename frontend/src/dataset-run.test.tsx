import { cleanup, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import App from "./App";
import { api, Benchmark, Dataset, Endpoint } from "./api";
import { LocaleProvider } from "./i18n/LocaleProvider";

afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
});

const endpoint = { id: "ep-1", display_name: "Test model", status: "available" } as Endpoint;
const readyDataset = {
  id: "ds-1",
  dataset_id: "demo",
  version: "1",
  status: "ready",
  input_field: "question",
  reference_field: "answer",
} as Dataset;
const quickStartBenchmark = {
  id: "benchmark-1",
  benchmark_id: "text-quick-check",
  version: "1.0.0",
  display_name: "Text Quick Check",
  source: "builtin",
  status: "available",
  manifest: { modalities: ["text"], sample_count: 3 },
  created_at: "2026-08-09T00:00:00Z",
};

function mockWorkspace({
  benchmarks = [quickStartBenchmark],
  datasets = [readyDataset],
  endpoints = [endpoint],
}: {
  benchmarks?: Benchmark[];
  datasets?: Dataset[];
  endpoints?: Endpoint[];
} = {}) {
  vi.spyOn(api, "listEndpoints").mockResolvedValue(endpoints);
  vi.spyOn(api, "listRuns").mockResolvedValue([]);
  vi.spyOn(api, "dashboard").mockResolvedValue(null as never);
  vi.spyOn(api, "listPromptPackages").mockResolvedValue([]);
  vi.spyOn(api, "listDatasets").mockResolvedValue(datasets);
  vi.spyOn(api, "listSuites").mockResolvedValue([]);
  vi.spyOn(api, "listBenchmarks").mockResolvedValue(benchmarks);
  vi.spyOn(api, "listTasks").mockResolvedValue([]);
  vi.spyOn(api, "analyticsMatrix").mockResolvedValue(null as never);
  vi.spyOn(api, "listUsers").mockResolvedValue([]);
  vi.spyOn(api, "listAuditEvents").mockResolvedValue([]);
  vi.spyOn(api, "systemHealth").mockResolvedValue(null as never);
}

async function openRuns() {
  const user = userEvent.setup();
  render(<LocaleProvider><App /></LocaleProvider>);
  await user.click(screen.getByRole("button", { name: "Runs" }));
  return user;
}

describe("evaluation run launch workspace", () => {
  it("queues a dataset run with schema-selected input and reference fields", async () => {
    mockWorkspace();
    vi.spyOn(api, "previewDataset").mockResolvedValue({
      fields: ["question", "answer"],
      rows: [{ question: "2 + 2?", answer: "4" }],
    });
    const createDatasetRun = vi.spyOn(api, "createDatasetRun").mockResolvedValue({
      id: "run-1",
      benchmark_id: "dataset-evaluation",
      total_samples: 1,
      status: "queued",
    } as never);
    const user = await openRuns();

    await user.selectOptions(screen.getByLabelText("Endpoint"), endpoint.id);
    await user.selectOptions(screen.getByLabelText("Dataset"), readyDataset.id);
    await waitFor(() => expect(screen.getByLabelText("Input field")).toHaveValue("question"));
    expect(screen.getByLabelText("Reference field")).toHaveValue("answer");
    await user.click(screen.getByRole("button", { name: "Queue dataset run" }));

    expect(createDatasetRun).toHaveBeenCalledWith({
      model_endpoint_id: endpoint.id,
      dataset_version_id: readyDataset.id,
      prompt_package_id: null,
      input_field: "question",
      reference_field: "answer",
      sample_limit: 100,
    });
  }, 10_000);

  it("uses saved field defaults when they are present in the loaded schema", async () => {
    mockWorkspace({
      datasets: [{ ...readyDataset, input_field: "prompt", reference_field: "expected" }],
    });
    vi.spyOn(api, "previewDataset").mockResolvedValue({
      fields: ["metadata", "prompt", "expected"],
      rows: [{ metadata: "m", prompt: "q", expected: "a" }],
    });
    const user = await openRuns();

    await user.selectOptions(screen.getByLabelText("Dataset"), readyDataset.id);

    await waitFor(() => expect(screen.getByLabelText("Input field")).toHaveValue("prompt"));
    expect(screen.getByLabelText("Reference field")).toHaveValue("expected");
  }, 10_000);

  it("replaces stale mappings with selections from the newly loaded schema", async () => {
    const second = { ...readyDataset, id: "ds-2", dataset_id: "other", input_field: null, reference_field: null };
    mockWorkspace({ datasets: [readyDataset, second] });
    vi.spyOn(api, "previewDataset").mockImplementation(async (datasetId) => datasetId === readyDataset.id
      ? { fields: ["question", "answer"], rows: [] }
      : { fields: ["prompt", "target"], rows: [] });
    const user = await openRuns();

    await user.selectOptions(screen.getByLabelText("Dataset"), readyDataset.id);
    await waitFor(() => expect(screen.getByLabelText("Reference field")).toHaveValue("answer"));
    await user.selectOptions(screen.getByLabelText("Dataset"), second.id);

    await waitFor(() => expect(screen.getByLabelText("Input field")).toHaveValue("prompt"));
    expect(screen.getByLabelText("Reference field")).toHaveValue("target");
  }, 10_000);

  it("blocks dataset queueing and reports a schema-loading failure", async () => {
    mockWorkspace();
    vi.spyOn(api, "previewDataset").mockRejectedValue(new Error("Prepared schema is unavailable."));
    const user = await openRuns();

    await user.selectOptions(screen.getByLabelText("Dataset"), readyDataset.id);

    expect(await screen.findByRole("alert")).toHaveTextContent("Prepared schema is unavailable.");
    expect(screen.getByRole("button", { name: "Queue dataset run" })).toBeDisabled();
  }, 10_000);

  it("queues an available built-in quick-start benchmark with its sample limit", async () => {
    const external = { ...quickStartBenchmark, id: "benchmark-2", benchmark_id: "external-pack", display_name: "External Pack", source: "pack:external" };
    mockWorkspace({ benchmarks: [quickStartBenchmark, external] });
    const createRun = vi.spyOn(api, "createRun").mockResolvedValue({ id: "run-1" } as never);
    vi.spyOn(api, "listAttempts").mockResolvedValue([]);
    vi.spyOn(api, "getRunSummary").mockResolvedValue(null as never);
    vi.spyOn(api, "listReports").mockResolvedValue([]);
    vi.spyOn(api, "listRunLogs").mockResolvedValue([]);
    const user = await openRuns();

    await user.selectOptions(screen.getByLabelText("Endpoint"), endpoint.id);
    expect(screen.getByLabelText("Quick-start benchmark")).toHaveTextContent("Text Quick Check");
    expect(screen.getByLabelText("Quick-start benchmark")).not.toHaveTextContent("External Pack");
    await user.click(screen.getByRole("button", { name: "Queue quick start" }));

    expect(createRun).toHaveBeenCalledWith(
      endpoint.id,
      undefined,
      {},
      null,
      "text-quick-check",
      "1.0.0",
      3,
    );
  }, 10_000);

  it("supports quick-start and dataset preflight from the shared endpoint context", async () => {
    mockWorkspace();
    vi.spyOn(api, "previewDataset").mockResolvedValue({ fields: ["question", "answer"], rows: [] });
    const validateRun = vi.spyOn(api, "validateRun").mockResolvedValue({ can_queue: true, issues: [], sample_count: 3 } as never);
    const validateDatasetRun = vi.spyOn(api, "validateDatasetRun").mockResolvedValue({ can_queue: true, issues: [], sample_count: 1 } as never);
    const user = await openRuns();

    await user.selectOptions(screen.getByLabelText("Endpoint"), endpoint.id);
    await user.click(screen.getByRole("button", { name: "Preflight quick start" }));
    expect(validateRun).toHaveBeenCalled();

    await user.selectOptions(screen.getByLabelText("Dataset"), readyDataset.id);
    await waitFor(() => expect(screen.getByLabelText("Reference field")).toHaveValue("answer"));
    await user.click(screen.getByRole("button", { name: "Preflight dataset" }));

    expect(validateDatasetRun).toHaveBeenCalledWith(expect.objectContaining({
      model_endpoint_id: endpoint.id,
      dataset_version_id: readyDataset.id,
      input_field: "question",
      reference_field: "answer",
    }));
    expect(screen.getByText("Ready to queue")).toBeVisible();
  }, 10_000);
});
