import { type FormEvent, useCallback, useEffect, useMemo, useState } from "react";

import type { FeatureRouteProps } from "../../app/types";
import { RunsPage } from "../../components/pages/OperationsPages";
import { DatasetRunLauncher, type DatasetRunForm } from "../../components/runs/DatasetRunLauncher";
import { datasetScoringRuleFor } from "../../evaluations/scoringMetrics";
import { useTranslation } from "../../i18n/LocaleProvider";
import { translateStaticTemplate } from "../../i18n/operationalCopy";
import { benchmarksApi, type Benchmark, type PromptPackage } from "../benchmarks/api";
import { datasetsApi, type Dataset } from "../datasets/api";
import { endpointsApi, type Endpoint } from "../endpoints/api";
import { reportCopy } from "../../i18n/catalog";
import { reportsApi, type Report, type ReportFormat } from "../reports/api";
import { reviewsApi, type JudgeAssessment, type JudgeAgreement, type Review, type ReviewAgreement } from "../reviews/api";
import { runsApi, type AggregateMetric, type EvaluationRun, type RunLogEntry, type RunPreflight, type RunSummary, type SampleAttempt } from "./api";
import { type JudgeForm, type ReviewForm, RunInspector } from "./RunInspector";

const initialDatasetRun: DatasetRunForm = { dataset_version_id: "", prompt_package_id: "", input_field: "", reference_field: "", sample_limit: "100", model_endpoint_id: "", metric: "default", judge_endpoint_id: "", judge_system_message: "" };
const initialReview: ReviewForm = { reviewer_id: "local-reviewer", rubric: "{}", score: "", labels: "", notes: "", review_stage: "primary" };
const initialJudge: JudgeForm = { endpoint_id: "", rubric: "{}", comparison_attempt_id: "", swap_test: true };

function optionalNumber(value: string) {
  return value.trim() === "" ? null : Number(value);
}

function parseJsonObject(value: string, label: string): Record<string, unknown> {
  const parsed: unknown = JSON.parse(value);
  if (!parsed || Array.isArray(parsed) || typeof parsed !== "object") throw new Error(`${label} must be a JSON object.`);
  return parsed as Record<string, unknown>;
}

function datasetRunPayload(form: DatasetRunForm) {
  const scoringRule = datasetScoringRuleFor(form.metric, { judgeEndpointId: form.judge_endpoint_id, systemMessage: form.judge_system_message });
  return {
    model_endpoint_id: form.model_endpoint_id, dataset_version_id: form.dataset_version_id,
    prompt_package_id: form.prompt_package_id || null, input_field: form.prompt_package_id ? null : form.input_field,
    reference_field: form.reference_field, sample_limit: Number(form.sample_limit) || 100,
    ...(scoringRule ? { scoring_rule: scoringRule } : {}),
  };
}

type RunsRouteProps = FeatureRouteProps<"runs"> & { routeSearch: string };

export function RunsRoute({ activeTab, navigate, reportError, routeSearch, showNotice }: RunsRouteProps) {
  const { formatNumber, locale, t } = useTranslation();
  const [attempts, setAttempts] = useState<SampleAttempt[]>([]);
  const [benchmarks, setBenchmarks] = useState<Benchmark[]>([]);
  const [busy, setBusy] = useState<string | null>(null);
  const [datasets, setDatasets] = useState<Dataset[]>([]);
  const [datasetsLoaded, setDatasetsLoaded] = useState(false);
  const [datasetRunFields, setDatasetRunFields] = useState<string[]>([]);
  const [datasetRunFieldsError, setDatasetRunFieldsError] = useState<string | null>(null);
  const [datasetRunFieldsLoading, setDatasetRunFieldsLoading] = useState(false);
  const [datasetRunForm, setDatasetRunForm] = useState<DatasetRunForm>(initialDatasetRun);
  const [datasetRunSchemaRequest, setDatasetRunSchemaRequest] = useState(0);
  const [endpoints, setEndpoints] = useState<Endpoint[]>([]);
  const [judgeAgreement, setJudgeAgreement] = useState<JudgeAgreement | null>(null);
  const [judgeAssessments, setJudgeAssessments] = useState<JudgeAssessment[]>([]);
  const [judgeForm, setJudgeForm] = useState(initialJudge);
  const [launchPreflight, setLaunchPreflight] = useState<{ kind: "quick-start" | "dataset"; result: RunPreflight } | null>(null);
  const [prompts, setPrompts] = useState<PromptPackage[]>([]);
  const [quickStartSampleLimit, setQuickStartSampleLimit] = useState("3");
  const [reports, setReports] = useState<Report[]>([]);
  const [reviewAgreement, setReviewAgreement] = useState<ReviewAgreement | null>(null);
  const [reviewForm, setReviewForm] = useState(initialReview);
  const [reviews, setReviews] = useState<Review[]>([]);
  const [runConcurrencyEdits, setRunConcurrencyEdits] = useState<Record<string, string>>({});
  const [runLogs, setRunLogs] = useState<RunLogEntry[]>([]);
  const [runMetrics, setRunMetrics] = useState<AggregateMetric[]>([]);
  const [runs, setRuns] = useState<EvaluationRun[]>([]);
  const [runSummary, setRunSummary] = useState<RunSummary | null>(null);
  const [selectedAttempt, setSelectedAttempt] = useState<SampleAttempt | null>(null);
  const [selectedPromptId, setSelectedPromptId] = useState("");
  const [selectedQuickStartBenchmark, setSelectedQuickStartBenchmark] = useState("text-quick-check@1.0.0");
  const [selectedRun, setSelectedRun] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    await Promise.all([
      benchmarksApi.list().then(setBenchmarks),
      datasetsApi.list().then((nextDatasets) => { setDatasets(nextDatasets); setDatasetsLoaded(true); }),
      endpointsApi.list().then(setEndpoints),
      benchmarksApi.listPrompts().then(setPrompts),
      runsApi.list().then(setRuns),
    ]);
  }, []);
  useEffect(() => { void refresh().catch(reportError); }, [refresh, reportError]);

  const availableEndpoints = useMemo(() => endpoints.filter((endpoint) => endpoint.status === "available"), [endpoints]);
  const quickStartBenchmarks = useMemo(() => benchmarks.filter((benchmark) => benchmark.source === "builtin" && ["available", "enabled"].includes(benchmark.status)), [benchmarks]);
  const selectedQuickStart = quickStartBenchmarks.find((benchmark) => `${benchmark.benchmark_id}@${benchmark.version}` === selectedQuickStartBenchmark) ?? quickStartBenchmarks[0] ?? null;
  const selectedDataset = datasets.find((dataset) => dataset.id === datasetRunForm.dataset_version_id) ?? null;
  const selectedRunInfo = runs.find((run) => run.id === selectedRun) ?? null;
  const fieldsCollide = Boolean(datasetRunForm.input_field) && datasetRunForm.input_field === datasetRunForm.reference_field;
  const handoffDatasetId = activeTab === "dataset-evaluation" ? new URLSearchParams(routeSearch).get("dataset") : null;

  useEffect(() => {
    if (!selectedQuickStart) return;
    const benchmarkKey = `${selectedQuickStart.benchmark_id}@${selectedQuickStart.version}`;
    if (benchmarkKey !== selectedQuickStartBenchmark) setSelectedQuickStartBenchmark(benchmarkKey);
    const manifestCount = Number(selectedQuickStart.manifest.sample_count);
    setQuickStartSampleLimit(Number.isFinite(manifestCount) && manifestCount > 0 ? String(manifestCount) : "1");
  }, [selectedQuickStart?.id]);

  useEffect(() => {
    if (!handoffDatasetId) return;
    setDatasetRunForm((current) => current.dataset_version_id === handoffDatasetId ? current : { ...current, dataset_version_id: handoffDatasetId, input_field: "", reference_field: "" });
  }, [handoffDatasetId]);

  useEffect(() => {
    const datasetId = datasetRunForm.dataset_version_id;
    if (!datasetId || !datasetsLoaded) { setDatasetRunFields([]); setDatasetRunFieldsError(null); setDatasetRunFieldsLoading(false); return; }
    let disposed = false;
    setDatasetRunFields([]); setDatasetRunFieldsError(null); setDatasetRunFieldsLoading(true);
    void datasetsApi.preview(datasetId, 50).then((preview) => {
      if (disposed) return;
      const fields = Array.from(new Set(preview.fields.map(String).filter(Boolean)));
      const inputField = selectedDataset?.input_field && fields.includes(selectedDataset.input_field) ? selectedDataset.input_field : fields[0] ?? "";
      const referenceField = selectedDataset?.reference_field && fields.includes(selectedDataset.reference_field) ? selectedDataset.reference_field : fields.find((field) => field !== inputField) ?? "";
      setDatasetRunFields(fields);
      setDatasetRunFieldsError(fields.length === 0 ? t("runLauncher.schemaEmpty") : referenceField ? null : t("runLauncher.schemaReferenceRequired"));
      setDatasetRunForm((current) => current.dataset_version_id === datasetId ? { ...current, input_field: inputField, reference_field: referenceField } : current);
    }).catch((error: unknown) => {
      if (disposed) return;
      setDatasetRunFieldsError(error instanceof Error ? error.message : t("runLauncher.schemaEmpty"));
      setDatasetRunForm((current) => current.dataset_version_id === datasetId ? { ...current, input_field: "", reference_field: "" } : current);
    }).finally(() => { if (!disposed) setDatasetRunFieldsLoading(false); });
    return () => { disposed = true; };
  }, [datasetRunForm.dataset_version_id, datasetRunSchemaRequest, datasetsLoaded, selectedDataset?.input_field, selectedDataset?.reference_field, t]);

  const selectRun = useCallback(async (runId: string) => {
    setSelectedRun(runId); setSelectedAttempt(null); setAttempts([]); setRunSummary(null); setRunMetrics([]); setReports([]); setRunLogs([]); setReviews([]); setReviewAgreement(null); setJudgeAssessments([]); setJudgeAgreement(null);
    try {
      const [nextAttempts, nextSummary, nextMetrics, nextReports, nextLogs] = await Promise.all([runsApi.listAttempts(runId), runsApi.summary(runId), runsApi.metrics(runId), reportsApi.list(runId), runsApi.logs(runId)]);
      setAttempts(nextAttempts); setRunSummary(nextSummary); setRunMetrics(nextMetrics); setReports(nextReports); setRunLogs(nextLogs);
    } catch (error) { reportError(error); }
  }, [reportError]);

  useEffect(() => {
    const runId = activeTab === "run-details" ? new URLSearchParams(routeSearch).get("run") : null;
    if (runId && runId !== selectedRun) void selectRun(runId);
  }, [activeTab, routeSearch, selectRun, selectedRun]);

  useEffect(() => {
    if (!selectedRun || !selectedRunInfo || !["queued", "running"].includes(selectedRunInfo.status)) return;
    return runsApi.subscribe(selectedRun, () => { void selectRun(selectedRun); void refresh(); });
  }, [refresh, selectRun, selectedRun, selectedRunInfo?.status]);

  function inspectRun(runId: string) { void selectRun(runId); navigate("runs", { runId, tab: "run-details" }); }

  async function preflightRun(endpointId: string, sampleLimit: number, benchmarkKey: string) {
    setLaunchPreflight(null); setBusy("preflight-quick-start");
    try {
      const [benchmarkId, benchmarkVersion] = benchmarkKey.split("@", 2);
      const preflight = await runsApi.validate(endpointId, selectedPromptId || undefined, {}, null, benchmarkId, benchmarkVersion, sampleLimit);
      setLaunchPreflight({ kind: "quick-start", result: preflight });
      const cost = preflight.estimated_cost === null ? translateStaticTemplate(locale, "cost not configured") : `${formatNumber(preflight.estimated_cost, 6)} ${preflight.currency ?? ""}`;
      showNotice(preflight.can_queue ? "Preflight ready: {{samples}} samples, {{requests}} requests, {{tokens}} estimated tokens, {{cost}}." : "Preflight blocked: {{issues}}", preflight.can_queue ? { samples: preflight.sample_count, requests: preflight.estimated_requests, tokens: preflight.estimated_input_tokens + preflight.estimated_output_tokens, cost } : { issues: preflight.issues.join(" ") });
    } catch (error) { reportError(error); } finally { setBusy(null); }
  }

  async function createRun(endpointId: string, sampleLimit: number, benchmarkKey: string) {
    setBusy(`run-${endpointId}`);
    try {
      const [benchmarkId, benchmarkVersion] = benchmarkKey.split("@", 2);
      const run = await runsApi.create(endpointId, selectedPromptId || undefined, {}, null, benchmarkId, benchmarkVersion, sampleLimit);
      await selectRun(run.id); await refresh(); navigate("runs", { runId: run.id, tab: "run-details" });
      showNotice("{{benchmark}} queued with an immutable configuration snapshot.", { benchmark: `${benchmarkId}@${benchmarkVersion}` });
    } catch (error) { reportError(error); } finally { setBusy(null); }
  }

  async function changeRun(run: EvaluationRun, action: "execute" | "pause" | "resume" | "cancel" | "clone" | "rerun" | "retry" | "archive") {
    setBusy(`${action}-${run.id}`);
    try {
      const result = action === "execute" ? await runsApi.execute(run.id) : action === "pause" ? await runsApi.pause(run.id) : action === "resume" ? await runsApi.resume(run.id) : action === "cancel" ? await runsApi.cancel(run.id) : action === "clone" ? await runsApi.clone(run.id) : action === "rerun" ? await runsApi.rerunBenchmark(run.id) : action === "retry" ? await runsApi.retryFailed(run.id) : await runsApi.archive(run.id);
      showNotice(action === "clone" ? "Run cloned with a new immutable configuration snapshot." : action === "rerun" ? "Benchmark rerun queued with a link to its source run." : action === "retry" ? "Failed samples were queued as new attempts." : action === "archive" ? "Run archived. Its evidence remains available through the API until deleted." : "Run {{action}}.", action === "execute" || action === "pause" || action === "resume" || action === "cancel" ? { action: action === "execute" ? "executed" : action === "pause" ? "paused" : action === "resume" ? "resumed" : "cancelled" } : undefined);
      await selectRun(result.id); await refresh();
    } catch (error) { reportError(error); } finally { setBusy(null); }
  }

  async function updateRunConcurrency(run: EvaluationRun) {
    setBusy(`run-cap-${run.id}`);
    try {
      const updated = await runsApi.updateConcurrency(run.id, optionalNumber(runConcurrencyEdits[run.id] ?? run.max_concurrency?.toString() ?? ""));
      setRunConcurrencyEdits((current) => ({ ...current, [run.id]: updated.max_concurrency?.toString() ?? "" }));
      showNotice("Run concurrency ceiling updated for future task claims; its evaluation snapshot remains unchanged."); await refresh();
    } catch (error) { reportError(error); } finally { setBusy(null); }
  }

  async function queueDatasetRun() {
    setBusy("dataset-run");
    try { await runsApi.createDataset(datasetRunPayload(datasetRunForm)); showNotice(t("datasetRun.queued")); setDatasetRunForm({ ...initialDatasetRun, model_endpoint_id: datasetRunForm.model_endpoint_id }); setLaunchPreflight(null); await refresh(); }
    catch (error) { reportError(error); } finally { setBusy(null); }
  }

  async function preflightDatasetRun() {
    setLaunchPreflight(null); setBusy("preflight-dataset");
    try {
      const result = await runsApi.validateDataset(datasetRunPayload(datasetRunForm)); setLaunchPreflight({ kind: "dataset", result });
      const judge = result.judge_estimate;
      showNotice(!result.can_queue ? "Preflight blocked: {{issues}}" : judge ? "Preflight ready: {{samples}} samples, {{judgeRequests}} judge requests, {{judgeTokens}} estimated judge tokens, {{cost}}." : "Preflight ready: {{samples}} samples.", !result.can_queue ? { issues: result.issues.join(" ") } : judge ? { samples: result.sample_count, judgeRequests: judge.estimated_requests, judgeTokens: judge.estimated_input_tokens + judge.estimated_output_tokens, cost: judge.estimated_cost === null ? translateStaticTemplate(locale, "cost not configured") : `${formatNumber(judge.estimated_cost, 6)} ${judge.currency ?? ""}` } : { samples: result.sample_count });
    } catch (error) { reportError(error); } finally { setBusy(null); }
  }

  async function loadMoreAttempts() {
    if (!selectedRun) return;
    setBusy("attempts-more");
    try { const next = await runsApi.listAttempts(selectedRun, attempts.length); setAttempts((current) => [...current, ...next.filter((item) => !current.some((existing) => existing.id === item.id))]); }
    catch (error) { reportError(error); } finally { setBusy(null); }
  }

  async function generateReport(runId: string, format: ReportFormat) {
    setBusy(`report-${runId}-${format}`);
    try {
      const report = await reportsApi.create(runId, format, "single_model", []); showNotice("{{format}} {{reportType}} report generated.", { format: format.toUpperCase(), reportType: "single model" });
      const reportUrl = await reportsApi.download(report.id); window.open(reportUrl, "_blank", "noopener,noreferrer"); window.setTimeout(() => URL.revokeObjectURL(reportUrl), 60_000);
      if (selectedRun === runId) await selectRun(runId); await refresh();
    } catch (error) { reportError(error); } finally { setBusy(null); }
  }

  async function deleteReport(report: Report) {
    const copy = reportCopy[locale]; if (!window.confirm(copy.deleteConfirm)) return;
    setBusy(`report-delete-${report.id}`);
    try { await reportsApi.remove(report.id); showNotice(copy.deletedNotice); if (selectedRun === report.run_id) await selectRun(selectedRun); await refresh(); }
    catch (error) { reportError(error instanceof Error ? error.message : copy.deleteFailed); } finally { setBusy(null); }
  }

  async function openReview(attempt: SampleAttempt) {
    setSelectedAttempt(attempt); setBusy(`review-${attempt.id}`);
    try { const [nextReviews, nextAgreement, nextJudges, nextJudgeAgreement] = await Promise.all([reviewsApi.list(attempt.id), reviewsApi.agreement(attempt.id), reviewsApi.listJudges(attempt.id), reviewsApi.judgeAgreement(attempt.id)]); setReviews(nextReviews); setReviewAgreement(nextAgreement); setJudgeAssessments(nextJudges); setJudgeAgreement(nextJudgeAgreement); }
    catch (error) { reportError(error); } finally { setBusy(null); }
  }

  async function createReview(event: FormEvent) {
    event.preventDefault(); if (!selectedAttempt) return; setBusy("review-submit");
    try {
      await reviewsApi.create({ sample_attempt_id: selectedAttempt.id, reviewer_id: reviewForm.reviewer_id, rubric: parseJsonObject(reviewForm.rubric, "Human-review rubric"), score: reviewForm.score === "" ? null : Number(reviewForm.score), labels: reviewForm.labels.split(",").map((label) => label.trim()).filter(Boolean), notes: reviewForm.notes || null, review_stage: reviewForm.review_stage, adjudicates_review_ids: reviewForm.review_stage === "adjudication" ? reviews.filter((review) => review.review_stage !== "adjudication").map((review) => review.id) : [] });
      setReviewForm(initialReview); const [nextReviews, nextAgreement] = await Promise.all([reviewsApi.list(selectedAttempt.id), reviewsApi.agreement(selectedAttempt.id)]); setReviews(nextReviews); setReviewAgreement(nextAgreement); showNotice("Human review saved separately from automated results.");
    } catch (error) { reportError(error); } finally { setBusy(null); }
  }

  async function createJudgeAssessment(event: FormEvent) {
    event.preventDefault(); if (!selectedAttempt || !judgeForm.endpoint_id) return; setBusy("judge-submit");
    try {
      const payload = { sample_attempt_id: selectedAttempt.id, judge_endpoint_id: judgeForm.endpoint_id, rubric: parseJsonObject(judgeForm.rubric, "Judge rubric") };
      if (judgeForm.comparison_attempt_id.trim()) await reviewsApi.createJudgeComparison({ ...payload, comparison_sample_attempt_id: judgeForm.comparison_attempt_id.trim(), swap_test: judgeForm.swap_test }); else await reviewsApi.createJudge(payload);
      const [nextAssessments, nextAgreement] = await Promise.all([reviewsApi.listJudges(selectedAttempt.id), reviewsApi.judgeAgreement(selectedAttempt.id)]); setJudgeAssessments(nextAssessments); setJudgeAgreement(nextAgreement);
      showNotice(judgeForm.comparison_attempt_id.trim() ? "Blinded pairwise judge evidence and swap-test results saved." : "Independent LLM-as-judge assessment saved with rationale evidence.");
    } catch (error) { reportError(error); } finally { setBusy(null); }
  }

  function preflightControls(kind: "quick-start" | "dataset") {
    const current = launchPreflight?.kind === kind ? launchPreflight.result : null;
    const checking = kind === "quick-start" ? busy === "preflight-quick-start" : busy === "preflight-dataset";
    const judgeMissing = datasetRunForm.metric === "llm_judge" && (!datasetRunForm.judge_endpoint_id || datasetRunForm.judge_endpoint_id === datasetRunForm.model_endpoint_id || !datasetRunForm.judge_system_message.trim());
    const datasetBlocked = datasetRunFieldsLoading || Boolean(datasetRunFieldsError) || fieldsCollide || !datasetRunForm.dataset_version_id || (!datasetRunForm.input_field && !datasetRunForm.prompt_package_id) || !datasetRunForm.reference_field || judgeMissing;
    return <div className="workspace-run-context-controls"><label>{t("datasetRun.endpoint")}<select required value={datasetRunForm.model_endpoint_id} onChange={(event) => { setLaunchPreflight(null); setDatasetRunForm((currentForm) => ({ ...currentForm, model_endpoint_id: event.target.value, judge_endpoint_id: currentForm.judge_endpoint_id === event.target.value ? "" : currentForm.judge_endpoint_id })); }}><option value="">—</option>{availableEndpoints.map((endpoint) => <option data-i18n-preserve key={endpoint.id} value={endpoint.id}>{endpoint.display_name}</option>)}</select></label><div className="actions workspace-preflight-actions">{kind === "quick-start" ? <button className="secondary" disabled={!datasetRunForm.model_endpoint_id || !selectedQuickStart || checking} onClick={() => void preflightRun(datasetRunForm.model_endpoint_id, Number(quickStartSampleLimit) || 1, selectedQuickStartBenchmark)} type="button">{t("runLauncher.preflightQuickStart")}</button> : <button className="secondary" disabled={!datasetRunForm.model_endpoint_id || datasetBlocked || checking} onClick={() => void preflightDatasetRun()} type="button">{t("runLauncher.preflightDataset")}</button>}</div><div aria-live="polite" className={`workspace-preflight-state ${current?.can_queue ? "is-ready" : current ? "is-blocked" : ""}`} role="status"><strong>{checking ? t("runLauncher.checking") : current?.can_queue ? t("runLauncher.ready") : current ? t("runLauncher.blocked") : t("runLauncher.notChecked")}</strong>{current && !current.can_queue && <span data-i18n-preserve>{current.issues.join(" ")}</span>}</div></div>;
  }

  function runActions(run: EvaluationRun) {
    const terminal = ["completed", "completed_with_errors", "cancelled", "failed"].includes(run.status);
    return <><button className="secondary" onClick={() => inspectRun(run.id)} type="button">Inspect</button>{!terminal && <><label className="compact-field">Run cap<input type="number" min="1" max="1000" value={runConcurrencyEdits[run.id] ?? run.max_concurrency?.toString() ?? ""} onChange={(event) => setRunConcurrencyEdits((current) => ({ ...current, [run.id]: event.target.value }))} placeholder="Endpoint" /></label><button className="secondary" disabled={busy === `run-cap-${run.id}`} onClick={() => void updateRunConcurrency(run)} type="button">Set cap</button></>}{run.status === "queued" && <button disabled={busy === `execute-${run.id}`} onClick={() => void changeRun(run, "execute")} type="button">Execute</button>}{["queued", "running"].includes(run.status) && <button className="secondary" disabled={busy === `pause-${run.id}`} onClick={() => void changeRun(run, "pause")} type="button">Pause</button>}{run.status === "paused" && <button disabled={busy === `resume-${run.id}`} onClick={() => void changeRun(run, "resume")} type="button">Resume</button>}{run.status.startsWith("completed") && <><button className="secondary" disabled={busy === `clone-${run.id}`} onClick={() => void changeRun(run, "clone")} type="button">Clone</button><button className="secondary" disabled={busy === `rerun-${run.id}`} onClick={() => void changeRun(run, "rerun")} type="button">Rerun benchmark</button></>}{run.status === "completed_with_errors" && <button disabled={busy === `retry-${run.id}`} onClick={() => void changeRun(run, "retry")} type="button">Retry failed</button>}{terminal && <button className="secondary" disabled={busy === `archive-${run.id}`} onClick={() => void changeRun(run, "archive")} type="button">Archive</button>}{!terminal && <button className="danger" disabled={busy === `cancel-${run.id}`} onClick={() => void changeRun(run, "cancel")} type="button">Cancel</button>}</>;
  }

  const inspector = selectedRunInfo ? <RunInspector actions={runActions(selectedRunInfo)} attempts={attempts} busy={busy} endpoints={endpoints} judgeAgreement={judgeAgreement} judgeAssessments={judgeAssessments} judgeForm={judgeForm} logs={runLogs} metrics={runMetrics} onCreateJudgeAssessment={createJudgeAssessment} onCreateReview={createReview} onDeleteReport={deleteReport} onGenerateReport={generateReport} onJudgeForm={setJudgeForm} onLoadMoreAttempts={loadMoreAttempts} onReview={openReview} onReviewForm={setReviewForm} reports={reports} reviewAgreement={reviewAgreement} reviewForm={reviewForm} reviews={reviews} run={selectedRunInfo} selectedAttempt={selectedAttempt} summary={runSummary} /> : null;
  const datasetLauncher = <DatasetRunLauncher busy={busy} datasets={datasets} endpoints={endpoints} fields={datasetRunFields} fieldsCollide={fieldsCollide} fieldsError={datasetRunFieldsError} fieldsLoading={datasetRunFieldsLoading} form={datasetRunForm} handoffDatasetId={handoffDatasetId} onFormChange={setDatasetRunForm} onPreflightReset={() => setLaunchPreflight(null)} onQueue={() => void queueDatasetRun()} onRetrySchema={() => { setLaunchPreflight(null); setDatasetRunSchemaRequest((current) => current + 1); }} prompts={prompts} />;
  const quickStartLauncher = <form className="form workspace-run-launcher" onSubmit={(event) => { event.preventDefault(); if (selectedQuickStart) void createRun(datasetRunForm.model_endpoint_id, Number(quickStartSampleLimit) || 1, selectedQuickStartBenchmark); }}><label>{t("runLauncher.quickStartBenchmark")}<select aria-label={t("runLauncher.quickStartBenchmark")} required value={selectedQuickStart ? `${selectedQuickStart.benchmark_id}@${selectedQuickStart.version}` : ""} onChange={(event) => { const benchmark = quickStartBenchmarks.find((item) => `${item.benchmark_id}@${item.version}` === event.target.value); setSelectedQuickStartBenchmark(event.target.value); setQuickStartSampleLimit(String(Number(benchmark?.manifest.sample_count) || 1)); setLaunchPreflight(null); }}><option value="">—</option>{quickStartBenchmarks.map((benchmark) => <option data-i18n-preserve key={benchmark.id} value={`${benchmark.benchmark_id}@${benchmark.version}`}>{benchmark.display_name}</option>)}</select></label>{selectedQuickStart && <div className="workspace-modality-tags">{(Array.isArray(selectedQuickStart.manifest.modalities) ? selectedQuickStart.manifest.modalities : []).map((modality) => <span className="badge" data-i18n-preserve key={String(modality)}>{String(modality)}</span>)}</div>}<label>{t("datasetRun.promptPackage")}<select value={selectedPromptId} onChange={(event) => { setSelectedPromptId(event.target.value); setLaunchPreflight(null); }}><option value="">—</option>{prompts.map((prompt) => <option data-i18n-preserve key={prompt.id} value={prompt.id}>{prompt.name} v{prompt.version}</option>)}</select></label><label>{t("datasetRun.sampleLimit")}<input min={1} max={10000} required type="number" value={quickStartSampleLimit} onChange={(event) => { setQuickStartSampleLimit(event.target.value); setLaunchPreflight(null); }} /></label><p className="workspace-launch-note">{t("runLauncher.offlineHint")}</p><button className="primary" disabled={!datasetRunForm.model_endpoint_id || !selectedQuickStart || busy === `run-${datasetRunForm.model_endpoint_id}`}>{t("runLauncher.queueQuickStart")}</button></form>;

  return <RunsPage activeTab={activeTab} availableEndpointCount={availableEndpoints.length} configuredEndpointCount={endpoints.length} datasetLauncher={datasetLauncher} datasetPreflight={preflightControls("dataset")} inspector={inspector} onSelect={inspectRun} onOpenModelSetup={(tab) => navigate("models", { tab })} onTabChange={(tab) => navigate("runs", { tab })} quickStartLauncher={quickStartLauncher} quickStartPreflight={preflightControls("quick-start")} renderActions={runActions} runs={runs} selectedRunId={selectedRun} />;
}
