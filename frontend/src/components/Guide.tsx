import type { WorkspaceNavigate, WorkspaceTabFor } from "../dashboard/routing";
import { PageHeader } from "./workspace/PageHeader";
import { WorkspacePanel } from "./workspace/WorkspacePanel";

const steps = [
  { title: "1. Add a model endpoint", description: "Models · configure the provider, run a connection test, and confirm it is available.", action: "Open Models", open: (navigate: WorkspaceNavigate) => navigate("models", { tab: "add-endpoint" }) },
  { title: "2. Register a dataset", description: "Datasets · declare the source and, optionally, the input and reference fields.", action: "Open Datasets", open: (navigate: WorkspaceNavigate) => navigate("datasets", { tab: "register-dataset" }) },
  { title: "3. Download and verify", description: "Download the dataset and wait until its status is ready.", action: "Review Datasets", open: (navigate: WorkspaceNavigate) => navigate("datasets", { tab: "dataset-inventory" }) },
  { title: "4. Queue a dataset run", description: "Runs · pick the dataset, evaluation metric, reference field, and endpoint, then queue the run.", action: "Open Runs", open: (navigate: WorkspaceNavigate) => navigate("runs", { tab: "dataset-evaluation" }) },
  { title: "5. Inspect evidence", description: "Runs · open the run to review samples, scores, latency, cost, and errors.", action: "Inspect Runs", open: (navigate: WorkspaceNavigate) => navigate("runs", { tab: "run-inventory" }) },
  { title: "6. Analyze results", description: "Analysis · inspect evaluation dimensions or compare two completed runs.", action: "Open Analysis", open: (navigate: WorkspaceNavigate) => navigate("analysis", { tab: "evidence-matrix" }) },
] as const;

type GuideProps = {
  activeTab: WorkspaceTabFor<"guide">;
  onOpenView: WorkspaceNavigate;
  onTabChange: (tab: WorkspaceTabFor<"guide">) => void;
};

export function Guide({ onOpenView }: GuideProps) {
  return (
    <div className="workspace-page guide-page">
      <PageHeader description="Register a model endpoint and a dataset, then queue evaluation runs and inspect the evidence." eyebrow="Overview" status="6 steps" title="How to use this workspace" />
      <div role="tabpanel" tabIndex={0}>
        <WorkspacePanel description="Each stage opens an essential evaluation destination, so the guide remains an actionable path rather than a static checklist." title="Evaluation workflow">
          <ol className="workspace-timeline">
            {steps.map(({ title, description, action, open }) => (
              <li key={title}>
                <div>
                  <h2>{title}</h2>
                  <p>{description}</p>
                </div>
                <button className="secondary" onClick={() => open(onOpenView)} type="button">
                  {action}
                </button>
              </li>
            ))}
          </ol>
        </WorkspacePanel>
      </div>
    </div>
  );
}
