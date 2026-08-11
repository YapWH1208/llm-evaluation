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

export const workspaceTabIds = {
  dashboard: ["summary", "evaluations", "readiness"],
  guide: ["getting-started", "prepare-data", "run-and-analyze"],
  models: ["model-inventory", "add-endpoint"],
  datasets: ["dataset-inventory", "register-dataset"],
  runs: ["run-inventory", "quick-start", "dataset-evaluation", "run-details"],
  analysis: ["evidence-matrix", "compare-runs"],
  settings: ["health", "access", "preferences"],
} as const satisfies Record<WorkspaceView, readonly string[]>;

export type WorkspaceTabFor<V extends WorkspaceView> = (typeof workspaceTabIds)[V][number];
export type WorkspaceTab = { [V in WorkspaceView]: WorkspaceTabFor<V> }[WorkspaceView];
export type WorkspaceNavigate = <V extends WorkspaceView>(
  view: V,
  options?: { replace?: boolean; tab?: WorkspaceTabFor<V> },
) => void;

export type WorkspaceRoute = {
  pathname: `/${string}`;
  replace: boolean;
  search: string;
  tab: WorkspaceTab;
  view: WorkspaceView;
};

export function defaultWorkspaceTab<V extends WorkspaceView>(view: V): WorkspaceTabFor<V> {
  return workspaceTabIds[view][0] as WorkspaceTabFor<V>;
}

function isWorkspaceTab<V extends WorkspaceView>(view: V, value: string | null): value is WorkspaceTabFor<V> {
  return value !== null && (workspaceTabIds[view] as readonly string[]).includes(value);
}

export function workspacePath<V extends WorkspaceView>(
  view: V,
  tab: WorkspaceTabFor<V> = defaultWorkspaceTab(view),
): string {
  const pathname = workspacePaths[view];
  return tab === defaultWorkspaceTab(view) ? pathname : `${pathname}?tab=${encodeURIComponent(tab)}`;
}

export function workspaceRoute(pathname: string, search = ""): WorkspaceRoute {
  const normalized = pathname === "/" ? "/" : pathname.replace(/\/+$/, "");
  let view: WorkspaceView = "dashboard";
  for (const [view, path] of Object.entries(workspacePaths) as Array<[WorkspaceView, `/${string}`]>) {
    if (normalized === path) {
      const normalizedSearch = search && !search.startsWith("?") ? `?${search}` : search;
      const rawRequestedTab = new URLSearchParams(normalizedSearch).get("tab");
      const requestedTab = view === "runs" && rawRequestedTab === "launch-evaluation"
        ? "quick-start"
        : rawRequestedTab;
      const tab = isWorkspaceTab(view, requestedTab) ? requestedTab : defaultWorkspaceTab(view);
      const canonicalSearch = tab === defaultWorkspaceTab(view) ? "" : `?tab=${encodeURIComponent(tab)}`;
      return {
        view,
        tab,
        pathname: path,
        search: canonicalSearch,
        replace: pathname !== path || normalizedSearch !== canonicalSearch,
      };
    }
  }

  return {
    view,
    tab: defaultWorkspaceTab(view),
    pathname: workspacePaths.dashboard,
    search: "",
    replace: true,
  };
}
