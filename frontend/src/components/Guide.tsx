import type { WorkspaceNavigate } from "../dashboard/routing";
import { firstEvaluationCopy, guideCopy } from "../i18n/catalog";
import { useTranslation } from "../i18n/LocaleProvider";
import { PageHeader } from "./workspace/PageHeader";
import { WorkspacePanel } from "./workspace/WorkspacePanel";

type GuideProps = {
  onOpenView: WorkspaceNavigate;
};

export function Guide({ onOpenView }: GuideProps) {
  const { locale } = useTranslation();
  const copy = guideCopy[locale];
  const onboarding = firstEvaluationCopy[locale];
  const fastestSteps = [
    { title: `1. ${onboarding.addEndpoint}`, description: copy.addDescription, action: copy.openModels, open: (navigate: WorkspaceNavigate) => navigate("models", { tab: "add-endpoint" }) },
    { title: `2. ${onboarding.testConnection}`, description: copy.testDescription, action: copy.reviewModels, open: (navigate: WorkspaceNavigate) => navigate("models", { tab: "model-inventory" }) },
    { title: `3. ${onboarding.startQuickStart}`, description: copy.quickDescription, action: copy.openQuickStart, open: (navigate: WorkspaceNavigate) => navigate("runs", { tab: "quick-start" }) },
    { title: `4. ${onboarding.inspectStep}`, description: copy.inspectDescription, action: copy.inspectRuns, open: (navigate: WorkspaceNavigate) => navigate("runs", { tab: "run-inventory" }) },
  ];
  const datasetSteps = [
    { title: `1. ${copy.datasetTitle}`, description: copy.datasetDescription, action: copy.openDatasets, open: (navigate: WorkspaceNavigate) => navigate("datasets", { tab: "register-dataset" }) },
    { title: `2. ${copy.prepareTitle}`, description: copy.prepareDescription, action: copy.reviewDatasets, open: (navigate: WorkspaceNavigate) => navigate("datasets", { tab: "dataset-inventory" }) },
    { title: `3. ${copy.datasetRunTitle}`, description: copy.datasetRunDescription, action: copy.openDatasetRun, open: (navigate: WorkspaceNavigate) => navigate("runs", { tab: "dataset-evaluation" }) },
    { title: `4. ${copy.analyzeTitle}`, description: copy.analyzeDescription, action: copy.openAnalysis, open: (navigate: WorkspaceNavigate) => navigate("analysis", { tab: "evidence-matrix" }) },
  ];
  const timeline = (steps: typeof fastestSteps) => <ol className="workspace-timeline">{steps.map(({ title, description, action, open }) => <li key={title}><div><h2>{title}</h2><p>{description}</p></div><button className="secondary" onClick={() => open(onOpenView)} type="button">{action}</button></li>)}</ol>;
  return (
    <div className="workspace-page guide-page">
      <PageHeader description={copy.pageDescription} eyebrow="Overview" status={copy.status} title="How to use this workspace" />
      <div role="tabpanel" tabIndex={0}>
        <WorkspacePanel description={copy.fastDescription} title={copy.fastTitle}>{timeline(fastestSteps)}</WorkspacePanel>
        <WorkspacePanel description={copy.customDescription} title={copy.customTitle}>{timeline(datasetSteps)}</WorkspacePanel>
      </div>
    </div>
  );
}
