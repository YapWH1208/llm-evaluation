import type { AnalyticsMatrix, Dashboard, Endpoint, EvaluationRun, SystemHealth, Task } from "../api";
import { buildDashboardAnalytics, buildRecentRunRows, type DashboardAnalyticsPoint, type RecentRunRow } from "../dashboard/analytics";
import type { View } from "../dashboard/navigation";
import { overviewCopy, type OverviewCopy } from "../i18n/catalog";
import { useTranslation } from "../i18n/LocaleProvider";
import { EfficiencySignals, EvaluationTrendChart, type DashboardVisualizationFormatters, type DashboardVisualizationLabels } from "./DashboardVisualizations";
import "./overview-dashboard.css";

type OverviewDashboardProps = {
  dashboard: Dashboard | null;
  analytics: AnalyticsMatrix | null;
  systemHealth: SystemHealth | null;
  endpoints: Endpoint[];
  runs: EvaluationRun[];
  tasks: Task[];
  onInspectRun: (runId: string) => void;
  onOpenView: (view: View) => void;
};

type Metric = {
  id: string;
  label: string;
  value: string;
  detail: string;
};

type ReadinessItem = {
  id: string;
  label: string;
  detail: string;
  attention: boolean;
  view: View;
};

function interpolate(template: string, values: Record<string, number | string>) {
  return template.replace(/\{\{(\w+)\}\}/g, (_match, key: string) => String(values[key] ?? ""));
}

function MetricCard({ metric }: { metric: Metric }) {
  return (
    <article className="dashboard-kpi">
      <span>{metric.label}</span>
      <strong>{metric.value}</strong>
      <small>{metric.detail}</small>
    </article>
  );
}

function ComparisonTable({ copy, formatters, points }: { copy: OverviewCopy; formatters: DashboardVisualizationFormatters; points: DashboardAnalyticsPoint[] }) {
  if (points.length === 0) return <p className="dashboard-empty">{copy.noHistory}</p>;

  return (
    <div className="table-scroll">
      <table className="dashboard-table">
        <thead>
          <tr>
            <th>{copy.model}</th>
            <th>{copy.benchmark}</th>
            <th>{copy.sampleCount}</th>
            <th>{copy.accuracy}</th>
            <th>{copy.latency}</th>
            <th>{copy.cost}</th>
            <th>{copy.errorRate}</th>
          </tr>
        </thead>
        <tbody>
          {points.map((point) => (
            <tr key={point.runId}>
              <td data-i18n-preserve title={point.modelName}>{point.modelName}</td>
              <td data-i18n-preserve title={point.benchmarkLabel}>{point.benchmarkLabel}</td>
              <td>{point.sampleCount}</td>
              <td>{formatters.percent(point.accuracy)}</td>
              <td>{formatters.latency(point.averageLatencyMs)}</td>
              <td>{formatters.cost(point.estimatedCost, point.currency)}</td>
              <td className={point.errorRate !== null && point.errorRate > 0 ? "metric-danger" : undefined}>{formatters.percent(point.errorRate)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function RecentEvaluationsTable({ copy, formatDate, formatters, onInspectRun, rows }: { copy: OverviewCopy; formatDate: (value: string | null | undefined) => string; formatters: DashboardVisualizationFormatters; onInspectRun: (runId: string) => void; rows: RecentRunRow[] }) {
  if (rows.length === 0) return <p className="dashboard-empty">{copy.noHistory}</p>;

  return (
    <div className="table-scroll">
      <table className="dashboard-table dashboard-table--runs">
        <thead>
          <tr>
            <th>{copy.recentEvaluations}</th>
            <th>{copy.model}</th>
            <th>{copy.progress}</th>
            <th>{copy.accuracy}</th>
            <th>{copy.p95Latency}</th>
            <th>{copy.started}</th>
            <th aria-label={copy.inspect} />
          </tr>
        </thead>
        <tbody>
          {rows.map((row) => {
            const progress = row.run.total_samples > 0 ? row.run.completed_samples / row.run.total_samples : null;
            return (
              <tr key={row.run.id}>
                <td>
                  <span className={`dashboard-status-badge ${row.run.status}`}>{row.run.status}</span>
                  <strong data-i18n-preserve title={`${row.run.benchmark_id} · v${row.run.benchmark_version}`}>{row.run.benchmark_id}</strong>
                </td>
                <td data-i18n-preserve title={row.modelName}>{row.modelName}</td>
                <td>{formatters.percent(progress)}</td>
                <td>{formatters.percent(row.accuracy)}</td>
                <td>{formatters.latency(row.averageLatencyMs)}</td>
                <td>{formatDate(row.run.started_at ?? row.run.created_at)}</td>
                <td><button aria-label={`${copy.inspect} ${row.run.id}`} className="secondary table-action" onClick={() => onInspectRun(row.run.id)} type="button">{copy.inspect}</button></td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

function ReadinessGrid({ copy, items, onOpenView }: { copy: OverviewCopy; items: ReadinessItem[]; onOpenView: (view: View) => void }) {
  return (
    <div className="readiness-grid">
      {items.map((item) => (
        <article className={item.attention ? "readiness-item is-attention" : "readiness-item"} key={item.id}>
          <span aria-hidden="true" className="status-dot" />
          <div>
            <strong>{item.label}</strong>
            <small>{item.detail}</small>
          </div>
          <button className="secondary" onClick={() => onOpenView(item.view)} type="button">{copy.manage}</button>
        </article>
      ))}
    </div>
  );
}

export function OverviewDashboard({ analytics, dashboard, endpoints, runs, systemHealth, tasks, onInspectRun, onOpenView }: OverviewDashboardProps) {
  const { formatCurrency, formatDate, formatNumber, formatPercent, locale } = useTranslation();
  const copy = overviewCopy[locale];
  const analyticsPoints = buildDashboardAnalytics(runs, analytics);
  const recentRows = buildRecentRunRows(runs, endpoints, analytics);
  const activeTasks = tasks.filter((task) => ["pending", "leased", "running", "retry_scheduled"].includes(task.status));
  const verifiedEndpoints = endpoints.filter((endpoint) => endpoint.status === "available");
  const formatters: DashboardVisualizationFormatters = {
    percent: (value) => value === null ? "--" : formatPercent(value),
    latency: (value) => value === null ? "--" : `${formatNumber(value)} ms`,
    cost: (value, currency) => value === null ? "--" : formatCurrency(value, currency, 4),
  };
  const visualizationLabels: DashboardVisualizationLabels = {
    accuracy: copy.accuracy,
    successRate: copy.successRate,
    evaluationTrend: copy.evaluationTrend,
    latency: copy.latency,
    cost: copy.cost,
    errorRate: copy.errorRate,
    limitedHistory: copy.limitedHistory,
    noHistory: copy.noHistory,
    model: copy.model,
    benchmark: copy.benchmark,
    unknownValue: copy.unknownValue,
  };

  if (!dashboard) {
    return (
      <section className="overview-dashboard" aria-labelledby="dashboard-title">
        <DashboardHeader copy={copy} onOpenView={onOpenView} />
        <section className="dashboard-panel overview-unavailable" aria-label={copy.unavailableRegion}>
          <div>
            <p className="eyebrow">{copy.currentWork}</p>
            <h2>{copy.unavailableTitle}</h2>
            <p className="dashboard-empty">{copy.unavailableDescription}</p>
          </div>
          <div className="overview-actions">
            <button onClick={() => onOpenView("models")} type="button">{copy.configureModel}</button>
            <button className="secondary" onClick={() => onOpenView("runs")} type="button">{copy.openRuns}</button>
          </div>
        </section>
      </section>
    );
  }

  const successfulRate = dashboard.quality.samples.total > 0 ? dashboard.quality.samples.successful / dashboard.quality.samples.total : null;
  const costMetrics = Object.entries(dashboard.api.estimated_cost_by_currency).map(([currency, value]) => ({
    id: `cost-${currency}`,
    label: `${copy.cost} · ${currency}`,
    value: formatters.cost(value, currency),
    detail: copy.completedEvidence,
  }));
  const kpis: Metric[] = [
    { id: "accuracy", label: copy.accuracy, value: formatters.percent(dashboard.quality.samples.accuracy), detail: interpolate(copy.successful, { successful: dashboard.quality.samples.successful, total: dashboard.quality.samples.total }) },
    { id: "success", label: copy.successRate, value: formatters.percent(successfulRate), detail: interpolate(copy.successful, { successful: dashboard.quality.samples.successful, total: dashboard.quality.samples.total }) },
    { id: "latency", label: copy.p95Latency, value: formatters.latency(dashboard.quality.latency_ms.p95), detail: interpolate(copy.measured, { count: dashboard.quality.latency_ms.measured_samples }) },
    ...costMetrics,
    { id: "errors", label: copy.apiErrors, value: formatters.percent(dashboard.api.request_error_rate), detail: interpolate(copy.requests, { count: dashboard.quality.errors.api_errors }) },
  ];
  const systemHealthState = systemHealth === null ? "unknown" : systemHealth.status === "ok" && systemHealth.database_connected ? "ready" : "attention";
  const readinessItems: ReadinessItem[] = [
    { id: "system", label: copy.systemReadiness, detail: systemHealthState === "ready" ? copy.operational : systemHealthState === "unknown" ? copy.unknownValue : copy.attentionNeeded, attention: systemHealthState === "attention", view: "settings" },
    { id: "endpoints", label: copy.modelEndpoints, detail: dashboard.endpoints.available > 0 ? interpolate(copy.availableForEvaluation, { count: dashboard.endpoints.available }) : copy.verifyModel, attention: dashboard.endpoints.available === 0, view: "models" },
    { id: "datasets", label: copy.evaluationData, detail: dashboard.datasets.ready > 0 ? interpolate(dashboard.datasets.ready === 1 ? copy.readyDataset : copy.readyDatasets, { count: dashboard.datasets.ready }) : copy.registerDataset, attention: dashboard.datasets.ready === 0, view: "datasets" },
    { id: "queue", label: copy.queuePressure, detail: dashboard.queue.pending === 0 ? copy.noWorkWaiting : interpolate(dashboard.queue.pending === 1 ? copy.taskNeedsCapacity : copy.tasksNeedCapacity, { count: dashboard.queue.pending }), attention: dashboard.queue.pending > 0, view: "runs" },
    { id: "workers", label: copy.workers, detail: formatNumber(dashboard.workers.active), attention: dashboard.workers.active === 0 && activeTasks.length > 0, view: "runs" },
  ];

  return (
    <section className="overview-dashboard" aria-labelledby="dashboard-title">
      <DashboardHeader copy={copy} onOpenView={onOpenView} />
      <section className="overview-kpis" aria-labelledby="performance-summary-title">
        <h2 className="sr-only" id="performance-summary-title">{copy.performanceSummary}</h2>
        {kpis.map((metric) => <MetricCard key={metric.id} metric={metric} />)}
      </section>
      <div className="overview-analytics-grid">
        <section className="dashboard-panel dashboard-panel--trend" aria-labelledby="evaluation-trend-title">
          <div className="dashboard-panel__heading"><h2 id="evaluation-trend-title">{copy.evaluationTrend}</h2><button className="secondary" onClick={() => onOpenView("analysis")} type="button">{copy.openAnalysis}</button></div>
          <EvaluationTrendChart formatters={formatters} labels={visualizationLabels} points={analyticsPoints} />
        </section>
        <section className="dashboard-panel dashboard-panel--comparison" aria-labelledby="comparison-title">
          <div className="dashboard-panel__heading"><h2 id="comparison-title">{copy.modelBenchmarkComparison}</h2><button className="secondary" onClick={() => onOpenView("analysis")} type="button">{copy.openAnalysis}</button></div>
          <ComparisonTable copy={copy} formatters={formatters} points={analyticsPoints.slice(-6).reverse()} />
        </section>
      </div>
      <section className="dashboard-panel" aria-labelledby="efficiency-title">
        <div className="dashboard-panel__heading"><h2 id="efficiency-title">{copy.latencyCostErrors}</h2></div>
        <EfficiencySignals formatters={formatters} labels={visualizationLabels} points={analyticsPoints} />
      </section>
      <section className="dashboard-panel" aria-labelledby="recent-evaluations-title">
        <div className="dashboard-panel__heading"><h2 id="recent-evaluations-title">{copy.recentEvaluations}</h2><button className="secondary" onClick={() => onOpenView("runs")} type="button">{copy.viewAllRuns}</button></div>
        <RecentEvaluationsTable copy={copy} formatDate={(value) => value ? formatDate(value) : "--"} formatters={formatters} onInspectRun={onInspectRun} rows={recentRows} />
      </section>
      <section className="dashboard-panel" aria-labelledby="system-readiness-title">
        <div className="dashboard-panel__heading"><h2 id="system-readiness-title">{copy.systemReadiness}</h2><span>{interpolate(copy.verified, { count: verifiedEndpoints.length })}</span></div>
        <ReadinessGrid copy={copy} items={readinessItems} onOpenView={onOpenView} />
      </section>
    </section>
  );
}

function DashboardHeader({ copy, onOpenView }: { copy: OverviewCopy; onOpenView: (view: View) => void }) {
  return (
    <header className="overview-dashboard__header">
      <div>
        <p className="eyebrow">{copy.performanceSummary}</p>
        <h1 id="dashboard-title">{copy.dashboardTitle}</h1>
        <p>{copy.dashboardDescription}</p>
      </div>
      <div className="overview-dashboard__actions">
        <button onClick={() => onOpenView("datasets")} type="button">{copy.setupEvaluation}</button>
        <button className="secondary" onClick={() => onOpenView("runs")} type="button">{copy.viewAllRuns}</button>
      </div>
    </header>
  );
}
