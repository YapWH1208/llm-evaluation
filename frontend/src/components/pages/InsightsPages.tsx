import { FormEvent, useState } from "react";

import type { AnalyticsCell, AnalyticsMatrix, Comparison, ScatterQuery, ScatterResponse } from "../../features/analytics/api";
import type { Dataset } from "../../features/datasets/api";
import type { Endpoint } from "../../features/endpoints/api";
import type { EvaluationRun } from "../../features/runs/api";
import type { WorkspaceTabFor } from "../../dashboard/routing";
import { comparisonCopy, workspacePageTabCopy } from "../../i18n/catalog";
import { useTranslation } from "../../i18n/LocaleProvider";
import { PageHeader } from "../workspace/PageHeader";
import { WorkspacePanel } from "../workspace/WorkspacePanel";
import { WorkspaceTabs, workspaceTabId, workspaceTabPanelId } from "../workspace/WorkspaceTabs";
import { EvidenceScatterWorkspace } from "../analysis/EvidenceScatter";
import { ComparisonEvidence } from "../analysis/ComparisonCharts";

export { EvidenceScatterWorkspace } from "../analysis/EvidenceScatter";
export { ComparisonEvidence } from "../analysis/ComparisonCharts";

type AnalysisDimension = keyof AnalyticsMatrix["heatmaps"];

export const analysisDimensions: ReadonlyArray<{ id: AnalysisDimension; label: string }> = [
  { id: "model_benchmark", label: "Model × benchmark" },
  { id: "model_capability", label: "Model × capability" },
  { id: "model_language", label: "Model × language" },
  { id: "model_difficulty", label: "Model × difficulty" },
  { id: "prompt_benchmark", label: "Prompt × benchmark" },
  { id: "model_modality", label: "Model × modality" },
];

type AnalysisPageProps = {
  activeTab: WorkspaceTabFor<"analysis">;
  busy: string | null;
  comparison: Comparison | null;
  completedRuns: EvaluationRun[];
  datasets: Dataset[];
  endpoints: Endpoint[];
  loadScatter: (query: ScatterQuery) => Promise<ScatterResponse>;
  onRunAChange: (runId: string) => void;
  onRunBChange: (runId: string) => void;
  onSubmitComparison: (event: FormEvent<HTMLFormElement>) => void;
  onTabChange: (tab: WorkspaceTabFor<"analysis">) => void;
  runA: string;
  runB: string;
  runs: EvaluationRun[];
};

export function AnalysisPage({ activeTab, busy, comparison, completedRuns, datasets, endpoints, loadScatter, onRunAChange, onRunBChange, onSubmitComparison, onTabChange, runA, runB, runs }: AnalysisPageProps) {
  const { locale } = useTranslation();
  const copy = workspacePageTabCopy[locale].analysis;

  return <div className="workspace-page analysis-page">
    <PageHeader description="Investigate supplied quality, reliability, latency, cost, and run-to-run evidence." eyebrow="Insights" status={<>{activeTab === "compare-runs" ? `${completedRuns.length} completed runs` : `${runs.length} runs available`}</>} title="Analysis" />
    <WorkspaceTabs ariaLabel="Analysis sections" idPrefix="analysis" onChange={onTabChange} tabs={[{ id: "evidence-matrix", label: copy.evidenceMatrix }, { id: "compare-runs", label: copy.compareRuns }]} value={activeTab} />
    <div aria-labelledby={workspaceTabId("analysis", activeTab)} id={workspaceTabPanelId("analysis", activeTab)} role="tabpanel" tabIndex={0}>
    {activeTab === "compare-runs" ? <ComparisonWorkspace busy={busy} comparison={comparison} completedRuns={completedRuns} onRunAChange={onRunAChange} onRunBChange={onRunBChange} onSubmit={onSubmitComparison} runA={runA} runB={runB} /> : <EvidenceScatterWorkspace datasets={datasets} endpoints={endpoints} loadScatter={loadScatter} runs={runs} />}
    </div>
  </div>;
}

export function CapabilityChart({ cells }: { cells: AnalyticsMatrix["capability_matrix"] }) {
  const { formatPercent: percent } = useTranslation();
  const entries = cells.filter((cell) => cell.accuracy !== null);
  const [selected, setSelected] = useState<string | null>(null);
  const height = Math.max(120, entries.length * 46 + 28);
  const active = entries.find((cell) => `${cell.model_endpoint_id}:${cell.capability}` === selected) ?? null;
  return <WorkspacePanel className="workspace-capability-chart" description="Click or use Enter on a bar to inspect the supplied model-capability result." title="Interactive capability chart" toolbar={<span className="workspace-count">{entries.length} scored cells</span>}>
    {entries.length === 0 ? <p className="empty">Complete a run to populate interactive score bars.</p> : <><div className="chart-scroll"><svg className="capability-chart" viewBox={`0 0 720 ${height}`} role="img" aria-label="Capability score chart"><line x1="250" x2="670" y1="12" y2="12" className="chart-axis" />{entries.map((cell, index) => { const key = `${cell.model_endpoint_id}:${cell.capability}`; const score = cell.accuracy ?? 0; const y = 30 + index * 46; const isActive = key === selected; return <g key={key} className={isActive ? "chart-bar selected" : "chart-bar"} role="button" tabIndex={0} aria-pressed={isActive} aria-label={`${cell.model_endpoint_id} ${cell.capability}: ${percent(score)}`} onClick={() => setSelected(key)} onKeyDown={(event) => { if (event.key === "Enter" || event.key === " ") { event.preventDefault(); setSelected(key); } }}><title>{`${cell.model_endpoint_id} · ${cell.capability}: ${percent(score)}`}</title><text x="8" y={y + 17}>{cell.capability}</text><text x="242" y={y + 17} textAnchor="end">{cell.model_endpoint_id.slice(0, 8)}</text><rect x="250" y={y} width="420" height="26" rx="5" className="chart-track" /><rect x="250" y={y} width={Math.max(3, score * 420)} height="26" rx="5" className="chart-value" /><text x="680" y={y + 18}>{percent(score)}</text></g>; })}</svg></div>{active && <p className="muted" aria-live="polite">Selected {active.capability}: {percent(active.accuracy)} score across {active.sample_count} samples, {percent(active.success_rate)} success, {percent(active.error_rate)} errors.</p>}</>}
  </WorkspacePanel>;
}

export function HeatmapBreakdown({ cells, dimension }: { cells: AnalyticsCell[]; dimension: string }) {
  const { formatCurrency: money, formatNumber: display, formatPercent: percent } = useTranslation();
  return <WorkspacePanel className="workspace-analysis-breakdown" description="Every row retains source counts, confidence interval, performance, reliability, latency, and cost context." title={`${dimension} breakdown`} toolbar={<span className="workspace-count">{cells.length} cells</span>}>
    {cells.length === 0 ? <p className="empty">Complete runs to populate this analysis.</p> : <div className="table-wrap workspace-dense-table"><table><thead><tr><th>Row</th><th>Column</th><th>Score</th><th>Samples / 95% CI</th><th>Baseline / Δ</th><th>Errors</th><th>Latency</th><th>Cost</th></tr></thead><tbody>{cells.map((cell) => <tr key={`${cell.x_key}-${cell.y_key}`}><td>{cell.x_label}</td><td>{cell.y_label}</td><td>{percent(cell.score)}</td><td>{cell.sample_count} · {cell.confidence_interval ? `${percent(cell.confidence_interval.lower)}–${percent(cell.confidence_interval.upper)}` : "--"}</td><td>{cell.baseline_score === null ? "--" : `${percent(cell.baseline_score)} / ${percent(cell.delta)}`}</td><td>{percent(cell.error_rate)}</td><td>{display(cell.average_latency_ms)} ms</td><td>{money(cell.estimated_cost, cell.currency)}</td></tr>)}</tbody></table></div>}
  </WorkspacePanel>;
}

type ComparisonWorkspaceProps = {
  busy: string | null;
  comparison: Comparison | null;
  completedRuns: EvaluationRun[];
  onRunAChange: (runId: string) => void;
  onRunBChange: (runId: string) => void;
  onSubmit: (event: FormEvent<HTMLFormElement>) => void;
  runA: string;
  runB: string;
};


function ComparisonWorkspace({ busy, comparison, completedRuns, onRunAChange, onRunBChange, onSubmit, runA, runB }: ComparisonWorkspaceProps) {
  const { formatDate, locale } = useTranslation();
  const copy = comparisonCopy[locale];
  const selectedA = completedRuns.find((run) => run.id === runA);
  const selectedB = completedRuns.find((run) => run.id === runB);
  const issue = selectedA && selectedB
    ? selectedA.id === selectedB.id
      ? copy.sameRun
      : selectedA.benchmark_id !== selectedB.benchmark_id || selectedA.benchmark_version !== selectedB.benchmark_version
        ? copy.incompatible
        : null
    : null;
  const selectedComparison = comparison?.run_a === runA && comparison.run_b === runB ? comparison : null;
  const runLabel = (run: EvaluationRun) => `${run.display_name || `${run.benchmark_id} · ${run.id.slice(0, 8)}`} · ${formatDate(run.completed_at)}`;
  return <>
    <WorkspacePanel className="workspace-compare-sources" description={copy.sourcesDescription} title={copy.sourcesTitle}>
      <form className="workspace-compare-form" onSubmit={(event) => issue ? event.preventDefault() : onSubmit(event)}><label>{copy.runA}<select required onChange={(event) => onRunAChange(event.target.value)} value={runA}><option value="">{copy.selectCompleted}</option>{completedRuns.map((run) => <option data-i18n-preserve key={run.id} value={run.id}>{runLabel(run)}</option>)}</select></label><span aria-hidden="true" className="workspace-compare-versus">A / B</span><label>{copy.runB}<select required onChange={(event) => onRunBChange(event.target.value)} value={runB}><option value="">{copy.selectCompleted}</option>{completedRuns.map((run) => <option data-i18n-preserve key={run.id} value={run.id}>{runLabel(run)}</option>)}</select></label><button disabled={busy === "compare" || Boolean(issue) || !runA || !runB} type="submit">{busy === "compare" ? copy.comparing : copy.compare}</button></form>
      {issue && <p className="workspace-compare-error" role="alert">{issue}</p>}
    </WorkspacePanel>
    <ComparisonEvidence comparison={selectedComparison} loading={busy === "compare"} />
  </>;
}
