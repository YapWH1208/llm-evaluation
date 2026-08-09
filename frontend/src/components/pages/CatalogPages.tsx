import { ChangeEvent, FormEvent, useEffect, useState } from "react";

import { api, Benchmark, Dataset, Endpoint, EvaluationSuite } from "../../api";
import { useTranslation } from "../../i18n/LocaleProvider";
import { translateStaticTemplate } from "../../i18n/operationalCopy";
import { PageHeader } from "../workspace/PageHeader";
import { WorkspacePanel } from "../workspace/WorkspacePanel";

type DatasetAction = (dataset: Dataset) => Promise<void>;
type DatasetUploadAction = (dataset: Dataset, event: ChangeEvent<HTMLInputElement>) => Promise<void>;

type BenchmarksPageProps = {
  benchmarks: Benchmark[];
  busy: string | null;
  onToggleStatus: (benchmark: Benchmark) => void;
};

export function benchmarkModalities(benchmark: Benchmark) {
  const modalities = benchmark.manifest.modalities;
  return Array.isArray(modalities) ? modalities.map(String).join(", ") : "--";
}

export function BenchmarksPage({ benchmarks, busy, onToggleStatus }: BenchmarksPageProps) {
  const [query, setQuery] = useState("");
  const normalizedQuery = query.trim().toLocaleLowerCase();
  const filteredBenchmarks = benchmarks.filter((benchmark) => [benchmark.benchmark_id, benchmark.display_name, benchmark.source, benchmark.status, benchmark.version, benchmarkModalities(benchmark)].join(" ").toLocaleLowerCase().includes(normalizedQuery));

  return (
    <div className="workspace-page benchmarks-page">
      <PageHeader
        actions={<label className="workspace-filter-control">Filter benchmarks<input aria-label="Filter benchmarks" onChange={(event) => setQuery(event.target.value)} placeholder="Name, source, status…" type="search" value={query} /></label>}
        description="Inspect versioned benchmark packs, their supported modalities, and the availability state used by new runs."
        eyebrow="Catalog"
        status={<><strong>{benchmarks.length}</strong> registered versions</>}
        title="Benchmarks"
      />
      <WorkspacePanel description="Filters affect this inventory only; registry records and their operational controls remain available in the loaded catalog." title="Benchmark registry" toolbar={<span className="workspace-count">{filteredBenchmarks.length} shown</span>}>
        {filteredBenchmarks.length === 0 ? <p className="empty">No benchmark versions match this filter.</p> : <div className="table-wrap workspace-dense-table"><table><thead><tr><th>Benchmark</th><th>Version</th><th>Source</th><th>Status</th><th>Modalities</th><th><span className="sr-only">Operation</span></th></tr></thead><tbody>{filteredBenchmarks.map((benchmark) => {
          const canToggle = ["registered", "enabled", "disabled"].includes(benchmark.status);
          return <tr key={benchmark.id}><td data-i18n-preserve><strong>{benchmark.display_name}</strong><span className="workspace-table-detail">{benchmark.benchmark_id}</span></td><td data-i18n-preserve>{benchmark.version}</td><td data-i18n-preserve title={benchmark.source}>{benchmark.source}</td><td><span className={`badge ${benchmark.status}`}>{benchmark.status}</span></td><td data-i18n-preserve>{benchmarkModalities(benchmark)}</td><td>{canToggle ? <button className="secondary workspace-table-action" disabled={busy === `benchmark-${benchmark.id}`} onClick={() => onToggleStatus(benchmark)} type="button">{benchmark.status === "disabled" ? "Enable" : "Disable"}</button> : <span className="workspace-table-detail">Managed by pack</span>}</td></tr>;
        })}</tbody></table></div>}
      </WorkspacePanel>
    </div>
  );
}

type DatasetsPageProps = {
  busy: string | null;
  datasets: Dataset[];
  onClear: DatasetAction;
  onDelete: DatasetAction;
  onOpenWorkspace?: () => void;
  onPause: DatasetAction;
  onPrepare: DatasetAction;
  onUpdate: (dataset: Dataset, payload: Record<string, string>) => Promise<void>;
  onUpload: DatasetUploadAction;
  onValidate: DatasetAction;
};

type DatasetPreview = { datasetId: string; fields: string[]; rows: Array<Record<string, string>> };

export function datasetEditForm(dataset: Dataset): Record<string, string> {
  return {
    checksum: dataset.checksum ?? "",
    credential_binding_id: dataset.credential_binding_id ?? "",
    dataset_id: dataset.dataset_id,
    input_field: dataset.input_field ?? "",
    license_text: dataset.license_text ?? "",
    reference_field: dataset.reference_field ?? "",
    revision: dataset.revision,
    source_url: dataset.source_url ?? "",
    version: dataset.version,
  };
}

export function datasetPrepareLabel(dataset: Dataset) {
  if (dataset.license_text && !dataset.license_accepted_at) return "Accept license";
  return dataset.status === "waiting" || dataset.status === "failed" ? "Retry download" : "Download and verify";
}

export async function loadDatasetPreview(dataset: Dataset) {
  return api.previewDataset(dataset.id, 5);
}

export function DatasetsPage({ busy, datasets, onClear, onDelete, onOpenWorkspace, onPause, onPrepare, onUpdate, onUpload, onValidate }: DatasetsPageProps) {
  const { formatNumber: display, locale } = useTranslation();
  const [usage, setUsage] = useState<{ cache_bytes: number; available_bytes: number } | null>(null);
  const usageKey = datasets.map((dataset) => `${dataset.id}:${dataset.status}`).join("|");
  const [preview, setPreview] = useState<DatasetPreview | null>(null);
  const [previewError, setPreviewError] = useState<string | null>(null);
  const [previewingId, setPreviewingId] = useState<string | null>(null);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [editForm, setEditForm] = useState<Record<string, string>>({});
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const selectedDataset = datasets.find((dataset) => dataset.id === selectedId) ?? datasets[0] ?? null;

  useEffect(() => { void api.datasetDiskUsage().then(setUsage).catch(() => setUsage(null)); }, [usageKey]);

  return (
    <div className="workspace-page datasets-page">
      <PageHeader
        actions={onOpenWorkspace ? <button onClick={onOpenWorkspace} type="button">Register dataset</button> : undefined}
        description="Manage source versions, cached data, licenses, and field mapping while keeping the selected dataset’s evidence in view."
        eyebrow="Catalog"
        status={<>{usage ? <><strong>{display(usage.cache_bytes)}</strong> cached · {display(usage.available_bytes)} free</> : "Loading disk usage…"}</>}
        title="Datasets"
      />
      {previewError && <p className="error" role="alert">{previewError}</p>}
      {datasets.length === 0 ? <WorkspacePanel title="No dataset versions"><p className="empty">Register a dataset source from the Workspace catalog, then return here to prepare, validate, and inspect it.</p></WorkspacePanel> : <div className="workspace-split workspace-split--catalog">
        <WorkspacePanel description="Select a source version to inspect its cache, metadata, and lifecycle actions." title="Dataset inventory" toolbar={<span className="workspace-count">{datasets.length} versions</span>}>
          <div className="workspace-inventory-list workspace-catalog-inventory">{datasets.map((dataset) => <button aria-pressed={selectedDataset?.id === dataset.id} className={selectedDataset?.id === dataset.id ? "workspace-select-row is-selected" : "workspace-select-row"} key={dataset.id} onClick={() => setSelectedId(dataset.id)} type="button"><span data-i18n-preserve><strong>{dataset.dataset_id} v{dataset.version}</strong></span><span className={`badge ${dataset.status}`}>{dataset.status.replaceAll("_", " ")}</span><small data-i18n-preserve>{dataset.revision} · {dataset.source_url ? "source configured" : "local upload"}</small><span className="sr-only">Inspect {dataset.dataset_id} v{dataset.version}</span></button>)}</div>
        </WorkspacePanel>
        {selectedDataset && <DatasetInspector busy={busy} dataset={selectedDataset} editForm={editForm} editing={editingId === selectedDataset.id} onClear={onClear} onDelete={onDelete} onEditForm={setEditForm} onPause={onPause} onPrepare={onPrepare} onStartEdit={() => { setEditingId(selectedDataset.id); setEditForm(datasetEditForm(selectedDataset)); }} onStopEdit={() => setEditingId(null)} onSubmitEdit={(event) => { event.preventDefault(); setEditingId(null); void onUpdate(selectedDataset, editForm); }} onUpload={onUpload} onValidate={onValidate} preview={preview?.datasetId === selectedDataset.id ? preview : null} previewing={previewingId === selectedDataset.id} onPreview={() => { setPreviewingId(selectedDataset.id); setPreviewError(null); void loadDatasetPreview(selectedDataset).then((data) => setPreview({ datasetId: selectedDataset.id, fields: data.fields, rows: data.rows })).catch((error: unknown) => { setPreviewError(error instanceof Error ? error.message : translateStaticTemplate(locale, "Preview unavailable.")); setPreview(null); }).finally(() => setPreviewingId(null)); }} />}
      </div>}
    </div>
  );
}

type DatasetInspectorProps = {
  busy: string | null;
  dataset: Dataset;
  editForm: Record<string, string>;
  editing: boolean;
  onClear: DatasetAction;
  onDelete: DatasetAction;
  onEditForm: (value: Record<string, string>) => void;
  onPause: DatasetAction;
  onPrepare: DatasetAction;
  onPreview: () => void;
  onStartEdit: () => void;
  onStopEdit: () => void;
  onSubmitEdit: (event: FormEvent<HTMLFormElement>) => void;
  onUpload: DatasetUploadAction;
  onValidate: DatasetAction;
  preview: DatasetPreview | null;
  previewing: boolean;
};

export function DatasetInspector({ busy, dataset, editForm, editing, onClear, onDelete, onEditForm, onPause, onPrepare, onPreview, onStartEdit, onStopEdit, onSubmitEdit, onUpload, onValidate, preview, previewing }: DatasetInspectorProps) {
  const { formatNumber: display } = useTranslation();
  return <WorkspacePanel className="workspace-dataset-inspector" title={<span data-i18n-preserve>{dataset.dataset_id} v{dataset.version}</span>} toolbar={<span className={`badge ${dataset.status}`}>{dataset.status.replaceAll("_", " ")}</span>}>
    <div className="workspace-inspector-summary">
      <p><span className="workspace-item-meta">Revision</span> <span data-i18n-preserve>{dataset.revision}</span> · {dataset.source_url ? <span data-i18n-preserve>{dataset.source_url}</span> : "Upload a local revision"}</p>
      <p><span className="workspace-item-meta">Cache</span> {dataset.size_bytes === null ? "Not cached" : `${display(dataset.size_bytes)} bytes`} · {dataset.checksum ? <span data-i18n-preserve>SHA-256 {dataset.checksum.slice(0, 12)}…</span> : "Checksum generated on import"}</p>
      {dataset.credential_binding_id && <p><span className="workspace-item-meta">Credential binding</span> <span data-i18n-preserve>{dataset.credential_binding_id}</span></p>}
      {dataset.input_field && <p><span className="workspace-item-meta">Input field</span> <span data-i18n-preserve>{dataset.input_field}</span>{dataset.reference_field && <><span className="workspace-item-meta"> · Reference field</span> <span data-i18n-preserve>{dataset.reference_field}</span></>}</p>}
      {dataset.error_message && <p className="error" data-i18n-preserve>{dataset.error_message}</p>}
    </div>
    {preview && <div className="table-wrap workspace-preview-table"><h3>Data preview</h3><table><thead><tr>{preview.fields.map((field) => <th key={field}>{field}</th>)}</tr></thead><tbody>{preview.rows.map((row, index) => <tr key={index}>{preview.fields.map((field) => <td key={field}>{row[field] ?? ""}</td>)}</tr>)}</tbody></table></div>}
    {editing && <form className="form workspace-dataset-edit-form" onSubmit={onSubmitEdit}><label>Dataset ID<input onChange={(event) => onEditForm({ ...editForm, dataset_id: event.target.value })} required value={editForm.dataset_id} /></label><div className="workspace-field-grid workspace-field-grid--two"><label>Version<input onChange={(event) => onEditForm({ ...editForm, version: event.target.value })} required value={editForm.version} /></label><label>Revision<input onChange={(event) => onEditForm({ ...editForm, revision: event.target.value })} required value={editForm.revision} /></label></div><label>Source HTTPS URL<input onChange={(event) => onEditForm({ ...editForm, source_url: event.target.value })} placeholder="https://… or hf://owner/repository/path" value={editForm.source_url} /></label><label>Expected SHA-256 checksum<input onChange={(event) => onEditForm({ ...editForm, checksum: event.target.value })} value={editForm.checksum} /></label><label>Credential binding ID<input onChange={(event) => onEditForm({ ...editForm, credential_binding_id: event.target.value })} value={editForm.credential_binding_id} /></label><div className="workspace-field-grid workspace-field-grid--two"><label>Input field<input onChange={(event) => onEditForm({ ...editForm, input_field: event.target.value })} value={editForm.input_field} /></label><label>Reference (output) field<input onChange={(event) => onEditForm({ ...editForm, reference_field: event.target.value })} value={editForm.reference_field} /></label></div><label>License text<textarea onChange={(event) => onEditForm({ ...editForm, license_text: event.target.value })} value={editForm.license_text} /></label><div className="actions"><button disabled={busy === `dataset-edit-${dataset.id}`}>Save changes</button><button className="secondary" onClick={onStopEdit} type="button">Cancel</button></div></form>}
    <div className="actions workspace-dataset-actions">
      {dataset.status !== "ready" && dataset.status !== "downloading" && <button disabled={busy === `dataset-${dataset.id}`} onClick={() => void onPrepare(dataset)} type="button">{datasetPrepareLabel(dataset)}</button>}
      {dataset.status === "downloading" && <button className="secondary" disabled={busy === `dataset-${dataset.id}`} onClick={() => void onPause(dataset)} type="button">Pause download</button>}
      {dataset.local_path && <><button className="secondary" disabled={busy === `dataset-validate-${dataset.id}`} onClick={() => void onValidate(dataset)} type="button">Validate cache</button><button className="secondary" disabled={busy === `dataset-clear-${dataset.id}`} onClick={() => void onClear(dataset)} type="button">Clear cache</button>{dataset.status === "ready" && <button className="secondary" disabled={previewing} onClick={onPreview} type="button">Preview</button>}<button className="secondary" onClick={onStartEdit} type="button">Edit</button><button className="secondary danger" disabled={busy === `dataset-delete-${dataset.id}`} onClick={() => void onDelete(dataset)} type="button">Delete</button></>}
      <label className="file-picker">Upload local revision<input accept=".json,.jsonl,.csv,.tsv,.txt,.zip,.parquet" aria-label={`Upload local revision for ${dataset.dataset_id}`} disabled={busy === `dataset-upload-${dataset.id}`} onChange={(event) => void onUpload(dataset, event)} type="file" /></label>
    </div>
  </WorkspacePanel>;
}

type SuitesPageProps = {
  busy: string | null;
  endpoints: Endpoint[];
  onOpenWorkspace: () => void;
  onQueue: (suiteId: string, endpointId: string) => void;
  suites: EvaluationSuite[];
};

export function suiteBenchmarkList(suite: EvaluationSuite) {
  return suite.benchmark_list.map((item) => `${item.benchmark_id ?? "benchmark"}@${item.version ?? ""}`).join(", ");
}

export function SuitesPage({ busy, endpoints, onOpenWorkspace, onQueue, suites }: SuitesPageProps) {
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const selectedSuite = suites.find((suite) => suite.id === selectedId) ?? suites[0] ?? null;
  const availableEndpoints = endpoints.filter((endpoint) => endpoint.status === "available");

  return <div className="workspace-page suites-page">
    <PageHeader actions={<button onClick={onOpenWorkspace} type="button">Open suite builder</button>} description="Compose versioned benchmark sets and queue them on ready endpoints without losing the benchmark evidence behind each suite." eyebrow="Catalog" status={<><strong>{suites.length}</strong> versioned suites</>} title="Suites" />
    {suites.length === 0 ? <WorkspacePanel title="No evaluation suites"><p className="empty">Create a suite from the Workspace catalog to define versioned benchmark composition and default execution settings.</p></WorkspacePanel> : <div className="workspace-split workspace-split--catalog">
      <WorkspacePanel description="Choose a versioned suite to inspect composition and queue it on an available endpoint." title="Suite inventory" toolbar={<span className="workspace-count">{suites.length} versions</span>}><div className="workspace-inventory-list workspace-catalog-inventory">{suites.map((suite) => <button aria-pressed={selectedSuite?.id === suite.id} className={selectedSuite?.id === suite.id ? "workspace-select-row is-selected" : "workspace-select-row"} key={suite.id} onClick={() => setSelectedId(suite.id)} type="button"><span data-i18n-preserve><strong>{suite.name} v{suite.version}</strong></span><small data-i18n-preserve>{suiteBenchmarkList(suite)}</small><span className="sr-only">Inspect {suite.name} v{suite.version}</span></button>)}</div></WorkspacePanel>
      {selectedSuite && <WorkspacePanel className="workspace-suite-inspector" description={selectedSuite.description || "No suite description was provided."} title={<span data-i18n-preserve>{selectedSuite.name} v{selectedSuite.version}</span>}>
        <h3>Benchmark composition</h3>
        <div className="table-wrap workspace-dense-table"><table><thead><tr><th>Benchmark</th><th>Version</th></tr></thead><tbody>{selectedSuite.benchmark_list.map((item, index) => <tr key={`${String(item.benchmark_id)}-${index}`} data-i18n-preserve><td>{String(item.benchmark_id ?? "benchmark")}</td><td>{String(item.version ?? "--")}</td></tr>)}</tbody></table></div>
        <div className="workspace-suite-queue"><div><h3>Queue suite</h3><p className="muted">Uses each selected endpoint’s saved connection and capacity configuration.</p></div>{availableEndpoints.length === 0 ? <p className="empty">No available endpoints are ready to receive this suite.</p> : <div className="actions">{availableEndpoints.map((endpoint) => <button disabled={busy === `suite-${selectedSuite.id}`} key={endpoint.id} onClick={() => onQueue(selectedSuite.id, endpoint.id)} type="button">Queue on <span data-i18n-preserve>{endpoint.display_name}</span></button>)}</div>}</div>
      </WorkspacePanel>}
    </div>}
  </div>;
}
