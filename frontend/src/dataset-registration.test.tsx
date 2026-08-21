import { cleanup, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import App from "./App";
import { analyticsApi } from "./features/analytics/api";
import { benchmarksApi } from "./features/benchmarks/api";
import { datasetsApi } from "./features/datasets/api";
import { endpointsApi } from "./features/endpoints/api";
import { runsApi } from "./features/runs/api";
import { LocaleProvider } from "./i18n/LocaleProvider";

afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
  window.history.replaceState(null, "", "/dashboard");
});

describe("dataset registration", () => {
  it("submits the administrator-configured credential binding with the dataset source", async () => {
    const user = userEvent.setup();
    vi.spyOn(endpointsApi, "list").mockResolvedValue([]);
    vi.spyOn(runsApi, "list").mockResolvedValue([]);
    vi.spyOn(analyticsApi, "dashboard").mockResolvedValue(null as never);
    vi.spyOn(benchmarksApi, "listPrompts").mockResolvedValue([]);
    vi.spyOn(datasetsApi, "list").mockResolvedValue([]);
    vi.spyOn(benchmarksApi, "list").mockResolvedValue([]);
    vi.spyOn(analyticsApi, "listTasks").mockResolvedValue([]);
    vi.spyOn(analyticsApi, "matrix").mockResolvedValue(null as never);
    vi.spyOn(analyticsApi, "systemHealth").mockResolvedValue(null as never);
    const createDataset = vi.spyOn(datasetsApi, "create").mockResolvedValue({} as never);

    render(<LocaleProvider><App /></LocaleProvider>);
    await user.click(screen.getByRole("link", { name: "Datasets" }));
    await user.click(screen.getByRole("tab", { name: "Register dataset" }));
    expect(screen.getByLabelText("Revision")).toHaveValue("main");
    await user.type(screen.getByLabelText("Dataset ID"), "private-corpus");
    await user.click(screen.getByText("Advanced settings (optional)"));
    await user.type(screen.getByLabelText("Source HTTPS URL"), "https://datasets.example.test/corpus.jsonl");
    await user.type(screen.getByLabelText("Credential binding ID"), "private-dataset");
    await user.click(screen.getByRole("button", { name: "Register dataset" }));

    expect(createDataset).toHaveBeenCalledWith({
      dataset_id: "private-corpus",
      version: "1",
      revision: "main",
      source_url: "https://datasets.example.test/corpus.jsonl",
      checksum: null,
      credential_binding_id: "private-dataset",
      license_text: null,
      input_field: null,
      reference_field: null,
      capabilities: [],
      languages: [],
      evaluation_type: "custom",
    });
  }, 10_000);

  it("submits capability, language, and evaluation metadata from multi-select controls", async () => {
    const user = userEvent.setup();
    vi.spyOn(endpointsApi, "list").mockResolvedValue([]);
    vi.spyOn(runsApi, "list").mockResolvedValue([]);
    vi.spyOn(analyticsApi, "dashboard").mockResolvedValue(null as never);
    vi.spyOn(benchmarksApi, "listPrompts").mockResolvedValue([]);
    vi.spyOn(datasetsApi, "list").mockResolvedValue([]);
    vi.spyOn(benchmarksApi, "list").mockResolvedValue([]);
    vi.spyOn(analyticsApi, "listTasks").mockResolvedValue([]);
    vi.spyOn(analyticsApi, "matrix").mockResolvedValue(null as never);
    vi.spyOn(analyticsApi, "systemHealth").mockResolvedValue(null as never);
    const createDataset = vi.spyOn(datasetsApi, "create").mockResolvedValue({} as never);

    render(<LocaleProvider><App /></LocaleProvider>);
    await user.click(screen.getByRole("link", { name: "Datasets" }));
    await user.click(screen.getByRole("tab", { name: "Register dataset" }));
    await user.type(screen.getByLabelText("Dataset ID"), "metadata-demo");
    await user.click(screen.getByText("Advanced settings (optional)"));
    await user.type(screen.getByLabelText("Capabilities"), "reasoning{Enter}coding{Enter}");
    await user.type(screen.getByLabelText("Languages"), "en{Enter}ms{Enter}");
    await user.type(screen.getByLabelText("Languages"), "{Backspace}");
    expect(screen.queryByRole("button", { name: "Remove language ms" })).not.toBeInTheDocument();
    await user.type(screen.getByLabelText("Languages"), "ms{Enter}");
    await user.selectOptions(screen.getByLabelText("Evaluation type"), "classification");

    expect(screen.getByRole("button", { name: "Remove capability reasoning" })).toBeVisible();
    await user.click(screen.getByRole("button", { name: "Remove capability coding" }));
    await user.click(screen.getByRole("button", { name: "Register dataset" }));

    expect(createDataset).toHaveBeenCalledWith(expect.objectContaining({
      capabilities: ["reasoning"],
      languages: ["en", "ms"],
      evaluation_type: "classification",
    }));
  }, 10_000);

  it("submits optional input and reference field defaults", async () => {
    const user = userEvent.setup();
    vi.spyOn(endpointsApi, "list").mockResolvedValue([]);
    vi.spyOn(runsApi, "list").mockResolvedValue([]);
    vi.spyOn(analyticsApi, "dashboard").mockResolvedValue(null as never);
    vi.spyOn(benchmarksApi, "listPrompts").mockResolvedValue([]);
    vi.spyOn(datasetsApi, "list").mockResolvedValue([]);
    vi.spyOn(benchmarksApi, "list").mockResolvedValue([]);
    vi.spyOn(analyticsApi, "listTasks").mockResolvedValue([]);
    vi.spyOn(analyticsApi, "matrix").mockResolvedValue(null as never);
    vi.spyOn(analyticsApi, "systemHealth").mockResolvedValue(null as never);
    const createDataset = vi.spyOn(datasetsApi, "create").mockResolvedValue({} as never);

    render(<LocaleProvider><App /></LocaleProvider>);
    await user.click(screen.getByRole("link", { name: "Datasets" }));
    await user.click(screen.getByRole("tab", { name: "Register dataset" }));
    await user.type(screen.getByLabelText("Dataset ID"), "fields-demo");
    await user.click(screen.getByText("Advanced settings (optional)"));
    await user.type(screen.getByLabelText("Input field"), "question");
    await user.type(screen.getByLabelText("Reference (output) field"), "answer");
    await user.click(screen.getByRole("button", { name: "Register dataset" }));

    expect(createDataset).toHaveBeenCalledWith(expect.objectContaining({
      dataset_id: "fields-demo",
      input_field: "question",
      reference_field: "answer",
    }));
  }, 10_000);
});
