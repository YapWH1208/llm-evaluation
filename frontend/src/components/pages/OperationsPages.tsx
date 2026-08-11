import { ReactNode, useMemo, useState } from "react";

import { EvaluationRun } from "../../api";
import type { WorkspaceTabFor } from "../../dashboard/routing";
import { workspacePageTabCopy } from "../../i18n/catalog";
import { useTranslation } from "../../i18n/LocaleProvider";
import { PageHeader } from "../workspace/PageHeader";
import { WorkspacePanel } from "../workspace/WorkspacePanel";
import { WorkspaceTabs, workspaceTabId, workspaceTabPanelId } from "../workspace/WorkspaceTabs";

type RunsPageProps = {
  activeTab: WorkspaceTabFor<"runs">;
  inspector: ReactNode;
  launcher: ReactNode;
  onSelect: (runId: string) => void;
  onTabChange: (tab: WorkspaceTabFor<"runs">) => void;
  preflight: ReactNode;
  quickStartLauncher?: ReactNode;
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
    const searchable = `${run.benchmark_id} ${run.benchmark_version} ${run.status} ${run.id}`.toLowerCase();
    return (status === "all" || run.status === status) && searchable.includes(query.trim().toLowerCase());
  }), [query, runs, status]);

  return <WorkspacePanel className="workspace-run-inventory" description="Select a snapshot to inspect lifecycle evidence and exportable artifacts." title="Run inventory" toolbar={<span className="workspace-count">{visibleRuns.length}/{runs.length} runs</span>}>
    <div className="workspace-operation-toolbar">
      <label className="workspace-filter-control">Find run<input aria-label="Find run" onChange={(event) => setQuery(event.target.value)} placeholder="Benchmark, status, or ID" value={query} /></label>
      <label className="workspace-filter-control">Run status<select aria-label="Run status" onChange={(event) => setStatus(event.target.value)} value={status}><option value="all">All states</option>{statuses.map((item) => <option key={item} value={item}>{item.replaceAll("_", " ")}</option>)}</select></label>
    </div>
    {runs.length === 0 ? <p className="empty">Verify a model endpoint to create the first run.</p> : visibleRuns.length === 0 ? <p className="empty">No runs match the current filters.</p> : <div className="workspace-run-list">{visibleRuns.map((run) => <article className={selectedRunId === run.id ? "workspace-run-row is-selected" : "workspace-run-row"} key={run.id}>
      <button aria-pressed={selectedRunId === run.id} className="workspace-run-summary" onClick={() => onSelect(run.id)} type="button"><strong data-i18n-preserve>{run.benchmark_id} v{run.benchmark_version}</strong><span><span className={`badge ${run.status}`}>{run.status.replaceAll("_", " ")}</span>{run.completed_samples}/{run.total_samples} samples · {formatDate(run.created_at)}</span></button>
      <div className="workspace-run-actions">{renderActions(run)}</div>
    </article>)}</div>}
  </WorkspacePanel>;
}

export function RunsPage({ activeTab, inspector, launcher, onSelect, onTabChange, preflight, quickStartLauncher, renderActions, runs, selectedRunId }: RunsPageProps) {
  const { locale, t } = useTranslation();
  const copy = workspacePageTabCopy[locale].runs;
  const selectedVisible = runs.some((run) => run.id === selectedRunId);
  return <div className="workspace-page runs-page">
    <PageHeader description="Launch immutable evaluation snapshots, then inspect their operational and evidence trail." eyebrow="Operations" status={<>{runs.length} total runs</>} title="Runs" />
    <WorkspaceTabs ariaLabel="Runs sections" idPrefix="runs" onChange={onTabChange} tabs={[{ id: "run-inventory", label: copy.runInventory }, { id: "launch-evaluation", label: copy.launchEvaluation }, { id: "run-details", label: copy.runDetails }]} value={activeTab} />
    <div aria-labelledby={workspaceTabId("runs", activeTab)} id={workspaceTabPanelId("runs", activeTab)} role="tabpanel" tabIndex={0}>
      {activeTab === "run-inventory" && <RunInventory onSelect={onSelect} renderActions={renderActions} runs={runs} selectedRunId={selectedRunId} />}
      {activeTab === "launch-evaluation" && <>
        <WorkspacePanel className="workspace-run-context" description={t("runLauncher.contextDescription")} title={t("runLauncher.contextTitle")}>{preflight}</WorkspacePanel>
        <div className="workspace-run-launch-grid">
          {quickStartLauncher && <WorkspacePanel description={t("runLauncher.quickStartDescription")} title={t("runLauncher.quickStartTitle")}>{quickStartLauncher}</WorkspacePanel>}
          <WorkspacePanel description={t("runLauncher.datasetDescription")} title={t("datasetRun.title")}>{launcher}</WorkspacePanel>
        </div>
      </>}
      {activeTab === "run-details" && (selectedVisible ? <section className="workspace-run-detail" aria-label="Selected run inspector">{inspector}</section> : <WorkspacePanel className="workspace-run-detail-empty" description="Select a run from Run inventory to open its summary, evidence, and lifecycle history." title="Select a run" />)}
    </div>
  </div>;
}
