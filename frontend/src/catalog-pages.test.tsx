import { cleanup, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import { Benchmark, Dataset, Endpoint, EvaluationSuite, api } from "./api";
import { benchmarkModalities, BenchmarksPage, datasetEditForm, datasetPrepareLabel, DatasetInspector, DatasetsPage, loadDatasetPreview, suiteBenchmarkList, SuitesPage } from "./components/pages/CatalogPages";
import { LocaleProvider } from "./i18n/LocaleProvider";

afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
});

const benchmark: Benchmark = {
  benchmark_id: "math-check",
  created_at: "2026-08-08T00:00:00Z",
  display_name: "Math Check",
  id: "benchmark-1",
  manifest: { modalities: ["text"] },
  source: "builtin",
  status: "enabled",
  version: "1",
};

const secondaryBenchmark: Benchmark = {
  ...benchmark,
  benchmark_id: "code-check",
  display_name: "Code Check",
  id: "benchmark-2",
  manifest: { modalities: ["text", "code"] },
  status: "registered",
};

const readyDataset: Dataset = {
  checksum: "a1b2c3d4",
  credential_binding_id: null,
  dataset_id: "support-set",
  error_message: null,
  id: "dataset-1",
  input_field: "question",
  license_accepted_at: null,
  license_text: null,
  local_path: "/data/support-set.jsonl",
  reference_field: "answer",
  revision: "stable",
  size_bytes: 128,
  source_url: "https://datasets.example.test/support-set.jsonl",
  status: "ready",
  version: "1",
};

const waitingDataset: Dataset = {
  ...readyDataset,
  dataset_id: "safety-set",
  id: "dataset-2",
  local_path: null,
  status: "waiting",
  version: "2",
};

const endpoint: Endpoint = {
  api_key_mask: "••••1234",
  api_key_max_concurrency: null,
  base_url: "https://provider.example/v1",
  currency: "USD",
  custom_headers: {},
  default_request_body: {},
  display_name: "Production endpoint",
  id: "endpoint-1",
  input_cost_per_million: null,
  input_tokens_per_minute: null,
  last_connection_error: null,
  max_concurrency: 2,
  model_name: "example-model",
  notes: null,
  output_cost_per_million: null,
  output_tokens_per_minute: null,
  protocol_profile: "openai_chat_completions",
  requests_per_minute: null,
  requests_per_second: null,
  status: "available",
  tags: [],
  timeout_seconds: 60,
  tokens_per_minute: null,
};

const suite: EvaluationSuite = {
  benchmark_list: [{ benchmark_id: "math-check", version: "1" }],
  created_at: "2026-08-08T00:00:00Z",
  created_by: null,
  default_prompt_overrides: {},
  default_request_body: {},
  description: "Daily smoke suite",
  id: "suite-1",
  name: "Daily checks",
  version: "3",
  weight_configuration: {},
};

function renderCatalogPage(page: React.ReactNode) {
  return render(<LocaleProvider>{page}</LocaleProvider>);
}

describe("catalog workspace pages", () => {
  it("formats benchmark modalities while retaining a fallback for manifests without a modality list", () => {
    expect(benchmarkModalities(secondaryBenchmark)).toBe("text, code");
    expect(benchmarkModalities({ ...benchmark, manifest: {} })).toBe("--");
  });

  it("creates an editable dataset form without converting absent metadata to strings", () => {
    expect(datasetEditForm({ ...readyDataset, checksum: null, credential_binding_id: null, license_text: null, source_url: null })).toEqual(expect.objectContaining({ checksum: "", credential_binding_id: "", license_text: "", source_url: "" }));
  });

  it("selects the correct preparation action for license, retry, and fresh download states", () => {
    expect(datasetPrepareLabel({ ...waitingDataset, license_text: "Terms" })).toBe("Accept license");
    expect(datasetPrepareLabel(waitingDataset)).toBe("Retry download");
    expect(datasetPrepareLabel({ ...waitingDataset, status: "registered" })).toBe("Download and verify");
  });

  it("loads the five-row dataset preview used by the selected inspector", async () => {
    const preview = { fields: ["question"], rows: [{ question: "2 + 2" }] };
    const previewRequest = vi.spyOn(api, "previewDataset").mockResolvedValue(preview);

    await expect(loadDatasetPreview(readyDataset)).resolves.toEqual(preview);
    expect(previewRequest).toHaveBeenCalledWith(readyDataset.id, 5);
  });

  it("keeps cache validation available in the selected dataset inspector", async () => {
    const user = userEvent.setup();
    const onValidate = vi.fn();
    renderCatalogPage(<DatasetInspector busy={null} dataset={readyDataset} editForm={{}} editing={false} onClear={vi.fn()} onDelete={vi.fn()} onEditForm={vi.fn()} onPause={vi.fn()} onPrepare={vi.fn()} onPreview={vi.fn()} onStartEdit={vi.fn()} onStopEdit={vi.fn()} onSubmitEdit={vi.fn()} onUpload={vi.fn()} onValidate={onValidate} preview={null} previewing={false} />);

    expect(screen.getByText("SHA-256 a1b2c3d4…")).toBeVisible();
    await user.click(screen.getByRole("button", { name: "Validate cache" }));
    expect(onValidate).toHaveBeenCalledWith(readyDataset);
  });

  it("renders selected preview rows after loading the dataset inspection sample", async () => {
    const user = userEvent.setup();
    vi.spyOn(api, "datasetDiskUsage").mockResolvedValue({ available_bytes: 1000, cache_bytes: 128, root: "/data", total_bytes: 2000 });
    vi.spyOn(api, "previewDataset").mockResolvedValue({ fields: ["question"], rows: [{ question: "2 + 2" }] });
    renderCatalogPage(<DatasetsPage busy={null} datasets={[readyDataset]} onClear={vi.fn()} onDelete={vi.fn()} onPause={vi.fn()} onPrepare={vi.fn()} onUpdate={vi.fn()} onUpload={vi.fn()} onValidate={vi.fn()} />);

    await user.click(screen.getByRole("button", { name: "Preview" }));

    expect(await screen.findByText("2 + 2")).toBeVisible();
  });

  it("formats the versioned benchmark composition shown for a suite", () => {
    expect(suiteBenchmarkList(suite)).toBe("math-check@1");
  });

  it("filters the benchmark registry while retaining the status action for matching data", async () => {
    const user = userEvent.setup();
    const onToggleStatus = vi.fn();
    renderCatalogPage(<BenchmarksPage benchmarks={[benchmark, secondaryBenchmark]} busy={null} onToggleStatus={onToggleStatus} />);

    expect(screen.getByRole("heading", { level: 1, name: "Benchmarks" })).toBeVisible();
    await user.type(screen.getByLabelText("Filter benchmarks"), "math");

    expect(screen.getByText("Math Check")).toBeVisible();
    expect(screen.queryByText("Code Check")).not.toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Disable" }));
    expect(onToggleStatus).toHaveBeenCalledWith(benchmark);
  });

  it("keeps the dataset inventory visible while selecting a versioned inspector", async () => {
    const user = userEvent.setup();
    vi.spyOn(api, "datasetDiskUsage").mockResolvedValue({ available_bytes: 1000, cache_bytes: 128, root: "/data", total_bytes: 2000 });
    renderCatalogPage(<DatasetsPage busy={null} datasets={[readyDataset, waitingDataset]} onClear={vi.fn()} onDelete={vi.fn()} onPause={vi.fn()} onPrepare={vi.fn()} onUpdate={vi.fn()} onUpload={vi.fn()} onValidate={vi.fn()} />);

    expect(screen.getByRole("heading", { level: 1, name: "Datasets" })).toBeVisible();
    expect(screen.getByRole("button", { name: /Inspect support-set v1/ })).toBeVisible();
    await user.click(screen.getByRole("button", { name: /Inspect safety-set v2/ }));

    expect(screen.getByRole("heading", { level: 2, name: "safety-set v2" })).toBeVisible();
    expect(screen.getByRole("button", { name: /Inspect support-set v1/ })).toBeVisible();
    expect(screen.getByRole("button", { name: "Retry download" })).toBeVisible();
  });

  it("uses one clear registration action for an empty dataset catalog", () => {
    vi.spyOn(api, "datasetDiskUsage").mockResolvedValue({ available_bytes: 1000, cache_bytes: 0, root: "/data", total_bytes: 2000 });
    renderCatalogPage(<DatasetsPage busy={null} datasets={[]} onClear={vi.fn()} onDelete={vi.fn()} onOpenWorkspace={vi.fn()} onPause={vi.fn()} onPrepare={vi.fn()} onUpdate={vi.fn()} onUpload={vi.fn()} onValidate={vi.fn()} />);

    expect(screen.getAllByRole("button", { name: "Register dataset" })).toHaveLength(1);
  });

  it("routes an empty suite inventory to the existing suite builder", async () => {
    const user = userEvent.setup();
    const onOpenWorkspace = vi.fn();
    renderCatalogPage(<SuitesPage busy={null} endpoints={[]} onOpenWorkspace={onOpenWorkspace} onQueue={vi.fn()} suites={[]} />);

    await user.click(screen.getByRole("button", { name: "Open suite builder" }));

    expect(onOpenWorkspace).toHaveBeenCalledOnce();
  });

  it("keeps a suite endpoint queue action available from the dense inventory", async () => {
    const user = userEvent.setup();
    const onQueue = vi.fn();
    renderCatalogPage(<SuitesPage busy={null} endpoints={[endpoint]} onOpenWorkspace={vi.fn()} onQueue={onQueue} suites={[suite]} />);

    await user.click(screen.getByRole("button", { name: "Queue on Production endpoint" }));

    expect(onQueue).toHaveBeenCalledWith(suite.id, endpoint.id);
  });
});
