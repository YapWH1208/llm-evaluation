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

describe("dataset evaluation run", () => {
  it("queues a run with the chosen dataset, reference field, and endpoint", async () => {
    const user = userEvent.setup();
    vi.spyOn(api, "listEndpoints").mockResolvedValue([{ id: "ep-1", display_name: "Test model", status: "available" }] as never);
    vi.spyOn(api, "listRuns").mockResolvedValue([]);
    vi.spyOn(api, "dashboard").mockResolvedValue(null as never);
    vi.spyOn(api, "listPromptPackages").mockResolvedValue([]);
    vi.spyOn(api, "listDatasets").mockResolvedValue([{ id: "ds-1", dataset_id: "demo", version: "1", status: "ready" }] as never);
    vi.spyOn(api, "listSuites").mockResolvedValue([]);
    vi.spyOn(api, "listBenchmarks").mockResolvedValue([]);
    vi.spyOn(api, "listTasks").mockResolvedValue([]);
    vi.spyOn(api, "analyticsMatrix").mockResolvedValue(null as never);
    vi.spyOn(api, "listUsers").mockResolvedValue([]);
    vi.spyOn(api, "listAuditEvents").mockResolvedValue([]);
    vi.spyOn(api, "systemHealth").mockResolvedValue(null as never);
    const createDatasetRun = vi.spyOn(api, "createDatasetRun").mockResolvedValue({ id: "run-1", benchmark_id: "dataset-evaluation", total_samples: 1, status: "queued" } as never);

    render(<LocaleProvider><App /></LocaleProvider>);
    await user.click(screen.getByRole("button", { name: "Runs" }));
    await user.selectOptions(screen.getByLabelText("Dataset"), "ds-1");
    await user.type(screen.getByLabelText("Reference field"), "answer");
    await user.selectOptions(screen.getByLabelText("Endpoint"), "ep-1");
    await user.click(screen.getByRole("button", { name: "Queue dataset run" }));

    expect(createDatasetRun).toHaveBeenCalledWith({
      model_endpoint_id: "ep-1",
      dataset_version_id: "ds-1",
      prompt_package_id: null,
      reference_field: "answer",
      sample_limit: 100,
    });
  }, 10_000);
});
