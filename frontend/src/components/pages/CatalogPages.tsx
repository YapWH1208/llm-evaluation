import { ChangeEvent, FormEvent, type ReactNode, useEffect, useState } from "react";

import { api, Dataset } from "../../api";
import type { WorkspaceTabFor } from "../../dashboard/routing";
import { workspacePageTabCopy } from "../../i18n/catalog";
import { useTranslation } from "../../i18n/LocaleProvider";
import { translateStaticTemplate } from "../../i18n/operationalCopy";
import { DatasetMetadataFields, type DatasetMetadataValues } from "../datasets/DatasetMetadataFields";
import { PageHeader } from "../workspace/PageHeader";
import { WorkspacePanel } from "../workspace/WorkspacePanel";
import { WorkspaceTabs, workspaceTabId, workspaceTabPanelId } from "../workspace/WorkspaceTabs";

type DatasetAction = (dataset: Dataset) => Promise<void>;
type DatasetUploadAction = (dataset: Dataset, event: ChangeEvent<HTMLInputElement>) => Promise<void>;

export type DatasetEditFormValues = DatasetMetadataValues & {
  checksum: string;
  credential_binding_id: string;
  dataset_id: string;
  input_field: string;
  license_text: string;
  reference_field: string;
  revision: string;
  source_url: string;
  version: string;
};

const emptyDatasetEditForm: DatasetEditFormValues = {
  checksum: "", credential_binding_id: "", dataset_id: "", input_field: "",
  license_text: "", reference_field: "", revision: "", source_url: "", version: "",
  capabilities: [], languages: [], evaluation_type: "custom",
};

type DatasetsPageProps = {
  activeTab: WorkspaceTabFor<"datasets">;
  busy: string | null;
  datasets: Dataset[];
  onClear: DatasetAction;
  onDelete: DatasetAction;
  onPause: DatasetAction;
  onPrepare: DatasetAction;
  onStartEvaluation?: (dataset: Dataset) => void;
  onTabChange: (tab: WorkspaceTabFor<"datasets">) => void;
  onUpdate: (dataset: Dataset, payload: DatasetEditFormValues) => Promise<void>;
  onUpload: DatasetUploadAction;
  onValidate: DatasetAction;
  registration: ReactNode;
};

type DatasetPreview = { datasetId: string; fields: string[]; rows: Array<Record<string, string>> };

export function datasetEditForm(dataset: Dataset): DatasetEditFormValues {
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
    capabilities: dataset.capabilities,
    languages: dataset.languages,
    evaluation_type: dataset.evaluation_type,
  };
}

export function datasetPrepareLabel(dataset: Dataset) {
  if (dataset.license_text && !dataset.license_accepted_at) return "Accept license";
  return dataset.status === "waiting" || dataset.status === "failed" ? "Retry download" : "Download and verify";
}

export async function loadDatasetPreview(dataset: Dataset) {
  return api.previewDataset(dataset.id, 5);
}

export function DatasetsPage({ activeTab, busy, datasets, onClear, onDelete, onPause, onPrepare, onStartEvaluation, onTabChange, onUpdate, onUpload, onValidate, registration }: DatasetsPageProps) {
  const { formatBytes, locale } = useTranslation();
  const copy = workspacePageTabCopy[locale].datasets;
  const [usage, setUsage] = useState<{ cache_bytes: number; available_bytes: number } | null>(null);
  const usageKey = datasets.map((dataset) => `${dataset.id}:${dataset.status}`).join("|");
  const [preview, setPreview] = useState<DatasetPreview | null>(null);
  const [previewError, setPreviewError] = useState<string | null>(null);
  const [previewingId, setPreviewingId] = useState<string | null>(null);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [editForm, setEditForm] = useState<DatasetEditFormValues>(emptyDatasetEditForm);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const selectedDataset = datasets.find((dataset) => dataset.id === selectedId) ?? datasets[0] ?? null;

  useEffect(() => { void api.datasetDiskUsage().then(setUsage).catch(() => setUsage(null)); }, [usageKey]);

  function requestPreview(dataset: Dataset) {
    setPreviewingId(dataset.id);
    setPreviewError(null);
    void loadDatasetPreview(dataset)
      .then((data) => setPreview({ datasetId: dataset.id, fields: data.fields, rows: data.rows }))
      .catch((error: unknown) => {
        setPreviewError(error instanceof Error ? error.message : translateStaticTemplate(locale, "Preview unavailable."));
        setPreview(null);
      })
      .finally(() => setPreviewingId(null));
  }

  return (
    <div className="workspace-page datasets-page">
      <PageHeader
        description="Manage source versions, cached data, licenses, and field mapping while keeping the selected dataset’s evidence in view."
        eyebrow="Catalog"
        status={<>{usage ? <><strong>{formatBytes(usage.cache_bytes)}</strong> cached · {formatBytes(usage.available_bytes)} free</> : "Loading disk usage…"}</>}
        title="Datasets"
      />
      <WorkspaceTabs ariaLabel="Datasets sections" idPrefix="datasets" onChange={onTabChange} tabs={[{ id: "dataset-inventory", label: copy.datasetInventory }, { id: "register-dataset", label: copy.registerDataset }]} value={activeTab} />
      <div aria-labelledby={workspaceTabId("datasets", activeTab)} id={workspaceTabPanelId("datasets", activeTab)} role="tabpanel" tabIndex={0}>
        {activeTab === "register-dataset" ? registration : <>
          {previewError && <p className="error" role="alert">{previewError}</p>}
          {datasets.length === 0 ? <WorkspacePanel title="No dataset versions"><p className="empty">Register a source, then prepare, validate, and inspect it here.</p><div className="actions"><button onClick={() => onTabChange("register-dataset")} type="button">{copy.registerDataset}</button></div></WorkspacePanel> : <div className="workspace-split workspace-split--catalog">
            <WorkspacePanel description="Select a source version to inspect its cache, metadata, and lifecycle actions." title="Dataset inventory" toolbar={<span className="workspace-count">{datasets.length} versions</span>}>
              <div className="workspace-inventory-list workspace-catalog-inventory">{datasets.map((dataset) => <button aria-pressed={selectedDataset?.id === dataset.id} className={selectedDataset?.id === dataset.id ? "workspace-select-row is-selected" : "workspace-select-row"} key={dataset.id} onClick={() => setSelectedId(dataset.id)} type="button"><span data-i18n-preserve><strong>{dataset.dataset_id} v{dataset.version}</strong></span><span className={`badge ${dataset.status}`}>{dataset.status.replaceAll("_", " ")}</span><small data-i18n-preserve>{dataset.revision} · {dataset.source_url ? "source configured" : "local upload"}</small><span className="sr-only">Inspect {dataset.dataset_id} v{dataset.version}</span></button>)}</div>
            </WorkspacePanel>
            {selectedDataset && <DatasetInspector
              busy={busy}
              dataset={selectedDataset}
              editForm={editForm}
              editing={editingId === selectedDataset.id}
              onClear={onClear}
              onDelete={onDelete}
              onEditForm={setEditForm}
              onPause={onPause}
              onPrepare={onPrepare}
              onPreview={() => requestPreview(selectedDataset)}
              onStartEdit={() => {
                setEditingId(selectedDataset.id);
                setEditForm(datasetEditForm(selectedDataset));
                setPreview(null);
                if (selectedDataset.status === "ready") requestPreview(selectedDataset);
              }}
              onStartEvaluation={onStartEvaluation}
              onStopEdit={() => setEditingId(null)}
              onSubmitEdit={(event) => {
                event.preventDefault();
                setEditingId(null);
                void onUpdate(selectedDataset, editForm);
              }}
              onUpload={onUpload}
              onValidate={onValidate}
              preview={preview?.datasetId === selectedDataset.id ? preview : null}
              previewing={previewingId === selectedDataset.id}
            />}
          </div>}
        </>}
      </div>
    </div>
  );
}

type DatasetInspectorProps = {
  busy: string | null;
  dataset: Dataset;
  editForm: DatasetEditFormValues;
  editing: boolean;
  onClear: DatasetAction;
  onDelete: DatasetAction;
  onEditForm: (value: DatasetEditFormValues) => void;
  onPause: DatasetAction;
  onPrepare: DatasetAction;
  onPreview: () => void;
  onStartEdit: () => void;
  onStartEvaluation?: (dataset: Dataset) => void;
  onStopEdit: () => void;
  onSubmitEdit: (event: FormEvent<HTMLFormElement>) => void;
  onUpload: DatasetUploadAction;
  onValidate: DatasetAction;
  preview: DatasetPreview | null;
  previewing: boolean;
};

const activeDatasetStatuses = new Set(["downloading", "verifying", "preparing", "removing"]);

export function DatasetInspector({ busy, dataset, editForm, editing, onClear, onDelete, onEditForm, onPause, onPrepare, onPreview, onStartEdit, onStartEvaluation, onStopEdit, onSubmitEdit, onUpload, onValidate, preview, previewing }: DatasetInspectorProps) {
  const { formatNumber: display, t } = useTranslation();
  const active = activeDatasetStatuses.has(dataset.status);
  const schemaFields = preview?.fields ?? [];
  const hasSchema = schemaFields.length > 0;
  const fieldsCollide = Boolean(editForm.input_field) && editForm.input_field === editForm.reference_field;
  const schemaMismatch = hasSchema && [editForm.input_field, editForm.reference_field].some((field) => field && !schemaFields.includes(field));
  return <WorkspacePanel className="workspace-dataset-inspector" title={<span data-i18n-preserve>{dataset.dataset_id} v{dataset.version}</span>} toolbar={<span className={`badge ${dataset.status}`}>{dataset.status.replaceAll("_", " ")}</span>}>
    <div className="workspace-inspector-summary">
      <p><span className="workspace-item-meta">Revision</span> <span data-i18n-preserve>{dataset.revision}</span> · {dataset.source_url ? <span data-i18n-preserve>{dataset.source_url}</span> : "Upload a local revision"}</p>
      <p><span className="workspace-item-meta">Cache</span> {dataset.size_bytes === null ? "Not cached" : `${display(dataset.size_bytes)} bytes`} · {dataset.checksum ? <span data-i18n-preserve>SHA-256 {dataset.checksum.slice(0, 12)}…</span> : "Checksum generated on import"}</p>
      {dataset.credential_binding_id && <p><span className="workspace-item-meta">Credential binding</span> <span data-i18n-preserve>{dataset.credential_binding_id}</span></p>}
      {dataset.input_field && <p><span className="workspace-item-meta">Input field</span> <span data-i18n-preserve>{dataset.input_field}</span>{dataset.reference_field && <><span className="workspace-item-meta"> · Reference field</span> <span data-i18n-preserve>{dataset.reference_field}</span></>}</p>}
      <p><span className="workspace-item-meta">{t("datasetRegister.evaluationType")}</span> <span data-i18n-preserve>{dataset.evaluation_type.replaceAll("_", " ")}</span></p>
      {dataset.capabilities.length > 0 && <p><span className="workspace-item-meta">{t("datasetRegister.capabilities")}</span> <span data-i18n-preserve>{dataset.capabilities.join(", ")}</span></p>}
      {dataset.languages.length > 0 && <p><span className="workspace-item-meta">{t("datasetRegister.languages")}</span> <span data-i18n-preserve>{dataset.languages.join(", ")}</span></p>}
      {dataset.error_message && <p className="error" data-i18n-preserve>{dataset.error_message}</p>}
    </div>
    {preview && <div className="table-wrap workspace-preview-table"><h3>Data preview</h3><table><thead><tr>{preview.fields.map((field) => <th key={field}>{field}</th>)}</tr></thead><tbody>{preview.rows.map((row, index) => <tr key={index}>{preview.fields.map((field) => <td key={field}>{row[field] ?? ""}</td>)}</tr>)}</tbody></table></div>}
    {editing && !active && <form className="form workspace-dataset-edit-form" onSubmit={onSubmitEdit}>
      <label>Dataset ID<input onChange={(event) => onEditForm({ ...editForm, dataset_id: event.target.value })} required value={editForm.dataset_id} /></label>
      <div className="workspace-field-grid workspace-field-grid--two">
        <label>Version<input onChange={(event) => onEditForm({ ...editForm, version: event.target.value })} required value={editForm.version} /></label>
        <label>Revision<input onChange={(event) => onEditForm({ ...editForm, revision: event.target.value })} required value={editForm.revision} /></label>
      </div>
      <label>Source HTTPS URL<input onChange={(event) => onEditForm({ ...editForm, source_url: event.target.value })} placeholder="https://… or hf://owner/repository/path" value={editForm.source_url} /></label>
      <label>Expected SHA-256 checksum<input onChange={(event) => onEditForm({ ...editForm, checksum: event.target.value })} value={editForm.checksum} /></label>
      <label>Credential binding ID<input onChange={(event) => onEditForm({ ...editForm, credential_binding_id: event.target.value })} value={editForm.credential_binding_id} /></label>
      {previewing && <p className="muted">{t("datasetRegister.schemaLoading")}</p>}
      <div className="workspace-field-grid workspace-field-grid--two">
        <label>{t("datasetRegister.inputField")}{hasSchema
          ? <select onChange={(event) => onEditForm({ ...editForm, input_field: event.target.value })} value={editForm.input_field}><option value="">—</option>{editForm.input_field && !schemaFields.includes(editForm.input_field) && <option data-i18n-preserve value={editForm.input_field}>{editForm.input_field}</option>}{schemaFields.map((field) => <option data-i18n-preserve key={field} value={field}>{field}</option>)}</select>
          : <input onChange={(event) => onEditForm({ ...editForm, input_field: event.target.value })} value={editForm.input_field} />}
        </label>
        <label>{t("datasetRegister.referenceField")}{hasSchema
          ? <select onChange={(event) => onEditForm({ ...editForm, reference_field: event.target.value })} value={editForm.reference_field}><option value="">—</option>{editForm.reference_field && !schemaFields.includes(editForm.reference_field) && <option data-i18n-preserve value={editForm.reference_field}>{editForm.reference_field}</option>}{schemaFields.map((field) => <option data-i18n-preserve key={field} value={field}>{field}</option>)}</select>
          : <input onChange={(event) => onEditForm({ ...editForm, reference_field: event.target.value })} value={editForm.reference_field} />}
        </label>
      </div>
      {!previewing && !hasSchema && <p className="muted">{t("datasetRegister.manualFieldHint")}</p>}
      {fieldsCollide && <p className="error" role="alert">{t("runLauncher.schemaDistinctFields")}</p>}
      {schemaMismatch && <p className="error" role="alert">{t("datasetRegister.schemaChanged")}</p>}
      <DatasetMetadataFields onChange={onEditForm} values={editForm} />
      <label>License text<textarea onChange={(event) => onEditForm({ ...editForm, license_text: event.target.value })} value={editForm.license_text} /></label>
      <div className="actions"><button disabled={busy === `dataset-edit-${dataset.id}` || previewing || fieldsCollide || schemaMismatch}>Save changes</button><button className="secondary" onClick={onStopEdit} type="button">Cancel</button></div>
    </form>}
    <div className="actions workspace-dataset-actions">
      {!active && dataset.status !== "ready" && <button disabled={busy === `dataset-${dataset.id}`} onClick={() => void onPrepare(dataset)} type="button">{datasetPrepareLabel(dataset)}</button>}
      {dataset.status === "downloading" && <button className="secondary" disabled={busy === `dataset-${dataset.id}`} onClick={() => void onPause(dataset)} type="button">Pause download</button>}
      {!active && dataset.local_path && <><button className="secondary" disabled={busy === `dataset-validate-${dataset.id}`} onClick={() => void onValidate(dataset)} type="button">Validate cache</button><button className="secondary" disabled={busy === `dataset-clear-${dataset.id}`} onClick={() => void onClear(dataset)} type="button">Clear cache</button>{dataset.status === "ready" && <button className="secondary" disabled={previewing} onClick={onPreview} type="button">Preview</button>}</>}
      {!active && dataset.status === "ready" && onStartEvaluation && <button onClick={() => onStartEvaluation(dataset)} type="button">{t("datasetRun.startEvaluation")}</button>}
      {!active && <><button className="secondary" onClick={onStartEdit} type="button">Edit</button><button className="secondary danger" disabled={busy === `dataset-delete-${dataset.id}`} onClick={() => void onDelete(dataset)} type="button">Delete</button><label className="file-picker">Upload local revision<input accept=".json,.jsonl,.csv,.tsv,.txt,.zip,.parquet" aria-label={`Upload local revision for ${dataset.dataset_id}`} disabled={busy === `dataset-upload-${dataset.id}`} onChange={(event) => void onUpload(dataset, event)} type="file" /></label></>}
    </div>
  </WorkspacePanel>;
}
