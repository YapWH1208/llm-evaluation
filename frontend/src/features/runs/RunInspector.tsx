import type { FormEvent, ReactNode } from "react";

import { RunDetailWorkspace } from "../../components/runs/RunDetailWorkspace";
import { datasetMetricLabelKeys } from "../../components/runs/DatasetRunLauncher";
import type { DatasetMetricId } from "../../evaluations/scoringMetrics";
import { useTranslation } from "../../i18n/LocaleProvider";
import { ReportsTable } from "../reports/ReportsTable";
import type { Report, ReportFormat } from "../reports/api";
import type { JudgeAssessment, JudgeAgreement, Review, ReviewAgreement } from "../reviews/api";
import type { Endpoint } from "../endpoints/api";
import type { AggregateMetric, EvaluationRun, RunLogEntry, RunSummary, SampleAttempt } from "./api";
import { EvidenceBrowser } from "./EvidenceBrowser";
import "../../evidence.css";

export type JudgeForm = { endpoint_id: string; rubric: string; comparison_attempt_id: string; swap_test: boolean };
export type ReviewForm = { reviewer_id: string; rubric: string; score: string; labels: string; notes: string; review_stage: "primary" | "secondary" | "adjudication" };

type RunInspectorProps = {
  actions: ReactNode;
  attempts: SampleAttempt[];
  busy: string | null;
  endpoints: Endpoint[];
  judgeAgreement: JudgeAgreement | null;
  judgeAssessments: JudgeAssessment[];
  judgeForm: JudgeForm;
  logs: RunLogEntry[];
  metrics: AggregateMetric[];
  onCreateJudgeAssessment: (event: FormEvent) => void;
  onCreateReview: (event: FormEvent) => void;
  onDeleteReport: (report: Report) => void;
  onGenerateReport: (runId: string, format: ReportFormat) => void;
  onJudgeForm: (value: JudgeForm) => void;
  onLoadMoreAttempts: () => Promise<void>;
  onReview: (attempt: SampleAttempt) => void;
  onReviewForm: (value: ReviewForm) => void;
  reports: Report[];
  reviewAgreement: ReviewAgreement | null;
  reviewForm: ReviewForm;
  reviews: Review[];
  run: EvaluationRun;
  selectedAttempt: SampleAttempt | null;
  summary: RunSummary | null;
};

export function RunInspector(props: RunInspectorProps) {
  const { formatDate, formatNumber, formatPercent, t } = useTranslation();
  const runRule = props.run.configuration_snapshot?.scoring_rule;
  const attemptRule = props.selectedAttempt?.reference_snapshot.scoring;
  const frozenScoringType = runRule && typeof runRule === "object" && !Array.isArray(runRule) && typeof (runRule as Record<string, unknown>).type === "string"
    ? String((runRule as Record<string, unknown>).type)
    : attemptRule && typeof attemptRule === "object" && !Array.isArray(attemptRule) && typeof (attemptRule as Record<string, unknown>).type === "string"
      ? String((attemptRule as Record<string, unknown>).type)
      : null;
  const frozenMetricKey = frozenScoringType ? datasetMetricLabelKeys[frozenScoringType as DatasetMetricId] : undefined;
  const effectiveMetric = frozenScoringType ? (frozenMetricKey ? t(frozenMetricKey) : frozenScoringType) : null;
  const evidence = <EvidenceBrowser attempts={props.attempts} busy={props.busy} selectedAttempt={props.selectedAttempt} onLoadMore={props.onLoadMoreAttempts} onReview={props.onReview} />;
  const reviews = props.selectedAttempt ? <>
    <JudgeWorkflow selectedAttempt={props.selectedAttempt} attempts={props.attempts} endpoints={props.endpoints} form={props.judgeForm} assessments={props.judgeAssessments} agreement={props.judgeAgreement} busy={props.busy} onForm={props.onJudgeForm} onSubmit={props.onCreateJudgeAssessment} />
    <section className="grid two"><article className="panel"><h2>Human review: {props.selectedAttempt.sample_id}</h2><form className="form" onSubmit={props.onCreateReview}>
      <label>Reviewer ID<input required value={props.reviewForm.reviewer_id} onChange={(event) => props.onReviewForm({ ...props.reviewForm, reviewer_id: event.target.value })} /></label>
      <label>Review stage<select value={props.reviewForm.review_stage} onChange={(event) => props.onReviewForm({ ...props.reviewForm, review_stage: event.target.value as ReviewForm["review_stage"] })}><option value="primary">Primary review</option><option value="secondary">Secondary review</option><option value="adjudication">Adjudication</option></select></label>
      <label>Rubric (JSON)<textarea value={props.reviewForm.rubric} onChange={(event) => props.onReviewForm({ ...props.reviewForm, rubric: event.target.value })} spellCheck={false} placeholder='{"quality":"high"}' /></label>
      <label>Score<input type="number" min="0" max="1" step="0.01" value={props.reviewForm.score} onChange={(event) => props.onReviewForm({ ...props.reviewForm, score: event.target.value })} /></label>
      <label>Labels (comma-separated)<input value={props.reviewForm.labels} onChange={(event) => props.onReviewForm({ ...props.reviewForm, labels: event.target.value })} /></label>
      <label>Notes<textarea value={props.reviewForm.notes} onChange={(event) => props.onReviewForm({ ...props.reviewForm, notes: event.target.value })} /></label>
      {props.reviewForm.review_stage === "adjudication" && <p className="muted">This records a final decision over all saved primary and secondary reviews.</p>}
      <button disabled={props.busy === "review-submit"}>Save review</button>
    </form></article><article className="panel"><h2>Review agreement</h2>{props.reviewAgreement ? <><p><strong>{props.reviewAgreement.status.replaceAll("_", " ")}</strong> · {props.reviewAgreement.distinct_reviewer_count} reviewer(s)</p><p className="muted">Score mean {formatNumber(props.reviewAgreement.numeric_score.mean)} · spread {formatNumber(props.reviewAgreement.numeric_score.range)} · label agreement {formatPercent(props.reviewAgreement.label_agreement)}</p><p className="muted">Primary {props.reviewAgreement.review_stage_counts.primary} · secondary {props.reviewAgreement.review_stage_counts.secondary} · adjudication {props.reviewAgreement.review_stage_counts.adjudication}</p></> : <p className="empty">Open a sample to load review agreement.</p>}
      <h3>Saved reviews</h3>{props.reviews.length === 0 ? <p className="empty">No human review has been saved for this attempt.</p> : <div className="review-list">{props.reviews.map((review) => <article className="review" key={review.id}><strong>{review.review_stage} · {review.reviewer_id} · {review.score ?? "no score"}</strong><p>{review.notes || "No notes"}</p><small>{review.labels.join(", ") || "No labels"} · {formatDate(review.created_at)}</small></article>)}</div>}
    </article></section>
  </> : <section className="panel run-detail-review-empty"><h2>Human and judge review</h2><p className="empty">Open a sample from Evidence to load review, agreement, and independent judge controls.</p></section>;
  const reports = <section className="panel"><div className="section-title"><h2>Report artifacts</h2><div className="actions"><button onClick={() => props.onGenerateReport(props.run.id, "html")}>HTML</button><button className="secondary" onClick={() => props.onGenerateReport(props.run.id, "markdown")}>Markdown</button><button className="secondary" onClick={() => props.onGenerateReport(props.run.id, "json")}>JSON</button><button className="secondary" onClick={() => props.onGenerateReport(props.run.id, "csv")}>CSV</button></div></div><ReportsTable onDelete={props.onDeleteReport} reports={props.reports} /></section>;
  return <RunDetailWorkspace actions={props.actions} effectiveMetric={effectiveMetric} evidence={evidence} logs={props.logs} metrics={props.metrics} reports={reports} reviewSelectionKey={props.selectedAttempt?.id ?? null} reviews={reviews} run={props.run} summary={props.summary} />;
}

function JudgeWorkflow({ selectedAttempt, attempts, endpoints, form, assessments, agreement, busy, onForm, onSubmit }: { selectedAttempt: SampleAttempt; attempts: SampleAttempt[]; endpoints: Endpoint[]; form: JudgeForm; assessments: JudgeAssessment[]; agreement: JudgeAgreement | null; busy: string | null; onForm: (value: JudgeForm) => void; onSubmit: (event: FormEvent) => void }) {
  const { formatDate, formatNumber, formatPercent } = useTranslation();
  const pairedAttempts = attempts.filter((attempt) => attempt.id !== selectedAttempt.id && attempt.sample_id === selectedAttempt.sample_id);
  return <section className="grid two"><article className="panel"><div className="section-title"><h2>Blinded pairwise judge</h2><span>Model identities are never sent to the judge.</span></div><form className="form" onSubmit={onSubmit}>
    <label>Independent judge endpoint<select required value={form.endpoint_id} onChange={(event) => onForm({ ...form, endpoint_id: event.target.value })}><option value="">Select available endpoint</option>{endpoints.filter((endpoint) => endpoint.status === "available").map((endpoint) => <option key={endpoint.id} value={endpoint.id}>{endpoint.display_name} · {endpoint.model_name}</option>)}</select></label>
    <label>Compare with matching sample attempt<select value={form.comparison_attempt_id} onChange={(event) => onForm({ ...form, comparison_attempt_id: event.target.value })}><option value="">Single-answer judge assessment</option>{pairedAttempts.map((attempt) => <option key={attempt.id} value={attempt.id}>{attempt.sample_id} · attempt {attempt.attempt_number} · {attempt.status}</option>)}</select></label>
    <label>Or paste a sample attempt ID<input value={form.comparison_attempt_id} onChange={(event) => onForm({ ...form, comparison_attempt_id: event.target.value })} placeholder="Cross-run matching sample attempt ID" /></label>
    {form.comparison_attempt_id && <label><input type="checkbox" checked={form.swap_test} onChange={(event) => onForm({ ...form, swap_test: event.target.checked })} /> Run reverse-order swap test</label>}
    <label>Rubric (JSON)<textarea value={form.rubric} onChange={(event) => onForm({ ...form, rubric: event.target.value })} spellCheck={false} placeholder='{"criterion":"answer quality"}' /></label>
    <button disabled={busy === "judge-submit"}>{form.comparison_attempt_id ? "Run blinded comparison" : "Request judge assessment"}</button>
  </form></article><article className="panel"><h2>Judge agreement</h2>{agreement ? <><p><strong>{agreement.status.replaceAll("_", " ")}</strong> · {agreement.successful_assessment_count}/{agreement.assessment_count} succeeded</p><p className="muted">Score mean {formatNumber(agreement.scores.mean)} · spread {formatNumber(agreement.scores.range)} · {agreement.judge_endpoint_count} judge endpoint(s)</p><p className="muted">Decisions: {agreement.decisions.distinct.join(", ") || "none"} · swap groups {agreement.swap_test_group_count}</p></> : <p className="empty">Open a sample to load judge agreement.</p>}<h3>Judge evidence</h3>{assessments.length === 0 ? <p className="empty">No independent judge assessment has been recorded.</p> : <div className="review-list">{assessments.map((assessment) => <article className="review" key={assessment.id}><strong>{assessment.label || assessment.status} · {assessment.score ?? "--"}</strong><p>{assessment.rationale || assessment.error_message || "No rationale returned."}</p><small>{assessment.selected_answer ? `winner ${assessment.selected_answer} · ` : ""}{assessment.answer_order.join(" / ") || "single answer"} · {formatDate(assessment.created_at)}</small></article>)}</div>}</article></section>;
}
