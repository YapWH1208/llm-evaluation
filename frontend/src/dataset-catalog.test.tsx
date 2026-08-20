import { cleanup, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import App from "./App";
import { analyticsApi } from "./features/analytics/api";
import { benchmarksApi } from "./features/benchmarks/api";
import { datasetsApi, type Dataset } from "./features/datasets/api";
import { endpointsApi } from "./features/endpoints/api";
import { runsApi } from "./features/runs/api";
import { LocaleProvider } from "./i18n/LocaleProvider";

afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
  window.history.replaceState(null, "", "/dashboard");
});

const readyDataset: Dataset = {
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
  capabilities: [],
  languages: [],
  evaluation_type: "custom",
};

async function renderApp(datasets = [readyDataset]) {
  vi.spyOn(endpointsApi, "list").mockResolvedValue([]);
  vi.spyOn(runsApi, "list").mockResolvedValue([]);
  vi.spyOn(analyticsApi, "dashboard").mockResolvedValue(null as never);
  vi.spyOn(benchmarksApi, "listPrompts").mockResolvedValue([]);
  vi.spyOn(datasetsApi, "list").mockResolvedValue(datasets);
  vi.spyOn(benchmarksApi, "list").mockResolvedValue([]);
  vi.spyOn(analyticsApi, "listTasks").mockResolvedValue([]);
  vi.spyOn(analyticsApi, "matrix").mockResolvedValue(null as never);
  vi.spyOn(analyticsApi, "systemHealth").mockResolvedValue(null as never);
  vi.spyOn(datasetsApi, "diskUsage").mockResolvedValue({ root: "/data", cache_bytes: 10, available_bytes: 1000, total_bytes: 2000 });
  render(<LocaleProvider><App /></LocaleProvider>);
  const user = userEvent.setup();
  await user.click(screen.getByRole("link", { name: "Datasets" }));
  return { user };
}

describe("dataset catalog", () => {
  it("previews the first rows of a ready dataset", async () => {
    const preview = vi.spyOn(datasetsApi, "preview").mockResolvedValue({ fields: ["question", "answer"], rows: [{ question: "2+2?", answer: "4" }] });
    const { user } = await renderApp();
    await user.click(screen.getByRole("button", { name: "Preview" }));
    await waitFor(() => expect(screen.getByRole("heading", { name: /Data preview/i })).toBeTruthy());
    expect(preview).toHaveBeenCalledWith("ds-1", 5);
    expect(screen.getByText("2+2?")).toBeTruthy();
  }, 10_000);

  it("edits dataset metadata through the inline form", async () => {
    vi.spyOn(datasetsApi, "preview").mockResolvedValue({ fields: ["question", "answer"], rows: [] });
    const update = vi.spyOn(datasetsApi, "update").mockResolvedValue({ ...readyDataset, dataset_id: "renamed" });
    const list = vi.spyOn(datasetsApi, "list");
    list.mockResolvedValue([readyDataset]);
    const { user } = await renderApp();
    await user.click(screen.getByRole("button", { name: "Edit" }));
    const idInput = screen
      .getAllByLabelText<HTMLInputElement>("Dataset ID")
      .find((element) => element.value === readyDataset.dataset_id);
    if (!idInput) {
      throw new Error("Expected the dataset edit form to contain the selected dataset ID");
    }
    await user.clear(idInput);
    await user.type(idInput, "renamed");
    await user.click(screen.getByRole("button", { name: "Save changes" }));
    expect(update).toHaveBeenCalledWith("ds-1", expect.objectContaining({ dataset_id: "renamed" }));
  }, 10_000);

  it("converts cleared optional fields to null when saving edits", async () => {
    vi.spyOn(datasetsApi, "preview").mockResolvedValue({ fields: ["question", "answer"], rows: [] });
    const update = vi.spyOn(datasetsApi, "update").mockResolvedValue({ ...readyDataset });
    vi.spyOn(datasetsApi, "list").mockResolvedValue([readyDataset]);
    const { user } = await renderApp();
    await user.click(screen.getByRole("button", { name: "Edit" }));
    await user.click(screen.getByRole("button", { name: "Save changes" }));
    expect(update).toHaveBeenCalledWith("ds-1", expect.objectContaining({
      dataset_id: "demo",
      version: "1",
      revision: "default",
      source_url: null,
      checksum: "abc",
      credential_binding_id: null,
      license_text: null,
      input_field: "question",
      reference_field: "answer",
      capabilities: [],
      languages: [],
      evaluation_type: "custom",
    }));
  }, 10_000);

  it("restores metadata and uses prepared schema selectors while editing", async () => {
    const dataset: Dataset = {
      ...readyDataset,
      capabilities: ["reasoning"],
      languages: ["en"],
      evaluation_type: "classification",
    };
    const preview = vi.spyOn(datasetsApi, "preview").mockResolvedValue({
      fields: ["question", "prompt", "answer"],
      rows: [],
    });
    const update = vi.spyOn(datasetsApi, "update").mockResolvedValue(dataset);
    const { user } = await renderApp([dataset]);

    await user.click(screen.getByRole("button", { name: "Edit" }));
    await waitFor(() => expect(preview).toHaveBeenCalledWith("ds-1", 5));
    expect(screen.getByLabelText("Input field")).toHaveValue("question");
    expect(screen.getByLabelText("Reference (output) field")).toHaveValue("answer");
    expect(screen.getByRole("button", { name: "Remove capability reasoning" })).toBeVisible();
    expect(screen.getByRole("button", { name: "Remove language en" })).toBeVisible();

    await user.selectOptions(screen.getByLabelText("Reference (output) field"), "question");
    expect(screen.getByRole("alert")).toHaveTextContent("Input and reference fields must be different.");
    expect(screen.getByRole("button", { name: "Save changes" })).toBeDisabled();
    await user.selectOptions(screen.getByLabelText("Reference (output) field"), "answer");
    await user.selectOptions(screen.getByLabelText("Input field"), "prompt");
    await user.type(screen.getByLabelText("Capabilities"), "coding{Enter}");
    await user.type(screen.getByLabelText("Languages"), "ms{Enter}");
    await user.selectOptions(screen.getByLabelText("Evaluation type"), "generation");
    await user.click(screen.getByRole("button", { name: "Save changes" }));

    expect(update).toHaveBeenCalledWith("ds-1", expect.objectContaining({
      input_field: "prompt",
      reference_field: "answer",
      capabilities: ["reasoning", "coding"],
      languages: ["en", "ms"],
      evaluation_type: "generation",
    }));
  }, 10_000);

  it("keeps manual field inputs available for an unprepared dataset", async () => {
    const dataset = { ...readyDataset, status: "waiting", local_path: null };
    const preview = vi.spyOn(datasetsApi, "preview");
    const { user } = await renderApp([dataset]);

    await user.click(screen.getByRole("button", { name: "Edit" }));

    expect(screen.getByLabelText("Input field").tagName).toBe("INPUT");
    expect(screen.getByLabelText("Reference (output) field").tagName).toBe("INPUT");
    expect(preview).not.toHaveBeenCalled();
  }, 10_000);

  it("disables the preview button while the preview request is in flight", async () => {
    let resolvePreview!: () => void;
    const pending = new Promise<void>((resolve) => { resolvePreview = resolve; });
    vi.spyOn(datasetsApi, "preview").mockReturnValue(pending as never);
    const { user } = await renderApp();
    const button = screen.getByRole("button", { name: "Preview" }) as HTMLButtonElement;
    await user.click(button);
    expect(button.disabled).toBe(true);
    resolvePreview();
    await waitFor(() => expect(button.disabled).toBe(false));
  }, 10_000);

  it("deletes a dataset after confirmation", async () => {
    const remove = vi.spyOn(datasetsApi, "remove").mockResolvedValue({ ...readyDataset });
    vi.spyOn(window, "confirm").mockReturnValue(true);
    const { user } = await renderApp();
    await user.click(screen.getByRole("button", { name: "Delete" }));
    expect(remove).toHaveBeenCalledWith("ds-1");
  }, 10_000);

  it("disables the delete button while the delete request is in flight", async () => {
    let resolveDelete!: () => void;
    const pending = new Promise<void>((resolve) => { resolveDelete = resolve; });
    vi.spyOn(datasetsApi, "remove").mockReturnValue(pending as never);
    vi.spyOn(window, "confirm").mockReturnValue(true);
    const { user } = await renderApp();
    const button = screen.getByRole("button", { name: "Delete" }) as HTMLButtonElement;
    await user.click(button);
    expect(button.disabled).toBe(true);
    resolveDelete();
    await waitFor(() => expect(button.disabled).toBe(false));
  }, 10_000);

  it("hands a ready dataset to the Runs launcher without queueing automatically", async () => {
    vi.spyOn(datasetsApi, "preview").mockResolvedValue({
      fields: ["question", "answer"],
      rows: [{ question: "2+2?", answer: "4" }],
    });
    const createDatasetRun = vi.spyOn(runsApi, "createDataset");
    const { user } = await renderApp();

    await user.click(screen.getByRole("button", { name: "Start evaluation" }));

    expect(await screen.findByRole("heading", { level: 1, name: "Runs" })).toBeVisible();
    expect(window.location.pathname).toBe("/runs");
    expect(window.location.search).toBe("?tab=dataset-evaluation&dataset=ds-1");
    expect(screen.getByText(/Selected from the dataset catalog/)).toBeVisible();
    expect(screen.getByLabelText("Dataset")).toHaveValue(readyDataset.id);
    await waitFor(() => expect(screen.getByLabelText("Input field")).toHaveValue("question"));
    expect(screen.getByLabelText("Reference field")).toHaveValue("answer");
    expect(createDatasetRun).not.toHaveBeenCalled();
  }, 10_000);

  it("refreshes schema mapping when the same dataset is handed off again", async () => {
    const preview = vi.spyOn(datasetsApi, "preview").mockResolvedValue({
      fields: ["question", "answer"],
      rows: [],
    });
    const { user } = await renderApp();

    await user.click(screen.getByRole("link", { name: "Runs" }));
    await user.click(screen.getByRole("tab", { name: "Dataset evaluation" }));
    await user.selectOptions(screen.getByLabelText("Dataset"), readyDataset.id);
    await waitFor(() => expect(screen.getByLabelText("Input field")).toHaveValue("question"));
    await user.click(screen.getByRole("link", { name: "Datasets" }));
    await user.click(screen.getByRole("button", { name: "Start evaluation" }));

    await waitFor(() => expect(preview).toHaveBeenCalledTimes(2));
    expect(screen.getByLabelText("Input field")).toHaveValue("question");
    expect(screen.getByLabelText("Reference field")).toHaveValue("answer");
  }, 10_000);
});
