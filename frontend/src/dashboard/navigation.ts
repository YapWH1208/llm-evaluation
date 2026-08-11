import type { NavigationGroupId, WorkspaceView } from "../i18n/catalog";

export type View = WorkspaceView;

export type NavigationItem = {
  view: View;
};

export type NavigationGroup = {
  id: NavigationGroupId;
  items: NavigationItem[];
};

export const navigationGroups: NavigationGroup[] = [
  { id: "overview", items: [{ view: "dashboard" }, { view: "guide" }] },
  { id: "configure", items: [{ view: "models" }, { view: "datasets" }] },
  { id: "operations", items: [{ view: "runs" }, { view: "leaderboard" }] },
  { id: "insights", items: [{ view: "analysis" }] },
  { id: "system", items: [{ view: "settings" }] },
];

export const navigationItems = navigationGroups.flatMap((group) => group.items);

export function navigationItem(view: View) {
  const item = navigationItems.find((candidate) => candidate.view === view);
  if (!item) throw new Error(`Unknown workspace view: ${view}`);
  return item;
}

export function navigationGroupFor(view: View) {
  const group = navigationGroups.find((candidate) => candidate.items.some((item) => item.view === view));
  if (!group) throw new Error(`Unknown workspace view: ${view}`);
  return group;
}
