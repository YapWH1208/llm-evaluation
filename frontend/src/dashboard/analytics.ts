import type { AnalyticsMatrix, Endpoint, EvaluationRun } from "../api";

type AnalyticsRow = AnalyticsMatrix["heatmap"][number];

export type DashboardAnalyticsPoint = {
  runId: string;
  completedAt: string | null;
  modelName: string;
  benchmarkLabel: string;
  accuracy: number | null;
  successRate: number | null;
  errorRate: number | null;
  averageLatencyMs: number | null;
  estimatedCost: number | null;
  currency: string | null;
  sampleCount: number;
};

export type RecentRunRow = {
  run: EvaluationRun;
  modelName: string;
  accuracy: number | null;
  successRate: number | null;
  errorRate: number | null;
  averageLatencyMs: number | null;
  estimatedCost: number | null;
  currency: string | null;
  sampleCount: number | null;
};

const TERMINAL_RUN_STATUSES = new Set(["completed", "completed_with_errors", "failed", "cancelled"]);

function timestamp(run: EvaluationRun): string | null {
  return run.completed_at ?? run.started_at ?? run.created_at;
}

function benchmarkLabel(row: AnalyticsRow): string {
  return row.benchmark_version ? `${row.benchmark_id} · v${row.benchmark_version}` : row.benchmark_id;
}

function analyticsByRun(analytics: AnalyticsMatrix | null): Map<string, AnalyticsRow> {
  return new Map((analytics?.heatmap ?? []).map((row) => [row.run_id, row]));
}

function firstText(...values: Array<string | null | undefined>): string {
  return values.find((value) => value?.trim())?.trim() ?? "--";
}

function normalizedCurrency(currency: string | null): string {
  return currency?.trim().toUpperCase() || "UNSPECIFIED";
}

function pointFor(run: EvaluationRun, row: AnalyticsRow): DashboardAnalyticsPoint {
  return {
    runId: run.id,
    completedAt: timestamp(run),
    modelName: firstText(row.model_name),
    benchmarkLabel: benchmarkLabel(row),
    accuracy: row.accuracy,
    successRate: row.success_rate,
    errorRate: row.error_rate,
    averageLatencyMs: row.average_latency_ms,
    estimatedCost: row.estimated_cost,
    currency: row.currency,
    sampleCount: row.sample_count,
  };
}

export function buildDashboardAnalytics(runs: EvaluationRun[], analytics: AnalyticsMatrix | null): DashboardAnalyticsPoint[] {
  const runsById = new Map(runs.map((run) => [run.id, run]));

  return (analytics?.heatmap ?? [])
    .flatMap((row) => {
      const run = runsById.get(row.run_id);
      return run ? [pointFor(run, row)] : [];
    })
    .sort((left, right) => (left.completedAt ?? "").localeCompare(right.completedAt ?? ""))
    .slice(-8);
}

export function buildRecentRunRows(
  runs: EvaluationRun[],
  endpoints: Endpoint[],
  analytics: AnalyticsMatrix | null,
  limit = 6,
): RecentRunRow[] {
  const endpointsById = new Map(endpoints.map((endpoint) => [endpoint.id, endpoint]));
  const rowsByRun = analyticsByRun(analytics);

  return runs
    .map((run, index) => ({ run, index }))
    .sort((left, right) => {
      const leftActive = !TERMINAL_RUN_STATUSES.has(left.run.status);
      const rightActive = !TERMINAL_RUN_STATUSES.has(right.run.status);
      if (leftActive !== rightActive) return leftActive ? -1 : 1;

      const byTimestamp = (timestamp(right.run) ?? "").localeCompare(timestamp(left.run) ?? "");
      return byTimestamp || left.index - right.index;
    })
    .slice(0, limit)
    .map(({ run }) => {
      const row = rowsByRun.get(run.id);
      return {
        run,
        modelName: firstText(endpointsById.get(run.model_endpoint_id)?.display_name, row?.model_name),
        accuracy: row?.accuracy ?? null,
        successRate: row?.success_rate ?? null,
        errorRate: row?.error_rate ?? null,
        averageLatencyMs: row?.average_latency_ms ?? null,
        estimatedCost: row?.estimated_cost ?? null,
        currency: row?.currency ?? null,
        sampleCount: row?.sample_count ?? null,
      };
    });
}

export function groupCostsByCurrency(points: DashboardAnalyticsPoint[]): Map<string, DashboardAnalyticsPoint[]> {
  return points.reduce((groups, point) => {
    if (point.estimatedCost === null) return groups;
    const currency = normalizedCurrency(point.currency);
    const rows = groups.get(currency) ?? [];
    rows.push(point);
    groups.set(currency, rows);
    return groups;
  }, new Map<string, DashboardAnalyticsPoint[]>());
}

export function chartCoordinates(
  values: Array<number | null>,
  width = 100,
  height = 48,
): Array<{ x: number; y: number } | null> {
  const measured = values.filter((value): value is number => value !== null);
  if (measured.length === 0) return values.map(() => null);

  const minimum = Math.min(...measured);
  const maximum = Math.max(...measured);
  const denominator = Math.max(values.length - 1, 1);

  return values.map((value, index) => {
    if (value === null) return null;
    const x = (index / denominator) * width;
    const y = minimum === maximum ? height / 2 : height - ((value - minimum) / (maximum - minimum)) * height;
    return { x, y };
  });
}
