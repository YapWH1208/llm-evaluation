import ApplicationWorkspace from "./components/ApplicationWorkspace";

/** Application entrypoint: the feature workspace owns feature state and effects. */
export default function App() {
  return <ApplicationWorkspace />;
}

export { ReportsTable, SharedReportPage } from "./components/ApplicationWorkspace";
