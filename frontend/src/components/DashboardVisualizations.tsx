import { chartCoordinates, groupCostsByCurrency, type DashboardAnalyticsPoint } from "../dashboard/analytics";

export type DashboardVisualizationLabels = {
  accuracy: string;
  successRate: string;
  evaluationTrend: string;
  latency: string;
  cost: string;
  errorRate: string;
  limitedHistory: string;
  noHistory: string;
  model: string;
  benchmark: string;
  unknownValue: string;
};

export type DashboardVisualizationFormatters = {
  percent: (value: number | null) => string;
  latency: (value: number | null) => string;
  cost: (value: number | null, currency: string | null) => string;
};

type VisualizationProps = {
  points: DashboardAnalyticsPoint[];
  labels: DashboardVisualizationLabels;
  formatters: DashboardVisualizationFormatters;
};

function segments(points: Array<{ x: number; y: number } | null>): string[] {
  const result: string[] = [];
  let current: string[] = [];

  for (const point of points) {
    if (point) current.push(`${point.x},${point.y}`);
    else if (current.length > 0) {
      result.push(current.join(" "));
      current = [];
    }
  }

  if (current.length > 0) result.push(current.join(" "));
  return result;
}

function MetricValue({ label, value }: { label: string; value: string }) {
  return value === "--" ? <span aria-label={label}>--</span> : <span>{value}</span>;
}

function TrendEvidenceTable({ formatters, labels, points }: VisualizationProps) {
  return (
    <div className="sr-only">
      <table>
        <thead>
          <tr>
            <th>{labels.model}</th>
            <th>{labels.benchmark}</th>
            <th>{labels.accuracy}</th>
            <th>{labels.successRate}</th>
          </tr>
        </thead>
        <tbody>
          {points.map((point) => (
            <tr key={point.runId}>
              <td>{point.modelName}</td>
              <td>{point.benchmarkLabel}</td>
              <td>{formatters.percent(point.accuracy)}</td>
              <td>{formatters.percent(point.successRate)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export function EvaluationTrendChart({ formatters, labels, points }: VisualizationProps) {
  if (points.length === 0) return <p className="dashboard-empty">{labels.noHistory}</p>;

  if (points.length === 1) {
    return (
      <div className="trend-state">
        <p className="dashboard-empty">{labels.limitedHistory}</p>
        <TrendEvidenceTable formatters={formatters} labels={labels} points={points} />
      </div>
    );
  }

  const accuracy = chartCoordinates(points.map((point) => point.accuracy), 240, 96, { minimum: 0, maximum: 1 });
  const successRate = chartCoordinates(points.map((point) => point.successRate), 240, 96, { minimum: 0, maximum: 1 });
  const translated = (series: Array<{ x: number; y: number } | null>) => series.map((point) => point ? { x: point.x + 32, y: point.y + 8 } : null);
  const accuracyPlot = translated(accuracy);
  const successRatePlot = translated(successRate);
  const latest = points.at(-1)!;

  return (
    <figure className="evaluation-trend" aria-labelledby="evaluation-trend-caption">
      <figcaption className="sr-only" id="evaluation-trend-caption">{labels.evaluationTrend}</figcaption>
      <svg aria-labelledby="evaluation-trend-caption" role="img" viewBox="0 0 280 126">
        {[{ y: 8, label: "100%" }, { y: 56, label: "50%" }, { y: 104, label: "0%" }].map((tick) => <g key={tick.label}><line className="trend-grid-line" x1="32" x2="272" y1={tick.y} y2={tick.y} /><text className="trend-axis-label" x="26" y={tick.y + 3}>{tick.label}</text></g>)}
        {segments(accuracyPlot).map((segment, index) => <polyline className="trend-series trend-series--accuracy" data-trend-series="accuracy" fill="none" key={`accuracy-${index}`} points={segment} />)}
        {segments(successRatePlot).map((segment, index) => <polyline className="trend-series trend-series--success" data-trend-series="success" fill="none" key={`success-${index}`} points={segment} />)}
        {points.map((point, index) => point.accuracy === null || !accuracyPlot[index] ? null : <circle className="trend-point trend-point--accuracy" cx={accuracyPlot[index]!.x} cy={accuracyPlot[index]!.y} data-trend-point="accuracy" data-value={point.accuracy} key={`accuracy-point-${point.runId}`} r="3" tabIndex={0}><title>{point.modelName} · {point.benchmarkLabel} · {labels.accuracy} {formatters.percent(point.accuracy)}</title></circle>)}
        {points.map((point, index) => point.successRate === null || !successRatePlot[index] ? null : <circle className="trend-point trend-point--success" cx={successRatePlot[index]!.x} cy={successRatePlot[index]!.y} data-trend-point="success-rate" data-value={point.successRate} key={`success-point-${point.runId}`} r="3" tabIndex={0}><title>{point.modelName} · {point.benchmarkLabel} · {labels.successRate} {formatters.percent(point.successRate)}</title></circle>)}
        {points[0].completedAt && <text className="trend-date-label" x="32" y="122">{points[0].completedAt.slice(0, 10)}</text>}
        {latest.completedAt && <text className="trend-date-label trend-date-label--end" x="272" y="122">{latest.completedAt.slice(0, 10)}</text>}
      </svg>
      <div className="trend-legend" aria-hidden="true">
        <span><i className="trend-swatch trend-swatch--accuracy" />{labels.accuracy} <MetricValue label={labels.unknownValue} value={formatters.percent(latest.accuracy)} /></span>
        <span><i className="trend-swatch trend-swatch--success" />{labels.successRate} <MetricValue label={labels.unknownValue} value={formatters.percent(latest.successRate)} /></span>
      </div>
      <TrendEvidenceTable formatters={formatters} labels={labels} points={points} />
    </figure>
  );
}

function signalWidth(value: number | null, maximum: number): string {
  if (value === null || maximum === 0) return "0%";
  if (value <= 0) return "0%";
  return `${Math.min(100, Math.max((value / maximum) * 100, 4))}%`;
}

export function EfficiencySignals({ formatters, labels, points }: VisualizationProps) {
  if (points.length === 0) return <p className="dashboard-empty">{labels.noHistory}</p>;

  const rows = points.slice(-4).reverse();
  const maxLatency = Math.max(...rows.map((point) => point.averageLatencyMs ?? 0));
  const maxCostByCurrency = new Map([...groupCostsByCurrency(rows)].map(([currency, currencyRows]) => [currency, Math.max(...currencyRows.map((point) => point.estimatedCost ?? 0))]));

  return (
    <div className="efficiency-signals">
      {rows.map((point) => (
        <article className="efficiency-row" key={point.runId}>
          <header>
            <strong>{point.modelName}</strong>
            <span>{point.benchmarkLabel}</span>
          </header>
          <div className="efficiency-row__metrics">
            <Signal kind="latency" label={labels.latency} unknownLabel={labels.unknownValue} value={formatters.latency(point.averageLatencyMs)} width={signalWidth(point.averageLatencyMs, maxLatency)} />
            <Signal kind="cost" label={labels.cost} unknownLabel={labels.unknownValue} value={formatters.cost(point.estimatedCost, point.currency)} width={signalWidth(point.estimatedCost, maxCostByCurrency.get(point.currency?.trim().toUpperCase() || "UNSPECIFIED") ?? 0)} />
            <Signal emphasis={point.errorRate !== null && point.errorRate > 0} kind="error" label={labels.errorRate} unknownLabel={labels.unknownValue} value={formatters.percent(point.errorRate)} width={signalWidth(point.errorRate, 1)} />
          </div>
        </article>
      ))}
    </div>
  );
}

function Signal({ emphasis = false, kind, label, unknownLabel, value, width }: { emphasis?: boolean; kind: "latency" | "cost" | "error"; label: string; unknownLabel: string; value: string; width: string }) {
  return (
    <div className={emphasis ? "signal is-emphasized" : "signal"} data-signal={kind} title={`${label}: ${value}`}>
      <span className="signal-label">{label}</span>
      <span className="signal-value"><MetricValue label={unknownLabel} value={value} /></span>
      <span aria-hidden="true" className="signal-track"><span className="signal-fill" style={{ width }} /></span>
    </div>
  );
}
