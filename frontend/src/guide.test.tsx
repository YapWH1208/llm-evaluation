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

describe("usage guide", () => {
  it("opens the guide from navigation and shows the workflow steps", async () => {
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

    render(<LocaleProvider><App /></LocaleProvider>);
    await user.click(screen.getByRole("button", { name: "Guide" }));
    expect(screen.getByRole("heading", { name: /How to use this workspace/i })).toBeTruthy();
    expect(screen.getByText(/1\. Add a model endpoint/i)).toBeTruthy();
  }, 10_000);
});
