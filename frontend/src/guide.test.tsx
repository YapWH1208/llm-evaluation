import { cleanup, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import App from "./App";
import { api } from "./api";
import { Guide } from "./components/Guide";
import { LocaleProvider } from "./i18n/LocaleProvider";

afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
});

describe("usage guide", () => {
  it("opens the guide from navigation and routes workflow steps to their workspace", async () => {
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
    await user.click(screen.getByRole("button", { name: "Open Models" }));
    expect(screen.getByLabelText("Base URL")).toBeTruthy();
  }, 10_000);

  it("keeps every workflow action inside the retained workspace", async () => {
    const user = userEvent.setup();
    const onOpenView = vi.fn();
    render(<Guide onOpenView={onOpenView} />);

    for (const action of screen.getAllByRole("button")) await user.click(action);

    expect(onOpenView.mock.calls.map(([view]) => view)).toEqual([
      "models",
      "datasets",
      "datasets",
      "runs",
      "runs",
      "analysis",
    ]);
    expect(screen.queryByText(/Workspace ·/)).not.toBeInTheDocument();
    expect(screen.queryByText(/Human review/)).not.toBeInTheDocument();
  });
});
