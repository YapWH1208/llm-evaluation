import type { NavigationGroupId, WorkspaceView } from "../i18n/catalog";

export type View = WorkspaceView;

export type NavigationItem = {
  view: View;
  glyph: string;
};

export type NavigationGroup = {
  id: NavigationGroupId;
  items: NavigationItem[];
};

export const navigationGroups: NavigationGroup[] = [
  { id: "overview", items: [{ view: "dashboard", glyph: "⌂" }, { view: "guide", glyph: "?" }] },
  { id: "configure", items: [
    { view: "models", glyph: "◌" }, { view: "capabilities", glyph: "✦" }, { view: "workspace", glyph: "◫" }, { view: "benchmarks", glyph: "▤" }, { view: "datasets", glyph: "▥" }, { view: "suites", glyph: "◷" },
  ] },
  { id: "operations", items: [{ view: "runs", glyph: "▶" }, { view: "queue", glyph: "≋" }, { view: "workers", glyph: "◉" }] },
  { id: "insights", items: [{ view: "analysis", glyph: "◒" }, { view: "compare", glyph: "⇄" }, { view: "reports", glyph: "▱" }, { view: "reviews", glyph: "✓" }] },
  { id: "system", items: [{ view: "users", glyph: "◍" }, { view: "settings", glyph: "⚙" }] },
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
