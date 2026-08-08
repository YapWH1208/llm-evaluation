import { cleanup, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import { Benchmark, Dataset, Endpoint, EvaluationSuite, api } from "./api";
import { BenchmarksPage, DatasetsPage, SuitesPage } from "./components/pages/CatalogPages";
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
