import { describe, expect, it } from "vitest";

import type { AnalyticsMatrix, Endpoint, EvaluationRun } from "../api";
import { buildDashboardAnalytics, buildRecentRunRows, chartCoordinates, groupCostsByCurrency } from "./analytics";

const emptyHeatmaps: AnalyticsMatrix["heatmaps"] = {
  model_benchmark: [],
  model_capability: [],
  model_language: [],
  model_difficulty: [],
  prompt_benchmark: [],
  model_modality: [],
};

function endpoint(id: string, displayName: string): Endpoint {
  return {
    id,
    display_name: displayName,
    base_url: "https://models.example.test",
    model_name: "model-id",
    protocol_profile: "openai_chat_completions",
    api_key_mask: "****",
    custom_headers: {},
    default_request_body: {},
    timeout_seconds: 60,
    status: "available",
    max_concurrency: 4,
    requests_per_second: null,
    requests_per_minute: null,
    tokens_per_minute: null,
    input_tokens_per_minute: null,
    output_tokens_per_minute: null,
    input_cost_per_million: null,
    output_cost_per_million: null,
    currency: "USD",
    tags: [],
    notes: null,
    last_connection_error: null,
    api_key_max_concurrency: null,
  };
}

function run(overrides: Partial<EvaluationRun> & Pick<EvaluationRun, "id">): EvaluationRun {
  return {
    display_name: "example-model_text-quick-check_20260801T090000Z",
    model_endpoint_id: "endpoint-1",
    created_by: null,
    max_concurrency: null,
    benchmark_id: "text-quick-check",
    benchmark_version: "1.0.0",
    status: "completed",
    total_samples: 10,
    completed_samples: 10,
    successful_samples: 10,
    failed_samples: 0,
    created_at: "2026-08-01T09:00:00Z",
    started_at: "2026-08-01T09:01:00Z",
    completed_at: "2026-08-01T09:02:00Z",
    archived_at: null,
    ...overrides,
  };
}

const analytics: AnalyticsMatrix = {
  baseline_run_id: null,
  heatmap: [
    {
      run_id: "run-new",
      model_endpoint_id: "endpoint-1",
      model_name: "analytics-new",
      benchmark_id: "text-quick-check",
      benchmark_version: "1.0.0",
      accuracy: 0.8,
      success_rate: 0.9,
      error_rate: 0.1,
      average_latency_ms: 240,
      estimated_cost: 2.5,
      currency: "eur",
      required_capabilities: [],
      sample_count: 10,
      confidence_interval: null,
    },
    {
      run_id: "run-old",
      model_endpoint_id: "unknown-endpoint",
      model_name: "analytics-old",
      benchmark_id: "text-quick-check",
      benchmark_version: "1.0.0",
      accuracy: 0,
      success_rate: 0,
      error_rate: 0,
      average_latency_ms: 0,
      estimated_cost: 0,
      currency: "usd",
      required_capabilities: [],
      sample_count: 10,
      confidence_interval: null,
    },
  ],
  capability_matrix: [],
  heatmaps: emptyHeatmaps,
};

describe("dashboard analytics projections", () => {
  it("joins analytics to runs chronologically while preserving measured zeroes", () => {
    const points = buildDashboardAnalytics([
      run({ id: "run-new", completed_at: "2026-08-04T10:00:00Z" }),
      run({ id: "run-old", completed_at: "2026-08-02T10:00:00Z" }),
    ], analytics);

    expect(points.map((point) => point.runId)).toEqual(["run-old", "run-new"]);
    expect(points[0]).toMatchObject({
      modelName: "analytics-old",
      benchmarkLabel: "text-quick-check · v1.0.0",
      accuracy: 0,
      successRate: 0,
      errorRate: 0,
      averageLatencyMs: 0,
      estimatedCost: 0,
      currency: "usd",
    });
  });

  it("keeps unmatched active runs first and resolves model names without fabricating metrics", () => {
    const rows = buildRecentRunRows([
      run({
        id: "run-old",
        model_endpoint_id: "unknown-endpoint",
        created_at: "2026-08-01T09:00:00Z",
        completed_at: "2026-08-02T10:00:00Z",
      }),
      run({
        id: "run-active",
        model_endpoint_id: "endpoint-2",
        status: "running",
        completed_samples: 3,
        successful_samples: 3,
        created_at: "2026-08-05T09:00:00Z",
        completed_at: null,
      }),
      run({ id: "run-new", created_at: "2026-08-03T09:00:00Z", completed_at: "2026-08-04T10:00:00Z" }),
    ], [endpoint("endpoint-1", "Production evaluator"), endpoint("endpoint-2", "Canary evaluator")], analytics);

    expect(rows.map((row) => row.run.id)).toEqual(["run-active", "run-new", "run-old"]);
    expect(rows[0]).toMatchObject({ modelName: "Canary evaluator", accuracy: null, averageLatencyMs: null, estimatedCost: null });
    expect(rows[1]).toMatchObject({ modelName: "Production evaluator", accuracy: 0.8, currency: "eur" });
    expect(rows[2]).toMatchObject({ modelName: "analytics-old", errorRate: 0 });
  });

  it("treats runs completed with errors as terminal instead of active in recent rows", () => {
    const rows = buildRecentRunRows([
      run({ id: "run-errors", status: "completed_with_errors", created_at: "2026-08-03T09:00:00Z", completed_at: "2026-08-03T10:00:00Z" }),
      run({ id: "run-clean", created_at: "2026-08-04T09:00:00Z", completed_at: "2026-08-04T10:00:00Z" }),
      run({ id: "run-running", status: "running", created_at: "2026-08-05T09:00:00Z", completed_at: null }),
    ], [], null);

    expect(rows.map((row) => row.run.id)).toEqual(["run-running", "run-clean", "run-errors"]);
  });

  it("groups cost evidence by normalized currency without cross-currency totals", () => {
    const points = buildDashboardAnalytics([
      run({ id: "run-old", completed_at: "2026-08-02T10:00:00Z" }),
      run({ id: "run-new", completed_at: "2026-08-04T10:00:00Z" }),
    ], analytics);

    const costs = groupCostsByCurrency(points);

    expect([...costs.keys()]).toEqual(["USD", "EUR"]);
    expect(costs.get("USD")?.map((point) => point.estimatedCost)).toEqual([0]);
    expect(costs.get("EUR")?.map((point) => point.estimatedCost)).toEqual([2.5]);
  });

  it("keeps unknown chart points disconnected and centers flat measured series", () => {
    expect(chartCoordinates([0, null, 0])).toEqual([
      { x: 0, y: 24 },
      null,
      { x: 100, y: 24 },
    ]);
  });
});
