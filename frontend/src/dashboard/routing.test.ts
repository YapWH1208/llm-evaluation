import { describe, expect, it } from "vitest";

import { workspacePath, workspacePaths, workspaceRoute } from "./routing";

describe("workspace routing", () => {
  it("maps exactly the eight retained views to unique canonical paths", () => {
    expect(workspacePaths).toEqual({
      dashboard: "/dashboard",
      guide: "/guide",
      models: "/models",
      datasets: "/datasets",
      runs: "/runs",
      leaderboard: "/leaderboard",
      analysis: "/analysis",
      settings: "/settings",
    });
    expect(new Set(Object.values(workspacePaths)).size).toBe(8);
    for (const [view, pathname] of Object.entries(workspacePaths)) {
      expect(workspacePath(view as keyof typeof workspacePaths)).toBe(pathname);
      expect(workspaceRoute(pathname)).toEqual({
        view,
        tab: expect.any(String),
        pathname,
        search: "",
        replace: false,
      });
    }
  });

  it("canonicalizes root, trailing slashes, and unknown paths", () => {
    expect(workspaceRoute("/")).toEqual({ view: "dashboard", tab: "summary", pathname: "/dashboard", search: "", replace: true });
    expect(workspaceRoute("/models/")).toEqual({ view: "models", tab: "model-inventory", pathname: "/models", search: "", replace: true });
    expect(workspaceRoute("/not-a-page")).toEqual({ view: "dashboard", tab: "summary", pathname: "/dashboard", search: "", replace: true });
  });

  it("deep-links non-default tabs and leaves default tabs on bare paths", () => {
    expect(workspaceRoute("/models", "?tab=add-endpoint")).toEqual({
      view: "models",
      tab: "add-endpoint",
      pathname: "/models",
      search: "?tab=add-endpoint",
      replace: false,
    });
    expect(workspacePath("analysis", "compare-runs")).toBe("/analysis?tab=compare-runs");
    expect(workspacePath("analysis", "evidence-matrix")).toBe("/analysis");
  });

  it("canonicalizes the legacy combined run launcher to quick start", () => {
    expect(workspaceRoute("/runs", "?tab=launch-evaluation")).toEqual({
      view: "runs",
      tab: "quick-start",
      pathname: "/runs",
      search: "?tab=quick-start",
      replace: true,
    });
  });

  it("preserves a bounded run identity only on run-detail links", () => {
    expect(workspacePath("runs", "run-details", { runId: "run-1" })).toBe("/runs?tab=run-details&run=run-1");
    expect(workspaceRoute("/runs", "?tab=run-details&run=run-1")).toEqual({
      view: "runs",
      tab: "run-details",
      pathname: "/runs",
      search: "?tab=run-details&run=run-1",
      replace: false,
    });
    expect(workspaceRoute("/runs", "?tab=run-inventory&run=run-1").search).toBe("");
    expect(workspaceRoute("/leaderboard", "?run=run-1").search).toBe("");
  });

  it("falls back to the page default and canonicalizes unsupported tab text", () => {
    expect(workspaceRoute("/runs", "?tab=unknown&token=secret")).toEqual({
      view: "runs",
      tab: "run-inventory",
      pathname: "/runs",
      search: "",
      replace: true,
    });
    expect(workspaceRoute("/datasets", "?source=hf#register")).toEqual({
      view: "datasets",
      tab: "dataset-inventory",
      pathname: "/datasets",
      search: "",
      replace: true,
    });
  });
});
