import { cleanup, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import App from "./App";
import { api, Benchmark, Dataset, Endpoint, EvaluationRun, PromptPackage } from "./api";
import { LocaleProvider } from "./i18n/LocaleProvider";

afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
  window.history.replaceState(null, "", "/dashboard");
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
const promptPackage = {
  id: "pp-1",
  name: "Templated",
  version: "1.0.0",
  prompt_type: "user_custom",
  system_message: null,
  user_template: "Q: {{question}}\nA:",
  few_shot_examples: [],
  scoring_rule: { type: "exact_match" },
  created_at: "2026-08-09T00:00:00Z",
} as PromptPackage;
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
  prompts = [promptPackage],
  runs = [],
}: {
  benchmarks?: Benchmark[];
  datasets?: Dataset[];
  endpoints?: Endpoint[];
  prompts?: PromptPackage[];
  runs?: EvaluationRun[];
} = {}) {
  vi.spyOn(api, "listEndpoints").mockResolvedValue(endpoints);
  vi.spyOn(api, "listRuns").mockResolvedValue(runs);
  vi.spyOn(api, "dashboard").mockResolvedValue(null as never);
  vi.spyOn(api, "listPromptPackages").mockResolvedValue(prompts);
  vi.spyOn(api, "listDatasets").mockResolvedValue(datasets);
  vi.spyOn(api, "listBenchmarks").mockResolvedValue(benchmarks);
  vi.spyOn(api, "listTasks").mockResolvedValue([]);
  vi.spyOn(api, "analyticsMatrix").mockResolvedValue(null as never);
  vi.spyOn(api, "systemHealth").mockResolvedValue(null as never);
}

async function openRuns() {
  const user = userEvent.setup();
  render(<LocaleProvider><App /></LocaleProvider>);
  await user.click(screen.getByRole("link", { name: "Runs" }));
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
    expect(validateDatasetRun.mock.calls[0][0]).not.toHaveProperty("scoring_rule");
    expect(screen.getByText("Ready to queue")).toBeVisible();
  }, 10_000);

  it("submits the selected metric to dataset preflight and creation", async () => {
    mockWorkspace();
    vi.spyOn(api, "previewDataset").mockResolvedValue({
      fields: ["question", "answer"],
      rows: [{ question: "2 + 2?", answer: "4" }],
    });
    const validateDatasetRun = vi.spyOn(api, "validateDatasetRun").mockResolvedValue({ can_queue: true, issues: [], sample_count: 1 } as never);
    const createDatasetRun = vi.spyOn(api, "createDatasetRun").mockResolvedValue({ id: "run-1" } as never);
    const user = await openRuns();

    await user.selectOptions(screen.getByLabelText("Endpoint"), endpoint.id);
    await user.selectOptions(screen.getByLabelText("Dataset"), readyDataset.id);
    await waitFor(() => expect(screen.getByLabelText("Reference field")).toHaveValue("answer"));
    const metric = screen.getByLabelText("Evaluation metric");
    expect(metric).toHaveTextContent("Default");
    expect(metric).toHaveTextContent("Exact match");
    expect(metric).toHaveTextContent("Normalized exact match");
    expect(metric).toHaveTextContent("Token F1");
    expect(metric).toHaveTextContent("BLEU");
    expect(metric).toHaveTextContent("ROUGE-L");
    await user.selectOptions(metric, "token_f1");
    await user.click(screen.getByRole("button", { name: "Preflight dataset" }));

    const expectedPayload = {
      model_endpoint_id: endpoint.id,
      dataset_version_id: readyDataset.id,
      prompt_package_id: null,
      input_field: "question",
      reference_field: "answer",
      sample_limit: 100,
      scoring_rule: { type: "token_f1" },
    };
    expect(validateDatasetRun).toHaveBeenCalledWith(expectedPayload);
    expect(screen.getByText("Ready to queue")).toBeVisible();

    await user.selectOptions(metric, "bleu");
    expect(screen.getByText("Not checked")).toBeVisible();
    await user.selectOptions(metric, "token_f1");
    await user.click(screen.getByRole("button", { name: "Queue dataset run" }));
    expect(createDatasetRun).toHaveBeenCalledWith(expectedPayload);
  }, 10_000);

  it("shows the immutable scoring metric in selected run evidence", async () => {
    const run = {
      id: "run-scored",
      model_endpoint_id: endpoint.id,
      created_by: null,
      max_concurrency: null,
      benchmark_id: "dataset-evaluation",
      benchmark_version: "1.0.0",
      configuration_snapshot: { scoring_rule: { type: "rouge_l" } },
      status: "completed",
      total_samples: 1,
      completed_samples: 1,
      successful_samples: 1,
      failed_samples: 0,
      created_at: "2026-08-10T00:00:00Z",
      started_at: "2026-08-10T00:00:01Z",
      completed_at: "2026-08-10T00:00:02Z",
      archived_at: null,
    } as EvaluationRun;
    mockWorkspace({ runs: [run] });
    vi.spyOn(api, "listAttempts").mockResolvedValue([]);
    vi.spyOn(api, "getRunSummary").mockResolvedValue(null as never);
    vi.spyOn(api, "listReports").mockResolvedValue([]);
    vi.spyOn(api, "listRunLogs").mockResolvedValue([]);
    const user = await openRuns();

    await user.click(screen.getByRole("button", { name: /dataset-evaluation v1.0.0/i }));

    const inspector = await screen.findByRole("region", { name: "Selected run inspector" });
    expect(within(inspector).getByText("Evaluation metric")).toBeVisible();
    expect(within(inspector).getByText("ROUGE-L")).toBeVisible();
  }, 10_000);

  it("queues a prompt-package dataset run without an input field and clears stale preflight state", async () => {
    mockWorkspace();
    vi.spyOn(api, "previewDataset").mockResolvedValue({
      fields: ["question", "answer"],
      rows: [{ question: "2 + 2?", answer: "4" }],
    });
    const validateDatasetRun = vi.spyOn(api, "validateDatasetRun").mockResolvedValue({ can_queue: true, issues: [], sample_count: 1 } as never);
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
    const packageSelects = screen.getAllByLabelText("Prompt package (optional)");
    await user.selectOptions(packageSelects[1], promptPackage.id);
    expect(screen.getByLabelText("Input field")).toBeDisabled();
    await user.click(screen.getByRole("button", { name: "Preflight dataset" }));
    await waitFor(() => expect(screen.getByText("Ready to queue")).toBeVisible());
    await user.click(screen.getByRole("button", { name: "Queue dataset run" }));

    expect(validateDatasetRun).toHaveBeenCalledWith(expect.objectContaining({ input_field: null, prompt_package_id: promptPackage.id }));
    expect(createDatasetRun).toHaveBeenCalledWith(expect.objectContaining({
      model_endpoint_id: endpoint.id,
      dataset_version_id: readyDataset.id,
      prompt_package_id: promptPackage.id,
      input_field: null,
      reference_field: "answer",
    }));
    expect(screen.getByText("Not checked")).toBeVisible();
  }, 10_000);

  it("blocks queueing a single-field dataset and explains the missing reference field", async () => {
    mockWorkspace();
    vi.spyOn(api, "previewDataset").mockResolvedValue({
      fields: ["only"],
      rows: [{ only: "value" }],
    });
    const user = await openRuns();

    await user.selectOptions(screen.getByLabelText("Dataset"), readyDataset.id);

    expect(await screen.findByText("This dataset exposes only one field; a distinct reference field is required.")).toBeVisible();
    expect(screen.getByRole("button", { name: "Queue dataset run" })).toBeDisabled();
    expect(screen.getByRole("button", { name: "Preflight dataset" })).toBeDisabled();
  }, 10_000);

  it("blocks queueing when input and reference fields are the same", async () => {
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

    await user.selectOptions(screen.getByLabelText("Dataset"), readyDataset.id);
    await waitFor(() => expect(screen.getByLabelText("Reference field")).toHaveValue("answer"));
    await user.selectOptions(screen.getByLabelText("Reference field"), "question");

    expect(screen.getByText("Input and reference fields must be different.")).toBeVisible();
    expect(screen.getByRole("button", { name: "Queue dataset run" })).toBeDisabled();
    await user.click(screen.getByRole("button", { name: "Queue dataset run" }));
    expect(createDatasetRun).not.toHaveBeenCalled();
  }, 10_000);

  it("retries the schema fetch after a transient preview failure", async () => {
    mockWorkspace();
    vi.spyOn(api, "previewDataset")
      .mockRejectedValueOnce(new Error("Prepared schema is unavailable."))
      .mockResolvedValueOnce({
        fields: ["question", "answer"],
        rows: [{ question: "2 + 2?", answer: "4" }],
      });
    const user = await openRuns();

    await user.selectOptions(screen.getByLabelText("Endpoint"), endpoint.id);
    await user.selectOptions(screen.getByLabelText("Dataset"), readyDataset.id);
    expect(await screen.findByRole("alert")).toHaveTextContent("Prepared schema is unavailable.");
    await user.click(screen.getByRole("button", { name: "Retry" }));

    await waitFor(() => expect(screen.getByLabelText("Input field")).toHaveValue("question"));
    expect(screen.getByRole("button", { name: "Queue dataset run" })).toBeEnabled();
  }, 10_000);
});
