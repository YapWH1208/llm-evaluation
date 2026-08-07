import { cleanup, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import App from "./App";
import { api } from "./api";
import { LocaleProvider } from "./i18n/LocaleProvider";

afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
});

const readyDataset = {
  id: "ds-1",
  dataset_id: "demo",
  version: "1",
  revision: "default",
  source_url: null,
  credential_binding_id: null,
  checksum: "abc",
  local_path: "/data/datasets/x",
  size_bytes: 10,
  license_text: null,
  license_accepted_at: null,
  status: "ready",
  error_message: null,
  input_field: "question",
  reference_field: "answer",
};

async function renderApp(datasets = [readyDataset]) {
  vi.spyOn(api, "listEndpoints").mockResolvedValue([]);
  vi.spyOn(api, "listRuns").mockResolvedValue([]);
  vi.spyOn(api, "dashboard").mockResolvedValue(null as never);
  vi.spyOn(api, "listPromptPackages").mockResolvedValue([]);
  vi.spyOn(api, "listDatasets").mockResolvedValue(datasets);
  vi.spyOn(api, "listSuites").mockResolvedValue([]);
  vi.spyOn(api, "listBenchmarks").mockResolvedValue([]);
  vi.spyOn(api, "listTasks").mockResolvedValue([]);
  vi.spyOn(api, "analyticsMatrix").mockResolvedValue(null as never);
  vi.spyOn(api, "listUsers").mockResolvedValue([]);
  vi.spyOn(api, "listAuditEvents").mockResolvedValue([]);
  vi.spyOn(api, "systemHealth").mockResolvedValue(null as never);
  vi.spyOn(api, "datasetDiskUsage").mockResolvedValue({ root: "/data", cache_bytes: 10, available_bytes: 1000, total_bytes: 2000 });
  render(<LocaleProvider><App /></LocaleProvider>);
  const user = userEvent.setup();
  await user.click(screen.getByRole("button", { name: "Datasets" }));
  return { user };
}

describe("dataset catalog", () => {
  it("previews the first rows of a ready dataset", async () => {
    const preview = vi.spyOn(api, "previewDataset").mockResolvedValue({ fields: ["question", "answer"], rows: [{ question: "2+2?", answer: "4" }] });
    const { user } = await renderApp();
    await user.click(screen.getByRole("button", { name: "Preview" }));
    await waitFor(() => expect(screen.getByRole("heading", { name: /Data preview/i })).toBeTruthy());
    expect(preview).toHaveBeenCalledWith("ds-1", 5);
    expect(screen.getByText("2+2?")).toBeTruthy();
  }, 10_000);

  it("edits dataset metadata through the inline form", async () => {
    const update = vi.spyOn(api, "updateDataset").mockResolvedValue({ ...readyDataset, dataset_id: "renamed" });
    const list = vi.spyOn(api, "listDatasets");
    list.mockResolvedValue([readyDataset]);
    const { user } = await renderApp();
    await user.click(screen.getByRole("button", { name: "Edit" }));
    const idInput = screen.getByLabelText("Dataset ID");
    await user.clear(idInput);
    await user.type(idInput, "renamed");
    await user.click(screen.getByRole("button", { name: "Save changes" }));
    expect(update).toHaveBeenCalledWith("ds-1", expect.objectContaining({ dataset_id: "renamed" }));
  }, 10_000);

  it("deletes a dataset after confirmation", async () => {
    const remove = vi.spyOn(api, "deleteDataset").mockResolvedValue({ ...readyDataset });
    vi.spyOn(window, "confirm").mockReturnValue(true);
    const { user } = await renderApp();
    await user.click(screen.getByRole("button", { name: "Delete" }));
    expect(remove).toHaveBeenCalledWith("ds-1");
  }, 10_000);
});
