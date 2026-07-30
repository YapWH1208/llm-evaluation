import type { Dashboard, Endpoint, EvaluationRun, Task } from "../api";
import type { View } from "../dashboard/navigation";
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

function formatNumber(value: number | null | undefined, digits = 2) {
  return value === null || value === undefined ? "--" : new Intl.NumberFormat(undefined, { maximumFractionDigits: digits }).format(value);
}

function formatPercent(value: number | null | undefined) {
  return value === null || value === undefined ? "--" : `${(value * 100).toFixed(1)}%`;
}

function formatDate(value: string | null) {
  return value ? new Intl.DateTimeFormat(document.documentElement.lang || undefined, { dateStyle: "medium", timeStyle: "short" }).format(new Date(value)) : "Not recorded";
}

function formatCost(costs: Record<string, number>) {
  const values = Object.entries(costs).map(([currency, value]) => new Intl.NumberFormat(undefined, { style: "currency", currency, maximumFractionDigits: 4 }).format(value));
  return values.join(" · ") || "--";
}

function MetricCard({ label, value, detail }: { label: string; value: string | number; detail: string }) {
  return <div className="metric-card"><span>{label}</span><strong>{value}</strong><small>{detail}</small></div>;
}

export function OverviewDashboard({ dashboard, endpoints, runs, tasks, onInspectRun, onOpenView }: OverviewDashboardProps) {
  const activeRuns = runs.filter((run) => !terminalRunStatuses.has(run.status)).slice(0, 4);
  const activeTasks = tasks.filter((task) => ["pending", "leased", "running", "retry_scheduled"].includes(task.status));
  const verifiedEndpoints = endpoints.filter((endpoint) => endpoint.status === "available");

  if (!dashboard) {
    return <section className="panel overview-unavailable" aria-label="Operational overview unavailable">
      <div>
        <p className="eyebrow">Overview</p>
        <h2>Operational signals are loading</h2>
        <p className="empty">The workspace is still reachable. Configure a model or inspect your evaluation runs while live status becomes available.</p>
      </div>
      <div className="overview-actions">
        <button onClick={() => onOpenView("models")}>Configure a model</button>
        <button className="secondary" onClick={() => onOpenView("runs")}>Open runs</button>
      </div>
    </section>;
  }

  return <div className="overview-dashboard">
    <section className="overview-hero" aria-label="Evaluation overview">
      <div>
        <p className="eyebrow">Evaluation operations</p>
        <h2>Keep every evaluation moving</h2>
        <p>Monitor current work, verify capacity, and act on the next setup step from one place.</p>
      </div>
      <div className="overview-hero-actions">
        <button onClick={() => onOpenView("runs")}>View all runs</button>
        <button className="secondary" onClick={() => onOpenView("workspace")}>Prepare workspace</button>
      </div>
    </section>

    <section className="dashboard" aria-label="Operational status">
      <MetricCard label="Active runs" value={dashboard.runs.active} detail={`${dashboard.queue.pending} pending · ${dashboard.queue.leased} leased`} />
      <MetricCard label="Endpoints" value={`${dashboard.endpoints.available}/${dashboard.endpoints.total}`} detail={`${dashboard.endpoints.unavailable} unavailable`} />
      <MetricCard label="Workers" value={dashboard.workers.active} detail={`${activeTasks.length} active queue tasks`} />
      <MetricCard label="Estimated cost" value={formatCost(dashboard.api.estimated_cost_by_currency)} detail="completed run evidence" />
    </section>

    <section className="overview-grid">
      <article className="panel overview-current-work">
        <div className="section-title"><div><p className="eyebrow">Current work</p><h2>Runs in progress</h2></div><button className="secondary" onClick={() => onOpenView("runs")}>Open runs</button></div>
        {activeRuns.length === 0 ? <div className="overview-empty"><strong>No active runs</strong><span>Start from a verified endpoint, benchmark, and dataset.</span><button onClick={() => onOpenView("workspace")}>Set up an evaluation</button></div> : <div className="overview-run-list">
          {activeRuns.map((run) => <button className="overview-run" key={run.id} onClick={() => onInspectRun(run.id)}>
            <span className={`badge ${run.status}`}>{run.status}</span>
            <strong>{run.benchmark_id} <small>v{run.benchmark_version}</small></strong>
            <span>{run.completed_samples}/{run.total_samples} samples</span>
            <span className="overview-run-link">Inspect</span>
          </button>)}
        </div>}
      </article>

      <article className="panel overview-readiness">
        <div className="section-title"><div><p className="eyebrow">Readiness</p><h2>Keep the workspace ready</h2></div><span>{verifiedEndpoints.length} verified</span></div>
        <div className="overview-readiness-list">
          <div><span className={`status-dot ${dashboard.endpoints.available > 0 ? "ready" : "attention"}`} /><div><strong>Model endpoints</strong><small>{dashboard.endpoints.available > 0 ? `${dashboard.endpoints.available} available for evaluation` : "Verify a model before queueing work"}</small></div><button className="secondary" onClick={() => onOpenView("models")}>{dashboard.endpoints.available > 0 ? "Manage" : "Configure"}</button></div>
          <div><span className={`status-dot ${dashboard.datasets.ready > 0 ? "ready" : "attention"}`} /><div><strong>Evaluation data</strong><small>{dashboard.datasets.ready > 0 ? `${dashboard.datasets.ready} ready dataset${dashboard.datasets.ready === 1 ? "" : "s"}` : "Register a dataset to start a benchmark"}</small></div><button className="secondary" onClick={() => onOpenView("datasets")}>{dashboard.datasets.ready > 0 ? "Review" : "Add data"}</button></div>
          <div><span className={`status-dot ${dashboard.queue.pending === 0 ? "ready" : "attention"}`} /><div><strong>Queue pressure</strong><small>{dashboard.queue.pending === 0 ? "No work is waiting" : `${dashboard.queue.pending} task${dashboard.queue.pending === 1 ? "" : "s"} need capacity`}</small></div><button className="secondary" onClick={() => onOpenView("queue")}>Inspect queue</button></div>
        </div>
      </article>
    </section>

    <section className="overview-grid overview-bottom-grid">
      <article className="panel">
        <div className="section-title"><div><p className="eyebrow">Evaluation health</p><h2>Quality at a glance</h2></div><button className="secondary" onClick={() => onOpenView("analysis")}>Open analysis</button></div>
        <div className="metric-grid">
          <MetricCard label="Accuracy" value={formatPercent(dashboard.quality.samples.accuracy)} detail={`${dashboard.quality.samples.successful}/${dashboard.quality.samples.total} successful`} />
          <MetricCard label="API errors" value={formatPercent(dashboard.api.request_error_rate)} detail={`${dashboard.quality.errors.api_errors} requests`} />
          <MetricCard label="P95 latency" value={`${formatNumber(dashboard.quality.latency_ms.p95)} ms`} detail={`${dashboard.quality.latency_ms.measured_samples} measured`} />
          <MetricCard label="Tokens" value={formatNumber(dashboard.quality.tokens.total)} detail={`${formatNumber(dashboard.quality.tokens.input)} in / ${formatNumber(dashboard.quality.tokens.output)} out`} />
        </div>
      </article>

      <article className="panel">
        <div className="section-title"><div><p className="eyebrow">Completed work</p><h2>Recent runs</h2></div><span>{dashboard.runs.completed} complete</span></div>
        {dashboard.runs.recent_completed.length === 0 ? <div className="overview-empty"><strong>No completed runs yet</strong><span>Results will appear here after the first evaluation finishes.</span><button className="secondary" onClick={() => onOpenView("runs")}>See run history</button></div> : <div className="recent-list">
          {dashboard.runs.recent_completed.slice(0, 4).map((run) => <button key={run.id} className="recent-run" onClick={() => onInspectRun(run.id)}><span className={`badge ${run.status}`}>{run.status}</span><strong>{run.benchmark_id}</strong><span>{run.completed_samples}/{run.total_samples} samples · {formatDate(run.completed_at)}</span></button>)}
        </div>}
      </article>
    </section>
  </div>;
}
