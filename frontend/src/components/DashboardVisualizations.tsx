import { chartCoordinates, type DashboardAnalyticsPoint } from "../dashboard/analytics";

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
    <table className="sr-only">
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

  const accuracy = chartCoordinates(points.map((point) => point.accuracy), 240, 96);
  const successRate = chartCoordinates(points.map((point) => point.successRate), 240, 96);
  const latest = points.at(-1)!;

  return (
    <figure className="evaluation-trend" aria-labelledby="evaluation-trend-caption">
      <figcaption className="sr-only" id="evaluation-trend-caption">{labels.evaluationTrend}</figcaption>
      <svg aria-labelledby="evaluation-trend-caption" role="img" viewBox="0 0 240 112">
        <line className="trend-grid-line" x1="0" x2="240" y1="0" y2="0" />
        <line className="trend-grid-line" x1="0" x2="240" y1="48" y2="48" />
        <line className="trend-grid-line" x1="0" x2="240" y1="96" y2="96" />
        {segments(accuracy).map((segment, index) => <polyline className="trend-series trend-series--accuracy" data-trend-series="accuracy" fill="none" key={`accuracy-${index}`} points={segment} />)}
        {segments(successRate).map((segment, index) => <polyline className="trend-series trend-series--success" data-trend-series="success" fill="none" key={`success-${index}`} points={segment} />)}
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
  return `${Math.max((value / maximum) * 100, 4)}%`;
}

export function EfficiencySignals({ formatters, labels, points }: VisualizationProps) {
  if (points.length === 0) return <p className="dashboard-empty">{labels.noHistory}</p>;

  const rows = points.slice(-4).reverse();
  const maxLatency = Math.max(...rows.map((point) => point.averageLatencyMs ?? 0));
  const maxCost = Math.max(...rows.map((point) => point.estimatedCost ?? 0));
  const maxError = Math.max(...rows.map((point) => point.errorRate ?? 0));

  return (
    <div className="efficiency-signals">
      {rows.map((point) => (
        <article className="efficiency-row" key={point.runId}>
          <header>
            <strong>{point.modelName}</strong>
            <span>{point.benchmarkLabel}</span>
          </header>
          <div className="efficiency-row__metrics">
            <Signal label={labels.latency} unknownLabel={labels.unknownValue} value={formatters.latency(point.averageLatencyMs)} width={signalWidth(point.averageLatencyMs, maxLatency)} />
            <Signal label={labels.cost} unknownLabel={labels.unknownValue} value={formatters.cost(point.estimatedCost, point.currency)} width={signalWidth(point.estimatedCost, maxCost)} />
            <Signal emphasis={point.errorRate !== null && point.errorRate > 0} label={labels.errorRate} unknownLabel={labels.unknownValue} value={formatters.percent(point.errorRate)} width={signalWidth(point.errorRate, maxError)} />
          </div>
        </article>
      ))}
    </div>
  );
}

function Signal({ emphasis = false, label, unknownLabel, value, width }: { emphasis?: boolean; label: string; unknownLabel: string; value: string; width: string }) {
  return (
    <div className={emphasis ? "signal is-emphasized" : "signal"}>
      <span className="signal-label">{label}</span>
      <span className="signal-value"><MetricValue label={unknownLabel} value={value} /></span>
      <span aria-hidden="true" className="signal-track"><span className="signal-fill" style={{ width }} /></span>
    </div>
  );
}
