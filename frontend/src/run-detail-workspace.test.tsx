import { cleanup, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it } from "vitest";

import type { AggregateMetric, EvaluationRun, RunSummary } from "./shared/api";
import { RunDetailWorkspace } from "./components/runs/RunDetailWorkspace";
import { LocaleProvider } from "./i18n/LocaleProvider";

afterEach(cleanup);

const run = {
  id: "run-1",
  display_name: "example-model_math-check_20260808T120000Z",
  model_endpoint_id: "endpoint-1",
  benchmark_id: "math-check",
  benchmark_version: "1",
  status: "completed_with_errors",
  total_samples: 10,
  completed_samples: 10,
  successful_samples: 8,
  failed_samples: 2,
  created_at: "2026-08-08T12:00:00Z",
  started_at: "2026-08-08T12:00:01Z",
  completed_at: "2026-08-08T12:05:00Z",
  archived_at: null,
} as EvaluationRun;

const summary: RunSummary = {
  samples: { total: 10, completed: 10, successful: 8, failed: 2, completion_rate: 1, success_rate: .8, accuracy: .8 },
  errors: { total: 2, rate: .2, api_errors: 1, api_error_rate: .1, parser_errors: 1, parser_error_rate: .1, by_type: { timeout: 1, response_parse_error: 1 } },
  latency_ms: { measured_samples: 8, average: 125, p50: 110, p95: 210, p99: 240 },
  tokens: { measured_samples: 8, input: 100, output: 80, total: 180 },
  cost: { measured_samples: 8, estimated: .012, actual: null, currency: "USD" },
  insights: { capabilities: [{ capability: "reasoning", score: .8, sample_count: 10 }], strongest_capability: { capability: "reasoning", score: .8, sample_count: 10 }, weakest_capability: { capability: "reasoning", score: .8, sample_count: 10 }, significant_anomalies: [], major_regressions: [] },
};

const metrics: AggregateMetric[] = [
  { id: "metric-1", run_id: run.id, benchmark_id: run.benchmark_id, model_endpoint_id: run.model_endpoint_id, metric_name: "pass_at_1", metric_label: "Pass@1", metric_value: .8, availability_reason: null, sample_count: 10, confidence_interval: null, aggregation_version: "2", profile_version: "1", unit: "ratio", profile: "code", required_evidence: [], created_at: run.completed_at! },
  { id: "metric-2", run_id: run.id, benchmark_id: run.benchmark_id, model_endpoint_id: run.model_endpoint_id, metric_name: "perplexity", metric_label: "Perplexity", metric_value: null, availability_reason: "Token log probabilities were not recorded.", sample_count: 5482, confidence_interval: null, aggregation_version: "2", profile_version: "1", unit: "perplexity", profile: "language_modeling", required_evidence: ["token_logprobs"], created_at: run.completed_at! },
  { id: "metric-3", run_id: run.id, benchmark_id: run.benchmark_id, model_endpoint_id: run.model_endpoint_id, metric_name: "average_latency_ms", metric_label: "Average latency", metric_value: 125, availability_reason: null, sample_count: 8, confidence_interval: { method: "bootstrap", lower: 100, upper: 140 }, aggregation_version: "2", profile_version: "1", unit: "milliseconds", profile: "operational", required_evidence: ["latency_ms"], created_at: run.completed_at! },
];

function renderWorkspace(reviewSelectionKey: string | null = null) {
  return render(<LocaleProvider><RunDetailWorkspace
    actions={<button type="button">Retry failed</button>}
    effectiveMetric="Pass@1"
    evidence={<p>Evidence slot</p>}
    logs={[{ timestamp: run.created_at, level: "info", event: "run.created", message: "Run created", task_id: null, sample_attempt_id: null, details: {} }]}
    metrics={metrics}
    reports={<p>Reports slot</p>}
    reviewSelectionKey={reviewSelectionKey}
    reviews={<p>Reviews slot</p>}
    run={run}
    summary={summary}
  /></LocaleProvider>);
}

describe("run detail workspace", () => {
  it("starts with an immutable identity header and a scannable overview", () => {
    renderWorkspace();

    expect(screen.getByRole("heading", { level: 2, name: run.display_name })).toBeVisible();
    expect(screen.getByText("completed with errors")).toBeVisible();
    expect(screen.getByRole("button", { name: "Retry failed" })).toBeVisible();
    expect(screen.getByRole("tab", { name: "Overview" })).toHaveAttribute("aria-selected", "true");
    expect(screen.getByText("10/10")).toBeVisible();
    expect(screen.getAllByText("80%")).toHaveLength(2);
    expect(screen.queryByText("Evidence slot")).not.toBeInTheDocument();
  });

  it("separates metrics, evidence, lifecycle, reports, and reviews without losing evidence", async () => {
    const user = userEvent.setup();
    renderWorkspace();

    await user.click(screen.getByRole("tab", { name: "Metrics" }));
    expect(screen.getByRole("cell", { name: "Pass@1 code" })).toBeVisible();
    expect(screen.getAllByRole("cell", { name: "80%" })).not.toHaveLength(0);
    expect(screen.getByText("Token log probabilities were not recorded.")).toBeVisible();
    expect(screen.getByRole("cell", { name: "100–140 ms" })).toBeVisible();
    await user.click(screen.getByRole("tab", { name: "Evidence" }));
    expect(screen.getByText("Evidence slot")).toBeVisible();
    await user.keyboard("{ArrowRight}");
    expect(screen.getByRole("tab", { name: "Lifecycle" })).toHaveAttribute("aria-selected", "true");
    expect(screen.getByText("Run created")).toBeVisible();

    await user.click(screen.getByRole("tab", { name: "Reports" }));
    expect(screen.getByText("Reports slot")).toBeVisible();
    await user.click(screen.getByRole("tab", { name: "Reviews" }));
    expect(screen.getByText("Reviews slot")).toBeVisible();
  });

  it("opens reviews when an evidence attempt is selected", () => {
    const view = renderWorkspace();
    view.rerender(<LocaleProvider><RunDetailWorkspace actions={null} effectiveMetric={null} evidence={<p>Evidence slot</p>} logs={[]} metrics={[]} reports={<p>Reports slot</p>} reviewSelectionKey="attempt-1" reviews={<p>Reviews slot</p>} run={run} summary={summary} /></LocaleProvider>);

    expect(screen.getByRole("tab", { name: "Reviews" })).toHaveAttribute("aria-selected", "true");
    expect(screen.getByText("Reviews slot")).toBeVisible();
  });

  it("labels the perplexity token count instead of presenting it as samples", async () => {
    const user = userEvent.setup();
    renderWorkspace();

    await user.click(screen.getByRole("tab", { name: "Metrics" }));
    expect(screen.getByRole("cell", { name: "5,482 tokens" })).toBeVisible();
  });

  it("groups the lifecycle log by task id without dropping entries", async () => {
    const user = userEvent.setup();
    render(<LocaleProvider><RunDetailWorkspace
      actions={null}
      effectiveMetric={null}
      evidence={<p>Evidence slot</p>}
      logs={[
        { timestamp: run.created_at, level: "info", event: "run.created", message: "Run created", task_id: null, sample_attempt_id: null, details: {} },
        { timestamp: run.created_at, level: "info", event: "task.claimed", message: "Task claimed", task_id: "task-alpha-1234", sample_attempt_id: null, details: {} },
        { timestamp: run.created_at, level: "info", event: "attempt.succeeded", message: "Attempt succeeded", task_id: "task-alpha-1234", sample_attempt_id: "attempt-1", details: { sample_id: "sample-1" } },
        { timestamp: run.created_at, level: "info", event: "task.claimed", message: "Second task claimed", task_id: "task-beta-5678", sample_attempt_id: null, details: {} },
      ]}
      metrics={[]}
      reports={<p>Reports slot</p>}
      reviewSelectionKey={null}
      reviews={<p>Reviews slot</p>}
      run={run}
      summary={summary}
    /></LocaleProvider>);

    await user.click(screen.getByRole("tab", { name: "Lifecycle" }));
    expect(screen.getByText("Run-level events")).toBeVisible();
    expect(screen.getByText("Task task-alp")).toBeVisible();
    expect(screen.getByText("Task task-bet")).toBeVisible();
    expect(screen.getByText("Run created")).toBeVisible();
    expect(screen.getByText("Task claimed")).toBeVisible();
    expect(screen.getByText("Attempt succeeded")).toBeVisible();
    expect(screen.getByText("Second task claimed")).toBeVisible();
  });
});
