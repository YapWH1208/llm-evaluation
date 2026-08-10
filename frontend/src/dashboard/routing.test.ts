import { describe, expect, it } from "vitest";

import { workspacePath, workspacePaths, workspaceRoute } from "./routing";

describe("workspace routing", () => {
  it("maps exactly the seven retained views to unique canonical paths", () => {
    expect(workspacePaths).toEqual({
      dashboard: "/dashboard",
      guide: "/guide",
      models: "/models",
      datasets: "/datasets",
      runs: "/runs",
      analysis: "/analysis",
      settings: "/settings",
    });
    expect(new Set(Object.values(workspacePaths)).size).toBe(7);
    for (const [view, pathname] of Object.entries(workspacePaths)) {
      expect(workspacePath(view as keyof typeof workspacePaths)).toBe(pathname);
      expect(workspaceRoute(pathname)).toEqual({ view, pathname, replace: false });
    }
  });

  it("canonicalizes root, trailing slashes, and unknown paths", () => {
    expect(workspaceRoute("/")).toEqual({ view: "dashboard", pathname: "/dashboard", replace: true });
    expect(workspaceRoute("/models/")).toEqual({ view: "models", pathname: "/models", replace: true });
    expect(workspaceRoute("/not-a-page")).toEqual({ view: "dashboard", pathname: "/dashboard", replace: true });
  });

  it("uses only the pathname and remains independent of query and hash text", () => {
    expect(workspaceRoute(new URL("https://example.test/datasets?source=hf#register").pathname)).toEqual({
      view: "datasets",
      pathname: "/datasets",
      replace: false,
    });
  });
});
