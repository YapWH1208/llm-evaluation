import { cleanup, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import App from "./App";
import { analyticsApi } from "./features/analytics/api";
import { benchmarksApi } from "./features/benchmarks/api";
import { datasetsApi } from "./features/datasets/api";
import { endpointsApi } from "./features/endpoints/api";
import { runsApi } from "./features/runs/api";
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
    vi.spyOn(endpointsApi, "list").mockResolvedValue([]);
    vi.spyOn(runsApi, "list").mockResolvedValue([]);
    vi.spyOn(analyticsApi, "dashboard").mockResolvedValue(null as never);
    vi.spyOn(benchmarksApi, "listPrompts").mockResolvedValue([]);
    vi.spyOn(datasetsApi, "list").mockResolvedValue([]);
    vi.spyOn(benchmarksApi, "list").mockResolvedValue([]);
    vi.spyOn(analyticsApi, "listTasks").mockResolvedValue([]);
    vi.spyOn(analyticsApi, "matrix").mockResolvedValue(null as never);
    vi.spyOn(analyticsApi, "systemHealth").mockResolvedValue(null as never);

    render(<LocaleProvider><App /></LocaleProvider>);
    await user.click(screen.getByRole("link", { name: "Guide" }));
    expect(screen.getByRole("heading", { name: /How to use this workspace/i })).toBeTruthy();
    expect(screen.getByText(/1\. Add model endpoint/i)).toBeTruthy();
    await user.click(screen.getByRole("button", { name: "Open Models" }));
    expect(window.location.search).toBe("?tab=add-endpoint");
    expect(screen.getByLabelText("Base URL")).toBeTruthy();
  }, 10_000);

  it("direct-loads, navigates, and restores retained pages through browser history", async () => {
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
    vi.spyOn(datasetsApi, "diskUsage").mockResolvedValue({ root: "/data", cache_bytes: 0, available_bytes: 1000, total_bytes: 2000 });
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

  it("numbers the fastest-path steps presentationally without relying on translated prefixes", () => {
    render(<LocaleProvider><Guide onOpenView={vi.fn()} /></LocaleProvider>);

    expect(screen.getByRole("heading", { name: "1. Add model endpoint" })).toBeVisible();
    expect(screen.getByRole("heading", { name: "2. Test model connection" })).toBeVisible();
    expect(screen.getByRole("heading", { name: "3. Start Quick start" })).toBeVisible();
    expect(screen.getByRole("heading", { name: "4. Inspect the result" })).toBeVisible();
  });

  it("keeps every workflow action inside the retained workspace", async () => {
    const user = userEvent.setup();
    const onOpenView = vi.fn();
    render(<LocaleProvider><Guide onOpenView={onOpenView} /></LocaleProvider>);

    for (const action of screen.getAllByRole("button")) await user.click(action);

    expect(onOpenView.mock.calls).toEqual([
      ["models", { tab: "add-endpoint" }],
      ["models", { tab: "model-inventory" }],
      ["runs", { tab: "quick-start" }],
      ["runs", { tab: "run-inventory" }],
      ["datasets", { tab: "register-dataset" }],
      ["datasets", { tab: "dataset-inventory" }],
      ["runs", { tab: "dataset-evaluation" }],
      ["analysis", { tab: "evidence-matrix" }],
    ]);
    expect(screen.getByRole("heading", { name: "Fastest path to a first result" })).toBeVisible();
    expect(screen.getByRole("heading", { name: "Evaluate your own data" })).toBeVisible();
    expect(screen.queryByText(/Workspace ·/)).not.toBeInTheDocument();
    expect(screen.queryByText(/Human review/)).not.toBeInTheDocument();
  });
});
