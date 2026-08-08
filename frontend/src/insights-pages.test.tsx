import { cleanup, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import { AnalyticsMatrix, Comparison, EvaluationRun } from "./api";
import { AnalysisPage, ComparePage } from "./components/pages/InsightsPages";
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

function renderInsightsPage(page: React.ReactNode) {
  return render(<LocaleProvider>{page}</LocaleProvider>);
}

describe("insight workspace pages", () => {
  it("switches analysis dimensions while keeping the supplied evidence table synchronized", async () => {
    const user = userEvent.setup();
    renderInsightsPage(<AnalysisPage analytics={analytics} completedRuns={[completedRun]} onSelectBaseline={vi.fn().mockResolvedValue(analytics)} />);

    await user.click(screen.getByRole("tab", { name: "Model × language" }));

    expect(screen.getByRole("heading", { name: "Model × language breakdown" })).toBeVisible();
    expect(screen.getByText("Evaluator A")).toBeVisible();
    expect(screen.getByText("English")).toBeVisible();
  });

  it("routes baseline selection through the existing controller callback", async () => {
    const user = userEvent.setup();
    const onSelectBaseline = vi.fn().mockResolvedValue({ ...analytics, baseline_run_id: completedRun.id });
    renderInsightsPage(<AnalysisPage analytics={analytics} completedRuns={[completedRun]} onSelectBaseline={onSelectBaseline} />);

    await user.selectOptions(screen.getByLabelText("Baseline run"), completedRun.id);

    expect(onSelectBaseline).toHaveBeenCalledWith(completedRun.id);
  });

  it("keeps both comparison sources, the submit path, and result evidence in one investigation surface", async () => {
    const user = userEvent.setup();
    const onRunAChange = vi.fn();
    const onRunBChange = vi.fn();
    const onSubmit = vi.fn((event: React.FormEvent) => event.preventDefault());
    renderInsightsPage(<ComparePage busy={null} comparison={comparison} completedRuns={[completedRun, secondRun]} onRunAChange={onRunAChange} onRunBChange={onRunBChange} onSubmit={onSubmit} runA={completedRun.id} runB={secondRun.id} />);

    await user.selectOptions(screen.getByLabelText("Run A"), secondRun.id);
    await user.selectOptions(screen.getByLabelText("Run B"), completedRun.id);
    await user.click(screen.getByRole("button", { name: "Compare runs" }));

    expect(onRunAChange).toHaveBeenCalledWith(secondRun.id);
    expect(onRunBChange).toHaveBeenCalledWith(completedRun.id);
    expect(onSubmit).toHaveBeenCalledTimes(1);
    expect(screen.getByText(/math-check v1/)).toBeVisible();
    expect(screen.getByRole("cell", { name: "8%" })).toBeVisible();
  });
});
