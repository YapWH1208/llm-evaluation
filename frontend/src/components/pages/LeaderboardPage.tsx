import { type MouseEvent, useEffect, useMemo, useState } from "react";

import type { Dataset, Endpoint, LeaderboardQuery, LeaderboardResponse, LeaderboardRow } from "../../shared/api";
import { workspacePath } from "../../dashboard/routing";
import { leaderboardCopy } from "../../i18n/catalog";
import { useTranslation } from "../../i18n/LocaleProvider";
import { METRIC_DEFINITIONS, type MetricId } from "../../metrics";
import { PageHeader } from "../workspace/PageHeader";
import { WorkspacePanel } from "../workspace/WorkspacePanel";

const PAGE_SIZE = 50;
const statuses = ["waiting_for_dataset", "queued", "running", "pausing", "paused", "cancelling", "completed", "completed_with_errors", "failed", "cancelled", "scoring", "aggregating", "generating_report"];
const evaluationTypes: Dataset["evaluation_type"][] = ["classification", "generation", "code", "language_modeling", "custom"];

type FilterState = {
  dataset: string;
  modelEndpointId: string;
  statuses: string[];
  createdFrom: string;
  createdTo: string;
  capability: string;
  language: string;
  evaluationType: Dataset["evaluation_type"] | "";
  availableMetric: string;
};

const emptyFilters: FilterState = {
  dataset: "",
  modelEndpointId: "",
  statuses: [],
  createdFrom: "",
  createdTo: "",
  capability: "",
  language: "",
  evaluationType: "",
  availableMetric: "",
};

type LeaderboardPageProps = {
  datasets: Dataset[];
  endpoints: Endpoint[];
  loadLeaderboard: (query: LeaderboardQuery) => Promise<LeaderboardResponse>;
  onInspectRun: (runId: string) => void;
};

export function LeaderboardPage({ datasets, endpoints, loadLeaderboard, onInspectRun }: LeaderboardPageProps) {
  const { formatDate, formatNumber, formatPercent, locale } = useTranslation();
  const copy = leaderboardCopy[locale];
  const [draft, setDraft] = useState<FilterState>(emptyFilters);
  const [query, setQuery] = useState<LeaderboardQuery>({ page: 1, page_size: PAGE_SIZE });
  const [result, setResult] = useState<LeaderboardResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [retryKey, setRetryKey] = useState(0);

  useEffect(() => {
    let disposed = false;
    setLoading(true);
    setError(null);
    void loadLeaderboard(query).then((next) => {
      if (!disposed) setResult(next);
    }).catch((reason: unknown) => {
      if (!disposed) setError(reason instanceof Error ? reason.message : copy.loadError);
    }).finally(() => {
      if (!disposed) setLoading(false);
    });
    return () => { disposed = true; };
  }, [loadLeaderboard, query, retryKey]);

  const rows = result?.items ?? [];
  const datasetsOptions = optionValues([...datasets.map((item) => item.dataset_id), ...rows.map((row) => row.dataset)]);
  const capabilityOptions = optionValues([...datasets.flatMap((item) => item.capabilities), ...rows.flatMap((row) => row.capabilities)]);
  const languageOptions = optionValues([...datasets.flatMap((item) => item.languages), ...rows.flatMap((row) => row.languages)]);
  const modelOptions = useMemo(() => {
    const byId = new Map(endpoints.map((endpoint) => [endpoint.id, { id: endpoint.id, label: `${endpoint.display_name} · ${endpoint.model_name}` }]));
    rows.forEach((row) => { if (!byId.has(row.model_endpoint_id)) byId.set(row.model_endpoint_id, { id: row.model_endpoint_id, label: row.model_name }); });
    return [...byId.values()].sort((left, right) => left.label.localeCompare(right.label));
  }, [endpoints, rows]);
  const activeFilters = filterChips(query, copy);
  const selectedMetric = query.available_metric && query.available_metric in METRIC_DEFINITIONS ? query.available_metric as MetricId : null;

  function applyFilters() {
    setQuery({ ...queryFromFilters(draft), page: 1, page_size: PAGE_SIZE });
  }

  function resetFilters() {
    setDraft(emptyFilters);
    setQuery({ page: 1, page_size: PAGE_SIZE });
  }

  function toggleStatus(status: string) {
    setDraft((current) => ({ ...current, statuses: current.statuses.includes(status) ? current.statuses.filter((item) => item !== status) : [...current.statuses, status] }));
  }

  function setFilter<K extends keyof FilterState>(key: K, value: FilterState[K]) {
    setDraft((current) => ({ ...current, [key]: value }));
  }

  function setSort(sort: string) {
    if (sort === "default") {
      setQuery((current) => withoutKeys({ ...current, page: 1 }, ["sort", "direction"]));
      return;
    }
    const direction = numericSort(sort) ? "desc" : "asc";
    setQuery((current) => ({ ...current, sort, direction, page: 1 }));
  }

  function sortFromHeader(sort: string) {
    const direction = query.sort === sort ? (query.direction === "desc" ? "asc" : "desc") : numericSort(sort) ? "desc" : "asc";
    setQuery((current) => ({ ...current, sort, direction, page: 1 }));
  }

  function clearFilter(key: keyof FilterState, status?: string) {
    const applied = filtersFromQuery(query);
    const nextDraft = status
      ? { ...applied, statuses: applied.statuses.filter((item) => item !== status) }
      : { ...applied, [key]: emptyFilters[key] };
    setDraft(nextDraft);
    setQuery((current) => ({ ...queryFromFilters(nextDraft), ...(current.sort ? { sort: current.sort, direction: current.direction } : {}), page: 1, page_size: PAGE_SIZE }));
  }

  function inspect(event: MouseEvent<HTMLAnchorElement>, run: LeaderboardRow) {
    if (event.button !== 0 || event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) return;
    event.preventDefault();
    onInspectRun(run.run_id);
  }

  const sortOptions = [
    { id: "default", label: copy.defaultOrder },
    { id: "name", label: copy.name }, { id: "model", label: copy.model }, { id: "dataset", label: copy.dataset }, { id: "status", label: copy.status }, { id: "created_at", label: copy.created },
    { id: "score", label: copy.score }, { id: "average_latency_ms", label: copy.averageLatency }, { id: "p95_latency_ms", label: copy.p95Latency }, { id: "estimated_cost", label: copy.cost }, { id: "sample_count", label: copy.samples },
    ...Object.entries(METRIC_DEFINITIONS).filter(([id]) => !["score", "average_latency_ms", "p95_latency_ms", "estimated_cost"].includes(id)).map(([id, definition]) => ({ id, label: definition.label })),
  ];

  return <div className="workspace-page workspace-leaderboard-page">
    <PageHeader description={copy.description} eyebrow={copy.eyebrow} status={<>{result?.total ?? 0} {copy.runs}</>} title={copy.title} />

    <WorkspacePanel className="workspace-leaderboard-explainer" description={copy.rankingExplanation} title={copy.defaultOrder} />

    <WorkspacePanel className="workspace-leaderboard-filters" description={copy.filtersDescription} title={copy.filtersTitle}>
      <div className="workspace-leaderboard-filter-grid">
        <label>{copy.dataset}<select onChange={(event) => setFilter("dataset", event.target.value)} value={draft.dataset}><option value="">{copy.all}</option>{datasetsOptions.map((value) => <option data-i18n-preserve key={value}>{value}</option>)}</select></label>
        <label>{copy.model}<select onChange={(event) => setFilter("modelEndpointId", event.target.value)} value={draft.modelEndpointId}><option value="">{copy.all}</option>{modelOptions.map((model) => <option data-i18n-preserve key={model.id} value={model.id}>{model.label}</option>)}</select></label>
        <label>{copy.fromDate}<input onChange={(event) => setFilter("createdFrom", event.target.value)} type="date" value={draft.createdFrom} /></label>
        <label>{copy.toDate}<input onChange={(event) => setFilter("createdTo", event.target.value)} type="date" value={draft.createdTo} /></label>
        <label>{copy.capability}<select onChange={(event) => setFilter("capability", event.target.value)} value={draft.capability}><option value="">{copy.all}</option>{capabilityOptions.map((value) => <option data-i18n-preserve key={value}>{value}</option>)}</select></label>
        <label>{copy.language}<select onChange={(event) => setFilter("language", event.target.value)} value={draft.language}><option value="">{copy.all}</option>{languageOptions.map((value) => <option data-i18n-preserve key={value}>{value}</option>)}</select></label>
        <label>{copy.evaluationType}<select onChange={(event) => setFilter("evaluationType", event.target.value as FilterState["evaluationType"])} value={draft.evaluationType}><option value="">{copy.all}</option>{evaluationTypes.map((value) => <option data-i18n-preserve key={value}>{value}</option>)}</select></label>
        <label>{copy.availableMetric}<select onChange={(event) => setFilter("availableMetric", event.target.value)} value={draft.availableMetric}><option value="">{copy.all}</option>{Object.entries(METRIC_DEFINITIONS).map(([id, definition]) => <option key={id} value={id}>{definition.label}</option>)}</select></label>
      </div>
      <fieldset className="workspace-leaderboard-statuses"><legend>{copy.status}</legend>{statuses.map((status) => <label data-i18n-preserve key={status}><input checked={draft.statuses.includes(status)} onChange={() => toggleStatus(status)} type="checkbox" />{status}</label>)}</fieldset>
      <div className="workspace-leaderboard-filter-actions"><button disabled={loading} onClick={applyFilters} type="button">{loading ? copy.applying : copy.apply}</button><button className="secondary" onClick={resetFilters} type="button">{copy.reset}</button></div>
      {activeFilters.length > 0 && <div aria-label={copy.activeFilters} className="workspace-leaderboard-chips">{activeFilters.map((chip) => <button aria-label={`${copy.removeFilter} ${chip.label}`} className="workspace-filter-chip" key={`${chip.key}-${chip.status ?? ""}`} onClick={() => clearFilter(chip.key, chip.status)} type="button"><span data-i18n-preserve>{chip.label}</span><b aria-hidden="true">×</b></button>)}</div>}
    </WorkspacePanel>

    <WorkspacePanel className="workspace-leaderboard-results" description={copy.resultsDescription} title={copy.resultsTitle} toolbar={<span className="workspace-count">{result?.total ?? 0} {copy.runs}</span>}>
      <div className="workspace-leaderboard-ordering">
        <label>{copy.sortBy}<select onChange={(event) => setSort(event.target.value)} value={query.sort ?? "default"}>{sortOptions.map((option) => <option key={option.id} value={option.id}>{option.label}</option>)}</select></label>
        <label>{copy.direction}<select disabled={!query.sort} onChange={(event) => setQuery((current) => ({ ...current, direction: event.target.value as "asc" | "desc", page: 1 }))} value={query.direction ?? "desc"}><option value="asc">{copy.ascending}</option><option value="desc">{copy.descending}</option></select></label>
        {query.sort && <button className="secondary" onClick={() => setSort("default")} type="button">{copy.restoreDefault}</button>}
      </div>

      {error ? <div className="workspace-leaderboard-state"><p className="error" role="alert" data-i18n-preserve>{error}</p><button onClick={() => setRetryKey((value) => value + 1)} type="button">{copy.retry}</button></div>
        : loading && !result ? <p aria-live="polite" className="empty">{copy.loading}</p>
          : rows.length === 0 ? <p className="empty">{copy.empty}</p>
            : <div className="table-wrap workspace-dense-table workspace-leaderboard-table"><table><thead><tr><th>#</th><SortableHeader copy={copy} currentDirection={query.direction} currentSort={query.sort} field="name" label={copy.name} onSort={sortFromHeader} /><SortableHeader copy={copy} currentDirection={query.direction} currentSort={query.sort} field="model" label={copy.model} onSort={sortFromHeader} /><SortableHeader copy={copy} currentDirection={query.direction} currentSort={query.sort} field="dataset" label={copy.dataset} onSort={sortFromHeader} /><SortableHeader copy={copy} currentDirection={query.direction} currentSort={query.sort} field="status" label={copy.status} onSort={sortFromHeader} /><SortableHeader copy={copy} currentDirection={query.direction} currentSort={query.sort} field="score" label={copy.score} onSort={sortFromHeader} /><SortableHeader copy={copy} currentDirection={query.direction} currentSort={query.sort} field="average_latency_ms" label={copy.averageLatency} onSort={sortFromHeader} /><SortableHeader copy={copy} currentDirection={query.direction} currentSort={query.sort} field="p95_latency_ms" label={copy.p95Latency} onSort={sortFromHeader} /><SortableHeader copy={copy} currentDirection={query.direction} currentSort={query.sort} field="estimated_cost" label={copy.cost} onSort={sortFromHeader} /><SortableHeader copy={copy} currentDirection={query.direction} currentSort={query.sort} field="sample_count" label={copy.samples} onSort={sortFromHeader} />{selectedMetric && <SortableHeader copy={copy} currentDirection={query.direction} currentSort={query.sort} field={selectedMetric} label={METRIC_DEFINITIONS[selectedMetric].label} onSort={sortFromHeader} />}<SortableHeader copy={copy} currentDirection={query.direction} currentSort={query.sort} field="created_at" label={copy.created} onSort={sortFromHeader} /><th>{copy.inspect}</th></tr></thead><tbody>{rows.map((row, index) => <tr key={row.run_id}><td>{((result?.page ?? 1) - 1) * (result?.page_size ?? PAGE_SIZE) + index + 1}</td><td><strong data-i18n-preserve>{row.display_name}</strong><small data-i18n-preserve>{row.benchmark_id} v{row.benchmark_version}</small></td><td data-i18n-preserve>{row.model_name}</td><td data-i18n-preserve>{row.dataset}</td><td><span className={`badge status-${row.status}`} data-i18n-preserve>{row.status}</span></td><td>{valueOr(row.score, (value) => formatPercent(value), copy.notAvailable)}</td><td>{valueOr(row.average_latency_ms, (value) => `${formatNumber(value)} ms`, copy.notAvailable)}</td><td>{valueOr(row.p95_latency_ms, (value) => `${formatNumber(value)} ms`, copy.notAvailable)}</td><td>{valueOr(row.estimated_cost, (value) => formatNumber(value, 6), copy.notAvailable)}</td><td>{formatNumber(row.sample_count)}</td>{selectedMetric && <td>{metricValue(row, selectedMetric, copy.notAvailable, formatNumber, formatPercent)}</td>}<td>{formatDate(row.created_at)}</td><td><a aria-label={`${copy.inspect} ${row.display_name}`} className="secondary button-link" href={workspacePath("runs", "run-details", { runId: row.run_id })} onClick={(event) => inspect(event, row)}>{copy.inspect}</a></td></tr>)}</tbody></table></div>}

      <div className="workspace-leaderboard-pagination"><span>{copy.page} {result?.page ?? query.page ?? 1} {copy.of} {result?.total_pages ?? 0}</span><div><button className="secondary" disabled={loading || (result?.page ?? 1) <= 1} onClick={() => setQuery((current) => ({ ...current, page: Math.max(1, (result?.page ?? current.page ?? 1) - 1) }))} type="button">{copy.previous}</button><button className="secondary" disabled={loading || (result?.page ?? 1) >= (result?.total_pages ?? 0)} onClick={() => setQuery((current) => ({ ...current, page: (result?.page ?? current.page ?? 1) + 1 }))} type="button">{copy.next}</button></div></div>
    </WorkspacePanel>
  </div>;
}

function SortableHeader({ copy, currentDirection, currentSort, field, label, onSort }: { copy: typeof leaderboardCopy.en; currentDirection?: "asc" | "desc"; currentSort?: string; field: string; label: string; onSort: (field: string) => void }) {
  const active = currentSort === field;
  const nextDirection = active ? currentDirection === "desc" ? "asc" : "desc" : numericSort(field) ? "desc" : "asc";
  return <th aria-sort={active ? currentDirection === "asc" ? "ascending" : "descending" : "none"}><button aria-label={`${copy.sortBy} ${label} ${nextDirection === "asc" ? copy.ascending.toLowerCase() : copy.descending.toLowerCase()}`} className="workspace-sort-button" onClick={() => onSort(field)} type="button">{label}<span aria-hidden="true">{active ? currentDirection === "asc" ? "↑" : "↓" : "↕"}</span></button></th>;
}

function queryFromFilters(filters: FilterState): LeaderboardQuery {
  return {
    ...(filters.dataset ? { dataset: filters.dataset } : {}),
    ...(filters.modelEndpointId ? { model_endpoint_id: filters.modelEndpointId } : {}),
    ...(filters.statuses.length ? { statuses: filters.statuses } : {}),
    ...(filters.createdFrom ? { created_from: `${filters.createdFrom}T00:00:00Z` } : {}),
    ...(filters.createdTo ? { created_to: `${filters.createdTo}T23:59:59.999Z` } : {}),
    ...(filters.capability ? { capability: filters.capability } : {}),
    ...(filters.language ? { language: filters.language } : {}),
    ...(filters.evaluationType ? { evaluation_type: filters.evaluationType } : {}),
    ...(filters.availableMetric ? { available_metric: filters.availableMetric } : {}),
  };
}

function filterChips(query: LeaderboardQuery, copy: typeof leaderboardCopy.en) {
  const chips: Array<{ key: keyof FilterState; label: string; status?: string }> = [];
  if (query.dataset) chips.push({ key: "dataset", label: `${copy.dataset}: ${query.dataset}` });
  if (query.model_endpoint_id) chips.push({ key: "modelEndpointId", label: `${copy.model}: ${query.model_endpoint_id}` });
  query.statuses?.forEach((status) => chips.push({ key: "statuses", label: `${copy.status}: ${status}`, status }));
  if (query.created_from) chips.push({ key: "createdFrom", label: `${copy.fromDate}: ${query.created_from.slice(0, 10)}` });
  if (query.created_to) chips.push({ key: "createdTo", label: `${copy.toDate}: ${query.created_to.slice(0, 10)}` });
  if (query.capability) chips.push({ key: "capability", label: `${copy.capability}: ${query.capability}` });
  if (query.language) chips.push({ key: "language", label: `${copy.language}: ${query.language}` });
  if (query.evaluation_type) chips.push({ key: "evaluationType", label: `${copy.evaluationType}: ${query.evaluation_type}` });
  if (query.available_metric) chips.push({ key: "availableMetric", label: `${copy.availableMetric}: ${query.available_metric}` });
  return chips;
}

function filtersFromQuery(query: LeaderboardQuery): FilterState {
  return {
    dataset: query.dataset ?? "",
    modelEndpointId: query.model_endpoint_id ?? "",
    statuses: query.statuses ?? [],
    createdFrom: query.created_from?.slice(0, 10) ?? "",
    createdTo: query.created_to?.slice(0, 10) ?? "",
    capability: query.capability ?? "",
    language: query.language ?? "",
    evaluationType: query.evaluation_type ?? "",
    availableMetric: query.available_metric ?? "",
  };
}

function numericSort(field: string) {
  return ["score", "average_latency_ms", "p95_latency_ms", "estimated_cost", "sample_count", ...Object.keys(METRIC_DEFINITIONS)].includes(field);
}

function optionValues(values: string[]) {
  return [...new Set(values.filter(Boolean))].sort((left, right) => left.localeCompare(right));
}

function valueOr(value: number | null, format: (value: number) => string, fallback: string) {
  return value === null ? fallback : format(value);
}

function metricValue(row: LeaderboardRow, metricId: MetricId, fallback: string, number: (value: number, precision?: number) => string, percent: (value: number) => string) {
  const metric = row.named_metrics[metricId];
  if (!metric || metric.value === null) return fallback;
  if (metric.unit === "ratio") return percent(metric.value);
  if (metric.unit === "milliseconds") return `${number(metric.value)} ms`;
  return number(metric.value, metric.unit === "currency" ? 6 : 2);
}

function withoutKeys<T extends object, K extends keyof T>(value: T, keys: K[]): Omit<T, K> {
  const next = { ...value };
  keys.forEach((key) => delete next[key]);
  return next;
}
