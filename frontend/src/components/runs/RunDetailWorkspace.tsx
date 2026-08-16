import { type ReactNode, useEffect, useState } from "react";

import type { AggregateMetric, EvaluationRun, RunLogEntry, RunSummary } from "../../api";
import { runDetailCopy } from "../../i18n/catalog";
import { useTranslation } from "../../i18n/LocaleProvider";
import type { MetricUnit } from "../../metrics";
import { WorkspaceTabs, workspaceTabId, workspaceTabPanelId } from "../workspace/WorkspaceTabs";

type RunDetailSection = "overview" | "metrics" | "evidence" | "lifecycle" | "reports" | "reviews";

type RunDetailWorkspaceProps = {
  actions: ReactNode;
  effectiveMetric: string | null;
  evidence: ReactNode;
  logs: RunLogEntry[];
  metrics: AggregateMetric[];
  reports: ReactNode;
  reviewSelectionKey: string | null;
  reviews: ReactNode;
  run: EvaluationRun;
  summary: RunSummary | null;
};

function SummaryMetric({ detail, label, value }: { detail?: string; label: string; value: string }) {
  return <article className="run-detail-kpi"><span>{label}</span><strong>{value}</strong>{detail && <small>{detail}</small>}</article>;
}

type LogGroup = { taskId: string | null; entries: RunLogEntry[] };

function groupLogsByTask(entries: RunLogEntry[]): LogGroup[] {
  const groups: LogGroup[] = [];
  const byTask = new Map<string | null, LogGroup>();
  for (const entry of entries) {
    const taskId = entry.task_id ?? null;
    const group = byTask.get(taskId);
    if (group) {
      group.entries.push(entry);
    } else {
      const next = { taskId, entries: [entry] };
      byTask.set(taskId, next);
      groups.push(next);
    }
  }
  return groups;
}

export function RunDetailWorkspace({ actions, effectiveMetric, evidence, logs, metrics, reports, reviewSelectionKey, reviews, run, summary }: RunDetailWorkspaceProps) {
  const { formatCurrency, formatDate, formatNumber, formatPercent, locale } = useTranslation();
  const copy = runDetailCopy[locale];
  const [section, setSection] = useState<RunDetailSection>("overview");

  useEffect(() => setSection("overview"), [run.id]);
  useEffect(() => { if (reviewSelectionKey) setSection("reviews"); }, [reviewSelectionKey]);

  const tabs = [
    { id: "overview" as const, label: copy.overview },
    { id: "metrics" as const, label: copy.metrics },
    { id: "evidence" as const, label: copy.evidence },
    { id: "lifecycle" as const, label: copy.lifecycle },
    { id: "reports" as const, label: copy.reports },
    { id: "reviews" as const, label: copy.reviews },
  ];

  function metricValue(metric: AggregateMetric) {
    if (metric.metric_value === null) return copy.notAvailable;
    return formatMetricValue(metric.metric_value, metric.unit, summary?.cost.currency ?? null, { formatCurrency, formatNumber, formatPercent });
  }

  function metricInterval(metric: AggregateMetric) {
    if (!metric.confidence_interval) return "—";
    const formatters = { formatCurrency, formatNumber, formatPercent };
    const lower = formatMetricValue(metric.confidence_interval.lower, metric.unit, summary?.cost.currency ?? null, formatters);
    const upper = formatMetricValue(metric.confidence_interval.upper, metric.unit, summary?.cost.currency ?? null, formatters);
    if (metric.unit === "milliseconds") return `${formatNumber(metric.confidence_interval.lower)}–${formatNumber(metric.confidence_interval.upper)} ms`;
    return `${lower}–${upper}`;
  }

  return <div className="run-detail-workspace">
    <header className="run-detail-hero">
      <div className="run-detail-identity">
        <p className="eyebrow" data-i18n-preserve>{run.benchmark_id} · v{run.benchmark_version}</p>
        <h2 data-i18n-preserve>{run.display_name || `${run.benchmark_id}_${run.id}`}</h2>
        <div className="run-detail-meta">
          <span className={`badge ${run.status}`}>{run.status.replaceAll("_", " ")}</span>
          <span><strong>{copy.runId}</strong> <span data-i18n-preserve>{run.id}</span></span>
          <span><strong>{copy.endpoint}</strong> <span data-i18n-preserve>{run.model_endpoint_id}</span></span>
          <span><strong>{copy.created}</strong> {formatDate(run.created_at)}</span>
        </div>
      </div>
      {actions && <div className="run-detail-actions">{actions}</div>}
    </header>

    <WorkspaceTabs ariaLabel={copy.sectionsLabel} idPrefix="run-detail" onChange={setSection} tabs={tabs} value={section} />
    <div aria-labelledby={workspaceTabId("run-detail", section)} className="run-detail-tabpanel" id={workspaceTabPanelId("run-detail", section)} role="tabpanel" tabIndex={0}>
      {section === "overview" && <div className="run-detail-stack">
        <section aria-labelledby="run-detail-performance" className="run-detail-section">
          <div className="run-detail-section-heading"><div><p className="eyebrow">{copy.overview}</p><h3 id="run-detail-performance">{copy.performanceTitle}</h3></div>{effectiveMetric && <span><span>{copy.effectiveMetric}</span>: <strong data-i18n-preserve>{effectiveMetric}</strong></span>}</div>
          {summary ? <div className="run-detail-kpis">
            <SummaryMetric detail={formatPercent(summary.samples.completion_rate)} label={copy.completion} value={`${summary.samples.completed}/${summary.samples.total}`} />
            <SummaryMetric detail={`${summary.samples.successful}/${summary.samples.completed} ${copy.samples.toLowerCase()}`} label={copy.accuracy} value={formatPercent(summary.samples.accuracy)} />
            <SummaryMetric detail={`${summary.samples.failed} ${copy.errorRate.toLowerCase()}`} label={copy.successRate} value={formatPercent(summary.samples.success_rate)} />
            <SummaryMetric detail={`${summary.errors.total} ${copy.errorRate.toLowerCase()}`} label={copy.errorRate} value={formatPercent(summary.errors.rate)} />
            <SummaryMetric detail={`${copy.p95Latency} ${formatNumber(summary.latency_ms.p95)} ms`} label={copy.averageLatency} value={`${formatNumber(summary.latency_ms.average)} ms`} />
            <SummaryMetric detail={`${formatNumber(summary.tokens.input, 0)} / ${formatNumber(summary.tokens.output, 0)} ${copy.tokens.toLowerCase()}`} label={copy.cost} value={formatCurrency(summary.cost.estimated, summary.cost.currency)} />
          </div> : <p className="empty">{copy.loadingSummary}</p>}
        </section>
        <section aria-label={copy.lifecycle} className="run-detail-facts">
          <div><span>{copy.benchmark}</span><strong data-i18n-preserve>{run.benchmark_id} v{run.benchmark_version}</strong></div>
          <div><span>{copy.started}</span><strong>{formatDate(run.started_at)}</strong></div>
          <div><span>{copy.completed}</span><strong>{formatDate(run.completed_at)}</strong></div>
        </section>
      </div>}

      {section === "metrics" && <div className="run-detail-stack">
        <section aria-labelledby="run-detail-named-metrics" className="run-detail-section">
          <div className="run-detail-section-heading"><div><p className="eyebrow">{copy.metrics}</p><h3 id="run-detail-named-metrics">{copy.metricsTitle}</h3><p>{copy.metricsDescription}</p></div><span>{metrics.length} {copy.metrics.toLowerCase()}</span></div>
          {metrics.length === 0 ? <p className="empty">{copy.noNamedMetrics}</p> : <div className="table-wrap run-detail-metrics-table"><table><thead><tr><th>{copy.metric}</th><th>{copy.value}</th><th>{copy.samples}</th><th>{copy.availability}</th></tr></thead><tbody>{metrics.map((metric) => <tr key={metric.id}><td><strong data-i18n-preserve>{metric.metric_label}</strong><small data-i18n-preserve>{metric.profile.replaceAll("_", " ")}</small></td><td>{metricValue(metric)}</td><td>{formatNumber(metric.sample_count, 0)}{metric.metric_name === "perplexity" ? ` ${copy.tokens.toLowerCase()}` : ""}</td><td>{metric.metric_value === null ? <span className="run-detail-unavailable" data-i18n-preserve>{metric.availability_reason || copy.notAvailable}</span> : metricInterval(metric)}</td></tr>)}</tbody></table></div>}
        </section>
        {summary && <section className="run-detail-insight-grid">
          <article className="run-detail-section"><h3>{copy.capabilityEvidence}</h3>{summary.insights.capabilities.length === 0 ? <p className="empty">{copy.noCapabilityEvidence}</p> : <div className="table-wrap"><table><thead><tr><th>{copy.capabilityEvidence}</th><th>{copy.value}</th><th>{copy.samples}</th></tr></thead><tbody>{summary.insights.capabilities.map((item) => <tr key={item.capability}><td data-i18n-preserve>{item.capability}</td><td>{formatPercent(item.score)}</td><td>{formatNumber(item.sample_count, 0)}</td></tr>)}</tbody></table></div>}<p className="muted">{copy.strongest}: <span data-i18n-preserve>{summary.insights.strongest_capability?.capability ?? copy.notAvailable}</span> · {copy.weakest}: <span data-i18n-preserve>{summary.insights.weakest_capability?.capability ?? copy.notAvailable}</span></p></article>
          <article className="run-detail-section"><h3>{copy.runSignals}</h3>{summary.insights.significant_anomalies.length === 0 && summary.insights.major_regressions.length === 0 ? <p className="empty">{copy.noRunSignals}</p> : <div className="run-detail-signal-list">{summary.insights.significant_anomalies.map((item) => <p key={item.kind}><strong data-i18n-preserve>{item.kind}</strong> {formatPercent(item.value)} ({formatPercent(item.threshold)})</p>)}{summary.insights.major_regressions.map((item) => <p key={item.metric}><strong data-i18n-preserve>{item.metric}</strong> {formatPercent(item.delta)} / {formatPercent(item.baseline)}</p>)}</div>}</article>
        </section>}
      </div>}

      {section === "evidence" && <div className="run-detail-slot">{evidence}</div>}
      {section === "lifecycle" && <section aria-labelledby="run-detail-lifecycle" className="run-detail-section"><div className="run-detail-section-heading"><div><p className="eyebrow">{copy.lifecycle}</p><h3 id="run-detail-lifecycle">{copy.lifecycleTitle}</h3></div><span>{copy.lifecycleHint}</span></div>{logs.length === 0 ? <p className="empty">{copy.noLogs}</p> : groupLogsByTask(logs.slice(-50).reverse()).map((group) => <section className="run-detail-log-group" key={group.taskId ?? "run"}><h4>{group.taskId ? `${copy.taskGroup} ${group.taskId.slice(0, 8)}` : copy.runGroup}</h4><ol className="run-detail-log">{group.entries.map((entry, index) => <li key={`${entry.event}-${entry.timestamp}-${index}`}><div><strong data-i18n-preserve>{entry.level.toUpperCase()} · {entry.event}</strong><time>{formatDate(entry.timestamp)}</time></div><p data-i18n-preserve>{entry.message}</p><small>{copy.task} <span data-i18n-preserve>{entry.task_id?.slice(0, 8) ?? copy.notAvailable}</span> · {copy.sample} <span data-i18n-preserve>{entry.details.sample_id ? String(entry.details.sample_id) : copy.notAvailable}</span></small></li>)}</ol></section>)}</section>}
      {section === "reports" && <div className="run-detail-slot">{reports}</div>}
      {section === "reviews" && <div className="run-detail-slot">{reviews}</div>}
    </div>
  </div>;
}

function formatMetricValue(value: number, unit: MetricUnit, currency: string | null, formatters: { formatCurrency: (value: number, currency: string | null) => string; formatNumber: (value: number, digits?: number) => string; formatPercent: (value: number) => string }) {
  if (unit === "ratio") return formatters.formatPercent(value);
  if (unit === "milliseconds") return `${formatters.formatNumber(value)} ms`;
  if (unit === "currency") return formatters.formatCurrency(value, currency);
  if (unit === "tokens") return formatters.formatNumber(value, 0);
  return formatters.formatNumber(value);
}
