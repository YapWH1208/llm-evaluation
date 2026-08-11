import { FormEvent, KeyboardEvent, useEffect, useMemo, useRef, useState } from "react";

import type { Dataset, Endpoint, EvaluationRun, ScatterPoint, ScatterQuery, ScatterResponse } from "../../api";
import { analysisScatterCopy } from "../../i18n/catalog";
import { useTranslation } from "../../i18n/LocaleProvider";
import { METRIC_DEFINITIONS } from "../../metrics";
import { WorkspacePanel } from "../workspace/WorkspacePanel";

type ScatterFilterState = {
  xAxis: string;
  yAxis: string;
  dateFrom: string;
  dateTo: string;
  modelEndpointId: string;
  dataset: string;
  status: string;
  capability: string;
  language: string;
  evaluationType: Dataset["evaluation_type"] | "";
  minScore: string;
  maxScore: string;
  minAccuracy: string;
  maxAccuracy: string;
  minLatency: string;
  maxLatency: string;
  minCost: string;
  maxCost: string;
};

const DEFAULT_FILTERS: ScatterFilterState = {
  xAxis: "score",
  yAxis: "average_latency_ms",
  dateFrom: "",
  dateTo: "",
  modelEndpointId: "",
  dataset: "",
  status: "",
  capability: "",
  language: "",
  evaluationType: "",
  minScore: "",
  maxScore: "",
  minAccuracy: "",
  maxAccuracy: "",
  minLatency: "",
  maxLatency: "",
  minCost: "",
  maxCost: "",
};

const metricOptions = Object.entries(METRIC_DEFINITIONS).map(([id, definition]) => ({ id, ...definition }));
const evaluationTypes: Dataset["evaluation_type"][] = ["classification", "generation", "code", "language_modeling", "custom"];

type EvidenceScatterWorkspaceProps = {
  datasets: Dataset[];
  endpoints: Endpoint[];
  loadScatter: (query: ScatterQuery) => Promise<ScatterResponse>;
  runs: EvaluationRun[];
};

function optionalNumber(value: string) {
  if (!value.trim()) return undefined;
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : undefined;
}

function inclusiveDate(value: string, endOfDay: boolean) {
  return value ? `${value}T${endOfDay ? "23:59:59.999" : "00:00:00.000"}Z` : undefined;
}

function buildQuery(filters: ScatterFilterState, selectedRunIds: string[] | null): ScatterQuery {
  return {
    x_axis: filters.xAxis,
    y_axis: filters.yAxis,
    ...(selectedRunIds === null ? {} : { run_ids: selectedRunIds }),
    ...(filters.dateFrom ? { date_from: inclusiveDate(filters.dateFrom, false) } : {}),
    ...(filters.dateTo ? { date_to: inclusiveDate(filters.dateTo, true) } : {}),
    ...(filters.modelEndpointId ? { model_endpoint_id: filters.modelEndpointId } : {}),
    ...(filters.dataset ? { dataset: filters.dataset } : {}),
    ...(filters.status ? { statuses: [filters.status] } : {}),
    ...(filters.capability ? { capability: filters.capability } : {}),
    ...(filters.language ? { language: filters.language } : {}),
    ...(filters.evaluationType ? { evaluation_type: filters.evaluationType } : {}),
    ...(optionalNumber(filters.minScore) !== undefined ? { min_score: optionalNumber(filters.minScore) } : {}),
    ...(optionalNumber(filters.maxScore) !== undefined ? { max_score: optionalNumber(filters.maxScore) } : {}),
    ...(optionalNumber(filters.minAccuracy) !== undefined ? { min_accuracy: optionalNumber(filters.minAccuracy) } : {}),
    ...(optionalNumber(filters.maxAccuracy) !== undefined ? { max_accuracy: optionalNumber(filters.maxAccuracy) } : {}),
    ...(optionalNumber(filters.minLatency) !== undefined ? { min_latency_ms: optionalNumber(filters.minLatency) } : {}),
    ...(optionalNumber(filters.maxLatency) !== undefined ? { max_latency_ms: optionalNumber(filters.maxLatency) } : {}),
    ...(optionalNumber(filters.minCost) !== undefined ? { min_cost: optionalNumber(filters.minCost) } : {}),
    ...(optionalNumber(filters.maxCost) !== undefined ? { max_cost: optionalNumber(filters.maxCost) } : {}),
    max_points: 500,
  };
}

function optionValues(values: Array<string | null | undefined>) {
  return [...new Set(values.filter((value): value is string => Boolean(value)))].sort((left, right) => left.localeCompare(right));
}

export function EvidenceScatterWorkspace({ datasets, endpoints, loadScatter, runs }: EvidenceScatterWorkspaceProps) {
  const { locale } = useTranslation();
  const copy = analysisScatterCopy[locale];
  const [filters, setFilters] = useState<ScatterFilterState>(DEFAULT_FILTERS);
  const [selectedRunIds, setSelectedRunIds] = useState<string[] | null>(null);
  const [response, setResponse] = useState<ScatterResponse | null>(null);
  const [catalogResponse, setCatalogResponse] = useState<ScatterResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const latestRequest = useRef(0);
  const lastQuery = useRef<ScatterQuery>(buildQuery(DEFAULT_FILTERS, null));

  const queryScatter = (query: ScatterQuery) => {
    const requestId = ++latestRequest.current;
    lastQuery.current = query;
    setLoading(true);
    setError(null);
    void loadScatter(query).then((next) => {
      if (latestRequest.current !== requestId) return;
      setResponse(next);
      setCatalogResponse((current) => current ?? next);
    }).catch(() => {
      if (latestRequest.current !== requestId) return;
      setResponse(null);
      setError(copy.loadError);
    }).finally(() => {
      if (latestRequest.current === requestId) setLoading(false);
    });
  };

  useEffect(() => {
    queryScatter(buildQuery(DEFAULT_FILTERS, null));
    return () => { latestRequest.current += 1; };
  }, [loadScatter]);

  const runOptions = useMemo(() => {
    const pointNames = new Map(catalogResponse?.points.map((point) => [point.run_id, point.display_name]) ?? []);
    const options = new Map(runs.map((run) => [run.id, pointNames.get(run.id) ?? run.display_name ?? `${run.benchmark_id} · ${run.id.slice(0, 8)}`]));
    catalogResponse?.selected_run_ids.forEach((runId) => options.set(runId, options.get(runId) ?? pointNames.get(runId) ?? runId));
    return [...options].map(([id, name]) => ({ id, name }));
  }, [catalogResponse, runs]);
  const endpointOptions = useMemo(() => {
    const options = new Map(endpoints.map((endpoint) => [endpoint.id, `${endpoint.display_name} · ${endpoint.model_name}`]));
    catalogResponse?.points.forEach((point) => options.set(point.model_endpoint_id, options.get(point.model_endpoint_id) ?? point.model_name));
    return [...options].map(([id, name]) => ({ id, name }));
  }, [catalogResponse, endpoints]);
  const capabilities = optionValues([...datasets.flatMap((item) => item.capabilities), ...(catalogResponse?.points.flatMap((point) => point.capabilities) ?? [])]);
  const languages = optionValues([...datasets.flatMap((item) => item.languages), ...(catalogResponse?.points.flatMap((point) => point.languages) ?? [])]);
  const datasetIds = optionValues([...datasets.map((item) => item.dataset_id), ...(catalogResponse?.points.map((point) => point.dataset) ?? [])]);
  const statuses = optionValues([...runs.map((run) => run.status), ...(catalogResponse?.points.map((point) => point.status) ?? [])]);
  const allRunsSelected = selectedRunIds === null;

  const toggleRun = (runId: string, checked: boolean) => {
    const current = selectedRunIds ?? runOptions.map((run) => run.id);
    const next = checked ? [...new Set([...current, runId])] : current.filter((id) => id !== runId);
    setSelectedRunIds(next.length === runOptions.length ? null : next);
  };

  const submit = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (selectedRunIds?.length === 0) {
      setResponse(null);
      setError(copy.chooseRun);
      return;
    }
    queryScatter(buildQuery(filters, selectedRunIds));
  };

  const reset = () => {
    setFilters(DEFAULT_FILTERS);
    setSelectedRunIds(null);
    queryScatter(buildQuery(DEFAULT_FILTERS, null));
  };

  const setFilter = <K extends keyof ScatterFilterState>(key: K, value: ScatterFilterState[K]) => {
    setFilters((current) => ({ ...current, [key]: value }));
  };

  return <div className="workspace-scatter-stack">
    <WorkspacePanel className="workspace-scatter-controls" description={copy.controlsDescription} title={copy.controlsTitle}>
      <form onSubmit={submit}>
        <div className="workspace-scatter-primary-filters">
          <label>{copy.horizontalAxis}<select onChange={(event) => setFilter("xAxis", event.target.value)} value={filters.xAxis}>{metricOptions.map((metric) => <option key={metric.id} value={metric.id}>{metric.label}</option>)}</select></label>
          <label>{copy.verticalAxis}<select onChange={(event) => setFilter("yAxis", event.target.value)} value={filters.yAxis}>{metricOptions.map((metric) => <option key={metric.id} value={metric.id}>{metric.label}</option>)}</select></label>
          <details className="workspace-run-multiselect">
            <summary>{allRunsSelected ? `${copy.allRuns} (${runOptions.length})` : `${selectedRunIds?.length ?? 0} / ${runOptions.length} ${copy.runsSelected}`}</summary>
            <fieldset><legend>{copy.runs}</legend><label><input checked={allRunsSelected} onChange={(event) => setSelectedRunIds(event.target.checked ? null : [])} type="checkbox" /> {copy.allRuns}</label>{runOptions.map((run) => <label key={run.id}><input checked={allRunsSelected || Boolean(selectedRunIds?.includes(run.id))} onChange={(event) => toggleRun(run.id, event.target.checked)} type="checkbox" /> {copy.includeRun} <span data-i18n-preserve>{run.name}</span></label>)}</fieldset>
          </details>
        </div>
        <details className="workspace-scatter-advanced">
          <summary>{copy.filters}</summary>
          <div className="workspace-scatter-filter-grid">
            <label>{copy.fromDate}<input onChange={(event) => setFilter("dateFrom", event.target.value)} type="date" value={filters.dateFrom} /></label>
            <label>{copy.toDate}<input onChange={(event) => setFilter("dateTo", event.target.value)} type="date" value={filters.dateTo} /></label>
            <label>{copy.model}<select onChange={(event) => setFilter("modelEndpointId", event.target.value)} value={filters.modelEndpointId}><option value="">{copy.all}</option>{endpointOptions.map((endpoint) => <option data-i18n-preserve key={endpoint.id} value={endpoint.id}>{endpoint.name}</option>)}</select></label>
            <label>{copy.dataset}<select onChange={(event) => setFilter("dataset", event.target.value)} value={filters.dataset}><option value="">{copy.all}</option>{datasetIds.map((datasetId) => <option data-i18n-preserve key={datasetId}>{datasetId}</option>)}</select></label>
            <label>{copy.status}<select onChange={(event) => setFilter("status", event.target.value)} value={filters.status}><option value="">{copy.all}</option>{statuses.map((status) => <option data-i18n-preserve key={status}>{status}</option>)}</select></label>
            <label>{copy.capability}<select onChange={(event) => setFilter("capability", event.target.value)} value={filters.capability}><option value="">{copy.all}</option>{capabilities.map((capability) => <option data-i18n-preserve key={capability}>{capability}</option>)}</select></label>
            <label>{copy.language}<select onChange={(event) => setFilter("language", event.target.value)} value={filters.language}><option value="">{copy.all}</option>{languages.map((language) => <option data-i18n-preserve key={language}>{language}</option>)}</select></label>
            <label>{copy.evaluationType}<select onChange={(event) => setFilter("evaluationType", event.target.value as ScatterFilterState["evaluationType"])} value={filters.evaluationType}><option value="">{copy.all}</option>{evaluationTypes.map((evaluationType) => <option data-i18n-preserve key={evaluationType}>{evaluationType}</option>)}</select></label>
            <NumericFilter label={copy.minScore} onChange={(value) => setFilter("minScore", value)} value={filters.minScore} />
            <NumericFilter label={copy.maxScore} onChange={(value) => setFilter("maxScore", value)} value={filters.maxScore} />
            <NumericFilter label={copy.minAccuracy} onChange={(value) => setFilter("minAccuracy", value)} value={filters.minAccuracy} />
            <NumericFilter label={copy.maxAccuracy} onChange={(value) => setFilter("maxAccuracy", value)} value={filters.maxAccuracy} />
            <NumericFilter label={copy.minLatency} onChange={(value) => setFilter("minLatency", value)} step="1" value={filters.minLatency} />
            <NumericFilter label={copy.maxLatency} onChange={(value) => setFilter("maxLatency", value)} step="1" value={filters.maxLatency} />
            <NumericFilter label={copy.minCost} onChange={(value) => setFilter("minCost", value)} step="0.000001" value={filters.minCost} />
            <NumericFilter label={copy.maxCost} onChange={(value) => setFilter("maxCost", value)} step="0.000001" value={filters.maxCost} />
          </div>
        </details>
        <div className="actions workspace-scatter-actions"><button disabled={loading} type="submit">{loading ? copy.applying : copy.applyFilters}</button><button className="secondary" disabled={loading} onClick={reset} type="button">{copy.resetFilters}</button></div>
      </form>
    </WorkspacePanel>
    {loading && !response ? <WorkspacePanel description={copy.chartDescription} title={copy.chartTitle}><p aria-live="polite" className="empty">{copy.loading}</p></WorkspacePanel> : error ? <WorkspacePanel description={copy.chartDescription} title={copy.chartTitle}><div className="workspace-scatter-error" role="alert"><p>{error}</p><button onClick={() => queryScatter(lastQuery.current)} type="button">{copy.retry}</button></div></WorkspacePanel> : response ? <ScatterEvidence response={response} /> : null}
  </div>;
}

function NumericFilter({ label, onChange, step = "0.01", value }: { label: string; onChange: (value: string) => void; step?: string; value: string }) {
  return <label>{label}<input inputMode="decimal" onChange={(event) => onChange(event.target.value)} step={step} type="number" value={value} /></label>;
}

function ScatterEvidence({ response }: { response: ScatterResponse }) {
  const { formatDate, formatNumber, formatPercent, locale } = useTranslation();
  const copy = analysisScatterCopy[locale];
  const [selectedPoint, setSelectedPoint] = useState<ScatterPoint | null>(null);
  const models = optionValues(response.points.map((point) => point.model_name));
  const modelIndex = new Map(models.map((model, index) => [model, index]));
  const xValues = response.points.map((point) => point.x);
  const yValues = response.points.map((point) => point.y);
  const [xMin, xMax] = extent(xValues, response.x_axis.unit);
  const [yMin, yMax] = extent(yValues, response.y_axis.unit);
  const xPosition = (value: number) => 72 + ((value - xMin) / (xMax - xMin || 1)) * 636;
  const yPosition = (value: number) => 332 - ((value - yMin) / (yMax - yMin || 1)) * 286;
  const displayMetric = (value: number, unit: string) => unit === "ratio" ? formatPercent(value) : `${formatNumber(value, unit === "currency" ? 6 : 2)}${unit === "milliseconds" ? " ms" : unit === "tokens" ? " tokens" : ""}`;
  const pointLabel = (point: ScatterPoint) => `${point.display_name}: ${response.x_axis.label} ${displayMetric(point.x, response.x_axis.unit)}; ${response.y_axis.label} ${displayMetric(point.y, response.y_axis.unit)}`;
  const inspectPoint = (point: ScatterPoint, event?: KeyboardEvent<SVGGElement>) => {
    if (event && event.key !== "Enter" && event.key !== " ") return;
    event?.preventDefault();
    setSelectedPoint(point);
  };

  return <>
    <WorkspacePanel className="workspace-scatter-chart-panel" description={copy.chartDescription} title={copy.chartTitle} toolbar={<span className="workspace-count">{response.plotted_count} / {response.eligible_run_count}</span>}>
      <div className="workspace-scatter-summary" aria-live="polite"><strong>{response.plotted_count} {copy.of} {response.eligible_run_count} {copy.eligibleRunsPlotted}</strong><span>{response.x_axis.label} × {response.y_axis.label}</span></div>
      {response.points.length === 0 ? <p className="empty">{copy.noPoints}</p> : <>
        <div className="workspace-scatter-legend" aria-label={copy.modelLegend}>{models.map((model, index) => <span data-i18n-preserve key={model}><i className={`workspace-scatter-swatch series-${index % 6}`} />{model}</span>)}</div>
        <div className="workspace-scatter-chart-scroll"><svg aria-labelledby="evidence-scatter-title evidence-scatter-description" className="workspace-scatter-chart" role="img" viewBox="0 0 760 390"><title id="evidence-scatter-title">{copy.scatterChart}</title><desc id="evidence-scatter-description">{copy.chartDescription}</desc><line className="workspace-scatter-axis" x1="72" x2="708" y1="332" y2="332" /><line className="workspace-scatter-axis" x1="72" x2="72" y1="46" y2="332" /><text className="workspace-scatter-tick" x="72" y="352">{displayMetric(xMin, response.x_axis.unit)}</text><text className="workspace-scatter-tick" textAnchor="end" x="708" y="352">{displayMetric(xMax, response.x_axis.unit)}</text><text className="workspace-scatter-tick" x="64" y="332" textAnchor="end">{displayMetric(yMin, response.y_axis.unit)}</text><text className="workspace-scatter-tick" x="64" y="50" textAnchor="end">{displayMetric(yMax, response.y_axis.unit)}</text><text className="workspace-scatter-axis-label" textAnchor="middle" x="390" y="380">{response.x_axis.label}</text><text className="workspace-scatter-axis-label" textAnchor="middle" transform="rotate(-90 18 190)" x="18" y="190">{response.y_axis.label}</text>{response.points.map((point) => <g aria-label={pointLabel(point)} className={`workspace-scatter-point series-${(modelIndex.get(point.model_name) ?? 0) % 6}${selectedPoint?.run_id === point.run_id ? " is-selected" : ""}`} key={point.run_id} onClick={() => inspectPoint(point)} onKeyDown={(event) => inspectPoint(point, event)} role="button" tabIndex={0} transform={`translate(${xPosition(point.x)} ${yPosition(point.y)})`}><title>{pointLabel(point)}</title><circle r="7" /><circle className="workspace-scatter-point-focus" r="12" /></g>)}</svg></div>
        {selectedPoint && <div aria-label={copy.selectedPoint} className="workspace-scatter-selected" role="status"><strong data-i18n-preserve>{selectedPoint.display_name}</strong><span>{response.x_axis.label}: {displayMetric(selectedPoint.x, response.x_axis.unit)} · {response.y_axis.label}: {displayMetric(selectedPoint.y, response.y_axis.unit)}</span><small data-i18n-preserve>{selectedPoint.model_name} · {selectedPoint.dataset} · {formatDate(selectedPoint.created_at)}</small></div>}
      </>}
      {(response.unavailable_count > 0 || response.truncated_count > 0) && <aside className="workspace-scatter-availability"><strong>{copy.availabilityTitle}</strong>{response.unavailable_count > 0 && <p>{response.unavailable_count} {copy.unavailableSummary}</p>}{response.unavailable_reasons.length > 0 && <ul>{response.unavailable_reasons.map((item) => <li key={`${item.axis}-${item.reason}`}>{item.axis === "x" ? copy.xAxis : copy.yAxis} · {item.count} · <span data-i18n-preserve>{item.reason}</span></li>)}</ul>}{response.truncated_count > 0 && <p>{response.truncated_count} {copy.truncatedSummary.replace("{{limit}}", String(response.max_points))}</p>}</aside>}
    </WorkspacePanel>
    <WorkspacePanel className="workspace-scatter-table-panel" description={copy.resultsDescription} title={copy.resultsTitle} toolbar={<span className="workspace-count">{response.points.length} {copy.rows}</span>}>
      {response.points.length === 0 ? <p className="empty">{copy.noPoints}</p> : <div className="table-wrap workspace-dense-table"><table><thead><tr><th>{copy.run}</th><th>{copy.model}</th><th>{copy.dataset}</th><th>{response.x_axis.label}</th><th>{response.y_axis.label}</th><th>{copy.status}</th><th>{copy.created}</th></tr></thead><tbody>{response.points.map((point) => <tr key={point.run_id}><td data-i18n-preserve>{point.display_name}</td><td data-i18n-preserve>{point.model_name}</td><td data-i18n-preserve>{point.dataset}</td><td>{displayMetric(point.x, response.x_axis.unit)}</td><td>{displayMetric(point.y, response.y_axis.unit)}</td><td data-i18n-preserve>{point.status}</td><td>{formatDate(point.created_at)}</td></tr>)}</tbody></table></div>}
    </WorkspacePanel>
  </>;
}

function extent(values: number[], unit: string): [number, number] {
  if (unit === "ratio") return [0, 1];
  if (values.length === 0) return [0, 1];
  const minimum = Math.min(...values);
  const maximum = Math.max(...values);
  const padding = minimum === maximum ? Math.abs(minimum) * .1 || (unit === "currency" ? .01 : 1) : (maximum - minimum) * .05;
  return [Math.max(0, minimum - padding), maximum + padding];
}
