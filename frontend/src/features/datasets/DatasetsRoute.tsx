import { type ChangeEvent, type FormEvent, useCallback, useEffect, useState } from "react";

import type { FeatureRouteProps } from "../../app/types";
import { DatasetRegistrationForm, type DatasetRegistrationFormValues } from "../../components/datasets/DatasetRegistrationForm";
import { DatasetsPage, type DatasetEditFormValues } from "../../components/pages/CatalogPages";
import { useTranslation } from "../../i18n/LocaleProvider";
import { translateStaticTemplate } from "../../i18n/operationalCopy";
import { datasetsApi, type Dataset } from "./api";

const initialDataset: DatasetRegistrationFormValues = {
  dataset_id: "", version: "1", revision: "main", source_url: "", checksum: "", credential_binding_id: "", license_text: "",
  input_field: "", reference_field: "", capabilities: [], languages: [], evaluation_type: "custom",
};

function fileAsDataUrl(file: File): Promise<string> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onerror = () => reject(reader.error ?? new Error("Unable to read selected file."));
    reader.onload = () => resolve(String(reader.result));
    reader.readAsDataURL(file);
  });
}

export function DatasetsRoute({ activeTab, navigate, reportError, showNotice }: FeatureRouteProps<"datasets">) {
  const { locale } = useTranslation();
  const [busy, setBusy] = useState<string | null>(null);
  const [datasets, setDatasets] = useState<Dataset[]>([]);
  const [form, setForm] = useState(initialDataset);
  const refresh = useCallback(async () => setDatasets(await datasetsApi.list()), []);

  useEffect(() => { void refresh().catch(reportError); }, [refresh, reportError]);

  async function createDataset(event: FormEvent) {
    event.preventDefault();
    setBusy("dataset");
    try {
      await datasetsApi.create({
        ...form, source_url: form.source_url || null, checksum: form.checksum || null,
        credential_binding_id: form.credential_binding_id || null, license_text: form.license_text || null,
        input_field: form.input_field || null, reference_field: form.reference_field || null,
      });
      setForm(initialDataset);
      showNotice("Dataset version registered.");
      await refresh();
    } catch (error) { reportError(error); } finally { setBusy(null); }
  }

  async function pauseDataset(dataset: Dataset) {
    setBusy(`dataset-${dataset.id}`);
    try {
      await datasetsApi.pause(dataset.id);
      showNotice("{{dataset}} download paused.", { dataset: dataset.dataset_id });
      await refresh();
    } catch (error) { reportError(error); } finally { setBusy(null); }
  }

  async function prepareDataset(dataset: Dataset) {
    setBusy(`dataset-${dataset.id}`);
    try {
      if (dataset.license_text && !dataset.license_accepted_at) {
        await datasetsApi.acceptLicense(dataset.id);
        showNotice("License accepted. The dataset can now be downloaded.");
      } else {
        await datasetsApi.download(dataset.id);
        showNotice("Dataset downloaded, verified, and cached.");
      }
      await refresh();
    } catch (error) { reportError(error); } finally { setBusy(null); }
  }

  async function uploadDataset(dataset: Dataset, event: ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0];
    if (!file) return;
    setBusy(`dataset-upload-${dataset.id}`);
    try {
      const dataUrl = await fileAsDataUrl(file);
      await datasetsApi.upload(dataset.id, { filename: file.name, base64_data: dataUrl.split(",", 2)[1] ?? "" });
      showNotice("Dataset upload checksum verified and stored in the local dataset cache.");
      await refresh();
    } catch (error) { reportError(error); } finally { setBusy(null); }
  }

  async function validateDataset(dataset: Dataset) {
    setBusy(`dataset-validate-${dataset.id}`);
    try { await datasetsApi.validate(dataset.id); showNotice("Dataset cache checksum and size were verified."); await refresh(); }
    catch (error) { reportError(error); } finally { setBusy(null); }
  }

  async function clearDatasetCache(dataset: Dataset) {
    if (!window.confirm(translateStaticTemplate(locale, "Remove the cached data for {{dataset}} v{{version}}? The registered version will remain.", { dataset: dataset.dataset_id, version: dataset.version }))) return;
    setBusy(`dataset-clear-${dataset.id}`);
    try { await datasetsApi.clearCache(dataset.id); showNotice("Dataset cache removed. You can download or upload it again."); await refresh(); }
    catch (error) { reportError(error); } finally { setBusy(null); }
  }

  async function updateDataset(dataset: Dataset, payload: DatasetEditFormValues) {
    setBusy(`dataset-edit-${dataset.id}`);
    try {
      await datasetsApi.update(dataset.id, {
        ...payload, source_url: payload.source_url || null, checksum: payload.checksum || null, license_text: payload.license_text || null,
        credential_binding_id: payload.credential_binding_id || null, input_field: payload.input_field || null, reference_field: payload.reference_field || null,
      });
      showNotice("Dataset version updated.");
      await refresh();
    } catch (error) { reportError(error); } finally { setBusy(null); }
  }

  async function deleteDataset(dataset: Dataset) {
    if (!window.confirm(translateStaticTemplate(locale, "Delete dataset version?"))) return;
    setBusy(`dataset-delete-${dataset.id}`);
    try { await datasetsApi.remove(dataset.id); showNotice("Dataset version deleted."); await refresh(); }
    catch (error) { reportError(error); } finally { setBusy(null); }
  }

  return <DatasetsPage activeTab={activeTab} busy={busy} datasets={datasets} onClear={clearDatasetCache} onDelete={deleteDataset} onPause={pauseDataset} onPrepare={prepareDataset} onStartEvaluation={(dataset) => navigate("runs", { datasetId: dataset.id, tab: "dataset-evaluation" })} onTabChange={(tab) => navigate("datasets", { tab })} onUpdate={updateDataset} onUpload={uploadDataset} onValidate={validateDataset} registration={<DatasetRegistrationForm busy={busy === "dataset"} onChange={setForm} onSubmit={createDataset} values={form} />} />;
}
