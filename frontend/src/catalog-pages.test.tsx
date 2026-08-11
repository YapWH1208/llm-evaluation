import { cleanup, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import { Dataset, api } from "./api";
import { datasetEditForm, datasetPrepareLabel, DatasetInspector, DatasetsPage, loadDatasetPreview } from "./components/pages/CatalogPages";
import { LocaleProvider } from "./i18n/LocaleProvider";

afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
});


const readyDataset: Dataset = {
  capabilities: [],
  checksum: "a1b2c3d4",
  credential_binding_id: null,
  dataset_id: "support-set",
  error_message: null,
  evaluation_type: "custom",
  id: "dataset-1",
  input_field: "question",
  languages: [],
  license_accepted_at: null,
  license_text: null,
  local_path: "/data/support-set.jsonl",
  reference_field: "answer",
  revision: "stable",
  size_bytes: 128,
  source_url: "https://datasets.example.test/support-set.jsonl",
  status: "ready",
  version: "1",
};

const waitingDataset: Dataset = {
  ...readyDataset,
  dataset_id: "safety-set",
  id: "dataset-2",
  local_path: null,
  status: "waiting",
  version: "2",
};


function renderCatalogPage(page: React.ReactNode) {
  return render(<LocaleProvider>{page}</LocaleProvider>);
}

describe("catalog workspace pages", () => {

  it("creates an editable dataset form without converting absent metadata to strings", () => {
    expect(datasetEditForm({ ...readyDataset, checksum: null, credential_binding_id: null, license_text: null, source_url: null })).toEqual(expect.objectContaining({ checksum: "", credential_binding_id: "", license_text: "", source_url: "" }));
  });

  it("selects the correct preparation action for license, retry, and fresh download states", () => {
    expect(datasetPrepareLabel({ ...waitingDataset, license_text: "Terms" })).toBe("Accept license");
    expect(datasetPrepareLabel(waitingDataset)).toBe("Retry download");
    expect(datasetPrepareLabel({ ...waitingDataset, status: "registered" })).toBe("Download and verify");
  });

  it("loads the five-row dataset preview used by the selected inspector", async () => {
    const preview = { fields: ["question"], rows: [{ question: "2 + 2" }] };
    const previewRequest = vi.spyOn(api, "previewDataset").mockResolvedValue(preview);

    await expect(loadDatasetPreview(readyDataset)).resolves.toEqual(preview);
    expect(previewRequest).toHaveBeenCalledWith(readyDataset.id, 5);
  });

  it("keeps cache validation available in the selected dataset inspector", async () => {
    const user = userEvent.setup();
    const onValidate = vi.fn();
    renderCatalogPage(<DatasetInspector busy={null} dataset={readyDataset} editForm={{}} editing={false} onClear={vi.fn()} onDelete={vi.fn()} onEditForm={vi.fn()} onPause={vi.fn()} onPrepare={vi.fn()} onPreview={vi.fn()} onStartEdit={vi.fn()} onStopEdit={vi.fn()} onSubmitEdit={vi.fn()} onUpload={vi.fn()} onValidate={onValidate} preview={null} previewing={false} />);

    expect(screen.getByText("SHA-256 a1b2c3d4…")).toBeVisible();
    await user.click(screen.getByRole("button", { name: "Validate cache" }));
    expect(onValidate).toHaveBeenCalledWith(readyDataset);
  });

  it("keeps edit and delete available for a failed dataset without a cache", async () => {
    const user = userEvent.setup();
    const failedDataset = {
      ...waitingDataset,
      error_message: "Source file not found.",
      status: "failed",
    };
    const onDelete = vi.fn();
    const onStartEdit = vi.fn();
    renderCatalogPage(<DatasetInspector busy={null} dataset={failedDataset} editForm={{}} editing={false} onClear={vi.fn()} onDelete={onDelete} onEditForm={vi.fn()} onPause={vi.fn()} onPrepare={vi.fn()} onPreview={vi.fn()} onStartEdit={onStartEdit} onStopEdit={vi.fn()} onSubmitEdit={vi.fn()} onUpload={vi.fn()} onValidate={vi.fn()} preview={null} previewing={false} />);

    await user.click(screen.getByRole("button", { name: "Edit" }));
    await user.click(screen.getByRole("button", { name: "Delete" }));

    expect(onStartEdit).toHaveBeenCalledOnce();
    expect(onDelete).toHaveBeenCalledWith(failedDataset);
    expect(screen.queryByRole("button", { name: "Validate cache" })).not.toBeInTheDocument();
  });

  it("suppresses mutation actions while a dataset is actively preparing", () => {
    renderCatalogPage(<DatasetInspector busy={null} dataset={{ ...waitingDataset, status: "preparing" }} editForm={datasetEditForm(waitingDataset)} editing onClear={vi.fn()} onDelete={vi.fn()} onEditForm={vi.fn()} onPause={vi.fn()} onPrepare={vi.fn()} onPreview={vi.fn()} onStartEdit={vi.fn()} onStopEdit={vi.fn()} onSubmitEdit={vi.fn()} onUpload={vi.fn()} onValidate={vi.fn()} preview={null} previewing={false} />);

    expect(screen.queryByRole("button", { name: "Edit" })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Delete" })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Download and verify" })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Save changes" })).not.toBeInTheDocument();
  });

  it("starts an evaluation handoff for a ready dataset without queueing it", async () => {
    const user = userEvent.setup();
    const onStartEvaluation = vi.fn();
    renderCatalogPage(<DatasetInspector busy={null} dataset={readyDataset} editForm={{}} editing={false} onClear={vi.fn()} onDelete={vi.fn()} onEditForm={vi.fn()} onPause={vi.fn()} onPrepare={vi.fn()} onPreview={vi.fn()} onStartEdit={vi.fn()} onStartEvaluation={onStartEvaluation} onStopEdit={vi.fn()} onSubmitEdit={vi.fn()} onUpload={vi.fn()} onValidate={vi.fn()} preview={null} previewing={false} />);

    await user.click(screen.getByRole("button", { name: "Start evaluation" }));

    expect(onStartEvaluation).toHaveBeenCalledWith(readyDataset);
  });

  it("renders selected preview rows after loading the dataset inspection sample", async () => {
    const user = userEvent.setup();
    vi.spyOn(api, "datasetDiskUsage").mockResolvedValue({ available_bytes: 1000, cache_bytes: 128, root: "/data", total_bytes: 2000 });
    vi.spyOn(api, "previewDataset").mockResolvedValue({ fields: ["question"], rows: [{ question: "2 + 2" }] });
    renderCatalogPage(<DatasetsPage activeTab="dataset-inventory" busy={null} datasets={[readyDataset]} onClear={vi.fn()} onDelete={vi.fn()} onPause={vi.fn()} onPrepare={vi.fn()} onTabChange={vi.fn()} onUpdate={vi.fn()} onUpload={vi.fn()} onValidate={vi.fn()} registration={<div>Dataset registration</div>} />);

    await user.click(screen.getByRole("button", { name: "Preview" }));

    expect(await screen.findByText("2 + 2")).toBeVisible();
  });

  it("refetches disk usage only when dataset cache state changes", async () => {
    const usageRequest = vi.spyOn(api, "datasetDiskUsage").mockResolvedValue({ available_bytes: 1000, cache_bytes: 128, root: "/data", total_bytes: 2000 });
    const page = <DatasetsPage activeTab="dataset-inventory" busy={null} datasets={[readyDataset]} onClear={vi.fn()} onDelete={vi.fn()} onPause={vi.fn()} onPrepare={vi.fn()} onTabChange={vi.fn()} onUpdate={vi.fn()} onUpload={vi.fn()} onValidate={vi.fn()} registration={<div>Dataset registration</div>} />;
    const { rerender } = renderCatalogPage(page);

    expect(usageRequest).toHaveBeenCalledTimes(1);

    rerender(<LocaleProvider><DatasetsPage activeTab="dataset-inventory" busy={null} datasets={[{ ...readyDataset }]} onClear={vi.fn()} onDelete={vi.fn()} onPause={vi.fn()} onPrepare={vi.fn()} onTabChange={vi.fn()} onUpdate={vi.fn()} onUpload={vi.fn()} onValidate={vi.fn()} registration={<div>Dataset registration</div>} /></LocaleProvider>);
    await waitFor(() => expect(usageRequest).toHaveBeenCalledTimes(1));

    rerender(<LocaleProvider><DatasetsPage activeTab="dataset-inventory" busy={null} datasets={[{ ...readyDataset, status: "verifying" }]} onClear={vi.fn()} onDelete={vi.fn()} onPause={vi.fn()} onPrepare={vi.fn()} onTabChange={vi.fn()} onUpdate={vi.fn()} onUpload={vi.fn()} onValidate={vi.fn()} registration={<div>Dataset registration</div>} /></LocaleProvider>);
    await waitFor(() => expect(usageRequest).toHaveBeenCalledTimes(2));
  });


  it("keeps the dataset inventory visible while selecting a versioned inspector", async () => {
    const user = userEvent.setup();
    vi.spyOn(api, "datasetDiskUsage").mockResolvedValue({ available_bytes: 1000, cache_bytes: 128, root: "/data", total_bytes: 2000 });
    renderCatalogPage(<DatasetsPage activeTab="dataset-inventory" busy={null} datasets={[readyDataset, waitingDataset]} onClear={vi.fn()} onDelete={vi.fn()} onPause={vi.fn()} onPrepare={vi.fn()} onTabChange={vi.fn()} onUpdate={vi.fn()} onUpload={vi.fn()} onValidate={vi.fn()} registration={<div>Dataset registration</div>} />);

    expect(screen.getByRole("heading", { level: 1, name: "Datasets" })).toBeVisible();
    expect(screen.getByRole("button", { name: /Inspect support-set v1/ })).toBeVisible();
    await user.click(screen.getByRole("button", { name: /Inspect safety-set v2/ }));

    expect(screen.getByRole("heading", { level: 2, name: "safety-set v2" })).toBeVisible();
    expect(screen.getByRole("button", { name: /Inspect support-set v1/ })).toBeVisible();
    expect(screen.getByRole("button", { name: "Retry download" })).toBeVisible();
  });

  it("keeps registration out of the dataset inventory tab", () => {
    vi.spyOn(api, "datasetDiskUsage").mockResolvedValue({ available_bytes: 1000, cache_bytes: 0, root: "/data", total_bytes: 2000 });
    renderCatalogPage(<DatasetsPage activeTab="dataset-inventory" busy={null} datasets={[readyDataset]} onClear={vi.fn()} onDelete={vi.fn()} onPause={vi.fn()} onPrepare={vi.fn()} onTabChange={vi.fn()} onUpdate={vi.fn()} onUpload={vi.fn()} onValidate={vi.fn()} registration={<section aria-label="Dataset registration">Registration form</section>} />);

    expect(screen.getByRole("tab", { name: "Dataset inventory" })).toHaveAttribute("aria-selected", "true");
    expect(screen.getByRole("heading", { name: "Dataset inventory" })).toBeVisible();
    expect(screen.queryByRole("region", { name: "Dataset registration" })).not.toBeInTheDocument();
  });

  it("shows only registration on the register-dataset tab", () => {
    vi.spyOn(api, "datasetDiskUsage").mockResolvedValue({ available_bytes: 1000, cache_bytes: 0, root: "/data", total_bytes: 2000 });
    renderCatalogPage(<DatasetsPage activeTab="register-dataset" busy={null} datasets={[readyDataset]} onClear={vi.fn()} onDelete={vi.fn()} onPause={vi.fn()} onPrepare={vi.fn()} onTabChange={vi.fn()} onUpdate={vi.fn()} onUpload={vi.fn()} onValidate={vi.fn()} registration={<section aria-label="Dataset registration">Registration form</section>} />);

    expect(screen.getByRole("region", { name: "Dataset registration" })).toBeVisible();
    expect(screen.getByRole("tab", { name: "Register dataset" })).toHaveAttribute("aria-selected", "true");
    expect(screen.queryByRole("heading", { name: "Dataset inventory" })).not.toBeInTheDocument();
  });

  it("routes an empty inventory call to action to dataset registration", async () => {
    const user = userEvent.setup();
    const onTabChange = vi.fn();
    vi.spyOn(api, "datasetDiskUsage").mockResolvedValue({ available_bytes: 1000, cache_bytes: 0, root: "/data", total_bytes: 2000 });
    renderCatalogPage(<DatasetsPage activeTab="dataset-inventory" busy={null} datasets={[]} onClear={vi.fn()} onDelete={vi.fn()} onPause={vi.fn()} onPrepare={vi.fn()} onTabChange={onTabChange} onUpdate={vi.fn()} onUpload={vi.fn()} onValidate={vi.fn()} registration={<section aria-label="Dataset registration">Registration form</section>} />);

    await user.click(screen.getByRole("button", { name: "Register dataset" }));

    expect(onTabChange).toHaveBeenCalledWith("register-dataset");
  });

});
