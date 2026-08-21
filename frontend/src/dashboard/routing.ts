import type { WorkspaceView } from "../i18n/catalog";

export const workspacePaths = {
  dashboard: "/dashboard",
  guide: "/guide",
  models: "/models",
  datasets: "/datasets",
  prompts: "/prompts",
  runs: "/runs",
  leaderboard: "/leaderboard",
  analysis: "/analysis",
  settings: "/settings",
} as const satisfies Record<WorkspaceView, `/${string}`>;

export const workspaceTabIds = {
  dashboard: ["summary", "evaluations", "readiness"],
  guide: ["getting-started", "prepare-data", "run-and-analyze"],
  models: ["model-inventory", "add-endpoint"],
  datasets: ["dataset-inventory", "register-dataset"],
  prompts: ["prompt-inventory", "new-prompt-package"],
  runs: ["run-inventory", "quick-start", "dataset-evaluation", "run-details"],
  leaderboard: ["rankings"],
  analysis: ["evidence-matrix", "compare-runs"],
  settings: ["health", "preferences"],
} as const satisfies Record<WorkspaceView, readonly string[]>;

export type WorkspaceTabFor<V extends WorkspaceView> = (typeof workspaceTabIds)[V][number];
export type WorkspaceTab = { [V in WorkspaceView]: WorkspaceTabFor<V> }[WorkspaceView];
export type WorkspaceNavigate = <V extends WorkspaceView>(
  view: V,
  options?: { datasetId?: string; replace?: boolean; runId?: string; tab?: WorkspaceTabFor<V> },
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
  options: { datasetId?: string; runId?: string } = {},
): string {
  const pathname = workspacePaths[view];
  const params = new URLSearchParams();
  if (tab !== defaultWorkspaceTab(view)) params.set("tab", tab);
  if (view === "runs" && tab === "dataset-evaluation" && validResourceId(options.datasetId)) params.set("dataset", options.datasetId);
  if (view === "runs" && tab === "run-details" && validRunId(options.runId)) params.set("run", options.runId);
  return params.size ? `${pathname}?${params.toString()}` : pathname;
}

function validRunId(value: string | null | undefined): value is string {
  return typeof value === "string" && /^[A-Za-z0-9_-]{1,200}$/.test(value);
}

function validResourceId(value: string | null | undefined): value is string {
  return typeof value === "string" && /^[A-Za-z0-9_-]{1,200}$/.test(value);
}

export function workspaceRoute(pathname: string, search = ""): WorkspaceRoute {
  const normalized = pathname === "/" ? "/" : pathname.replace(/\/+$/, "");
  const view: WorkspaceView = "dashboard";
  for (const [view, path] of Object.entries(workspacePaths) as Array<[WorkspaceView, `/${string}`]>) {
    if (normalized === path) {
      const normalizedSearch = search && !search.startsWith("?") ? `?${search}` : search;
      const rawRequestedTab = new URLSearchParams(normalizedSearch).get("tab");
      const requestedTab = view === "runs" && rawRequestedTab === "launch-evaluation"
        ? "quick-start"
        : rawRequestedTab;
      const tab = isWorkspaceTab(view, requestedTab) ? requestedTab : defaultWorkspaceTab(view);
      const requestedRunId = new URLSearchParams(normalizedSearch).get("run");
      const requestedDatasetId = new URLSearchParams(normalizedSearch).get("dataset");
      const canonicalSearch = workspacePath(view, tab, {
        datasetId: view === "runs" && tab === "dataset-evaluation" && validResourceId(requestedDatasetId) ? requestedDatasetId : undefined,
        runId: view === "runs" && tab === "run-details" && validRunId(requestedRunId) ? requestedRunId : undefined,
      }).slice(path.length);
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
