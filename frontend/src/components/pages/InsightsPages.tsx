import { FormEvent, useEffect, useState } from "react";

import { AnalyticsCell, AnalyticsMatrix, Comparison, EvaluationRun } from "../../api";
import { useTranslation } from "../../i18n/LocaleProvider";
import { PageHeader } from "../workspace/PageHeader";
import { WorkspacePanel } from "../workspace/WorkspacePanel";
import { WorkspaceTabs } from "../workspace/WorkspaceTabs";

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
  analytics: AnalyticsMatrix | null;
  completedRuns: EvaluationRun[];
  onSelectBaseline: (runId: string) => Promise<AnalyticsMatrix>;
};

export function AnalysisPage({ analytics, completedRuns, onSelectBaseline }: AnalysisPageProps) {
  const [matrix, setMatrix] = useState<AnalyticsMatrix | null>(analytics);
  const [baselineRunId, setBaselineRunId] = useState(analytics?.baseline_run_id ?? "");
  const [dimension, setDimension] = useState<AnalysisDimension>("model_benchmark");
  useEffect(() => { setMatrix(analytics); setBaselineRunId(analytics?.baseline_run_id ?? ""); }, [analytics]);

  const cells = matrix?.heatmaps[dimension] ?? [];
  const selectedDimension = analysisDimensions.find((item) => item.id === dimension) ?? analysisDimensions[0];

  return <div className="workspace-page analysis-page">
    <PageHeader description="Investigate supplied quality, reliability, latency, and cost evidence across evaluation dimensions." eyebrow="Insights" status={<>{matrix ? `${cells.length} ${selectedDimension.label.toLowerCase()} cells` : "Loading analysis"}</>} title="Analysis" />
    {!matrix ? <WorkspacePanel description="The analysis matrix is loading from the evaluation service." title="Analysis matrix"><p className="empty">Loading analysis matrix...</p></WorkspacePanel> : <>
      <WorkspacePanel className="workspace-analysis-context" description="The selected baseline applies to every evidence cell and delta shown below." title="Analysis context">
        <label className="workspace-filter-control">Baseline run<select onChange={(event) => { const runId = event.target.value; setBaselineRunId(runId); void onSelectBaseline(runId).then(setMatrix); }} value={baselineRunId}><option value="">No baseline</option>{completedRuns.map((run) => <option key={run.id} value={run.id}>{run.benchmark_id} · {run.id.slice(0, 8)}</option>)}</select></label>
      </WorkspacePanel>
      <WorkspaceTabs onChange={setDimension} tabs={analysisDimensions} value={dimension} />
      <div className="workspace-insights-grid">
        <CapabilityChart cells={matrix.capability_matrix} />
        <HeatmapBreakdown cells={cells} dimension={selectedDimension.label} />
      </div>
    </>}
  </div>;
}

export function CapabilityChart({ cells }: { cells: AnalyticsMatrix["capability_matrix"] }) {
  const { formatPercent: percent } = useTranslation();
  const entries = cells.filter((cell) => cell.accuracy !== null);
  const [selected, setSelected] = useState<string | null>(null);
  const height = Math.max(120, entries.length * 46 + 28);
  const active = entries.find((cell) => `${cell.model_endpoint_id}:${cell.capability}` === selected) ?? null;
  return <WorkspacePanel className="workspace-capability-chart" description="Click or use Enter on a bar to inspect the supplied model-capability result." title="Interactive capability chart" toolbar={<span className="workspace-count">{entries.length} scored cells</span>}>
    {entries.length === 0 ? <p className="empty">Complete a run to populate interactive score bars.</p> : <><div className="chart-scroll"><svg className="capability-chart" viewBox={`0 0 720 ${height}`} role="img" aria-label="Capability accuracy chart"><line x1="250" x2="670" y1="12" y2="12" className="chart-axis" />{entries.map((cell, index) => { const key = `${cell.model_endpoint_id}:${cell.capability}`; const score = cell.accuracy ?? 0; const y = 30 + index * 46; const isActive = key === selected; return <g key={key} className={isActive ? "chart-bar selected" : "chart-bar"} role="button" tabIndex={0} aria-pressed={isActive} aria-label={`${cell.model_endpoint_id} ${cell.capability}: ${percent(score)}`} onClick={() => setSelected(key)} onKeyDown={(event) => { if (event.key === "Enter" || event.key === " ") { event.preventDefault(); setSelected(key); } }}><title>{`${cell.model_endpoint_id} · ${cell.capability}: ${percent(score)}`}</title><text x="8" y={y + 17}>{cell.capability}</text><text x="242" y={y + 17} textAnchor="end">{cell.model_endpoint_id.slice(0, 8)}</text><rect x="250" y={y} width="420" height="26" rx="5" className="chart-track" /><rect x="250" y={y} width={Math.max(3, score * 420)} height="26" rx="5" className="chart-value" /><text x="680" y={y + 18}>{percent(score)}</text></g>; })}</svg></div>{active && <p className="muted" aria-live="polite">Selected {active.capability}: {percent(active.accuracy)} accuracy across {active.sample_count} samples, {percent(active.success_rate)} success, {percent(active.error_rate)} errors.</p>}</>}
  </WorkspacePanel>;
}

export function HeatmapBreakdown({ cells, dimension }: { cells: AnalyticsCell[]; dimension: string }) {
  const { formatCurrency: money, formatNumber: display, formatPercent: percent } = useTranslation();
  return <WorkspacePanel className="workspace-analysis-breakdown" description="Every row retains source counts, confidence interval, performance, reliability, latency, and cost context." title={`${dimension} breakdown`} toolbar={<span className="workspace-count">{cells.length} cells</span>}>
    {cells.length === 0 ? <p className="empty">Complete runs to populate this analysis.</p> : <div className="table-wrap workspace-dense-table"><table><thead><tr><th>Row</th><th>Column</th><th>Score</th><th>Samples / 95% CI</th><th>Baseline / Δ</th><th>Errors</th><th>Latency</th><th>Cost</th></tr></thead><tbody>{cells.map((cell) => <tr key={`${cell.x_key}-${cell.y_key}`}><td>{cell.x_label}</td><td>{cell.y_label}</td><td>{percent(cell.score)}</td><td>{cell.sample_count} · {cell.confidence_interval ? `${percent(cell.confidence_interval.lower)}–${percent(cell.confidence_interval.upper)}` : "--"}</td><td>{cell.baseline_score === null ? "--" : `${percent(cell.baseline_score)} / ${percent(cell.delta)}`}</td><td>{percent(cell.error_rate)}</td><td>{display(cell.average_latency_ms)} ms</td><td>{money(cell.estimated_cost, cell.currency)}</td></tr>)}</tbody></table></div>}
  </WorkspacePanel>;
}

type ComparePageProps = {
  busy: string | null;
  comparison: Comparison | null;
  completedRuns: EvaluationRun[];
  onRunAChange: (runId: string) => void;
  onRunBChange: (runId: string) => void;
  onSubmit: (event: FormEvent<HTMLFormElement>) => void;
  runA: string;
  runB: string;
};

export function ComparePage({ busy, comparison, completedRuns, onRunAChange, onRunBChange, onSubmit, runA, runB }: ComparePageProps) {
  const { formatDate } = useTranslation();
  return <div className="workspace-page compare-page">
    <PageHeader description="Compare two completed runs from the same benchmark version and retain the complete evidence trail." eyebrow="Insights" status={<>{completedRuns.length} completed runs</>} title="Compare runs" />
    <WorkspacePanel className="workspace-compare-sources" description="Choose two distinct completed snapshots. Differences are always calculated as Run A minus Run B." title="Comparison sources">
      <form className="workspace-compare-form" onSubmit={onSubmit}><label>Run A<select required onChange={(event) => onRunAChange(event.target.value)} value={runA}><option value="">Select completed run</option>{completedRuns.map((run) => <option key={run.id} value={run.id}>{run.benchmark_id} · {run.id.slice(0, 8)} · {formatDate(run.completed_at)}</option>)}</select></label><span aria-hidden="true" className="workspace-compare-versus">A / B</span><label>Run B<select required onChange={(event) => onRunBChange(event.target.value)} value={runB}><option value="">Select completed run</option>{completedRuns.map((run) => <option key={run.id} value={run.id}>{run.benchmark_id} · {run.id.slice(0, 8)} · {formatDate(run.completed_at)}</option>)}</select></label><button disabled={busy === "compare"} type="submit">{busy === "compare" ? "Comparing…" : "Compare runs"}</button></form>
    </WorkspacePanel>
    <ComparisonEvidence comparison={comparison} loading={busy === "compare"} />
  </div>;
}

export function ComparisonEvidence({ comparison, loading }: { comparison: Comparison | null; loading: boolean }) {
  const { formatNumber: display, formatPercent: percent } = useTranslation();
  if (!comparison) return <WorkspacePanel description="Select two source runs and compare them to expose shared-sample outcomes and metric deltas." title="Comparison evidence"><p className="empty">{loading ? "Comparing selected runs..." : "Choose two completed runs to begin an evidence-backed comparison."}</p></WorkspacePanel>;
  const metrics = [
    ["A-only correct", comparison.outcomes.run_a_only_correct, "sample outcomes"],
    ["B-only correct", comparison.outcomes.run_b_only_correct, "sample outcomes"],
    ["Latency difference", `${display(comparison.differences.average_latency_ms)} ms`, "A minus B"],
    ["Cost difference", display(comparison.differences.estimated_cost, 6), "A minus B"],
  ];
  return <WorkspacePanel className="workspace-comparison-evidence" description={<span data-i18n-preserve>{comparison.benchmark.id} v{comparison.benchmark.version} · {comparison.shared_samples} shared samples</span>} title="Comparison evidence">
    <div className="workspace-insight-metrics">{metrics.map(([label, value, detail]) => <article key={String(label)}><span>{label}</span><strong>{value}</strong><small>{detail}</small></article>)}</div>
    <div className="table-wrap workspace-dense-table"><table><thead><tr><th>Metric</th><th>Run A</th><th>Run B</th><th>A - B</th></tr></thead><tbody><tr><td>Accuracy</td><td>{percent(comparison.run_a_summary.samples.accuracy)}</td><td>{percent(comparison.run_b_summary.samples.accuracy)}</td><td>{percent(comparison.differences.accuracy)}</td></tr><tr><td>Success rate</td><td>{percent(comparison.run_a_summary.samples.success_rate)}</td><td>{percent(comparison.run_b_summary.samples.success_rate)}</td><td>{percent(comparison.differences.success_rate)}</td></tr><tr><td>P95 latency</td><td>{display(comparison.run_a_summary.latency_ms.p95)} ms</td><td>{display(comparison.run_b_summary.latency_ms.p95)} ms</td><td>{display(comparison.differences.p95_latency_ms)} ms</td></tr><tr><td>Output tokens</td><td>{display(comparison.run_a_summary.tokens.output)}</td><td>{display(comparison.run_b_summary.tokens.output)}</td><td>{display(comparison.differences.output_tokens)}</td></tr></tbody></table></div>
  </WorkspacePanel>;
}
