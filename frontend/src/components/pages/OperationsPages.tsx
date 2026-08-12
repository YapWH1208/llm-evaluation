import { ReactNode, useMemo, useState } from "react";

import { EvaluationRun } from "../../api";
import type { WorkspaceTabFor } from "../../dashboard/routing";
import { firstEvaluationCopy, workspacePageTabCopy } from "../../i18n/catalog";
import { useTranslation } from "../../i18n/LocaleProvider";
import { PageHeader } from "../workspace/PageHeader";
import { WorkspacePanel } from "../workspace/WorkspacePanel";
import { WorkspaceTabs, workspaceTabId, workspaceTabPanelId } from "../workspace/WorkspaceTabs";

type RunsPageProps = {
  activeTab: WorkspaceTabFor<"runs">;
  availableEndpointCount: number;
  configuredEndpointCount: number;
  datasetLauncher: ReactNode;
  datasetPreflight: ReactNode;
  inspector: ReactNode;
  onSelect: (runId: string) => void;
  onOpenModelSetup: (tab: WorkspaceTabFor<"models">) => void;
  onTabChange: (tab: WorkspaceTabFor<"runs">) => void;
  quickStartLauncher: ReactNode;
  quickStartPreflight: ReactNode;
  renderActions: (run: EvaluationRun) => ReactNode;
  runs: EvaluationRun[];
  selectedRunId: string | null;
};

export function RunInventory({ onSelect, renderActions, runs, selectedRunId }: Pick<RunsPageProps, "onSelect" | "renderActions" | "runs" | "selectedRunId">) {
  const { formatDate } = useTranslation();
  const [query, setQuery] = useState("");
  const [status, setStatus] = useState("all");
  const statuses = useMemo(() => Array.from(new Set(runs.map((run) => run.status))).sort(), [runs]);
  const visibleRuns = useMemo(() => runs.filter((run) => {
    const searchable = `${run.display_name} ${run.benchmark_id} ${run.benchmark_version} ${run.status} ${run.id}`.toLowerCase();
    return (status === "all" || run.status === status) && searchable.includes(query.trim().toLowerCase());
  }), [query, runs, status]);

  return <WorkspacePanel className="workspace-run-inventory" description="Select a snapshot to inspect lifecycle evidence and exportable artifacts." title="Run inventory" toolbar={<span className="workspace-count">{visibleRuns.length}/{runs.length} runs</span>}>
    <div className="workspace-operation-toolbar">
      <label className="workspace-filter-control">Find run<input aria-label="Find run" onChange={(event) => setQuery(event.target.value)} placeholder="Benchmark, status, or ID" value={query} /></label>
      <label className="workspace-filter-control">Run status<select aria-label="Run status" onChange={(event) => setStatus(event.target.value)} value={status}><option value="all">All states</option>{statuses.map((item) => <option key={item} value={item}>{item.replaceAll("_", " ")}</option>)}</select></label>
    </div>
    {runs.length === 0 ? <p className="empty">Verify a model endpoint to create the first run.</p> : visibleRuns.length === 0 ? <p className="empty">No runs match the current filters.</p> : <div className="workspace-run-list">{visibleRuns.map((run) => <article className={selectedRunId === run.id ? "workspace-run-row is-selected" : "workspace-run-row"} key={run.id}>
      <button aria-pressed={selectedRunId === run.id} className="workspace-run-summary" onClick={() => onSelect(run.id)} type="button"><strong data-i18n-preserve>{run.display_name || `${run.benchmark_id} v${run.benchmark_version}`}</strong><span><span data-i18n-preserve>{run.benchmark_id} v{run.benchmark_version}</span><span className={`badge ${run.status}`}>{run.status.replaceAll("_", " ")}</span>{run.completed_samples}/{run.total_samples} samples · {formatDate(run.created_at)}</span></button>
      <div className="workspace-run-actions">{renderActions(run)}</div>
    </article>)}</div>}
  </WorkspacePanel>;
}

export function RunsPage({ activeTab, availableEndpointCount, configuredEndpointCount, datasetLauncher, datasetPreflight, inspector, onOpenModelSetup, onSelect, onTabChange, quickStartLauncher, quickStartPreflight, renderActions, runs, selectedRunId }: RunsPageProps) {
  const { locale, t } = useTranslation();
  const copy = workspacePageTabCopy[locale].runs;
  const onboarding = firstEvaluationCopy[locale];
  const selectedVisible = runs.some((run) => run.id === selectedRunId);
  return <div className="workspace-page runs-page">
    <PageHeader description="Launch immutable evaluation snapshots, then inspect their operational and evidence trail." eyebrow="Operations" status={<>{runs.length} total runs</>} title="Runs" />
    <WorkspaceTabs ariaLabel="Runs sections" idPrefix="runs" onChange={onTabChange} tabs={[{ id: "run-inventory", label: copy.runInventory }, { id: "quick-start", label: copy.quickStart }, { id: "dataset-evaluation", label: copy.datasetEvaluation }, { id: "run-details", label: copy.runDetails }]} value={activeTab} />
    <div aria-labelledby={workspaceTabId("runs", activeTab)} id={workspaceTabPanelId("runs", activeTab)} role="tabpanel" tabIndex={0}>
      {activeTab === "run-inventory" && <RunInventory onSelect={onSelect} renderActions={renderActions} runs={runs} selectedRunId={selectedRunId} />}
      {activeTab === "quick-start" && <>{availableEndpointCount === 0 && <section className="workspace-prerequisite" role="status"><div><strong>{configuredEndpointCount === 0 ? onboarding.quickStartMissing : onboarding.quickStartNeedsTest}</strong><small>{onboarding.quickStartBlocked}</small></div><button onClick={() => onOpenModelSetup(configuredEndpointCount === 0 ? "add-endpoint" : "model-inventory")} type="button">{configuredEndpointCount === 0 ? onboarding.addEndpoint : onboarding.testConnection}</button></section>}<div className="workspace-run-launch-grid">
        <WorkspacePanel className="workspace-run-context" description={t("runLauncher.contextDescription")} title={t("runLauncher.contextTitle")}>{quickStartPreflight}</WorkspacePanel>
        <WorkspacePanel description={t("runLauncher.quickStartDescription")} title={t("runLauncher.quickStartTitle")}>{quickStartLauncher}</WorkspacePanel>
      </div></>}
      {activeTab === "dataset-evaluation" && <div className="workspace-run-launch-grid">
        <WorkspacePanel className="workspace-run-context" description={t("runLauncher.contextDescription")} title={t("runLauncher.contextTitle")}>{datasetPreflight}</WorkspacePanel>
        <WorkspacePanel description={t("runLauncher.datasetDescription")} title={t("datasetRun.title")}>{datasetLauncher}</WorkspacePanel>
      </div>}
      {activeTab === "run-details" && (selectedVisible ? <section className="workspace-run-detail" aria-label="Selected run inspector">{inspector}</section> : <WorkspacePanel className="workspace-run-detail-empty" description="Select a run from Run inventory to open its summary, evidence, and lifecycle history." title="Select a run" />)}
    </div>
  </div>;
}
