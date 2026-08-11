import { cleanup, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import { AnalyticsMatrix, Comparison, Dataset, Endpoint, EvaluationRun, ScatterResponse } from "./api";
import { AnalysisPage, CapabilityChart, ComparisonEvidence, EvidenceScatterWorkspace, HeatmapBreakdown } from "./components/pages/InsightsPages";
import { LocaleProvider } from "./i18n/LocaleProvider";

afterEach(cleanup);

const completedRun = {
  id: "run-a",
  display_name: "model-a_math-check_20260808-120000",
  benchmark_id: "math-check",
  benchmark_version: "1",
  status: "completed",
  completed_at: "2026-08-08T12:00:00Z",
} as EvaluationRun;

const secondRun = {
  ...completedRun,
  id: "run-b",
  display_name: "model-b_math-check_20260808-130000",
  benchmark_id: "math-check",
} as EvaluationRun;

const incompatibleRun = {
  ...secondRun,
  id: "run-c",
  display_name: "model-c_truthful-qa_20260808-140000",
  benchmark_id: "truthful-qa",
} as EvaluationRun;

const endpoint = {
  id: "endpoint-a",
  display_name: "Evaluator A",
  model_name: "model-a",
} as Endpoint;

const dataset = {
  id: "dataset-version-a",
  dataset_id: "math-check",
  version: "1",
  capabilities: ["reasoning"],
  languages: ["en"],
  evaluation_type: "classification",
} as Dataset;

const scatterResponse = {
  x_axis: { metric_name: "score", label: "Primary score", unit: "ratio", profile: "all" },
  y_axis: { metric_name: "average_latency_ms", label: "Average latency", unit: "milliseconds", profile: "operational" },
  selected_run_ids: ["run-a", "run-b"],
  eligible_run_count: 2,
  plottable_count: 2,
  plotted_count: 2,
  unavailable_count: 0,
  unavailable_by_axis: { x: 0, y: 0, both: 0 },
  unavailable_reasons: [],
  truncated_count: 0,
  max_points: 500,
  points: [
    { run_id: "run-a", display_name: "model-a_math-check_20260808-120000", model_endpoint_id: "endpoint-a", model_name: "model-a", dataset: "math-check", benchmark_id: "math-check", benchmark_version: "1", status: "completed", created_at: "2026-08-08T12:00:00Z", capabilities: ["reasoning"], languages: ["en"], evaluation_type: "classification", x: .83, y: 320, x_metric: "score", y_metric: "average_latency_ms", x_availability_reason: null, y_availability_reason: null },
    { run_id: "run-b", display_name: "model-b_math-check_20260808-130000", model_endpoint_id: "endpoint-b", model_name: "model-b", dataset: "math-check", benchmark_id: "math-check", benchmark_version: "1", status: "completed", created_at: "2026-08-08T13:00:00Z", capabilities: ["reasoning"], languages: ["en"], evaluation_type: "classification", x: .75, y: 380, x_metric: "score", y_metric: "average_latency_ms", x_availability_reason: null, y_availability_reason: null },
  ],
} as ScatterResponse;

const languageCell = {
  x_key: "model-a",
  x_label: "Evaluator A",
  y_key: "en",
  y_label: "English",
  run_ids: ["run-a"],
  score: .91,
  sample_count: 12,
  confidence_interval: { method: "wilson", lower: .75, upper: .98 },
  success_rate: .92,
  error_rate: .08,
  average_latency_ms: 320,
  estimated_cost: .12,
  currency: "USD",
  baseline_score: null,
  delta: null,
};

const analytics = {
  baseline_run_id: null,
  heatmap: [],
  capability_matrix: [],
  heatmaps: {
    model_benchmark: [],
    model_capability: [],
    model_language: [languageCell],
    model_difficulty: [],
    prompt_benchmark: [],
    model_modality: [],
  },
} as AnalyticsMatrix;

const capabilityCell = {
  model_endpoint_id: "model-a",
  capability: "reasoning",
  accuracy: .8,
  success_rate: .85,
  error_rate: .15,
  average_latency_ms: 250,
  estimated_cost: .04,
  sample_count: 10,
  confidence_interval: null,
  baseline_score: null,
  delta: null,
  run_count: 1,
} as AnalyticsMatrix["capability_matrix"][number];

const comparison = {
  run_a: "run-a",
  run_b: "run-b",
  benchmark: { id: "math-check", version: "1" },
  shared_samples: 12,
  outcomes: { both_correct: 8, run_a_only_correct: 2, run_b_only_correct: 1, both_incorrect: 1 },
  run_a_summary: { samples: { accuracy: .83, success_rate: .92 }, latency_ms: { p95: 320 }, tokens: { output: 1000 } },
  run_b_summary: { samples: { accuracy: .75, success_rate: .83 }, latency_ms: { p95: 380 }, tokens: { output: 1100 } },
  differences: { accuracy: .08, success_rate: .09, error_rate: -.09, average_latency_ms: -60, p95_latency_ms: -60, estimated_cost: -.01, output_tokens: -100 },
  runs: {
    a: { id: "run-a", display_name: "model-a_math-check_20260808-120000", model_endpoint_id: "endpoint-a", model_name: "model-a", status: "completed", created_at: "2026-08-08T12:00:00Z" },
    b: { id: "run-b", display_name: "model-b_math-check_20260808-130000", model_endpoint_id: "endpoint-b", model_name: "model-b", status: "completed", created_at: "2026-08-08T13:00:00Z" },
  },
  named_metrics: [
    { metric_name: "score", label: "Primary score", unit: "ratio", profile: "all", run_a: { value: .83, availability_reason: null, sample_count: 12 }, run_b: { value: .75, availability_reason: null, sample_count: 12 }, delta: .08 },
    { metric_name: "f1_macro", label: "Macro F1", unit: "ratio", profile: "classification", run_a: { value: .8, availability_reason: null, sample_count: 12 }, run_b: { value: null, availability_reason: "Labels were unavailable.", sample_count: 0 }, delta: null },
    { metric_name: "p95_latency_ms", label: "p95 latency", unit: "milliseconds", profile: "operational", run_a: { value: 320, availability_reason: null, sample_count: 12 }, run_b: { value: 380, availability_reason: null, sample_count: 12 }, delta: -60 },
    { metric_name: "estimated_cost", label: "Estimated cost", unit: "currency", profile: "operational", run_a: { value: .04, availability_reason: null, sample_count: 12 }, run_b: { value: .05, availability_reason: null, sample_count: 12 }, delta: -.01 },
    { metric_name: "output_tokens", label: "Output tokens", unit: "tokens", profile: "operational", run_a: { value: 1000, availability_reason: null, sample_count: 12 }, run_b: { value: 1100, availability_reason: null, sample_count: 12 }, delta: -100 },
  ],
  metric_groups: [],
  outcome_distribution: [
    { outcome: "both_correct", count: 8 },
    { outcome: "run_a_only_correct", count: 2 },
    { outcome: "run_b_only_correct", count: 1 },
    { outcome: "both_incorrect", count: 1 },
  ],
} as unknown as Comparison;

comparison.metric_groups = ["ratio", "milliseconds", "currency", "tokens"].map((unit) => ({ unit, metrics: comparison.named_metrics.filter((metric) => metric.unit === unit) }));

function analysisProps(overrides: Partial<React.ComponentProps<typeof AnalysisPage>> = {}) {
  return {
    activeTab: "evidence-matrix" as const,
    busy: null,
    comparison,
    completedRuns: [completedRun, secondRun],
    datasets: [dataset],
    endpoints: [endpoint],
    loadScatter: vi.fn().mockResolvedValue(scatterResponse),
    onRunAChange: vi.fn(),
    onRunBChange: vi.fn(),
    onSubmitComparison: vi.fn((event: React.FormEvent) => event.preventDefault()),
    onTabChange: vi.fn(),
    runA: completedRun.id,
    runB: secondRun.id,
    runs: [completedRun, secondRun],
    ...overrides,
  };
}

function renderInsightsPage(page: React.ReactNode) {
  return render(<LocaleProvider>{page}</LocaleProvider>);
}

describe("insight workspace pages", () => {
  it("loads a bounded scatter with every run selected and equivalent chart/table evidence", async () => {
    const loadScatter = vi.fn().mockResolvedValue(scatterResponse);
    renderInsightsPage(<EvidenceScatterWorkspace datasets={[dataset]} endpoints={[endpoint]} loadScatter={loadScatter} runs={[completedRun, secondRun]} />);

    await waitFor(() => expect(loadScatter).toHaveBeenCalledWith({ x_axis: "score", y_axis: "average_latency_ms", max_points: 500 }));
    expect(screen.getByRole("checkbox", { name: "All runs" })).toBeChecked();
    expect(screen.getByRole("checkbox", { name: /Include model-a_math-check/ })).toBeChecked();
    expect(screen.getByText("2 of 2 eligible runs plotted")).toBeVisible();
    expect(screen.getByText("100%")).toBeVisible();
    expect(screen.getByRole("button", { name: /model-a_math-check_20260808-120000.*83%.*320 ms/ })).toBeVisible();
    expect(screen.getByRole("row", { name: /model-a_math-check_20260808-120000.*83%.*320 ms/ })).toBeVisible();
  });

  it("keeps selectors usable from scatter evidence when shared inventories are unavailable", async () => {
    renderInsightsPage(<EvidenceScatterWorkspace datasets={[]} endpoints={[]} loadScatter={vi.fn().mockResolvedValue(scatterResponse)} runs={[]} />);

    expect(await screen.findByRole("checkbox", { name: /Include model-a_math-check/ })).toBeChecked();
    expect(screen.getByRole("checkbox", { name: /Include model-b_math-check/ })).toBeChecked();
    expect(screen.getByLabelText("Model")).toHaveTextContent("model-a");
    expect(screen.getByLabelText("Dataset")).toHaveTextContent("math-check");
    expect(screen.getByLabelText("Capability")).toHaveTextContent("reasoning");
    expect(screen.getByLabelText("Language")).toHaveTextContent("en");
  });

  it("retains discovered run choices after a filtered response narrows the result", async () => {
    const user = userEvent.setup();
    const loadScatter = vi.fn()
      .mockResolvedValueOnce(scatterResponse)
      .mockResolvedValue({ ...scatterResponse, selected_run_ids: ["run-a"], eligible_run_count: 1, plottable_count: 1, plotted_count: 1, points: [scatterResponse.points[0]] });
    renderInsightsPage(<EvidenceScatterWorkspace datasets={[]} endpoints={[]} loadScatter={loadScatter} runs={[]} />);
    const runB = await screen.findByRole("checkbox", { name: /Include model-b_math-check/ });

    await user.click(runB);
    await user.click(screen.getByRole("button", { name: "Apply filters" }));
    await screen.findByText("1 of 1 eligible runs plotted");

    expect(screen.getByRole("checkbox", { name: /Include model-b_math-check/ })).not.toBeChecked();
  });

  it("applies independent axes, selected runs, and the complete filter set", async () => {
    const user = userEvent.setup();
    const loadScatter = vi.fn().mockResolvedValue(scatterResponse);
    renderInsightsPage(<EvidenceScatterWorkspace datasets={[dataset]} endpoints={[endpoint]} loadScatter={loadScatter} runs={[completedRun, secondRun]} />);
    await screen.findByText("2 of 2 eligible runs plotted");

    await user.selectOptions(screen.getByLabelText("Horizontal axis"), "accuracy");
    await user.selectOptions(screen.getByLabelText("Vertical axis"), "estimated_cost");
    await user.click(screen.getByRole("checkbox", { name: /Include model-b_math-check/ }));
    await user.type(screen.getByLabelText("From date"), "2026-08-01");
    await user.type(screen.getByLabelText("To date"), "2026-08-09");
    await user.selectOptions(screen.getByLabelText("Model"), "endpoint-a");
    await user.selectOptions(screen.getByLabelText("Dataset"), "math-check");
    await user.selectOptions(screen.getByLabelText("Status"), "completed");
    await user.selectOptions(screen.getByLabelText("Capability"), "reasoning");
    await user.selectOptions(screen.getByLabelText("Language"), "en");
    await user.selectOptions(screen.getByLabelText("Evaluation type"), "classification");
    await user.type(screen.getByLabelText("Minimum score"), "0.5");
    await user.type(screen.getByLabelText("Maximum score"), "0.95");
    await user.type(screen.getByLabelText("Minimum accuracy"), "0.6");
    await user.type(screen.getByLabelText("Maximum accuracy"), "0.9");
    await user.type(screen.getByLabelText("Minimum latency (ms)"), "100");
    await user.type(screen.getByLabelText("Maximum latency (ms)"), "500");
    await user.type(screen.getByLabelText("Minimum cost"), "0.01");
    await user.type(screen.getByLabelText("Maximum cost"), "0.2");
    await user.click(screen.getByRole("button", { name: "Apply filters" }));

    await waitFor(() => expect(loadScatter).toHaveBeenLastCalledWith({
      x_axis: "accuracy",
      y_axis: "estimated_cost",
      run_ids: ["run-a"],
      date_from: "2026-08-01T00:00:00.000Z",
      date_to: "2026-08-09T23:59:59.999Z",
      model_endpoint_id: "endpoint-a",
      dataset: "math-check",
      statuses: ["completed"],
      capability: "reasoning",
      language: "en",
      evaluation_type: "classification",
      min_score: .5,
      max_score: .95,
      min_accuracy: .6,
      max_accuracy: .9,
      min_latency_ms: 100,
      max_latency_ms: 500,
      min_cost: .01,
      max_cost: .2,
      max_points: 500,
    }));
  });

  it("supports keyboard point inspection and explains unavailable and truncated evidence", async () => {
    const user = userEvent.setup();
    const constrained = {
      ...scatterResponse,
      eligible_run_count: 11,
      plottable_count: 7,
      plotted_count: 2,
      unavailable_count: 4,
      unavailable_by_axis: { x: 1, y: 2, both: 1 },
      unavailable_reasons: [{ axis: "y" as const, reason: "Cost evidence was not recorded.", count: 3 }],
      truncated_count: 5,
    };
    renderInsightsPage(<EvidenceScatterWorkspace datasets={[dataset]} endpoints={[endpoint]} loadScatter={vi.fn().mockResolvedValue(constrained)} runs={[completedRun, secondRun]} />);

    const point = await screen.findByRole("button", { name: /model-a_math-check_20260808-120000/ });
    point.focus();
    await user.keyboard("{Enter}");

    expect(screen.getByRole("status", { name: "Selected evidence point" })).toHaveTextContent("model-a_math-check_20260808-120000");
    expect(screen.getByText("4 runs omitted because an axis value is unavailable.")).toBeVisible();
    expect(screen.getByRole("listitem")).toHaveTextContent("Y axis · 3 · Cost evidence was not recorded.");
    expect(screen.getByText("5 additional plottable runs were not rendered because the 500-point limit was reached.")).toBeVisible();
  });

  it("resets filters and exposes a retryable query error", async () => {
    const user = userEvent.setup();
    const loadScatter = vi.fn()
      .mockResolvedValueOnce(scatterResponse)
      .mockRejectedValueOnce(new Error("scatter unavailable"))
      .mockResolvedValue(scatterResponse);
    renderInsightsPage(<EvidenceScatterWorkspace datasets={[dataset]} endpoints={[endpoint]} loadScatter={loadScatter} runs={[completedRun, secondRun]} />);
    await screen.findByText("2 of 2 eligible runs plotted");

    await user.selectOptions(screen.getByLabelText("Horizontal axis"), "accuracy");
    await user.click(screen.getByRole("button", { name: "Apply filters" }));
    expect(await screen.findByText("Scatter evidence could not be loaded.")).toBeVisible();
    await user.click(screen.getByRole("button", { name: "Retry" }));
    await screen.findByText("2 of 2 eligible runs plotted");
    await user.click(screen.getByRole("button", { name: "Reset filters" }));

    await waitFor(() => expect(loadScatter).toHaveBeenLastCalledWith({ x_axis: "score", y_axis: "average_latency_ms", max_points: 500 }));
    expect(screen.getByRole("checkbox", { name: "All runs" })).toBeChecked();
  });

  it("keeps capability-chart selection available through keyboard-reachable result bars", async () => {
    const user = userEvent.setup();
    renderInsightsPage(<CapabilityChart cells={[capabilityCell]} />);

    await user.click(screen.getByRole("button", { name: "model-a reasoning: 80%" }));
    expect(screen.getByText(/Selected reasoning: 80% score across 10 samples/)).toBeVisible();
  });

  it("renders the selected heatmap evidence as a directly inspectable breakdown", () => {
    renderInsightsPage(<HeatmapBreakdown cells={[languageCell]} dimension="Model × language" />);

    expect(screen.getByRole("heading", { name: "Model × language breakdown" })).toBeVisible();
    expect(screen.getByRole("cell", { name: "English" })).toBeVisible();
  });

  it("renders unit-aware comparison bars, outcomes, missing reasons, and exact values", () => {
    renderInsightsPage(<ComparisonEvidence comparison={comparison} loading={false} />);

    expect(screen.getByText(/math-check v1/)).toBeVisible();
    expect(screen.getByRole("heading", { name: "Quality · ratio" })).toBeVisible();
    expect(screen.getByRole("heading", { name: "Performance · milliseconds" })).toBeVisible();
    expect(screen.getByRole("img", { name: /Primary score.*Run A 83%.*Run B 75%/ })).toBeVisible();
    expect(screen.getByRole("img", { name: /p95 latency.*Run A 320 ms.*Run B 380 ms/ })).toBeVisible();
    expect(screen.getByRole("img", { name: /Outcome distribution.*Both correct 8.*A only correct 2.*B only correct 1.*Both incorrect 1/ })).toBeVisible();
    expect(screen.getAllByText("Labels were unavailable.")).toHaveLength(2);
    expect(screen.getByRole("row", { name: /Primary score.*83%.*75%.*8%/ })).toBeVisible();
    expect(screen.getByRole("cell", { name: "N/A" })).toBeVisible();
  });

  it("uses immutable display names and blocks incompatible benchmark selections", async () => {
    const user = userEvent.setup();
    const props = analysisProps({ activeTab: "compare-runs", completedRuns: [completedRun, secondRun, incompatibleRun], runB: incompatibleRun.id });
    renderInsightsPage(<AnalysisPage {...props} />);

    expect(screen.getAllByRole("option", { name: /model-a_math-check_20260808-120000/ })).toHaveLength(2);
    expect(screen.getAllByRole("option", { name: /model-c_truthful-qa_20260808-140000/ })).toHaveLength(2);
    expect(screen.getByRole("alert")).toHaveTextContent("Choose runs from the same benchmark version.");
    expect(screen.getByRole("button", { name: "Compare runs" })).toBeDisabled();

    await user.selectOptions(screen.getByLabelText("Run B"), secondRun.id);
    expect(props.onRunBChange).toHaveBeenCalledWith(secondRun.id);
  });

  it("keeps comparison loading and empty states explicit", () => {
    const { rerender } = render(<LocaleProvider><ComparisonEvidence comparison={null} loading /></LocaleProvider>);
    expect(screen.getByText("Comparing selected runs…")).toBeVisible();

    rerender(<LocaleProvider><ComparisonEvidence comparison={null} loading={false} /></LocaleProvider>);
    expect(screen.getByText("Choose two completed runs to begin an evidence-backed comparison.")).toBeVisible();
  });

  it("keeps the scatter workspace exclusive and routes top-level tab changes", async () => {
    const user = userEvent.setup();
    const props = analysisProps({ completedRuns: [completedRun] });
    renderInsightsPage(<AnalysisPage {...props} />);

    expect(screen.getByRole("tab", { name: "Evidence matrix" })).toHaveAttribute("aria-selected", "true");
    expect(await screen.findByLabelText("Horizontal axis")).toBeVisible();
    expect(screen.getByRole("heading", { name: "Evidence scatter" })).toBeVisible();
    expect(screen.queryByLabelText("Run A")).not.toBeInTheDocument();

    await user.click(screen.getByRole("tab", { name: "Compare runs" }));
    expect(props.onTabChange).toHaveBeenCalledWith("compare-runs");
  });

  it("keeps comparison sources, submission, and evidence in the Analysis workspace", async () => {
    const user = userEvent.setup();
    const onRunAChange = vi.fn();
    const onRunBChange = vi.fn();
    const onSubmit = vi.fn((event: React.FormEvent) => event.preventDefault());
    renderInsightsPage(<AnalysisPage {...analysisProps({ activeTab: "compare-runs", onRunAChange, onRunBChange, onSubmitComparison: onSubmit })} />);

    expect(screen.getByRole("tab", { name: "Compare runs" })).toHaveAttribute("aria-selected", "true");
    expect(screen.queryByLabelText("Horizontal axis")).not.toBeInTheDocument();
    await user.selectOptions(screen.getByLabelText("Run A"), secondRun.id);
    await user.selectOptions(screen.getByLabelText("Run B"), completedRun.id);
    await user.click(screen.getByRole("button", { name: "Compare runs" }));

    expect(onRunAChange).toHaveBeenCalledWith(secondRun.id);
    expect(onRunBChange).toHaveBeenCalledWith(completedRun.id);
    expect(onSubmit).toHaveBeenCalledTimes(1);
    expect(screen.getByText(/math-check v1/)).toBeVisible();
    expect(screen.getByRole("cell", { name: "8%" })).toBeVisible();
    expect(screen.getAllByRole("heading", { level: 1 })).toHaveLength(1);
  });
});
