import type { Dashboard, Endpoint, EvaluationRun, Task } from "../api";
import type { View } from "../dashboard/navigation";
import { overviewCopy } from "../i18n/catalog";
import { useTranslation } from "../i18n/LocaleProvider";
import "./overview-dashboard.css";

type OverviewDashboardProps = {
  dashboard: Dashboard | null;
  endpoints: Endpoint[];
  runs: EvaluationRun[];
  tasks: Task[];
  onInspectRun: (runId: string) => void;
  onOpenView: (view: View) => void;
};

const terminalRunStatuses = new Set(["completed", "completed_with_errors", "cancelled", "failed"]);

function interpolate(template: string, values: Record<string, number | string>) {
  return template.replace(/\{\{(\w+)\}\}/g, (_match, key: string) => String(values[key] ?? ""));
}

function MetricCard({ label, value, detail }: { label: string; value: string | number; detail: string }) {
  return <div className="metric-card"><span>{label}</span><strong>{value}</strong><small>{detail}</small></div>;
}

export function OverviewDashboard({ dashboard, endpoints, runs, tasks, onInspectRun, onOpenView }: OverviewDashboardProps) {
  const { formatCurrency, formatDate, formatNumber, formatPercent, locale } = useTranslation();
  const copy = overviewCopy[locale];
  const activeRuns = runs.filter((run) => !terminalRunStatuses.has(run.status)).slice(0, 4);
  const activeTasks = tasks.filter((task) => ["pending", "leased", "running", "retry_scheduled"].includes(task.status));
  const verifiedEndpoints = endpoints.filter((endpoint) => endpoint.status === "available");
  const formatCost = (costs: Record<string, number>) => Object.entries(costs).map(([currency, value]) => formatCurrency(value, currency, 4)).join(" · ") || "--";

  if (!dashboard) {
    return <section className="panel overview-unavailable" aria-label={copy.unavailableRegion}>
      <div>
        <p className="eyebrow">{copy.currentWork}</p>
        <h2>{copy.unavailableTitle}</h2>
        <p className="empty">{copy.unavailableDescription}</p>
      </div>
      <div className="overview-actions">
        <button onClick={() => onOpenView("models")}>{copy.configureModel}</button>
        <button className="secondary" onClick={() => onOpenView("runs")}>{copy.openRuns}</button>
      </div>
    </section>;
  }

  return <div className="overview-dashboard">
    <section className="overview-hero" aria-label={copy.operations}>
      <div>
        <p className="eyebrow">{copy.operations}</p>
        <h2>{copy.heroTitle}</h2>
        <p>{copy.heroDescription}</p>
      </div>
      <div className="overview-hero-actions">
        <button onClick={() => onOpenView("runs")}>{copy.viewAllRuns}</button>
        <button className="secondary" onClick={() => onOpenView("workspace")}>{copy.prepareWorkspace}</button>
      </div>
    </section>

    <section className="dashboard" aria-label={copy.operationalStatus}>
      <MetricCard label={copy.activeRuns} value={dashboard.runs.active} detail={interpolate(copy.pendingLeased, { pending: dashboard.queue.pending, leased: dashboard.queue.leased })} />
      <MetricCard label={copy.endpoints} value={`${dashboard.endpoints.available}/${dashboard.endpoints.total}`} detail={interpolate(copy.unavailable, { count: dashboard.endpoints.unavailable })} />
      <MetricCard label={copy.workers} value={dashboard.workers.active} detail={interpolate(copy.activeQueueTasks, { count: activeTasks.length })} />
      <MetricCard label={copy.estimatedCost} value={formatCost(dashboard.api.estimated_cost_by_currency)} detail={copy.completedEvidence} />
    </section>

    <section className="overview-grid">
      <article className="panel overview-current-work">
        <div className="section-title"><div><p className="eyebrow">{copy.currentWork}</p><h2>{copy.runsInProgress}</h2></div><button className="secondary" onClick={() => onOpenView("runs")}>{copy.openRuns}</button></div>
        {activeRuns.length === 0 ? <div className="overview-empty"><strong>{copy.noActiveRuns}</strong><span>{copy.noActiveDescription}</span><button onClick={() => onOpenView("workspace")}>{copy.setupEvaluation}</button></div> : <div className="overview-run-list">
          {activeRuns.map((run) => <button className="overview-run" key={run.id} onClick={() => onInspectRun(run.id)}>
            <span className={`badge ${run.status}`}>{run.status}</span>
            <strong data-i18n-preserve>{run.benchmark_id} <small>v{run.benchmark_version}</small></strong>
            <span>{run.completed_samples}/{run.total_samples} {copy.samples}</span>
            <span className="overview-run-link">{copy.inspect}</span>
          </button>)}
        </div>}
      </article>

      <article className="panel overview-readiness">
        <div className="section-title"><div><p className="eyebrow">{copy.readiness}</p><h2>{copy.workspaceReady}</h2></div><span>{interpolate(copy.verified, { count: verifiedEndpoints.length })}</span></div>
        <div className="overview-readiness-list">
          <div><span className={`status-dot ${dashboard.endpoints.available > 0 ? "ready" : "attention"}`} /><div><strong>{copy.modelEndpoints}</strong><small>{dashboard.endpoints.available > 0 ? interpolate(copy.availableForEvaluation, { count: dashboard.endpoints.available }) : copy.verifyModel}</small></div><button className="secondary" onClick={() => onOpenView("models")}>{dashboard.endpoints.available > 0 ? copy.manage : copy.configure}</button></div>
          <div><span className={`status-dot ${dashboard.datasets.ready > 0 ? "ready" : "attention"}`} /><div><strong>{copy.evaluationData}</strong><small>{dashboard.datasets.ready > 0 ? interpolate(dashboard.datasets.ready === 1 ? copy.readyDataset : copy.readyDatasets, { count: dashboard.datasets.ready }) : copy.registerDataset}</small></div><button className="secondary" onClick={() => onOpenView("datasets")}>{dashboard.datasets.ready > 0 ? copy.review : copy.addData}</button></div>
          <div><span className={`status-dot ${dashboard.queue.pending === 0 ? "ready" : "attention"}`} /><div><strong>{copy.queuePressure}</strong><small>{dashboard.queue.pending === 0 ? copy.noWorkWaiting : interpolate(dashboard.queue.pending === 1 ? copy.taskNeedsCapacity : copy.tasksNeedCapacity, { count: dashboard.queue.pending })}</small></div><button className="secondary" onClick={() => onOpenView("queue")}>{copy.inspectQueue}</button></div>
        </div>
      </article>
    </section>

    <section className="overview-grid overview-bottom-grid">
      <article className="panel">
        <div className="section-title"><div><p className="eyebrow">{copy.evaluationHealth}</p><h2>{copy.qualityAtGlance}</h2></div><button className="secondary" onClick={() => onOpenView("analysis")}>{copy.openAnalysis}</button></div>
        <div className="metric-grid">
          <MetricCard label={copy.accuracy} value={formatPercent(dashboard.quality.samples.accuracy)} detail={interpolate(copy.successful, { successful: dashboard.quality.samples.successful, total: dashboard.quality.samples.total })} />
          <MetricCard label={copy.apiErrors} value={formatPercent(dashboard.api.request_error_rate)} detail={interpolate(copy.requests, { count: dashboard.quality.errors.api_errors })} />
          <MetricCard label={copy.p95Latency} value={`${formatNumber(dashboard.quality.latency_ms.p95)} ms`} detail={interpolate(copy.measured, { count: dashboard.quality.latency_ms.measured_samples })} />
          <MetricCard label={copy.tokens} value={formatNumber(dashboard.quality.tokens.total)} detail={interpolate(copy.inputOutput, { input: formatNumber(dashboard.quality.tokens.input), output: formatNumber(dashboard.quality.tokens.output) })} />
        </div>
      </article>

      <article className="panel">
        <div className="section-title"><div><p className="eyebrow">{copy.completedWork}</p><h2>{copy.recentRuns}</h2></div><span>{interpolate(copy.complete, { count: dashboard.runs.completed })}</span></div>
        {dashboard.runs.recent_completed.length === 0 ? <div className="overview-empty"><strong>{copy.noCompleted}</strong><span>{copy.noCompletedDescription}</span><button className="secondary" onClick={() => onOpenView("runs")}>{copy.runHistory}</button></div> : <div className="recent-list">
          {dashboard.runs.recent_completed.slice(0, 4).map((run) => <button key={run.id} className="recent-run" onClick={() => onInspectRun(run.id)}><span className={`badge ${run.status}`}>{run.status}</span><strong>{run.benchmark_id}</strong><span>{run.completed_samples}/{run.total_samples} {copy.samples} · {formatDate(run.completed_at)}</span></button>)}
        </div>}
      </article>
    </section>
  </div>;
}
