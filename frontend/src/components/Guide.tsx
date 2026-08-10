import { View } from "../dashboard/navigation";
import { PageHeader } from "./workspace/PageHeader";
import { WorkspacePanel } from "./workspace/WorkspacePanel";

const steps = [
  ["1. Add a model endpoint", "Models · configure the provider, run a connection test, and confirm it is available.", "models", "Open Models"],
  ["2. Register a dataset", "Datasets · declare the source and, optionally, the input and reference fields.", "datasets", "Open Datasets"],
  ["3. Download and verify", "Download the dataset and wait until its status is ready.", "datasets", "Review Datasets"],
  ["4. Queue a dataset run", "Runs · pick the dataset, evaluation metric, reference field, and endpoint, then queue the run.", "runs", "Open Runs"],
  ["5. Inspect evidence", "Runs · open the run to review samples, scores, latency, cost, and errors.", "runs", "Inspect Runs"],
  ["6. Analyze results", "Analysis · inspect evaluation dimensions or compare two completed runs.", "analysis", "Open Analysis"],
] as const;

export function Guide({ onOpenView }: { onOpenView: (view: View) => void }) {
  return (
    <div className="workspace-page guide-page">
      <PageHeader description="Register a model endpoint and a dataset, then queue evaluation runs and inspect the evidence." eyebrow="Overview" status="6 steps" title="How to use this workspace" />
      <WorkspacePanel description="Each stage opens an essential evaluation destination, so the guide remains an actionable path rather than a static checklist." title="Evaluation workflow">
        <ol className="workspace-timeline">
          {steps.map(([title, description, view, action]) => <li key={title}><div><h2>{title}</h2><p>{description}</p></div><button className="secondary" onClick={() => onOpenView(view)} type="button">{action}</button></li>)}
        </ol>
      </WorkspacePanel>
    </div>
  );
}
