import { cleanup, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import { AnalyticsMatrix, Comparison, EvaluationRun } from "./api";
import { AnalysisPage, CapabilityChart, ComparisonEvidence, HeatmapBreakdown } from "./components/pages/InsightsPages";
import { LocaleProvider } from "./i18n/LocaleProvider";

afterEach(cleanup);

const completedRun = {
  id: "run-a",
  benchmark_id: "math-check",
  benchmark_version: "1",
  status: "completed",
  completed_at: "2026-08-08T12:00:00Z",
} as EvaluationRun;

const secondRun = {
  ...completedRun,
  id: "run-b",
  benchmark_id: "math-check",
} as EvaluationRun;

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
} as Comparison;

function analysisProps(overrides: Partial<React.ComponentProps<typeof AnalysisPage>> = {}) {
  return {
    activeTab: "evidence-matrix" as const,
    analytics,
    busy: null,
    comparison,
    completedRuns: [completedRun, secondRun],
    onRunAChange: vi.fn(),
    onRunBChange: vi.fn(),
    onSelectBaseline: vi.fn().mockResolvedValue(analytics),
    onSubmitComparison: vi.fn((event: React.FormEvent) => event.preventDefault()),
    onTabChange: vi.fn(),
    runA: completedRun.id,
    runB: secondRun.id,
    ...overrides,
  };
}

function renderInsightsPage(page: React.ReactNode) {
  return render(<LocaleProvider>{page}</LocaleProvider>);
}

describe("insight workspace pages", () => {
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

  it("presents comparison evidence independently from the source selector state", () => {
    renderInsightsPage(<ComparisonEvidence comparison={comparison} loading={false} />);

    expect(screen.getByText(/math-check v1/)).toBeVisible();
    expect(screen.getByRole("cell", { name: "8%" })).toBeVisible();
  });

  it("switches analysis dimensions while keeping the supplied evidence table synchronized", async () => {
    const user = userEvent.setup();
    renderInsightsPage(<AnalysisPage {...analysisProps({ completedRuns: [completedRun] })} />);

    await user.click(screen.getByRole("tab", { name: "Model × language" }));

    expect(screen.getByRole("heading", { name: "Model × language breakdown" })).toBeVisible();
    expect(screen.getByText("Evaluator A")).toBeVisible();
    expect(screen.getByText("English")).toBeVisible();
  });

  it("keeps the evidence matrix exclusive and routes top-level tab changes", async () => {
    const user = userEvent.setup();
    const props = analysisProps({ completedRuns: [completedRun] });
    renderInsightsPage(<AnalysisPage {...props} />);

    expect(screen.getByRole("tab", { name: "Evidence matrix" })).toHaveAttribute("aria-selected", "true");
    expect(screen.getByLabelText("Baseline run")).toBeVisible();
    expect(screen.queryByLabelText("Run A")).not.toBeInTheDocument();

    await user.click(screen.getByRole("tab", { name: "Compare runs" }));
    expect(props.onTabChange).toHaveBeenCalledWith("compare-runs");
  });

  it("routes baseline selection through the existing controller callback", async () => {
    const user = userEvent.setup();
    const onSelectBaseline = vi.fn().mockResolvedValue({ ...analytics, baseline_run_id: completedRun.id });
    renderInsightsPage(<AnalysisPage {...analysisProps({ completedRuns: [completedRun], onSelectBaseline })} />);

    await user.selectOptions(screen.getByLabelText("Baseline run"), completedRun.id);

    expect(onSelectBaseline).toHaveBeenCalledWith(completedRun.id);
  });

  it("keeps a user-chosen baseline and its delta cells across background refreshes", async () => {
    const user = userEvent.setup();
    const baselineCell = { ...languageCell, baseline_score: .9, delta: -.01 };
    const baselineMatrix = { ...analytics, baseline_run_id: completedRun.id, heatmaps: { ...analytics.heatmaps, model_language: [baselineCell] } } as AnalyticsMatrix;
    const onSelectBaseline = vi.fn().mockResolvedValue(baselineMatrix);
    const { rerender } = render(<LocaleProvider><AnalysisPage {...analysisProps({ completedRuns: [completedRun], onSelectBaseline })} /></LocaleProvider>);

    await user.click(screen.getByRole("tab", { name: "Model × language" }));
    await user.selectOptions(screen.getByLabelText("Baseline run"), completedRun.id);

    expect(screen.getByRole("cell", { name: "90% / -1%" })).toBeVisible();

    rerender(<LocaleProvider><AnalysisPage {...analysisProps({ analytics: { ...analytics, heatmaps: { ...analytics.heatmaps, model_language: [languageCell] } }, completedRuns: [completedRun], onSelectBaseline })} /></LocaleProvider>);

    expect((screen.getByLabelText("Baseline run") as HTMLSelectElement).value).toBe(completedRun.id);
    expect(screen.getByRole("cell", { name: "90% / -1%" })).toBeVisible();
  });

  it("reverts the baseline selector when the requested matrix fails", async () => {
    const user = userEvent.setup();
    const onSelectBaseline = vi.fn().mockRejectedValue(new Error("baseline unavailable"));
    renderInsightsPage(<AnalysisPage {...analysisProps({ completedRuns: [completedRun], onSelectBaseline })} />);

    await user.selectOptions(screen.getByLabelText("Baseline run"), completedRun.id);

    await waitFor(() => expect((screen.getByLabelText("Baseline run") as HTMLSelectElement).value).toBe(""));
  });

  it("wires the active analysis dimension to its tab panel", async () => {
    const user = userEvent.setup();
    renderInsightsPage(<AnalysisPage {...analysisProps({ completedRuns: [completedRun] })} />);

    expect(screen.getByRole("tabpanel", { name: "Model × benchmark" })).toBeVisible();

    await user.click(screen.getByRole("tab", { name: "Model × language" }));

    expect(screen.getByRole("tabpanel", { name: "Model × language" })).toBeVisible();
  });

  it("keeps comparison sources, submission, and evidence in the Analysis workspace", async () => {
    const user = userEvent.setup();
    const onRunAChange = vi.fn();
    const onRunBChange = vi.fn();
    const onSubmit = vi.fn((event: React.FormEvent) => event.preventDefault());
    renderInsightsPage(<AnalysisPage {...analysisProps({ activeTab: "compare-runs", onRunAChange, onRunBChange, onSubmitComparison: onSubmit })} />);

    expect(screen.getByRole("tab", { name: "Compare runs" })).toHaveAttribute("aria-selected", "true");
    expect(screen.queryByLabelText("Baseline run")).not.toBeInTheDocument();
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
