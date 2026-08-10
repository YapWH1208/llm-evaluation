import type { WorkspaceView } from "../i18n/catalog";

export const workspacePaths = {
  dashboard: "/dashboard",
  guide: "/guide",
  models: "/models",
  datasets: "/datasets",
  runs: "/runs",
  analysis: "/analysis",
  settings: "/settings",
} as const satisfies Record<WorkspaceView, `/${string}`>;

export function workspacePath(view: WorkspaceView): `/${string}` {
  return workspacePaths[view];
}

export function workspaceRoute(pathname: string): { view: WorkspaceView; pathname: `/${string}`; replace: boolean } {
  const normalized = pathname === "/" ? "/" : pathname.replace(/\/+$/, "");
  for (const [view, path] of Object.entries(workspacePaths) as Array<[WorkspaceView, `/${string}`]>) {
    if (normalized === path) return { view, pathname: path, replace: pathname !== path };
  }
  return { view: "dashboard", pathname: workspacePaths.dashboard, replace: true };
}
