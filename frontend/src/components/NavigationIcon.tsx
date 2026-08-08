import type { View } from "../dashboard/navigation";

const iconPaths = {
  dashboard: "M4 4h6v6H4zM14 4h6v6h-6zM4 14h6v6H4zM14 14h6v6h-6z",
  guide: "M5 4h9a5 5 0 0 1 5 5v11H10a5 5 0 0 0-5-5z",
  models: "M12 3a4 4 0 1 0 0 8 4 4 0 0 0 0-8zM4 21a8 8 0 0 1 16 0",
  capabilities: "M12 3l1.8 5.2L19 10l-5.2 1.8L12 17l-1.8-5.2L5 10l5.2-1.8z",
  workspace: "M4 7h16v12H4zM7 7V4h10v3",
  benchmarks: "M5 19V9m7 10V5m7 14v-7",
  datasets: "M4 6c0-2 16-2 16 0s-16 2-16 0zm0 0v6c0 2 16 2 16 0V6m-16 6v6c0 2 16 2 16 0v-6",
  suites: "M5 5h14v14H5zM8 9h8M8 13h8M8 17h5",
  runs: "M8 5v14l11-7z",
  queue: "M5 7h14M5 12h14M5 17h14",
  workers: "M7 8a3 3 0 1 0 0-6 3 3 0 0 0 0 6zm10 0a3 3 0 1 0 0-6M2 21a5 5 0 0 1 10 0m0 0a5 5 0 0 1 10 0",
  analysis: "M4 19V5m0 14h16M7 15l4-4 3 2 5-6",
  compare: "M8 5H4v4M4 9l5-5m7 15h4v-4m0 0-5 5",
  reports: "M6 3h9l3 3v15H6zM9 11h6M9 15h6",
  reviews: "M5 4h14v16H5zM8 9l2 2 5-5M8 15h8",
  users: "M9 11a4 4 0 1 0 0-8 4 4 0 0 0 0 8zm7-1a3 3 0 1 0 0-6M2 21a7 7 0 0 1 14 0m0-7a6 6 0 0 1 6 6",
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
