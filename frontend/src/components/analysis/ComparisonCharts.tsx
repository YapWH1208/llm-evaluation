import type { Comparison } from "../../shared/api";
import { comparisonCopy } from "../../i18n/catalog";
import { useTranslation } from "../../i18n/LocaleProvider";
import { WorkspacePanel } from "../workspace/WorkspacePanel";

type MetricRow = Comparison["named_metrics"][number];

export function ComparisonEvidence({ comparison, loading }: { comparison: Comparison | null; loading: boolean }) {
  const { formatDate, formatNumber, formatPercent, locale } = useTranslation();
  const copy = comparisonCopy[locale];
  if (!comparison) return <WorkspacePanel description={copy.description} title={copy.title}><p aria-live="polite" className="empty">{loading ? copy.loading : copy.empty}</p></WorkspacePanel>;

  const displayValue = (value: number | null, unit: string) => {
    if (value === null) return copy.notAvailable;
    if (unit === "ratio") return formatPercent(value);
    const formatted = formatNumber(value, unit === "currency" ? 6 : 2);
    if (unit === "milliseconds") return `${formatted} ms`;
    if (unit === "tokens") return `${formatted} ${copy.tokens}`;
    return formatted;
  };
  const groups = comparison.metric_groups?.length ? comparison.metric_groups : groupMetrics(comparison.named_metrics ?? []);
  const outcomes = comparison.outcome_distribution?.length ? comparison.outcome_distribution : outcomeRows(comparison);
  const outcomeLabels: Record<Comparison["outcome_distribution"][number]["outcome"], string> = {
    both_correct: copy.bothCorrect,
    run_a_only_correct: copy.aOnlyCorrect,
    run_b_only_correct: copy.bOnlyCorrect,
    both_incorrect: copy.bothIncorrect,
  };
  const outcomeLabel = outcomes.map((item) => `${outcomeLabels[item.outcome]} ${item.count}`).join("; ");
  const outcomeTotal = outcomes.reduce((total, item) => total + item.count, 0);

  return <div className="workspace-comparison-stack">
    <WorkspacePanel className="workspace-comparison-overview" description={<span data-i18n-preserve>{comparison.benchmark.id} v{comparison.benchmark.version} · {comparison.shared_samples} {copy.sharedSamples}</span>} title={copy.title}>
      <div className="workspace-comparison-runs">
        {(["a", "b"] as const).map((side) => <article key={side}><span>{side === "a" ? copy.runA : copy.runB}</span><strong data-i18n-preserve>{comparison.runs[side].display_name}</strong><small data-i18n-preserve>{comparison.runs[side].model_name} · {formatDate(comparison.runs[side].created_at)}</small></article>)}
      </div>
    </WorkspacePanel>

    <div className="workspace-comparison-groups">
      {groups.length === 0 ? <WorkspacePanel description={copy.noMetricsDescription} title={copy.metricCharts}><p className="empty">{copy.noMetrics}</p></WorkspacePanel> : groups.map((group) => <MetricGroupChart copy={copy} displayValue={displayValue} group={group} key={group.unit} />)}
    </div>

    <WorkspacePanel className="workspace-outcome-panel" description={copy.outcomeDescription} title={copy.outcomeTitle}>
      <div aria-label={`${copy.outcomeTitle}: ${outcomeLabel}`} className="workspace-outcome-chart" role="img">
        <div className="workspace-outcome-stack">{outcomes.map((item, index) => <span className={`outcome-${index}`} key={item.outcome} style={{ width: `${outcomeTotal ? (item.count / outcomeTotal) * 100 : 0}%` }} />)}</div>
        <div className="workspace-outcome-legend">{outcomes.map((item, index) => <span key={item.outcome}><i className={`outcome-${index}`} /><strong>{item.count}</strong>{outcomeLabels[item.outcome]}</span>)}</div>
      </div>
    </WorkspacePanel>

    <WorkspacePanel className="workspace-comparison-table-panel" description={copy.exactDescription} title={copy.exactTitle} toolbar={<span className="workspace-count">{comparison.named_metrics.length} {copy.metrics}</span>}>
      {comparison.named_metrics.length === 0 ? <p className="empty">{copy.noMetrics}</p> : <div className="table-wrap workspace-dense-table"><table><thead><tr><th>{copy.metric}</th><th>{copy.runA}</th><th>{copy.samples}</th><th>{copy.runB}</th><th>{copy.samples}</th><th>{copy.delta}</th><th>{copy.unit}</th></tr></thead><tbody>{comparison.named_metrics.map((metric) => <tr key={metric.metric_name}><td><strong>{metric.label}</strong><small>{metric.profile}</small></td><MetricValueCell metric={metric} side="run_a" value={displayValue(metric.run_a.value, metric.unit)} /><td>{metric.run_a.sample_count}</td><MetricValueCell metric={metric} side="run_b" value={displayValue(metric.run_b.value, metric.unit)} /><td>{metric.run_b.sample_count}</td><td>{displayValue(metric.delta, metric.unit)}</td><td>{metric.unit}</td></tr>)}</tbody></table></div>}
    </WorkspacePanel>
  </div>;
}

function MetricGroupChart({ copy, displayValue, group }: { copy: typeof comparisonCopy.en; displayValue: (value: number | null, unit: string) => string; group: Comparison["metric_groups"][number] }) {
  const availableValues = group.metrics.flatMap((metric) => [metric.run_a.value, metric.run_b.value]).filter((value): value is number => value !== null);
  const maximum = group.unit === "ratio" ? 1 : Math.max(0, ...availableValues) || 1;
  const title = `${unitGroupLabel(group.unit, copy)} · ${group.unit}`;
  return <WorkspacePanel className="workspace-comparison-group" description={copy.unitScaleDescription} title={title}>
    <div className="workspace-comparison-bars">{group.metrics.map((metric) => {
      const label = `${metric.label}: ${copy.runA} ${displayValue(metric.run_a.value, metric.unit)}; ${copy.runB} ${displayValue(metric.run_b.value, metric.unit)}`;
      return <article aria-label={label} key={metric.metric_name} role="img"><strong>{metric.label}</strong><div className="workspace-comparison-bar-row"><span>{copy.runA}</span><i><b className="run-a" style={{ width: metric.run_a.value === null ? "0%" : `${Math.max(0, metric.run_a.value / maximum) * 100}%` }} /></i><em>{displayValue(metric.run_a.value, metric.unit)}</em></div><div className="workspace-comparison-bar-row"><span>{copy.runB}</span><i><b className="run-b" style={{ width: metric.run_b.value === null ? "0%" : `${Math.max(0, metric.run_b.value / maximum) * 100}%` }} /></i><em>{displayValue(metric.run_b.value, metric.unit)}</em></div>{metric.run_a.availability_reason && <small>{copy.runA}: <span data-i18n-preserve>{metric.run_a.availability_reason}</span></small>}{metric.run_b.availability_reason && <small>{copy.runB}: <span data-i18n-preserve>{metric.run_b.availability_reason}</span></small>}</article>;
    })}</div>
  </WorkspacePanel>;
}

function MetricValueCell({ metric, side, value }: { metric: MetricRow; side: "run_a" | "run_b"; value: string }) {
  const reason = metric[side].availability_reason;
  return <td>{value}{reason && <small data-i18n-preserve>{reason}</small>}</td>;
}

function groupMetrics(metrics: MetricRow[]): Comparison["metric_groups"] {
  const groups = new Map<string, MetricRow[]>();
  metrics.forEach((metric) => groups.set(metric.unit, [...(groups.get(metric.unit) ?? []), metric]));
  return [...groups].map(([unit, rows]) => ({ unit, metrics: rows }));
}

function outcomeRows(comparison: Comparison): Comparison["outcome_distribution"] {
  return (["both_correct", "run_a_only_correct", "run_b_only_correct", "both_incorrect"] as const).map((outcome) => ({ outcome, count: comparison.outcomes[outcome] }));
}

function unitGroupLabel(unit: string, copy: typeof comparisonCopy.en) {
  if (unit === "ratio") return copy.quality;
  if (unit === "milliseconds") return copy.performance;
  if (unit === "currency") return copy.cost;
  if (unit === "tokens") return copy.usage;
  if (unit === "perplexity") return copy.languageModeling;
  return copy.otherMetrics;
}
