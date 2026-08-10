import type { View } from "../dashboard/navigation";

const iconPaths = {
  dashboard: "M4 4h6v6H4zM14 4h6v6h-6zM4 14h6v6H4zM14 14h6v6h-6z",
  guide: "M5 4h9a5 5 0 0 1 5 5v11H10a5 5 0 0 0-5-5z",
  models: "M12 3a4 4 0 1 0 0 8 4 4 0 0 0 0-8zM4 21a8 8 0 0 1 16 0",
  datasets: "M4 6c0-2 16-2 16 0s-16 2-16 0zm0 0v6c0 2 16 2 16 0V6m-16 6v6c0 2 16 2 16 0v-6",
  runs: "M8 5v14l11-7z",
  analysis: "M4 19V5m0 14h16M7 15l4-4 3 2 5-6",
  settings: "M12 8a4 4 0 1 0 0 8 4 4 0 0 0 0-8zM4 12h2m12 0h2M12 4v2m0 12v2M6.3 6.3l1.4 1.4m8.6 8.6 1.4 1.4m0-11.4-1.4 1.4m-8.6 8.6-1.4 1.4",
} satisfies Record<View, string>;

export function NavigationIcon({ view }: { view: View }) {
  return (
    <svg aria-hidden="true" data-navigation-icon={view} fill="none" stroke="currentColor" strokeLinecap="round" strokeLinejoin="round" strokeWidth="1.7" viewBox="0 0 24 24">
      <path d={iconPaths[view]} />
    </svg>
  );
}

export function MenuIcon() {
  return (
    <svg aria-hidden="true" fill="none" stroke="currentColor" strokeLinecap="round" strokeWidth="1.8" viewBox="0 0 24 24">
      <path d="M4 7h16M4 12h16M4 17h16" />
    </svg>
  );
}
