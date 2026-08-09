import { View } from "../dashboard/navigation";
import { PageHeader } from "./workspace/PageHeader";
import { WorkspacePanel } from "./workspace/WorkspacePanel";

const steps = [
  ["1. Add a model endpoint", "Models · configure the provider, run a connection test, and confirm it is available.", "models", "Open Models"],
  ["2. Register a dataset", "Datasets · declare the source and, optionally, the input and reference fields.", "datasets", "Open Datasets"],
  ["3. Download and verify", "Download the dataset and wait until its status is ready.", "datasets", "Review Datasets"],
  ["4. Create a prompt package", "Workspace · write the user template; record fields render through {{ placeholders }}.", "workspace", "Open Workspace"],
  ["5. Queue a dataset run", "Runs · pick the dataset, reference field, and endpoint, then queue the run.", "runs", "Open Runs"],
  ["6. Inspect evidence", "Open the run to review samples, scores, latency, cost, and errors.", "runs", "Inspect Runs"],
  ["7. Judge, review, and report", "Run blind pairwise judging, save human reviews, and generate reports.", "reviews", "Open Human review"],
] as const;

export function Guide({ onOpenView }: { onOpenView: (view: View) => void }) {
  return (
    <div className="workspace-page guide-page">
      <PageHeader description="Register a model endpoint and a dataset, then queue evaluation runs and inspect the evidence." eyebrow="Overview" status="7 steps" title="How to use this workspace" />
      <WorkspacePanel description="Each stage opens the existing workspace destination, so the guide remains an actionable path rather than a static checklist." title="Evaluation workflow">
        <ol className="workspace-timeline">
          {steps.map(([title, description, view, action]) => <li key={title}><div><h2>{title}</h2><p>{description}</p></div><button className="secondary" onClick={() => onOpenView(view)} type="button">{action}</button></li>)}
        </ol>
      </WorkspacePanel>
    </div>
  );
}
