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
  window.history.replaceState(null, "", "/");
});

describe("usage guide", () => {
  it("opens the guide from navigation and routes workflow steps to their workspace", async () => {
    const user = userEvent.setup();
    vi.spyOn(api, "listEndpoints").mockResolvedValue([]);
    vi.spyOn(api, "listRuns").mockResolvedValue([]);
    vi.spyOn(api, "dashboard").mockResolvedValue(null as never);
    vi.spyOn(api, "listPromptPackages").mockResolvedValue([]);
    vi.spyOn(api, "listDatasets").mockResolvedValue([]);
    vi.spyOn(api, "listBenchmarks").mockResolvedValue([]);
    vi.spyOn(api, "listTasks").mockResolvedValue([]);
    vi.spyOn(api, "analyticsMatrix").mockResolvedValue(null as never);
    vi.spyOn(api, "systemHealth").mockResolvedValue(null as never);

    render(<LocaleProvider><App /></LocaleProvider>);
    await user.click(screen.getByRole("link", { name: "Guide" }));
    expect(screen.getByRole("heading", { name: /How to use this workspace/i })).toBeTruthy();
    expect(screen.getByRole("tab", { name: "Getting started" })).toHaveAttribute("aria-selected", "true");
    expect(screen.getByText(/1\. Add a model endpoint/i)).toBeTruthy();
    await user.click(screen.getByRole("button", { name: "Open Models" }));
    expect(window.location.search).toBe("?tab=add-endpoint");
    expect(screen.getByLabelText("Base URL")).toBeTruthy();
  }, 10_000);

  it("direct-loads, navigates, and restores retained pages through browser history", async () => {
    const user = userEvent.setup();
    vi.spyOn(api, "listEndpoints").mockResolvedValue([]);
    vi.spyOn(api, "listRuns").mockResolvedValue([]);
    vi.spyOn(api, "dashboard").mockResolvedValue(null as never);
    vi.spyOn(api, "listPromptPackages").mockResolvedValue([]);
    vi.spyOn(api, "listDatasets").mockResolvedValue([]);
    vi.spyOn(api, "listBenchmarks").mockResolvedValue([]);
    vi.spyOn(api, "listTasks").mockResolvedValue([]);
    vi.spyOn(api, "analyticsMatrix").mockResolvedValue(null as never);
    vi.spyOn(api, "systemHealth").mockResolvedValue(null as never);
    vi.spyOn(api, "datasetDiskUsage").mockResolvedValue({ root: "/data", cache_bytes: 0, available_bytes: 1000, total_bytes: 2000 });
    window.history.replaceState(null, "", "/models");

    render(<LocaleProvider><App /></LocaleProvider>);

    expect(screen.getByRole("heading", { level: 1, name: "Models" })).toBeVisible();
    expect(screen.getByRole("link", { name: "Models" })).toHaveAttribute("aria-current", "page");
    await user.click(screen.getByRole("link", { name: "Datasets" }));
    expect(await screen.findByRole("heading", { level: 1, name: "Datasets" })).toBeVisible();
    expect(window.location.pathname).toBe("/datasets");
    expect(screen.getByRole("link", { name: "Datasets" })).toHaveAttribute("href", "/datasets");

    window.history.pushState(null, "", "/guide");
    window.dispatchEvent(new PopStateEvent("popstate"));

    expect(await screen.findByRole("heading", { level: 1, name: "How to use this workspace" })).toBeVisible();
  }, 10_000);

  it("keeps every workflow action inside the retained workspace", async () => {
    const user = userEvent.setup();
    const onOpenView = vi.fn();
    const { rerender } = render(<LocaleProvider><Guide activeTab="getting-started" onOpenView={onOpenView} onTabChange={vi.fn()} /></LocaleProvider>);

    for (const action of screen.getAllByRole("button")) await user.click(action);
    rerender(<LocaleProvider><Guide activeTab="prepare-data" onOpenView={onOpenView} onTabChange={vi.fn()} /></LocaleProvider>);
    for (const action of screen.getAllByRole("button").filter((button) => button.getAttribute("role") !== "tab")) await user.click(action);
    rerender(<LocaleProvider><Guide activeTab="run-and-analyze" onOpenView={onOpenView} onTabChange={vi.fn()} /></LocaleProvider>);
    for (const action of screen.getAllByRole("button").filter((button) => button.getAttribute("role") !== "tab")) await user.click(action);

    expect(onOpenView.mock.calls).toEqual([
      ["models", { tab: "add-endpoint" }],
      ["datasets", { tab: "register-dataset" }],
      ["datasets", { tab: "dataset-inventory" }],
      ["runs", { tab: "launch-evaluation" }],
      ["runs", { tab: "run-inventory" }],
      ["analysis", { tab: "evidence-matrix" }],
    ]);
    expect(screen.queryByText(/Workspace ·/)).not.toBeInTheDocument();
    expect(screen.queryByText(/Human review/)).not.toBeInTheDocument();
  });
});
