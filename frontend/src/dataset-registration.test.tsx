import { cleanup, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import App from "./App";
import { api } from "./api";
import { LocaleProvider } from "./i18n/LocaleProvider";

afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
});

describe("dataset registration", () => {
  it("submits the administrator-configured credential binding with the dataset source", async () => {
    const user = userEvent.setup();
    vi.spyOn(api, "listEndpoints").mockResolvedValue([]);
    vi.spyOn(api, "listRuns").mockResolvedValue([]);
    vi.spyOn(api, "dashboard").mockResolvedValue(null as never);
    vi.spyOn(api, "listPromptPackages").mockResolvedValue([]);
    vi.spyOn(api, "listDatasets").mockResolvedValue([]);
    vi.spyOn(api, "listSuites").mockResolvedValue([]);
    vi.spyOn(api, "listBenchmarks").mockResolvedValue([]);
    vi.spyOn(api, "listTasks").mockResolvedValue([]);
    vi.spyOn(api, "analyticsMatrix").mockResolvedValue(null as never);
    vi.spyOn(api, "listUsers").mockResolvedValue([]);
    vi.spyOn(api, "listAuditEvents").mockResolvedValue([]);
    vi.spyOn(api, "systemHealth").mockResolvedValue(null as never);
    const createDataset = vi.spyOn(api, "createDataset").mockResolvedValue({} as never);

    render(<LocaleProvider><App /></LocaleProvider>);
    await user.click(screen.getByRole("button", { name: "Workspace" }));
    expect(screen.getByLabelText("Revision")).toHaveValue("main");
    await user.type(screen.getByLabelText("Dataset ID"), "private-corpus");
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
    });
  }, 10_000);

  it("submits optional input and reference field defaults", async () => {
    const user = userEvent.setup();
    vi.spyOn(api, "listEndpoints").mockResolvedValue([]);
    vi.spyOn(api, "listRuns").mockResolvedValue([]);
    vi.spyOn(api, "dashboard").mockResolvedValue(null as never);
    vi.spyOn(api, "listPromptPackages").mockResolvedValue([]);
    vi.spyOn(api, "listDatasets").mockResolvedValue([]);
    vi.spyOn(api, "listSuites").mockResolvedValue([]);
    vi.spyOn(api, "listBenchmarks").mockResolvedValue([]);
    vi.spyOn(api, "listTasks").mockResolvedValue([]);
    vi.spyOn(api, "analyticsMatrix").mockResolvedValue(null as never);
    vi.spyOn(api, "listUsers").mockResolvedValue([]);
    vi.spyOn(api, "listAuditEvents").mockResolvedValue([]);
    vi.spyOn(api, "systemHealth").mockResolvedValue(null as never);
    const createDataset = vi.spyOn(api, "createDataset").mockResolvedValue({} as never);

    render(<LocaleProvider><App /></LocaleProvider>);
    await user.click(screen.getByRole("button", { name: "Workspace" }));
    await user.type(screen.getByLabelText("Dataset ID"), "fields-demo");
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
