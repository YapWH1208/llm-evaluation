import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";

import type { DashboardAnalyticsPoint } from "../dashboard/analytics";
import { EfficiencySignals, EvaluationTrendChart, type DashboardVisualizationFormatters, type DashboardVisualizationLabels } from "./DashboardVisualizations";

afterEach(cleanup);

const labels: DashboardVisualizationLabels = {
  accuracy: "Accuracy",
  successRate: "Success rate",
  evaluationTrend: "Evaluation trend",
  latency: "Latency",
  cost: "Cost",
  errorRate: "Error rate",
  limitedHistory: "More completed runs are needed to show a trend.",
  noHistory: "Evaluation history is not available yet.",
  model: "Model",
  benchmark: "Benchmark",
  unknownValue: "Not available",
};

const formatters: DashboardVisualizationFormatters = {
  percent: (value) => value === null ? "--" : `${Math.round(value * 100)}%`,
  latency: (value) => value === null ? "--" : `${value} ms`,
  cost: (value, currency) => value === null ? "--" : `${currency ?? "USD"} ${value.toFixed(2)}`,
};

const points: DashboardAnalyticsPoint[] = [
  {
    runId: "run-a",
    completedAt: "2026-08-01T09:00:00Z",
    modelName: "Evaluator A",
    benchmarkLabel: "text-quick-check · v1.0.0",
    accuracy: 0,
    successRate: 0,
    errorRate: 0,
    averageLatencyMs: 0,
    estimatedCost: 0,
    currency: "USD",
    sampleCount: 12,
  },
  {
    runId: "run-b",
    completedAt: "2026-08-02T09:00:00Z",
    modelName: "Evaluator B",
    benchmarkLabel: "text-quick-check · v1.0.0",
    accuracy: 0.8,
    successRate: 0.9,
    errorRate: 0.1,
    averageLatencyMs: 240,
    estimatedCost: 1.25,
    currency: "EUR",
    sampleCount: 12,
  },
];

describe("dashboard visualizations", () => {
  it("renders an honest empty trend state without an SVG", () => {
    render(<EvaluationTrendChart formatters={formatters} labels={labels} points={[]} />);

    expect(screen.getByText(labels.noHistory)).toBeVisible();
    expect(screen.queryByRole("img", { name: labels.evaluationTrend })).not.toBeInTheDocument();
  });

  it("keeps one observed run as accessible evidence instead of inventing a trend", () => {
    render(<EvaluationTrendChart formatters={formatters} labels={labels} points={[points[0]]} />);

    expect(screen.getByText(labels.limitedHistory)).toBeVisible();
    expect(screen.queryByRole("img", { name: labels.evaluationTrend })).not.toBeInTheDocument();
    expect(document.querySelectorAll("tbody tr")).toHaveLength(1);
    expect(document.body).toHaveTextContent("Evaluator A");
    expect(document.body).toHaveTextContent("0%");
  });

  it("renders two measured trend series and a text-equivalent evidence table", () => {
    render(<EvaluationTrendChart formatters={formatters} labels={labels} points={points} />);

    expect(screen.getByRole("img", { name: labels.evaluationTrend })).toBeVisible();
    expect(document.querySelectorAll("[data-trend-series]")).toHaveLength(2);
    expect(document.querySelectorAll("[data-trend-point]")).toHaveLength(4);
    expect(document.querySelector('[data-trend-point="accuracy"][data-value="0"]')).toHaveAttribute("cy", "104");
    expect(document.querySelectorAll(".trend-axis-label")).toHaveLength(3);
    expect(document.querySelector("[data-trend-point='accuracy'] title")).toHaveTextContent("Evaluator A · text-quick-check · v1.0.0 · Accuracy 0%");
    expect(document.querySelectorAll("tbody tr")).toHaveLength(2);
    expect(document.body).toHaveTextContent("80%");
    expect(document.body).toHaveTextContent("90%");
  });

  it("shows zeroes, currencies, and errors as separate efficiency signals", () => {
    render(<EfficiencySignals formatters={formatters} labels={labels} points={points} />);

    expect(screen.getByText("0 ms")).toBeVisible();
    expect(screen.getByText("USD 0.00")).toBeVisible();
    expect(screen.getByText("EUR 1.25")).toBeVisible();
    expect(screen.getByText("10%")).toBeVisible();
    expect(screen.queryByText(labels.unknownValue)).not.toBeInTheDocument();
    expect(document.querySelector('.efficiency-row:first-child [data-signal="error"] .signal-fill')).toHaveStyle({ width: "10%" });
  });

  it("never compares cost bar lengths across currencies", () => {
    render(<EfficiencySignals formatters={formatters} labels={labels} points={[
      { ...points[0], estimatedCost: 1, currency: "USD" },
      { ...points[1], estimatedCost: 100, currency: "EUR" },
    ]} />);

    const costFills = [...document.querySelectorAll('[data-signal="cost"] .signal-fill')];
    expect(costFills).toHaveLength(2);
    expect(costFills[0]).toHaveStyle({ width: "100%" });
    expect(costFills[1]).toHaveStyle({ width: "100%" });
  });
});
