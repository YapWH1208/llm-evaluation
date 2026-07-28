import { ChangeEvent, FormEvent, useCallback, useEffect, useMemo, useState } from "react";
import {
  api,
  AuditEvent,
  ApiError,
  AnalyticsMatrix,
  Asset,
  Benchmark,
  Capability,
  Comparison,
  Dashboard,
  Dataset,
  Endpoint,
  EvaluationRun,
  EvaluationSuite,
  JudgeAssessment,
  JudgeAgreement,
  PromptPackage,
  Report,
  ReportType,
  Review,
  ReviewAgreement,
  RunSummary,
  RunLogEntry,
  SampleAttempt,
  SystemHealth,
  Task,
  User,
} from "./api";
import "./evidence.css";

type View = "dashboard" | "models" | "capabilities" | "workspace" | "benchmarks" | "datasets" | "suites" | "runs" | "queue" | "workers" | "analysis" | "compare" | "reports" | "reviews" | "users" | "settings";
type Theme = "dark" | "light";
type Locale = "en" | "zh-CN";

const navigationLabels: Record<Locale, Record<View, string>> = {
  en: { dashboard: "Dashboard", models: "Models", capabilities: "Capabilities", workspace: "Workspace", benchmarks: "Benchmarks", datasets: "Datasets", suites: "Suites", runs: "Runs", queue: "Task queue", workers: "Workers", analysis: "Analysis", compare: "Compare", reports: "Reports", reviews: "Human review", users: "Users", settings: "Settings" },
  "zh-CN": { dashboard: "仪表盘", models: "模型", capabilities: "能力", workspace: "工作区", benchmarks: "评测基准", datasets: "数据集", suites: "评测套件", runs: "运行任务", queue: "任务队列", workers: "工作节点", analysis: "分析", compare: "对比", reports: "报告", reviews: "人工评审", users: "用户", settings: "设置" },
};

const initialEndpoint = {
  base_url: "",
  api_key: "",
  model_name: "",
  protocol_profile: "openai_chat_completions",
  custom_headers: "{}",
  display_name: "",
  input_cost_per_million: "",
  output_cost_per_million: "",
  currency: "USD",
  tags: "",
  notes: "",
  default_request_body: "{}",
  max_concurrency: "1",
  api_key_max_concurrency: "",
  requests_per_second: "",
  requests_per_minute: "",
  tokens_per_minute: "",
  input_tokens_per_minute: "",
  output_tokens_per_minute: "",
};
const initialPrompt = { name: "", version: "1", prompt_type: "user_custom", system_message: "", user_template: "{{ question }}", few_shot_examples: "[]", output_format: "{}", response_parser: "{}", scoring_rule: "{}", change_log: "" };
const initialDataset = { dataset_id: "", version: "1", revision: "default", source_url: "", checksum: "", credential_env_var: "", license_text: "" };
const initialSuite = { name: "", version: "1", description: "", benchmarks: "text-quick-check@1.0.0", default_request_body: "{}", default_prompt_overrides: "{}", weight_configuration: "{}" };
const initialReview = { reviewer_id: "local-reviewer", rubric: "{}", score: "", labels: "", notes: "", review_stage: "primary" as "primary" | "secondary" | "adjudication" };
const initialJudge = { endpoint_id: "", rubric: "{}", comparison_attempt_id: "", swap_test: true };
const initialMultimodal = { endpoint_id: "", prompt: "", reference_answer: "", sample_id: "custom-sample", asset_id: "" };
const initialUser = { email: "", display_name: "", role: "viewer", max_concurrency: "" };
const initialShare = { days: "7", password: "", allow_download: false, include_evidence: false };

function formatDate(value: string | null) {
  return value ? new Intl.DateTimeFormat(document.documentElement.lang || undefined, { dateStyle: "medium", timeStyle: "short" }).format(new Date(value)) : "Not recorded";
}

function display(value: number | null | undefined, digits = 2) {
  return value === null || value === undefined ? "--" : new Intl.NumberFormat(undefined, { maximumFractionDigits: digits }).format(value);
}

function percent(value: number | null | undefined) {
  return value === null || value === undefined ? "--" : `${(value * 100).toFixed(1)}%`;
}

function money(value: number | null | undefined, currency: string | null | undefined) {
  return value === null || value === undefined ? "Not configured" : `${display(value, 6)} ${currency ?? ""}`.trim();
}

function optionalNumber(value: string) {
  return value.trim() === "" ? null : Number(value);
}

function parseJsonObject(value: string, label: string): Record<string, unknown> {
  const parsed: unknown = JSON.parse(value);
  if (!parsed || Array.isArray(parsed) || typeof parsed !== "object") throw new Error(`${label} must be a JSON object.`);
  return parsed as Record<string, unknown>;
}

function parseJsonArray(value: string, label: string): unknown[] {
  const parsed: unknown = JSON.parse(value);
  if (!Array.isArray(parsed)) throw new Error(`${label} must be a JSON array.`);
  return parsed;
}

type EvidenceMedia = { assetId: string; kind: "image" | "audio" | "video" | "file"; mimeType: string };

function evidenceMedia(attempt: SampleAttempt): EvidenceMedia[] {
  const messages = attempt.input_snapshot.messages;
  if (!Array.isArray(messages)) return [];
  const previews: EvidenceMedia[] = [];
  for (const message of messages) {
    if (!message || typeof message !== "object" || !Array.isArray((message as Record<string, unknown>).content)) continue;
    for (const part of (message as { content: unknown[] }).content) {
      if (!part || typeof part !== "object") continue;
      const record = part as Record<string, unknown>;
      const source = record.source;
      const assetId = source && typeof source === "object" ? (source as Record<string, unknown>).asset_id : null;
      const kind = record.type;
      const mimeType = record.mime_type;
      if (typeof assetId === "string" && ["image", "audio", "video", "file"].includes(String(kind)) && typeof mimeType === "string") {
        previews.push({ assetId, kind: kind as EvidenceMedia["kind"], mimeType });
      }
    }
  }
  return previews;
}

function EvidenceMediaPreview({ attempt }: { attempt: SampleAttempt }) {
  const media = useMemo(() => evidenceMedia(attempt), [attempt]);
  const mediaKey = media.map((item) => item.assetId).join(",");
  const [urls, setUrls] = useState<Record<string, string>>({});
  useEffect(() => {
    let disposed = false;
    const objectUrls: string[] = [];
    void Promise.all(media.map(async (item) => {
      try {
        const url = await api.assetPreviewObjectUrl(item.assetId);
        if (disposed) {
          URL.revokeObjectURL(url);
          return null;
        }
        objectUrls.push(url);
        return [item.assetId, url] as const;
      } catch {
        return null;
      }
    })).then((resolved) => {
      if (disposed) return;
      setUrls(Object.fromEntries(resolved.filter((item): item is readonly [string, string] => item !== null)));
    });
    return () => { disposed = true; objectUrls.forEach((url) => URL.revokeObjectURL(url)); };
  }, [mediaKey]);
  if (media.length === 0) return null;
  return <section className="panel"><div className="section-title"><h2>Media preview</h2><span>Fetched only after this sample is selected.</span></div><div className="media-preview">{media.map((item) => {
    const url = urls[item.assetId];
    if (!url) return <p className="muted" key={item.assetId}>Loading {item.kind} evidence…</p>;
    if (item.kind === "image") return <img key={item.assetId} src={url} alt={`Evidence asset ${item.assetId}`} />;
    if (item.kind === "audio") return <audio key={item.assetId} controls src={url}>Audio preview unavailable.</audio>;
    if (item.kind === "video") return <video key={item.assetId} controls src={url}>Video preview unavailable.</video>;
    return <a key={item.assetId} href={url} download={`evidence.${item.mimeType.split("/")[1] ?? "file"}`}>Download attached file</a>;
  })}</div></section>;
}

export default function App() {
  const [view, setView] = useState<View>("dashboard");
  const [theme, setTheme] = useState<Theme>(() => window.localStorage.getItem("lle-theme") === "light" ? "light" : "dark");
  const [locale, setLocale] = useState<Locale>(() => window.localStorage.getItem("lle-locale") === "zh-CN" ? "zh-CN" : "en");
  const [apiToken, setApiToken] = useState(() => window.sessionStorage.getItem("lle-api-token") ?? "");
  const [endpoints, setEndpoints] = useState<Endpoint[]>([]);
  const [runs, setRuns] = useState<EvaluationRun[]>([]);
  const [dashboard, setDashboard] = useState<Dashboard | null>(null);
  const [prompts, setPrompts] = useState<PromptPackage[]>([]);
  const [datasets, setDatasets] = useState<Dataset[]>([]);
  const [suites, setSuites] = useState<EvaluationSuite[]>([]);
  const [benchmarks, setBenchmarks] = useState<Benchmark[]>([]);
  const [capabilities, setCapabilities] = useState<Record<string, Capability[]>>({});
  const [attempts, setAttempts] = useState<SampleAttempt[]>([]);
  const [reports, setReports] = useState<Report[]>([]);
  const [selectedRun, setSelectedRun] = useState<string | null>(null);
  const [runSummary, setRunSummary] = useState<RunSummary | null>(null);
  const [runLogs, setRunLogs] = useState<RunLogEntry[]>([]);
  const [selectedAttempt, setSelectedAttempt] = useState<SampleAttempt | null>(null);
  const [reviews, setReviews] = useState<Review[]>([]);
  const [reviewAgreement, setReviewAgreement] = useState<ReviewAgreement | null>(null);
  const [judgeAssessments, setJudgeAssessments] = useState<JudgeAssessment[]>([]);
  const [judgeAgreement, setJudgeAgreement] = useState<JudgeAgreement | null>(null);
  const [judgeForm, setJudgeForm] = useState(initialJudge);
  const [comparison, setComparison] = useState<Comparison | null>(null);
  const [comparisonRunA, setComparisonRunA] = useState("");
  const [comparisonRunB, setComparisonRunB] = useState("");
  const [form, setForm] = useState(initialEndpoint);
  const [promptForm, setPromptForm] = useState(initialPrompt);
  const [datasetForm, setDatasetForm] = useState(initialDataset);
  const [suiteForm, setSuiteForm] = useState(initialSuite);
  const [reviewForm, setReviewForm] = useState(initialReview);
  const [multimodalForm, setMultimodalForm] = useState(initialMultimodal);
  const [uploadedAssets, setUploadedAssets] = useState<Asset[]>([]);
  const [tasks, setTasks] = useState<Task[]>([]);
  const [analytics, setAnalytics] = useState<AnalyticsMatrix | null>(null);
  const [users, setUsers] = useState<User[]>([]);
  const [auditEvents, setAuditEvents] = useState<AuditEvent[]>([]);
  const [systemHealth, setSystemHealth] = useState<SystemHealth | null>(null);
  const [userForm, setUserForm] = useState(initialUser);
  const [selectedPromptId, setSelectedPromptId] = useState("");
  const [selectedBenchmark, setSelectedBenchmark] = useState("text-quick-check@1.0.0");
  const [runRequestBody, setRunRequestBody] = useState("{}");
  const [runMaxConcurrency, setRunMaxConcurrency] = useState("");
  const [runConcurrencyEdits, setRunConcurrencyEdits] = useState<Record<string, string>>({});
  const [reportType, setReportType] = useState<ReportType>("single_model");
  const [relatedReportRunId, setRelatedReportRunId] = useState("");
  const [shareForm, setShareForm] = useState(initialShare);
  const [busy, setBusy] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    const [nextEndpoints, nextRuns, nextDashboard, nextPrompts, nextDatasets, nextSuites, nextBenchmarks, nextTasks, nextAnalytics, nextUsers, nextAuditEvents, nextSystemHealth] = await Promise.all([
      api.listEndpoints(), api.listRuns(), api.dashboard(), api.listPromptPackages(), api.listDatasets(), api.listSuites(), api.listBenchmarks(), api.listTasks(), api.analyticsMatrix(), api.listUsers().catch(() => []), api.listAuditEvents().catch(() => []), api.systemHealth().catch(() => null),
    ]);
    setEndpoints(nextEndpoints);
    setRuns(nextRuns);
    setDashboard(nextDashboard);
    setPrompts(nextPrompts);
    setDatasets(nextDatasets);
    setSuites(nextSuites);
    setBenchmarks(nextBenchmarks);
    setTasks(nextTasks);
    setAnalytics(nextAnalytics);
    setUsers(nextUsers);
    setAuditEvents(nextAuditEvents);
    setSystemHealth(nextSystemHealth);
  }, []);

  useEffect(() => { void refresh().catch(showError); }, [refresh]);

  useEffect(() => {
    document.documentElement.dataset.theme = theme;
    window.localStorage.setItem("lle-theme", theme);
  }, [theme]);

  useEffect(() => {
    document.documentElement.lang = locale;
    window.localStorage.setItem("lle-locale", locale);
  }, [locale]);

  const completedRuns = useMemo(() => runs.filter((run) => run.status.startsWith("completed")), [runs]);
  const selectedRunInfo = runs.find((run) => run.id === selectedRun) ?? null;

  useEffect(() => {
    if (!selectedRun || !selectedRunInfo || !["queued", "running"].includes(selectedRunInfo.status)) return;
    const events = new EventSource(api.runEventsUrl(selectedRun));
    const update = () => {
      void selectRun(selectedRun);
      void refresh();
    };
    events.addEventListener("run", update);
    return () => events.close();
  }, [selectedRun, selectedRunInfo?.status]);

  useEffect(() => {
    if (!["queue", "workers"].includes(view)) return;
    const events = new EventSource(api.workerEventsUrl());
    const update = () => { void refresh().catch(showError); };
    events.addEventListener("worker", update);
    return () => events.close();
  }, [view, refresh]);

  function showError(error: unknown) {
    setNotice(error instanceof ApiError ? error.message : error instanceof Error ? error.message : "Unable to reach the evaluation service.");
  }

  async function createEndpoint(event: FormEvent) {
    event.preventDefault();
    setBusy("endpoint");
    try {
      const defaultRequestBody: unknown = JSON.parse(form.default_request_body);
      const customHeaders: unknown = JSON.parse(form.custom_headers);
      if (!defaultRequestBody || Array.isArray(defaultRequestBody) || typeof defaultRequestBody !== "object") {
        throw new Error("Default request body must be a JSON object.");
      }
      if (!customHeaders || Array.isArray(customHeaders) || typeof customHeaders !== "object") {
        throw new Error("Custom headers must be a JSON object.");
      }
      await api.createEndpoint({
        ...form,
        default_request_body: defaultRequestBody,
        custom_headers: customHeaders,
        tags: form.tags.split(",").map((tag) => tag.trim()).filter(Boolean),
        notes: form.notes || null,
        input_cost_per_million: optionalNumber(form.input_cost_per_million),
        output_cost_per_million: optionalNumber(form.output_cost_per_million),
        max_concurrency: Number(form.max_concurrency),
        api_key_max_concurrency: optionalNumber(form.api_key_max_concurrency),
        requests_per_second: optionalNumber(form.requests_per_second),
        requests_per_minute: optionalNumber(form.requests_per_minute),
        tokens_per_minute: optionalNumber(form.tokens_per_minute),
        input_tokens_per_minute: optionalNumber(form.input_tokens_per_minute),
        output_tokens_per_minute: optionalNumber(form.output_tokens_per_minute),
        currency: form.currency.toUpperCase(),
      });
      setForm(initialEndpoint);
      setNotice("Endpoint saved. Test its connection before starting a run.");
      await refresh();
    } catch (error) { showError(error); } finally { setBusy(null); }
  }

  async function testEndpoint(id: string) {
    setBusy(`test-${id}`);
    try {
      const result = await api.testEndpoint(id);
      setNotice(result.message);
      await refresh();
    } catch (error) { showError(error); } finally { setBusy(null); }
  }

  async function probeCapabilities(endpointId: string) {
    setBusy(`capabilities-${endpointId}`);
    try {
      const detected = await api.detectCapabilities(endpointId);
      setCapabilities((current) => ({ ...current, [endpointId]: detected }));
      setNotice("Capability probe completed. Declared capability settings were not changed.");
    } catch (error) { showError(error); } finally { setBusy(null); }
  }

  async function declareCapability(endpointId: string, capability: Capability, status: "supported" | "unsupported" | "unknown") {
    setBusy(`declare-${endpointId}-${capability.capability_key}`);
    try {
      const updated = await api.declareCapability(endpointId, capability.capability_key, status);
      setCapabilities((current) => ({ ...current, [endpointId]: (current[endpointId] ?? []).map((item) => item.capability_key === updated.capability_key ? updated : item) }));
      setNotice("User capability declaration saved alongside detection evidence.");
    } catch (error) { showError(error); } finally { setBusy(null); }
  }

  async function preflightRun(endpointId: string) {
    setBusy(`preflight-${endpointId}`);
    try {
      const [benchmarkId, benchmarkVersion] = selectedBenchmark.split("@", 2);
      const preflight = await api.validateRun(endpointId, selectedPromptId || undefined, parseJsonObject(runRequestBody, "Run Request Body override"), optionalNumber(runMaxConcurrency), benchmarkId, benchmarkVersion);
      const cost = preflight.estimated_cost === null ? "cost not configured" : `${display(preflight.estimated_cost, 6)} ${preflight.currency ?? ""}`;
      setNotice(preflight.can_queue ? `Preflight ready: ${preflight.sample_count} samples, ${preflight.estimated_requests} requests, ${preflight.estimated_input_tokens + preflight.estimated_output_tokens} estimated tokens, ${cost}.` : `Preflight blocked: ${preflight.issues.join(" ")}`);
    } catch (error) { showError(error); } finally { setBusy(null); }
  }

  async function createRun(endpointId: string) {
    setBusy(`run-${endpointId}`);
    try {
      const [benchmarkId, benchmarkVersion] = selectedBenchmark.split("@", 2);
      const run = await api.createRun(endpointId, selectedPromptId || undefined, parseJsonObject(runRequestBody, "Run Request Body override"), optionalNumber(runMaxConcurrency), benchmarkId, benchmarkVersion);
      await selectRun(run.id);
      setView("runs");
      setNotice(`${benchmarkId}@${benchmarkVersion} queued with an immutable configuration snapshot.`);
      await refresh();
    } catch (error) { showError(error); } finally { setBusy(null); }
  }

  async function changeRun(run: EvaluationRun, action: "execute" | "pause" | "resume" | "cancel" | "clone" | "rerun" | "retry" | "archive") {
    setBusy(`${action}-${run.id}`);
    try {
      const result = action === "execute" ? await api.executeRun(run.id)
        : action === "pause" ? await api.pauseRun(run.id)
          : action === "resume" ? await api.resumeRun(run.id)
            : action === "cancel" ? await api.cancelRun(run.id)
              : action === "clone" ? await api.cloneRun(run.id)
                : action === "rerun" ? await api.rerunBenchmark(run.id)
                  : action === "retry" ? await api.retryFailedRun(run.id)
                    : await api.archiveRun(run.id);
      setNotice(action === "clone" ? "Run cloned with a new immutable configuration snapshot." : action === "rerun" ? "Benchmark rerun queued with a link to its source run." : action === "retry" ? "Failed samples were queued as new attempts." : action === "archive" ? "Run archived. Its evidence remains available through the API until deleted." : `Run ${action === "execute" ? "executed" : action + "d"}.`);
      await selectRun(result.id);
      await refresh();
    } catch (error) { showError(error); } finally { setBusy(null); }
  }

  async function updateRunConcurrency(run: EvaluationRun) {
    setBusy(`run-cap-${run.id}`);
    try {
      const value = runConcurrencyEdits[run.id] ?? (run.max_concurrency?.toString() ?? "");
      const updated = await api.updateRunConcurrency(run.id, optionalNumber(value));
      setRunConcurrencyEdits((current) => ({ ...current, [run.id]: updated.max_concurrency?.toString() ?? "" }));
      setNotice("Run concurrency ceiling updated for future task claims; its evaluation snapshot remains unchanged.");
      await refresh();
    } catch (error) { showError(error); } finally { setBusy(null); }
  }

  async function updateBenchmarkStatus(benchmark: Benchmark) {
    const status = benchmark.status === "disabled" ? "enabled" : "disabled";
    setBusy(`benchmark-${benchmark.id}`);
    try {
      await api.updateBenchmark(benchmark.id, { status });
      setNotice(`${benchmark.display_name} is now ${status}.`);
      await refresh();
    } catch (error) { showError(error); } finally { setBusy(null); }
  }

  async function pauseDataset(dataset: Dataset) {
    setBusy(`dataset-${dataset.id}`);
    try {
      await api.pauseDataset(dataset.id);
      setNotice(`${dataset.dataset_id} download paused.`);
      await refresh();
    } catch (error) { showError(error); } finally { setBusy(null); }
  }

  async function selectRun(runId: string) {
    setSelectedRun(runId);
    setSelectedAttempt(null);
    setReviewAgreement(null);
    try {
      const [nextAttempts, nextSummary, nextReports, nextLogs] = await Promise.all([
        api.listAttempts(runId), api.getRunSummary(runId), api.listReports(runId), api.listRunLogs(runId),
      ]);
      setAttempts(nextAttempts);
      setRunSummary(nextSummary);
      setReports(nextReports);
      setRunLogs(nextLogs);
    } catch (error) { showError(error); }
  }

  async function loadMoreAttempts() {
    if (!selectedRun) return;
    setBusy("attempts-more");
    try {
      const next = await api.listAttempts(selectedRun, attempts.length);
      setAttempts((current) => [...current, ...next.filter((item) => !current.some((existing) => existing.id === item.id))]);
    } catch (error) { showError(error); } finally { setBusy(null); }
  }

  async function generateReport(runId: string, format: "html" | "json" | "csv" | "parquet" | "markdown" | "pdf") {
    setBusy(`report-${runId}-${format}`);
    try {
      const comparisonType = ["multi_model_comparison", "regression", "prompt_comparison"].includes(reportType);
      const report = await api.createReport(runId, format, reportType, comparisonType && relatedReportRunId ? [relatedReportRunId] : []);
      setNotice(`${format.toUpperCase()} ${reportType.replaceAll("_", " ")} report generated.`);
      window.open(api.reportDownloadUrl(report.id), "_blank", "noopener,noreferrer");
      if (selectedRun === runId) await selectRun(runId);
      await refresh();
    } catch (error) { showError(error); } finally { setBusy(null); }
  }

  async function shareReport(report: Report) {
    setBusy(`share-${report.id}`);
    try {
      const days = Math.min(365, Math.max(1, Number(shareForm.days) || 7));
      const share = await api.createReportShare(report.id, {
        expires_at: new Date(Date.now() + days * 86_400_000).toISOString(),
        password: shareForm.password || undefined,
        allow_download: shareForm.allow_download,
        include_evidence: shareForm.include_evidence,
      });
      setNotice(`Read-only share link (expires ${formatDate(share.expires_at)}): ${share.share_url}`);
    } catch (error) { showError(error); } finally { setBusy(null); }
  }

  async function createPrompt(event: FormEvent) {
    event.preventDefault();
    setBusy("prompt");
    try {
      await api.createPromptPackage({ ...promptForm, system_message: promptForm.system_message || null, few_shot_examples: parseJsonArray(promptForm.few_shot_examples, "Few-shot examples"), output_format: parseJsonObject(promptForm.output_format, "Output format"), response_parser: parseJsonObject(promptForm.response_parser, "Response parser"), scoring_rule: parseJsonObject(promptForm.scoring_rule, "Scoring rule"), change_log: promptForm.change_log || null });
      setPromptForm(initialPrompt);
      setNotice("Versioned prompt package saved.");
      await refresh();
    } catch (error) { showError(error); } finally { setBusy(null); }
  }

  async function createDataset(event: FormEvent) {
    event.preventDefault();
    setBusy("dataset");
    try {
      await api.createDataset({ ...datasetForm, source_url: datasetForm.source_url || null, checksum: datasetForm.checksum || null, credential_env_var: datasetForm.credential_env_var || null, license_text: datasetForm.license_text || null });
      setDatasetForm(initialDataset);
      setNotice("Dataset version registered.");
      await refresh();
    } catch (error) { showError(error); } finally { setBusy(null); }
  }

  async function createUser(event: FormEvent) {
    event.preventDefault();
    setBusy("user");
    try {
      const created = await api.createUser({ ...userForm, max_concurrency: optionalNumber(userForm.max_concurrency) });
      setUserForm(initialUser);
      setNotice(`User created. Copy this API token now: ${created.api_token}`);
      await refresh();
    } catch (error) { showError(error); } finally { setBusy(null); }
  }

  async function createSuite(event: FormEvent) {
    event.preventDefault();
    const benchmark_list = suiteForm.benchmarks.split(",").map((value) => value.trim()).filter(Boolean).map((value) => {
      const [benchmark_id, version = "1.0.0"] = value.split("@", 2);
      return { benchmark_id, version };
    });
    setBusy("suite");
    try { await api.createSuite({ name: suiteForm.name, version: suiteForm.version, description: suiteForm.description || null, benchmark_list, default_request_body: parseJsonObject(suiteForm.default_request_body, "Suite default request body"), default_prompt_overrides: parseJsonObject(suiteForm.default_prompt_overrides, "Suite default prompt overrides"), weight_configuration: parseJsonObject(suiteForm.weight_configuration, "Suite weight configuration") }); setSuiteForm(initialSuite); setNotice("Versioned evaluation suite saved."); await refresh(); } catch (error) { showError(error); } finally { setBusy(null); }
  }

  async function queueSuite(suiteId: string, endpointId: string) {
    setBusy(`suite-${suiteId}`);
    try { const nextRuns = await api.createSuiteRuns(suiteId, endpointId, parseJsonObject(runRequestBody, "Run Request Body override"), optionalNumber(runMaxConcurrency)); setNotice(`${nextRuns.length} suite run(s) queued.`); if (nextRuns[0]) await selectRun(nextRuns[0].id); setView("runs"); await refresh(); } catch (error) { showError(error); } finally { setBusy(null); }
  }

  async function uploadAsset(event: ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0];
    if (!file) return;
    setBusy("asset-upload");
    try {
      const dataUrl = await fileAsDataUrl(file);
      const asset = await api.uploadAsset({ filename: file.name, mime_type: file.type, base64_data: dataUrl.split(",", 2)[1] ?? "" });
      setUploadedAssets((current) => [asset, ...current.filter((item) => item.id !== asset.id)]);
      setMultimodalForm((current) => ({ ...current, asset_id: asset.id }));
      setNotice("Validated media asset uploaded and selected for the custom run.");
    } catch (error) { showError(error); } finally { setBusy(null); }
  }

  async function createMultimodalRun(event: FormEvent) {
    event.preventDefault();
    const asset = uploadedAssets.find((item) => item.id === multimodalForm.asset_id);
    if (!asset || !multimodalForm.endpoint_id) {
      setNotice("Select an available endpoint and upload or select a media asset first.");
      return;
    }
    setBusy("multimodal-run");
    try {
      const run = await api.createCustomMultimodalRun({
        model_endpoint_id: multimodalForm.endpoint_id,
        sample_id: multimodalForm.sample_id,
        reference_answer: multimodalForm.reference_answer,
        messages: [{ role: "user", content: [{ type: "text", text: multimodalForm.prompt }, { type: asset.media_kind, source: { asset_id: asset.id }, mime_type: asset.mime_type }] }],
      });
      setMultimodalForm(initialMultimodal);
      await selectRun(run.id);
      setView("runs");
      setNotice("Custom multimodal run queued with an immutable asset snapshot.");
      await refresh();
    } catch (error) { showError(error); } finally { setBusy(null); }
  }

  async function prepareDataset(dataset: Dataset) {
    setBusy(`dataset-${dataset.id}`);
    try {
      if (dataset.license_text && !dataset.license_accepted_at) {
        await api.acceptDatasetLicense(dataset.id);
        setNotice("License accepted. The dataset can now be downloaded.");
      } else {
        await api.downloadDataset(dataset.id);
        setNotice("Dataset downloaded, verified, and cached.");
      }
      await refresh();
    } catch (error) { showError(error); } finally { setBusy(null); }
  }

  async function uploadDataset(dataset: Dataset, event: ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0];
    if (!file) return;
    setBusy(`dataset-upload-${dataset.id}`);
    try {
      const dataUrl = await fileAsDataUrl(file);
      await api.uploadDataset(dataset.id, { filename: file.name, base64_data: dataUrl.split(",", 2)[1] ?? "" });
      setNotice("Dataset upload checksum verified and stored in the local dataset cache.");
      await refresh();
    } catch (error) { showError(error); } finally { setBusy(null); }
  }

  async function validateDataset(dataset: Dataset) {
    setBusy(`dataset-validate-${dataset.id}`);
    try { await api.validateDataset(dataset.id); setNotice("Dataset cache checksum and size were verified."); await refresh(); }
    catch (error) { showError(error); } finally { setBusy(null); }
  }

  async function clearDatasetCache(dataset: Dataset) {
    if (!window.confirm(`Remove the cached data for ${dataset.dataset_id} v${dataset.version}? The registered version will remain.`)) return;
    setBusy(`dataset-clear-${dataset.id}`);
    try { await api.clearDatasetCache(dataset.id); setNotice("Dataset cache removed. You can download or upload it again."); await refresh(); }
    catch (error) { showError(error); } finally { setBusy(null); }
  }

  async function compareRuns(event: FormEvent) {
    event.preventDefault();
    if (!comparisonRunA || !comparisonRunB || comparisonRunA === comparisonRunB) {
      setNotice("Choose two different runs from the same benchmark version.");
      return;
    }
    setBusy("compare");
    try {
      setComparison(await api.compare(comparisonRunA, comparisonRunB));
    } catch (error) { showError(error); } finally { setBusy(null); }
  }

  async function openReview(attempt: SampleAttempt) {
    setSelectedAttempt(attempt);
    setBusy(`review-${attempt.id}`);
    try { const [nextReviews, nextAgreement, nextJudges, nextJudgeAgreement] = await Promise.all([api.listReviews(attempt.id), api.getReviewAgreement(attempt.id), api.listJudgeAssessments(attempt.id), api.getJudgeAgreement(attempt.id)]); setReviews(nextReviews); setReviewAgreement(nextAgreement); setJudgeAssessments(nextJudges); setJudgeAgreement(nextJudgeAgreement); } catch (error) { showError(error); } finally { setBusy(null); }
  }

  async function createReview(event: FormEvent) {
    event.preventDefault();
    if (!selectedAttempt) return;
    setBusy("review-submit");
    try {
      const labels = reviewForm.labels.split(",").map((label) => label.trim()).filter(Boolean);
      await api.createReview({
        sample_attempt_id: selectedAttempt.id,
        reviewer_id: reviewForm.reviewer_id,
        rubric: parseJsonObject(reviewForm.rubric, "Human-review rubric"),
        score: reviewForm.score === "" ? null : Number(reviewForm.score),
        labels,
        notes: reviewForm.notes || null,
        review_stage: reviewForm.review_stage,
        adjudicates_review_ids: reviewForm.review_stage === "adjudication" ? reviews.filter((review) => review.review_stage !== "adjudication").map((review) => review.id) : [],
      });
      setReviewForm(initialReview);
      const [nextReviews, nextAgreement] = await Promise.all([api.listReviews(selectedAttempt.id), api.getReviewAgreement(selectedAttempt.id)]);
      setReviews(nextReviews);
      setReviewAgreement(nextAgreement);
      setNotice("Human review saved separately from automated results.");
    } catch (error) { showError(error); } finally { setBusy(null); }
  }

  async function createJudgeAssessment(event: FormEvent) {
    event.preventDefault();
    if (!selectedAttempt || !judgeForm.endpoint_id) return;
    setBusy("judge-submit");
    try {
      const payload = { sample_attempt_id: selectedAttempt.id, judge_endpoint_id: judgeForm.endpoint_id, rubric: parseJsonObject(judgeForm.rubric, "Judge rubric") };
      if (judgeForm.comparison_attempt_id.trim()) await api.createJudgeComparison({ ...payload, comparison_sample_attempt_id: judgeForm.comparison_attempt_id.trim(), swap_test: judgeForm.swap_test });
      else await api.createJudgeAssessment(payload);
      const [nextAssessments, nextAgreement] = await Promise.all([api.listJudgeAssessments(selectedAttempt.id), api.getJudgeAgreement(selectedAttempt.id)]);
      setJudgeAssessments(nextAssessments);
      setJudgeAgreement(nextAgreement);
      setNotice(judgeForm.comparison_attempt_id.trim() ? "Blinded pairwise judge evidence and swap-test results saved." : "Independent LLM-as-judge assessment saved with rationale evidence.");
    } catch (error) { showError(error); } finally { setBusy(null); }
  }

  async function updateTaskPriority(task: Task, priority: number) {
    setBusy(`task-${task.id}`);
    try {
      const updated = await api.updateTaskPriority(task.id, priority);
      setTasks((current) => current.map((item) => item.id === updated.id ? updated : item));
      setNotice(`Task priority updated to ${updated.priority}.`);
    } catch (error) { showError(error); } finally { setBusy(null); }
  }

  return (
    <main>
      <header className="hero">
        <div>
          <p className="eyebrow">Evaluation workspace</p>
          <h1>LLM / SLM Evaluation Platform</h1>
          <p>Reproducible runs, durable evidence, and cost-aware model decisions.</p>
        </div>
        <div className="actions"><button className="secondary" aria-pressed={theme === "light"} onClick={() => setTheme(theme === "dark" ? "light" : "dark")}>{theme === "dark" ? "Light mode" : "Dark mode"}</button><div className="metric"><strong>{dashboard?.runs.completed ?? 0}</strong><span>completed runs</span></div></div>
      </header>

      <nav className="tabs" aria-label="Workspace sections">
        {(["dashboard", "models", "capabilities", "workspace", "benchmarks", "datasets", "suites", "runs", "queue", "workers", "analysis", "compare", "reports", "reviews", "users", "settings"] as View[]).map((item) => (
          <button className={view === item ? "tab selected" : "tab"} key={item} onClick={() => setView(item)}>{navigationLabels[locale][item]}</button>
        ))}
      </nav>
      {notice && <button className="notice" onClick={() => setNotice(null)}>{notice}<span>Dismiss</span></button>}

      {view === "dashboard" && <DashboardView dashboard={dashboard} onRun={(runId) => { void selectRun(runId); setView("runs"); }} />}

      {view === "models" && <>
        <section className="grid two">
          <article className="panel">
            <h2>Add model endpoint</h2>
            <form onSubmit={createEndpoint} className="form">
              <label>Display name<input value={form.display_name} onChange={(event) => setForm({ ...form, display_name: event.target.value })} placeholder="My local model" /></label>
              <label>Base URL<input required type="url" value={form.base_url} onChange={(event) => setForm({ ...form, base_url: event.target.value })} placeholder="https://provider.example/v1" /></label>
              <label>Model name<input required value={form.model_name} onChange={(event) => setForm({ ...form, model_name: event.target.value })} placeholder="model-id" /></label>
              <label>Protocol profile<select value={form.protocol_profile} onChange={(event) => setForm({ ...form, protocol_profile: event.target.value as Endpoint["protocol_profile"] })}><option value="openai_chat_completions">OpenAI-compatible Chat Completions</option><option value="openai_responses">OpenAI-compatible Responses API</option><option value="anthropic_messages">Anthropic Messages</option><option value="gemini_generate_content">Gemini GenerateContent</option><option value="azure_openai_chat_completions">Azure OpenAI Chat Completions</option><option value="ollama_chat">Ollama Chat</option><option value="custom_http_json">Custom HTTP JSON</option></select></label>
              <label>API key<input required={form.protocol_profile !== "ollama_chat"} type="password" value={form.api_key} onChange={(event) => setForm({ ...form, api_key: event.target.value })} placeholder={form.protocol_profile === "ollama_chat" ? "Optional for a local Ollama service" : "Stored encrypted"} /></label>
              <label>Custom headers (JSON)<textarea value={form.custom_headers} onChange={(event) => setForm({ ...form, custom_headers: event.target.value })} spellCheck={false} placeholder='{"X-Provider-Project":"project-id"}' /></label>
              <label>Default request body (JSON)<textarea value={form.default_request_body} onChange={(event) => setForm({ ...form, default_request_body: event.target.value })} spellCheck={false} /></label>
              <div className="field-row"><label>Endpoint concurrency<input required type="number" min="1" max="1000" value={form.max_concurrency} onChange={(event) => setForm({ ...form, max_concurrency: event.target.value })} /></label><label>Shared API-key concurrency<input type="number" min="1" max="1000" value={form.api_key_max_concurrency} onChange={(event) => setForm({ ...form, api_key_max_concurrency: event.target.value })} placeholder="Unlimited" /></label><label>Requests / minute<input type="number" min="1" value={form.requests_per_minute} onChange={(event) => setForm({ ...form, requests_per_minute: event.target.value })} placeholder="Unlimited" /></label><label>Tokens / minute<input type="number" min="1" value={form.tokens_per_minute} onChange={(event) => setForm({ ...form, tokens_per_minute: event.target.value })} placeholder="Unlimited" /></label></div>
              <div className="field-row"><label>Requests / second<input type="number" min="1" value={form.requests_per_second} onChange={(event) => setForm({ ...form, requests_per_second: event.target.value })} placeholder="Unlimited" /></label><label>Input tokens / minute<input type="number" min="1" value={form.input_tokens_per_minute} onChange={(event) => setForm({ ...form, input_tokens_per_minute: event.target.value })} placeholder="Unlimited" /></label><label>Output tokens / minute<input type="number" min="1" value={form.output_tokens_per_minute} onChange={(event) => setForm({ ...form, output_tokens_per_minute: event.target.value })} placeholder="Unlimited" /></label></div>
              <div className="field-row"><label>Input / 1M tokens<input type="number" min="0" step="any" value={form.input_cost_per_million} onChange={(event) => setForm({ ...form, input_cost_per_million: event.target.value })} /></label><label>Output / 1M tokens<input type="number" min="0" step="any" value={form.output_cost_per_million} onChange={(event) => setForm({ ...form, output_cost_per_million: event.target.value })} /></label><label>Currency<input value={form.currency} onChange={(event) => setForm({ ...form, currency: event.target.value })} maxLength={8} /></label></div>
              <label>Tags (comma-separated)<input value={form.tags} onChange={(event) => setForm({ ...form, tags: event.target.value })} placeholder="production, vision" /></label><label>Notes<textarea value={form.notes} onChange={(event) => setForm({ ...form, notes: event.target.value })} /></label>
              <button disabled={busy === "endpoint"}>{busy === "endpoint" ? "Saving..." : "Save encrypted endpoint"}</button>
            </form>
          </article>
          <article className="panel">
            <h2>Run configuration</h2>
            <label className="select-label">Benchmark pack<select value={selectedBenchmark} onChange={(event) => setSelectedBenchmark(event.target.value)}>{benchmarks.filter((benchmark) => !["disabled", "deprecated", "broken"].includes(benchmark.status)).map((benchmark) => <option key={benchmark.id} value={`${benchmark.benchmark_id}@${benchmark.version}`}>{benchmark.display_name} v{benchmark.version}</option>)}</select></label>
            <label className="select-label">Prompt package for a new run<select value={selectedPromptId} onChange={(event) => setSelectedPromptId(event.target.value)}><option value="">Built-in benchmark prompt</option>{prompts.map((prompt) => <option key={prompt.id} value={prompt.id}>{prompt.name} v{prompt.version}</option>)}</select></label>
            <label>Run Request Body override (JSON)<textarea value={runRequestBody} onChange={(event) => setRunRequestBody(event.target.value)} spellCheck={false} placeholder='{"temperature":0}' /></label>
            <label>Run concurrency cap<input type="number" min="1" max="1000" value={runMaxConcurrency} onChange={(event) => setRunMaxConcurrency(event.target.value)} placeholder="Use endpoint capacity" /></label>
            <p className="muted">Connection tests and execution use the saved endpoint. The run override is merged after suite and benchmark defaults; benchmark-forced fields still win. API keys never return to the browser.</p>
          </article>
        </section>
        <section className="panel"><div className="section-title"><h2>Models</h2><span>{endpoints.length} configured</span></div>
          {endpoints.length === 0 ? <p className="empty">No model endpoints yet.</p> : <div className="cards">{endpoints.map((endpoint) => <article className="card" key={endpoint.id}>
            <div><h3>{endpoint.display_name}</h3><p>{endpoint.model_name} · {endpoint.api_key_mask}</p><p className="muted">{endpoint.base_url}</p></div>
            <div className="split"><span className={`badge ${endpoint.status}`}>{endpoint.status}</span><span className="muted">{endpoint.max_concurrency} endpoint / {endpoint.api_key_max_concurrency ?? "∞"} shared-key concurrent · {money(endpoint.input_cost_per_million, endpoint.currency)} in / 1M</span></div>
            <div className="actions"><button className="secondary" disabled={busy === `test-${endpoint.id}`} onClick={() => void testEndpoint(endpoint.id)}>Test connection</button><button className="secondary" disabled={busy === `capabilities-${endpoint.id}`} onClick={() => void probeCapabilities(endpoint.id)}>Probe capabilities</button><button disabled={endpoint.status !== "available" || busy === `run-${endpoint.id}`} onClick={() => void createRun(endpoint.id)}>Queue selected benchmark</button></div>
            {capabilities[endpoint.id] && <div className="capability-list">{capabilities[endpoint.id].map((item) => <label key={item.id}>{item.capability_key}<select value={item.user_declared_status} disabled={busy === `declare-${endpoint.id}-${item.capability_key}`} onChange={(event) => void declareCapability(endpoint.id, item, event.target.value as "supported" | "unsupported" | "unknown")}><option value="unknown">User: unknown</option><option value="supported">User: supported</option><option value="unsupported">User: unsupported</option></select><small>{item.auto_detection_status} · {item.effective_status}</small></label>)}</div>}
          </article>)}</div>}
        </section>
      </>}

      {view === "capabilities" && <section className="panel"><div className="section-title"><h2>Model capabilities</h2><span>Detection evidence and user declarations remain separate.</span></div>{endpoints.length === 0 ? <p className="empty">Add a model endpoint before probing capabilities.</p> : <div className="cards">{endpoints.map((endpoint) => <article className="card" key={endpoint.id}><h3>{endpoint.display_name}</h3><div className="actions"><button className="secondary" disabled={busy === `capabilities-${endpoint.id}`} onClick={() => void probeCapabilities(endpoint.id)}>Probe capabilities</button></div>{capabilities[endpoint.id] ? <div className="capability-list">{capabilities[endpoint.id].map((item) => <label key={item.id}>{item.capability_key}<select value={item.user_declared_status} onChange={(event) => void declareCapability(endpoint.id, item, event.target.value as "supported" | "unsupported" | "unknown")}><option value="unknown">User: unknown</option><option value="supported">User: supported</option><option value="unsupported">User: unsupported</option></select><small>{item.auto_detection_status} · {item.effective_status}</small></label>)}</div> : <p className="muted">No probe result loaded yet.</p>}</article>)}</div>}</section>}

      {view === "benchmarks" && <section className="panel"><div className="section-title"><h2>Benchmarks</h2><span>{benchmarks.length} registered versions</span></div><div className="table-wrap"><table><thead><tr><th>Benchmark</th><th>Version</th><th>Source</th><th>Status</th><th>Modalities</th><th>Operation</th></tr></thead><tbody>{benchmarks.map((benchmark) => <tr key={benchmark.id}><td>{benchmark.display_name}</td><td>{benchmark.version}</td><td>{benchmark.source}</td><td><span className={`badge ${benchmark.status}`}>{benchmark.status}</span></td><td>{Array.isArray(benchmark.manifest.modalities) ? benchmark.manifest.modalities.join(", ") : "--"}</td><td>{["registered", "enabled", "disabled"].includes(benchmark.status) ? <button className="secondary" disabled={busy === `benchmark-${benchmark.id}`} onClick={() => void updateBenchmarkStatus(benchmark)}>{benchmark.status === "disabled" ? "Enable" : "Disable"}</button> : "Managed by pack"}</td></tr>)}</tbody></table></div></section>}

      {view === "datasets" && <DatasetCatalog datasets={datasets} busy={busy} onPrepare={prepareDataset} onPause={pauseDataset} onUpload={uploadDataset} onValidate={validateDataset} onClear={clearDatasetCache} />}

      {view === "suites" && <section className="panel"><div className="section-title"><h2>Evaluation suites</h2><span>{suites.length} versioned suites</span></div>{suites.length === 0 ? <p className="empty">Create a suite from the Workspace catalog.</p> : <div className="cards">{suites.map((suite) => <article className="card" key={suite.id}><h3>{suite.name} v{suite.version}</h3><p className="muted">{suite.benchmark_list.map((item) => `${item.benchmark_id ?? "benchmark"}@${item.version ?? ""}`).join(", ")}</p>{endpoints.filter((endpoint) => endpoint.status === "available").map((endpoint) => <button key={endpoint.id} disabled={busy === `suite-${suite.id}`} onClick={() => void queueSuite(suite.id, endpoint.id)}>Queue on {endpoint.display_name}</button>)}</article>)}</div>}</section>}

      {view === "workspace" && <>
        <section className="grid two">
          <article className="panel"><h2>Create prompt package</h2><form onSubmit={createPrompt} className="form"><label>Name<input required value={promptForm.name} onChange={(event) => setPromptForm({ ...promptForm, name: event.target.value })} /></label><label>Version<input required value={promptForm.version} onChange={(event) => setPromptForm({ ...promptForm, version: event.target.value })} /></label><label>Prompt type<select value={promptForm.prompt_type} onChange={(event) => setPromptForm({ ...promptForm, prompt_type: event.target.value })}><option value="official">Official prompt</option><option value="platform_default">Platform default</option><option value="user_custom">User custom</option><option value="benchmark_variant">Benchmark variant</option><option value="language_specific">Language-specific</option></select></label><label>System message<textarea value={promptForm.system_message} onChange={(event) => setPromptForm({ ...promptForm, system_message: event.target.value })} /></label><label>User template<textarea required value={promptForm.user_template} onChange={(event) => setPromptForm({ ...promptForm, user_template: event.target.value })} placeholder="{{ question }}, {{ context }}, {{ image }}, {{ audio }}, {{ video }}, {{ language }}" /></label><label>Few-shot examples (JSON array)<textarea value={promptForm.few_shot_examples} onChange={(event) => setPromptForm({ ...promptForm, few_shot_examples: event.target.value })} spellCheck={false} /></label><label>Output format (JSON)<textarea value={promptForm.output_format} onChange={(event) => setPromptForm({ ...promptForm, output_format: event.target.value })} spellCheck={false} /></label><label>Response parser (JSON)<textarea value={promptForm.response_parser} onChange={(event) => setPromptForm({ ...promptForm, response_parser: event.target.value })} spellCheck={false} /></label><label>Scoring rule (JSON)<textarea value={promptForm.scoring_rule} onChange={(event) => setPromptForm({ ...promptForm, scoring_rule: event.target.value })} spellCheck={false} /></label><label>Change log<textarea value={promptForm.change_log} onChange={(event) => setPromptForm({ ...promptForm, change_log: event.target.value })} /></label><button disabled={busy === "prompt"}>Save versioned prompt</button></form></article>
          <article className="panel"><h2>Register dataset version</h2><form onSubmit={createDataset} className="form"><label>Dataset ID<input required value={datasetForm.dataset_id} onChange={(event) => setDatasetForm({ ...datasetForm, dataset_id: event.target.value })} /></label><div className="field-row"><label>Version<input required value={datasetForm.version} onChange={(event) => setDatasetForm({ ...datasetForm, version: event.target.value })} /></label><label>Revision<input required value={datasetForm.revision} onChange={(event) => setDatasetForm({ ...datasetForm, revision: event.target.value })} /></label></div><label>Source URL or local path<input value={datasetForm.source_url} onChange={(event) => setDatasetForm({ ...datasetForm, source_url: event.target.value })} placeholder="https://…, hf://owner/repository/path, or file:///…" /></label><label>Expected SHA-256 checksum<input value={datasetForm.checksum} onChange={(event) => setDatasetForm({ ...datasetForm, checksum: event.target.value })} placeholder="Optional; calculated after first verified download" /></label><label>Credential environment variable<input value={datasetForm.credential_env_var} onChange={(event) => setDatasetForm({ ...datasetForm, credential_env_var: event.target.value.toUpperCase() })} placeholder="Optional, e.g. HUGGINGFACE_TOKEN" /></label><label>License text<textarea value={datasetForm.license_text} onChange={(event) => setDatasetForm({ ...datasetForm, license_text: event.target.value })} /></label><button disabled={busy === "dataset"}>Register dataset</button></form></article>
        </section>
        <section className="grid two"><article className="panel"><h2>Custom multimodal quick check</h2><form className="form" onSubmit={createMultimodalRun}><label>Endpoint<select required value={multimodalForm.endpoint_id} onChange={(event) => setMultimodalForm({ ...multimodalForm, endpoint_id: event.target.value })}><option value="">Select available endpoint</option>{endpoints.filter((endpoint) => endpoint.status === "available").map((endpoint) => <option key={endpoint.id} value={endpoint.id}>{endpoint.display_name} · {endpoint.model_name}</option>)}</select></label><label>Sample ID<input required value={multimodalForm.sample_id} onChange={(event) => setMultimodalForm({ ...multimodalForm, sample_id: event.target.value })} /></label><label>Prompt<textarea required value={multimodalForm.prompt} onChange={(event) => setMultimodalForm({ ...multimodalForm, prompt: event.target.value })} placeholder="Describe or answer a question about the attached media." /></label><label>Expected text answer<textarea required value={multimodalForm.reference_answer} onChange={(event) => setMultimodalForm({ ...multimodalForm, reference_answer: event.target.value })} /></label><label>Uploaded media<select required value={multimodalForm.asset_id} onChange={(event) => setMultimodalForm({ ...multimodalForm, asset_id: event.target.value })}><option value="">Upload an asset first</option>{uploadedAssets.map((asset) => <option key={asset.id} value={asset.id}>{asset.original_filename} · {asset.media_kind}</option>)}</select></label><button disabled={busy === "multimodal-run"}>Queue multimodal run</button></form></article><article className="panel"><h2>Media asset upload</h2><p className="muted">Files are validated by MIME signature, content-addressed, and stored outside browser memory before they enter a run snapshot.</p><label className="file-picker">Choose image, audio, video, or PDF<input type="file" accept="image/png,image/jpeg,image/gif,image/webp,audio/wav,audio/mpeg,video/mp4,video/webm,application/pdf" onChange={(event) => void uploadAsset(event)} /></label>{busy === "asset-upload" && <p className="muted">Uploading and validating asset...</p>}{uploadedAssets.length > 0 && <div className="asset-list">{uploadedAssets.map((asset) => <button className={multimodalForm.asset_id === asset.id ? "asset selected" : "asset"} key={asset.id} onClick={() => setMultimodalForm({ ...multimodalForm, asset_id: asset.id })}><strong>{asset.original_filename}</strong><span>{asset.media_kind} · {display(asset.size_bytes)} bytes</span></button>)}</div>}</article></section>
        <section className="grid two"><article className="panel"><h2>Create evaluation suite</h2><form onSubmit={createSuite} className="form"><label>Name<input required value={suiteForm.name} onChange={(event) => setSuiteForm({ ...suiteForm, name: event.target.value })} /></label><label>Version<input required value={suiteForm.version} onChange={(event) => setSuiteForm({ ...suiteForm, version: event.target.value })} /></label><label>Benchmarks (id@version)<input required value={suiteForm.benchmarks} onChange={(event) => setSuiteForm({ ...suiteForm, benchmarks: event.target.value })} /></label><label>Suite default Request Body (JSON)<textarea value={suiteForm.default_request_body} onChange={(event) => setSuiteForm({ ...suiteForm, default_request_body: event.target.value })} spellCheck={false} /></label><label>Prompt overrides (JSON)<textarea value={suiteForm.default_prompt_overrides} onChange={(event) => setSuiteForm({ ...suiteForm, default_prompt_overrides: event.target.value })} spellCheck={false} /></label><label>Weight configuration (JSON)<textarea value={suiteForm.weight_configuration} onChange={(event) => setSuiteForm({ ...suiteForm, weight_configuration: event.target.value })} spellCheck={false} /></label><label>Description<textarea value={suiteForm.description} onChange={(event) => setSuiteForm({ ...suiteForm, description: event.target.value })} /></label><button disabled={busy === "suite"}>Save suite</button></form></article><article className="panel"><h2>Evaluation suites</h2>{suites.length === 0 ? <p className="empty">No suites have been created.</p> : <div className="cards">{suites.map((suite) => <article className="card" key={suite.id}><h3>{suite.name} v{suite.version}</h3><p className="muted">{suite.benchmark_list.map((item) => `${item.benchmark_id ?? "benchmark"}@${item.version ?? ""}`).join(", ")}</p>{endpoints.filter((endpoint) => endpoint.status === "available").map((endpoint) => <button key={endpoint.id} disabled={busy === `suite-${suite.id}`} onClick={() => void queueSuite(suite.id, endpoint.id)}>Queue on {endpoint.display_name}</button>)}</article>)}</div>}</article></section>
        <section className="panel"><div className="section-title"><h2>Benchmark registry</h2><span>{benchmarks.length} registered</span></div><div className="table-wrap"><table><thead><tr><th>Benchmark</th><th>Version</th><th>Source</th><th>Status</th></tr></thead><tbody>{benchmarks.map((benchmark) => <tr key={benchmark.id}><td>{benchmark.display_name}</td><td>{benchmark.version}</td><td>{benchmark.source}</td><td><span className={`badge ${benchmark.status}`}>{benchmark.status}</span></td></tr>)}</tbody></table></div></section>
        <section className="panel"><div className="section-title"><h2>Dataset cache</h2><span>{datasets.length} registered</span></div>{datasets.length === 0 ? <p className="empty">Register a dataset version to manage downloads and licenses.</p> : <div className="cards">{datasets.map((dataset) => <article className="card" key={dataset.id}><div><h3>{dataset.dataset_id} v{dataset.version}</h3><p className="muted">{dataset.source_url || "No source URL"}</p>{dataset.error_message && <p className="error">{dataset.error_message}</p>}</div><span className={`badge ${dataset.status}`}>{dataset.status}</span>{dataset.status !== "ready" && <div className="actions"><button disabled={busy === `dataset-${dataset.id}`} onClick={() => void prepareDataset(dataset)}>{dataset.license_text && !dataset.license_accepted_at ? "Accept license" : "Download and verify"}</button></div>}</article>)}</div>}</section>
      </>}

      {view === "runs" && <>
        <section className="panel"><div className="section-title"><h2>Run preflight</h2><span>Validate compatibility and estimate work without creating a queue entry.</span></div><div className="actions">{endpoints.filter((endpoint) => endpoint.status === "available").map((endpoint) => <button className="secondary" key={endpoint.id} disabled={busy === `preflight-${endpoint.id}`} onClick={() => void preflightRun(endpoint.id)}>{busy === `preflight-${endpoint.id}` ? "Checking…" : `Preflight ${endpoint.display_name}`}</button>)}</div></section>
        <section className="panel"><div className="section-title"><h2>Evaluation runs</h2><span>{runs.length} total</span></div>{runs.length === 0 ? <p className="empty">Verify a model endpoint to create the first run.</p> : <div className="run-list">{runs.map((run) => <article className={`run ${selectedRun === run.id ? "selected" : ""}`} key={run.id}><button className="run-summary" onClick={() => void selectRun(run.id)}><strong>{run.benchmark_id} v{run.benchmark_version}</strong><span>{run.status} · {run.completed_samples}/{run.total_samples} samples · {formatDate(run.created_at)}</span></button><div className="actions"><button className="secondary" onClick={() => void selectRun(run.id)}>Inspect</button>{!["completed", "completed_with_errors", "cancelled", "failed"].includes(run.status) && <><label className="compact-field">Run cap<input type="number" min="1" max="1000" value={runConcurrencyEdits[run.id] ?? (run.max_concurrency?.toString() ?? "")} onChange={(event) => setRunConcurrencyEdits((current) => ({ ...current, [run.id]: event.target.value }))} placeholder="Endpoint" /></label><button className="secondary" disabled={busy === `run-cap-${run.id}`} onClick={() => void updateRunConcurrency(run)}>Set cap</button></>}{run.status === "queued" && <button disabled={busy === `execute-${run.id}`} onClick={() => void changeRun(run, "execute")}>Execute</button>}{["queued", "running"].includes(run.status) && <button className="secondary" disabled={busy === `pause-${run.id}`} onClick={() => void changeRun(run, "pause")}>Pause</button>}{run.status === "paused" && <button disabled={busy === `resume-${run.id}`} onClick={() => void changeRun(run, "resume")}>Resume</button>}{run.status.startsWith("completed") && <><button className="secondary" disabled={busy === `clone-${run.id}`} onClick={() => void changeRun(run, "clone")}>Clone</button><button className="secondary" disabled={busy === `rerun-${run.id}`} onClick={() => void changeRun(run, "rerun")}>Rerun benchmark</button></>}{run.status === "completed_with_errors" && <button disabled={busy === `retry-${run.id}`} onClick={() => void changeRun(run, "retry")}>Retry failed</button>}{["completed", "completed_with_errors", "cancelled", "failed"].includes(run.status) && <button className="secondary" disabled={busy === `archive-${run.id}`} onClick={() => void changeRun(run, "archive")}>Archive</button>}{!["completed", "completed_with_errors", "cancelled", "failed"].includes(run.status) && <button className="danger" disabled={busy === `cancel-${run.id}`} onClick={() => void changeRun(run, "cancel")}>Cancel</button>}</div></article>)}</div>}</section>
        {selectedRunInfo && <RunDetail run={selectedRunInfo} summary={runSummary} logs={runLogs} attempts={attempts} reports={reports} selectedAttempt={selectedAttempt} reviews={reviews} reviewAgreement={reviewAgreement} judgeAssessments={judgeAssessments} judgeAgreement={judgeAgreement} judgeForm={judgeForm} endpoints={endpoints} reviewForm={reviewForm} busy={busy} onJudgeForm={setJudgeForm} onReviewForm={setReviewForm} onReview={openReview} onLoadMoreAttempts={loadMoreAttempts} onCreateJudgeAssessment={createJudgeAssessment} onCreateReview={createReview} onGenerateReport={generateReport} />}
      </>}

      {view === "queue" && <section className="panel"><div className="section-title"><h2>Task queue</h2><span>{tasks.length} tasks loaded · virtualized</span></div>{tasks.length === 0 ? <p className="empty">No queued work exists.</p> : <VirtualTaskQueue tasks={tasks} busy={busy} onPriority={updateTaskPriority} />}</section>}

      {view === "workers" && <section className="panel"><div className="section-title"><h2>Workers</h2><span>Live updates are streamed from the worker event channel.</span></div>{tasks.length === 0 ? <p className="empty">No worker leases are active.</p> : <div className="table-wrap"><table><thead><tr><th>Worker</th><th>Task</th><th>Run</th><th>State</th><th>Lease expiry</th></tr></thead><tbody>{tasks.filter((task) => ["leased", "running"].includes(task.status)).map((task) => <tr key={task.id}><td>{task.leased_by ?? "--"}</td><td>{task.task_type}</td><td>{task.run_id.slice(0, 8)}</td><td><span className={`badge ${task.status}`}>{task.status}</span></td><td>{formatDate(task.lease_expires_at)}</td></tr>)}</tbody></table></div>}</section>}

      {view === "analysis" && <AnalysisView analytics={analytics} completedRuns={completedRuns} />}

      {view === "compare" && <section className="panel"><h2>Model and run comparison</h2><p className="muted">Runs must use the same benchmark version. Differences are run A minus run B.</p><form className="comparison-form" onSubmit={compareRuns}><label>Run A<select required value={comparisonRunA} onChange={(event) => setComparisonRunA(event.target.value)}><option value="">Select completed run</option>{completedRuns.map((run) => <option key={run.id} value={run.id}>{run.benchmark_id} · {run.id.slice(0, 8)} · {formatDate(run.completed_at)}</option>)}</select></label><label>Run B<select required value={comparisonRunB} onChange={(event) => setComparisonRunB(event.target.value)}><option value="">Select completed run</option>{completedRuns.map((run) => <option key={run.id} value={run.id}>{run.benchmark_id} · {run.id.slice(0, 8)} · {formatDate(run.completed_at)}</option>)}</select></label><button disabled={busy === "compare"}>Compare</button></form>{comparison && <ComparisonView comparison={comparison} />}</section>}

      {view === "reports" && <section className="panel"><h2>Reports</h2>{selectedRunInfo ? <><p>Generate a portable report for <strong>{selectedRunInfo.benchmark_id}</strong>, or download previous artifacts.</p><div className="comparison-form"><label>Report type<select value={reportType} onChange={(event) => setReportType(event.target.value as ReportType)}><option value="single_model">Single-model complete</option><option value="multi_model_comparison">Multi-model comparison</option><option value="regression">Regression</option><option value="prompt_comparison">Prompt comparison</option><option value="benchmark">Benchmark</option><option value="reliability">Reliability</option><option value="cost">Cost</option><option value="human_review">Human review</option></select></label>{["multi_model_comparison", "regression", "prompt_comparison"].includes(reportType) && <label>Related completed run<select value={relatedReportRunId} onChange={(event) => setRelatedReportRunId(event.target.value)}><option value="">Select run</option>{completedRuns.filter((run) => run.id !== selectedRunInfo.id).map((run) => <option key={run.id} value={run.id}>{run.benchmark_id} · {run.id.slice(0, 8)}</option>)}</select></label>}</div><div className="actions"><button onClick={() => void generateReport(selectedRunInfo.id, "html")}>Generate HTML</button><button className="secondary" onClick={() => void generateReport(selectedRunInfo.id, "markdown")}>Generate Markdown</button><button className="secondary" onClick={() => void generateReport(selectedRunInfo.id, "pdf")}>Generate PDF</button><button className="secondary" onClick={() => void generateReport(selectedRunInfo.id, "json")}>Generate JSON</button><button className="secondary" onClick={() => void generateReport(selectedRunInfo.id, "csv")}>Generate CSV</button><button className="secondary" onClick={() => void generateReport(selectedRunInfo.id, "parquet")}>Generate Parquet</button></div><ReportsTable reports={reports} onShare={shareReport} /></> : <p className="empty">Choose a run in the Runs page before generating a report.</p>}</section>}

      {view === "reviews" && <section className="panel"><div className="section-title"><h2>Human review</h2><span>Reviewer scores remain separate from deterministic and judge evidence.</span></div>{selectedRunInfo ? <RunDetail run={selectedRunInfo} summary={runSummary} logs={runLogs} attempts={attempts} reports={[]} selectedAttempt={selectedAttempt} reviews={reviews} reviewAgreement={reviewAgreement} judgeAssessments={judgeAssessments} judgeAgreement={judgeAgreement} judgeForm={judgeForm} endpoints={endpoints} reviewForm={reviewForm} busy={busy} onJudgeForm={setJudgeForm} onReviewForm={setReviewForm} onReview={openReview} onLoadMoreAttempts={loadMoreAttempts} onCreateJudgeAssessment={createJudgeAssessment} onCreateReview={createReview} onGenerateReport={generateReport} /> : <p className="empty">Select a run and sample from the Runs page to review it.</p>}</section>}

      {view === "users" && <section className="grid two"><article className="panel"><h2>Create user</h2><form className="form" onSubmit={createUser}><label>Email<input required type="email" value={userForm.email} onChange={(event) => setUserForm({ ...userForm, email: event.target.value })} /></label><label>Display name<input required value={userForm.display_name} onChange={(event) => setUserForm({ ...userForm, display_name: event.target.value })} /></label><label>Role<select value={userForm.role} onChange={(event) => setUserForm({ ...userForm, role: event.target.value })}><option value="viewer">Viewer</option><option value="reviewer">Reviewer</option><option value="evaluator">Evaluator</option><option value="admin">Admin</option></select></label><label>User concurrency cap<input type="number" min="1" max="1000" value={userForm.max_concurrency} onChange={(event) => setUserForm({ ...userForm, max_concurrency: event.target.value })} placeholder="Unlimited" /></label><button disabled={busy === "user"}>Create API-token user</button></form></article><article className="panel"><h2>Users and audit trail</h2>{users.length === 0 ? <p className="empty">User administration needs an administrator bearer token when server authentication is enabled.</p> : <div className="table-wrap"><table><thead><tr><th>User</th><th>Role</th><th>Cap</th><th>Status</th><th>Created</th></tr></thead><tbody>{users.map((user) => <tr key={user.id}><td>{user.display_name}<br /><small>{user.email}</small></td><td>{user.role}</td><td>{user.max_concurrency ?? "∞"}</td><td>{user.status}</td><td>{formatDate(user.created_at)}</td></tr>)}</tbody></table></div>}<h3>Recent audit events</h3>{auditEvents.length === 0 ? <p className="empty">No events available.</p> : <div className="table-wrap"><table><thead><tr><th>Action</th><th>Entity</th><th>When</th></tr></thead><tbody>{auditEvents.slice(0, 12).map((event) => <tr key={event.id}><td>{event.action}</td><td>{event.entity_type}</td><td>{formatDate(event.created_at)}</td></tr>)}</tbody></table></div>}</article></section>}

      {view === "settings" && <section className="grid two"><article className="panel"><h2>System settings</h2><p className="muted">Runtime settings are configured through the deployment environment; sensitive values never return to the browser.</p><dl><dt>Database</dt><dd>{systemHealth?.database ?? "Unavailable"} · {systemHealth?.database_connected ? "connected" : "unavailable"}</dd><dt>Schema version</dt><dd>{systemHealth?.schema_version ?? "--"}</dd><dt>Health</dt><dd>{systemHealth?.status ?? "Unavailable"}</dd><dt>Queue</dt><dd>{systemHealth ? `${systemHealth.queue.pending} pending · ${systemHealth.queue.active} active` : "--"}</dd><dt>Disk</dt><dd>{systemHealth ? `${display(systemHealth.disk.available_bytes)} free of ${display(systemHealth.disk.total_bytes)}` : "--"}</dd><dt>Theme</dt><dd>{theme}</dd></dl><label>Workspace language<select value={locale} onChange={(event) => setLocale(event.target.value as Locale)}><option value="en">English</option><option value="zh-CN">简体中文</option></select></label><label>Administrator or user bearer token<input type="password" value={apiToken} onChange={(event) => setApiToken(event.target.value)} placeholder="Optional when server auth is enabled" /></label><div className="actions"><button onClick={() => { api.setBearerToken(apiToken); void refresh().catch(showError); }}>Save token</button><button className="secondary" onClick={() => { setApiToken(""); api.setBearerToken(""); void refresh().catch(showError); }}>Clear token</button></div></article><article className="panel"><h2>SQLite operating guidance</h2><p>SQLite is suitable for local or small-team use. Use PostgreSQL or MongoDB for multi-process, distributed worker deployments; configure global worker ceilings with deployment environment settings.</p><button className="secondary" onClick={() => setTheme(theme === "dark" ? "light" : "dark")}>Switch to {theme === "dark" ? "light" : "dark"} mode</button></article></section>}
    </main>
  );
}

function DashboardView({ dashboard, onRun }: { dashboard: Dashboard | null; onRun: (runId: string) => void }) {
  if (!dashboard) return <section className="panel"><p className="empty">Loading operational status...</p></section>;
  return <>
    <section className="dashboard" aria-label="Operational status"><Metric label="Active runs" value={dashboard.runs.active} detail={`${dashboard.queue.pending} pending · ${dashboard.queue.leased} leased`} /><Metric label="Endpoints" value={`${dashboard.endpoints.available}/${dashboard.endpoints.total}`} detail={`${dashboard.endpoints.unavailable} unavailable`} /><Metric label="Workers" value={dashboard.workers.active} detail="active leased workers" /><Metric label="Estimated cost" value={Object.entries(dashboard.api.estimated_cost_by_currency).map(([currency, value]) => money(value, currency)).join(" · ") || "--"} detail="completed run evidence" /></section>
    <section className="grid two"><article className="panel"><h2>Evaluation health</h2><div className="metric-grid"><Metric label="Accuracy" value={percent(dashboard.quality.samples.accuracy)} detail={`${dashboard.quality.samples.successful}/${dashboard.quality.samples.total} successful`} /><Metric label="API errors" value={percent(dashboard.api.request_error_rate)} detail={`${dashboard.quality.errors.api_errors} requests`} /><Metric label="P95 latency" value={`${display(dashboard.quality.latency_ms.p95)} ms`} detail={`${dashboard.quality.latency_ms.measured_samples} measured`} /><Metric label="Tokens" value={display(dashboard.quality.tokens.total)} detail={`${display(dashboard.quality.tokens.input)} in / ${display(dashboard.quality.tokens.output)} out`} /></div></article><article className="panel"><h2>Recent completed runs</h2>{dashboard.runs.recent_completed.length === 0 ? <p className="empty">No completed runs yet.</p> : <div className="recent-list">{dashboard.runs.recent_completed.map((run) => <button key={run.id} className="recent-run" onClick={() => onRun(run.id)}><strong>{run.benchmark_id}</strong><span>{run.completed_samples}/{run.total_samples} samples · {formatDate(run.completed_at)}</span></button>)}</div>}</article></section>
  </>;
}

function Metric({ label, value, detail }: { label: string; value: string | number; detail: string }) {
  return <div className="metric-card"><span>{label}</span><strong>{value}</strong><small>{detail}</small></div>;
}

function VirtualTaskQueue({ tasks, busy, onPriority }: { tasks: Task[]; busy: string | null; onPriority: (task: Task, priority: number) => Promise<void> }) {
  const rowHeight = 52;
  const windowSize = 30;
  const [scrollTop, setScrollTop] = useState(0);
  const start = Math.max(0, Math.floor(scrollTop / rowHeight) - 4);
  const end = Math.min(tasks.length, start + windowSize + 8);
  const visible = tasks.slice(start, end);
  const editable = (task: Task) => ["pending", "retry_scheduled"].includes(task.status);
  return <div className="table-wrap virtual-table-viewport" onScroll={(event) => setScrollTop(event.currentTarget.scrollTop)}><table><thead><tr><th>Task</th><th>Parent</th><th>Run</th><th>Status</th><th>Priority</th><th>Attempts</th><th>Worker</th><th>Created</th></tr></thead><tbody>{start > 0 && <tr aria-hidden="true"><td colSpan={8} className="virtual-spacer" style={{ height: start * rowHeight }} /></tr>}{visible.map((task) => <tr key={task.id}><td>{task.task_type}</td><td>{task.parent_task_id?.slice(0, 8) ?? "--"}</td><td>{task.run_id.slice(0, 8)}</td><td><span className={`badge ${task.status}`}>{task.status}</span></td><td><div className="actions"><span>{task.priority}</span><button className="secondary" disabled={busy === `task-${task.id}` || !editable(task)} onClick={() => void onPriority(task, task.priority - 10)}>-10</button><button disabled={busy === `task-${task.id}` || !editable(task)} onClick={() => void onPriority(task, task.priority + 10)}>+10</button></div></td><td>{task.attempt_count}</td><td>{task.leased_by ?? "--"}</td><td>{formatDate(task.created_at)}</td></tr>)}{end < tasks.length && <tr aria-hidden="true"><td colSpan={8} className="virtual-spacer" style={{ height: (tasks.length - end) * rowHeight }} /></tr>}</tbody></table></div>;
}

function DatasetCatalog({ datasets, busy, onPrepare, onPause, onUpload, onValidate, onClear }: { datasets: Dataset[]; busy: string | null; onPrepare: (dataset: Dataset) => Promise<void>; onPause: (dataset: Dataset) => Promise<void>; onUpload: (dataset: Dataset, event: ChangeEvent<HTMLInputElement>) => Promise<void>; onValidate: (dataset: Dataset) => Promise<void>; onClear: (dataset: Dataset) => Promise<void> }) {
  const [usage, setUsage] = useState<{ cache_bytes: number; available_bytes: number } | null>(null);
  useEffect(() => { void api.datasetDiskUsage().then(setUsage).catch(() => setUsage(null)); }, [datasets]);
  return <section className="panel"><div className="section-title"><div><h2>Dataset catalog</h2><span>{datasets.length} versioned sources</span></div><span>{usage ? `${display(usage.cache_bytes)} cached · ${display(usage.available_bytes)} free` : "Loading disk usage…"}</span></div>{datasets.length === 0 ? <p className="empty">Register a dataset source from the Workspace catalog.</p> : <div className="cards">{datasets.map((dataset) => <article className="card" key={dataset.id}><div className="section-title"><h3>{dataset.dataset_id} v{dataset.version}</h3><span className={`badge ${dataset.status}`}>{dataset.status.replaceAll("_", " ")}</span></div><p className="muted">Revision {dataset.revision} · {dataset.source_url ? "source configured" : "upload a local file"}</p><p className="muted">{dataset.size_bytes === null ? "Not cached" : `${display(dataset.size_bytes)} bytes`} · {dataset.checksum ? `SHA-256 ${dataset.checksum.slice(0, 12)}…` : "Checksum generated on import"}</p>{dataset.credential_env_var && <p className="muted">Server credential reference: {dataset.credential_env_var}</p>}{dataset.error_message && <p className="error">{dataset.error_message}</p>}<div className="actions">{dataset.status !== "ready" && dataset.status !== "downloading" && <button disabled={busy === `dataset-${dataset.id}`} onClick={() => void onPrepare(dataset)}>{dataset.license_text && !dataset.license_accepted_at ? "Accept license" : dataset.status === "waiting" || dataset.status === "failed" ? "Retry download" : "Download and verify"}</button>}{dataset.status === "downloading" && <button className="secondary" disabled={busy === `dataset-${dataset.id}`} onClick={() => void onPause(dataset)}>Pause download</button>}{dataset.local_path && <><button className="secondary" disabled={busy === `dataset-validate-${dataset.id}`} onClick={() => void onValidate(dataset)}>Validate cache</button><button className="secondary" disabled={busy === `dataset-clear-${dataset.id}`} onClick={() => void onClear(dataset)}>Clear cache</button></>}<label className="file-picker">Upload local revision<input aria-label={`Upload local revision for ${dataset.dataset_id}`} type="file" accept=".json,.jsonl,.csv,.tsv,.txt,.zip,.parquet" disabled={busy === `dataset-upload-${dataset.id}`} onChange={(event) => void onUpload(dataset, event)} /></label></div></article>)}</div>}</section>;
}

function SampleEvidenceBrowser({ attempts, onReview, onLoadMore, loadingMore }: { attempts: SampleAttempt[]; onReview: (attempt: SampleAttempt) => void; onLoadMore: () => Promise<void>; loadingMore: boolean }) {
  const [query, setQuery] = useState("");
  const [status, setStatus] = useState("all");
  const [correctness, setCorrectness] = useState("all");
  const [capability, setCapability] = useState("all");
  const [modality, setModality] = useState("all");
  const [language, setLanguage] = useState("all");
  const [difficulty, setDifficulty] = useState("all");
  const [errorKind, setErrorKind] = useState("all");
  const [judgeState, setJudgeState] = useState("all");
  const [reviewState, setReviewState] = useState("all");
  const [anomaly, setAnomaly] = useState("all");
  const [visibleCount, setVisibleCount] = useState(100);
  const options = (field: "capability" | "language" | "difficulty") => Array.from(new Set(attempts.map((attempt) => attempt.sample_metadata[field]).filter(Boolean))).sort();
  const modalities = Array.from(new Set(attempts.map((attempt) => String(attempt.input_snapshot.modality ?? "unknown")))).sort();
  const averages = { latency: attempts.reduce((sum, attempt) => sum + (attempt.latency_ms ?? 0), 0) / Math.max(1, attempts.filter((attempt) => attempt.latency_ms !== null).length), tokens: attempts.reduce((sum, attempt) => sum + (attempt.input_tokens ?? 0) + (attempt.output_tokens ?? 0), 0) / Math.max(1, attempts.length), cost: attempts.reduce((sum, attempt) => sum + (attempt.estimated_cost ?? 0), 0) / Math.max(1, attempts.length) };
  const filtered = useMemo(() => attempts.filter((attempt) => {
    const searchable = `${attempt.sample_id} ${attempt.parsed_prediction ?? ""} ${attempt.error_type ?? ""} ${attempt.error_message ?? ""}`.toLowerCase();
    const apiError = (attempt.error_type ?? "").startsWith("http_") || ["timeout", "connection_error"].includes(attempt.error_type ?? "");
    const tokens = (attempt.input_tokens ?? 0) + (attempt.output_tokens ?? 0);
    const anomalous = anomaly === "all" || (anomaly === "latency" && (attempt.latency_ms ?? 0) > averages.latency * 2) || (anomaly === "tokens" && tokens > averages.tokens * 2) || (anomaly === "cost" && (attempt.estimated_cost ?? 0) > averages.cost * 2);
    return (status === "all" || attempt.status === status) && (correctness === "all" || (correctness === "correct" && attempt.score === 1) || (correctness === "incorrect" && attempt.score !== 1)) && (capability === "all" || attempt.sample_metadata.capability === capability) && (modality === "all" || String(attempt.input_snapshot.modality ?? "unknown") === modality) && (language === "all" || attempt.sample_metadata.language === language) && (difficulty === "all" || attempt.sample_metadata.difficulty === difficulty) && (errorKind === "all" || (errorKind === "api" && apiError) || (errorKind === "parser" && attempt.error_type === "response_parse_error") || (errorKind === "any" && Boolean(attempt.error_type))) && (judgeState === "all" || (judgeState === "disagreement" && attempt.judge_disagreement) || (judgeState === "agreement" && !attempt.judge_disagreement)) && (reviewState === "all" || attempt.human_review_status === reviewState) && anomalous && searchable.includes(query.trim().toLowerCase());
  }), [anomaly, attempts, averages.cost, averages.latency, averages.tokens, capability, correctness, difficulty, errorKind, judgeState, language, modality, query, reviewState, status]);
  const visible = filtered.slice(0, visibleCount);
  const update = () => setVisibleCount(100);
  return <section className="panel"><div className="section-title"><h2>Sample evidence</h2><span>{filtered.length}/{attempts.length} attempts</span></div>{attempts.length === 0 ? <p className="empty">This run has no saved attempts yet.</p> : <><div className="comparison-form"><label>Search samples<input value={query} onChange={(event) => { setQuery(event.target.value); update(); }} placeholder="sample, prediction, error" /></label><label>Status<select value={status} onChange={(event) => { setStatus(event.target.value); update(); }}><option value="all">All states</option><option value="succeeded">Succeeded</option><option value="failed">Failed</option><option value="pending">Pending</option><option value="running">Running</option></select></label><label>Correctness<select value={correctness} onChange={(event) => { setCorrectness(event.target.value); update(); }}><option value="all">All</option><option value="correct">Correct</option><option value="incorrect">Incorrect</option></select></label><label>Capability<select value={capability} onChange={(event) => { setCapability(event.target.value); update(); }}><option value="all">All</option>{options("capability").map((item) => <option value={item} key={item}>{item}</option>)}</select></label><label>Modality<select value={modality} onChange={(event) => { setModality(event.target.value); update(); }}><option value="all">All</option>{modalities.map((item) => <option value={item} key={item}>{item}</option>)}</select></label><label>Language<select value={language} onChange={(event) => { setLanguage(event.target.value); update(); }}><option value="all">All</option>{options("language").map((item) => <option value={item} key={item}>{item}</option>)}</select></label><label>Difficulty<select value={difficulty} onChange={(event) => { setDifficulty(event.target.value); update(); }}><option value="all">All</option>{options("difficulty").map((item) => <option value={item} key={item}>{item}</option>)}</select></label><label>Error type<select value={errorKind} onChange={(event) => { setErrorKind(event.target.value); update(); }}><option value="all">All</option><option value="any">Any error</option><option value="api">API error</option><option value="parser">Parser error</option></select></label><label>Judge<select value={judgeState} onChange={(event) => { setJudgeState(event.target.value); update(); }}><option value="all">All</option><option value="disagreement">Disagreement</option><option value="agreement">No disagreement</option></select></label><label>Human review<select value={reviewState} onChange={(event) => { setReviewState(event.target.value); update(); }}><option value="all">All</option><option value="unreviewed">Unreviewed</option><option value="reviewed">Reviewed</option><option value="adjudicated">Adjudicated</option></select></label><label>Anomaly<select value={anomaly} onChange={(event) => { setAnomaly(event.target.value); update(); }}><option value="all">None</option><option value="latency">Latency &gt; 2× mean</option><option value="tokens">Tokens &gt; 2× mean</option><option value="cost">Cost &gt; 2× mean</option></select></label></div>{visible.length === 0 ? <p className="empty">No samples match these filters.</p> : visible.map((attempt) => <details className="attempt" key={attempt.id}><summary><span>{attempt.sample_id} · attempt {attempt.attempt_number}</span><span className={`badge ${attempt.status}`}>{attempt.status}</span><span>{attempt.sample_metadata.capability ?? "unclassified"} · {attempt.sample_metadata.language ?? "unknown"}</span><span>score {attempt.score ?? "--"}</span><span>{display(attempt.latency_ms)} ms · {display(attempt.input_tokens)}/{display(attempt.output_tokens)} tokens · {display(attempt.estimated_cost, 6)}</span></summary><div className="evidence"><pre>{JSON.stringify({ input: attempt.input_snapshot, request: attempt.request_snapshot, reference: attempt.reference_snapshot, prediction: attempt.parsed_prediction, metadata: attempt.sample_metadata, judge_disagreement: attempt.judge_disagreement, human_review_status: attempt.human_review_status }, null, 2)}</pre><pre>{attempt.raw_response ?? attempt.error_message ?? "No response captured."}</pre></div><div className="actions"><button className="secondary" onClick={() => void onReview(attempt)}>Human review</button></div></details>)}{visible.length < filtered.length && <div className="actions"><button className="secondary" onClick={() => setVisibleCount((value) => value + 100)}>Load next 100 samples</button></div>}</>}</section>;
}

function RunDetail({ run, summary, logs, attempts, reports, selectedAttempt, reviews, reviewAgreement, judgeAssessments, judgeAgreement, judgeForm, endpoints, reviewForm, busy, onJudgeForm, onReviewForm, onReview, onLoadMoreAttempts, onCreateJudgeAssessment, onCreateReview, onGenerateReport }: { run: EvaluationRun; summary: RunSummary | null; logs: RunLogEntry[]; attempts: SampleAttempt[]; reports: Report[]; selectedAttempt: SampleAttempt | null; reviews: Review[]; reviewAgreement: ReviewAgreement | null; judgeAssessments: JudgeAssessment[]; judgeAgreement: JudgeAgreement | null; judgeForm: typeof initialJudge; endpoints: Endpoint[]; reviewForm: typeof initialReview; busy: string | null; onJudgeForm: (value: typeof initialJudge) => void; onReviewForm: (value: typeof initialReview) => void; onReview: (attempt: SampleAttempt) => void; onLoadMoreAttempts: () => Promise<void>; onCreateJudgeAssessment: (event: FormEvent) => void; onCreateReview: (event: FormEvent) => void; onGenerateReport: (runId: string, format: "html" | "json" | "csv" | "parquet" | "markdown" | "pdf") => void }) {
  return <>
    <section className="panel"><div className="section-title"><h2>Run executive summary</h2><span>{run.id.slice(0, 8)}</span></div>{summary ? <div className="metric-grid"><Metric label="Completion" value={`${summary.samples.completed}/${summary.samples.total}`} detail={percent(summary.samples.completion_rate)} /><Metric label="Accuracy" value={percent(summary.samples.accuracy)} detail={percent(summary.samples.success_rate) + " success rate"} /><Metric label="Latency" value={`${display(summary.latency_ms.average)} ms`} detail={`P50 ${display(summary.latency_ms.p50)} · P95 ${display(summary.latency_ms.p95)}`} /><Metric label="Cost" value={money(summary.cost.estimated, summary.cost.currency)} detail={`${summary.tokens.input} input / ${summary.tokens.output} output tokens`} /></div> : <p className="empty">Loading summary...</p>}</section>
    <section className="panel"><div className="section-title"><h2>Durable run log</h2><span>Refreshes with live run events</span></div>{logs.length === 0 ? <p className="empty">No task or sample lifecycle events have been recorded.</p> : <div className="review-list">{logs.slice(-50).reverse().map((entry, index) => <article className="review" key={`${entry.event}-${entry.timestamp}-${index}`}><strong>{entry.level.toUpperCase()} · {entry.event}</strong><p>{entry.message}</p><small>{formatDate(entry.timestamp)} · task {entry.task_id?.slice(0, 8) ?? "--"} · sample {entry.details.sample_id ? String(entry.details.sample_id) : "--"}</small></article>)}</div>}</section>
    {summary && <section className="grid two"><article className="panel"><h2>Capability evidence</h2>{summary.insights.capabilities.length === 0 ? <p className="empty">No scored capability evidence yet.</p> : <div className="table-wrap"><table><thead><tr><th>Capability</th><th>Score</th><th>Samples</th></tr></thead><tbody>{summary.insights.capabilities.map((item) => <tr key={item.capability}><td>{item.capability}</td><td>{percent(item.score)}</td><td>{item.sample_count}</td></tr>)}</tbody></table></div>}<p className="muted">Strongest: {summary.insights.strongest_capability?.capability ?? "--"} · weakest: {summary.insights.weakest_capability?.capability ?? "--"}</p></article><article className="panel"><h2>Run signals</h2>{summary.insights.significant_anomalies.length === 0 && summary.insights.major_regressions.length === 0 ? <p className="empty">No significant anomalies or regressions detected.</p> : <>{summary.insights.significant_anomalies.map((item) => <p key={item.kind}><strong>{item.kind}</strong> {percent(item.value)} (threshold {percent(item.threshold)})</p>)}{summary.insights.major_regressions.map((item) => <p key={item.metric}><strong>{item.metric} regression</strong> {percent(item.delta)} versus baseline {percent(item.baseline)}</p>)}</>}</article></section>}
    <SampleEvidenceBrowser attempts={attempts} onReview={onReview} onLoadMore={onLoadMoreAttempts} loadingMore={busy === "attempts-more"} />
    <div className="actions"><button className="secondary" disabled={busy === "attempts-more"} onClick={() => void onLoadMoreAttempts()}>{busy === "attempts-more" ? "Loading next page…" : "Load next evidence page"}</button></div>
    {selectedAttempt && <EvidenceMediaPreview attempt={selectedAttempt} />}
    {selectedAttempt && <JudgeWorkflow selectedAttempt={selectedAttempt} attempts={attempts} endpoints={endpoints} form={judgeForm} assessments={judgeAssessments} agreement={judgeAgreement} busy={busy} onForm={onJudgeForm} onSubmit={onCreateJudgeAssessment} />}
    {selectedAttempt && <><section className="grid two"><article className="panel"><h2>Human review: {selectedAttempt.sample_id}</h2><form className="form" onSubmit={onCreateReview}><label>Reviewer ID<input required value={reviewForm.reviewer_id} onChange={(event) => onReviewForm({ ...reviewForm, reviewer_id: event.target.value })} /></label><label>Review stage<select value={reviewForm.review_stage} onChange={(event) => onReviewForm({ ...reviewForm, review_stage: event.target.value as typeof reviewForm.review_stage })}><option value="primary">Primary review</option><option value="secondary">Secondary review</option><option value="adjudication">Adjudication</option></select></label><label>Rubric (JSON)<textarea value={reviewForm.rubric} onChange={(event) => onReviewForm({ ...reviewForm, rubric: event.target.value })} spellCheck={false} placeholder='{"quality":"high"}' /></label><label>Score<input type="number" min="0" max="1" step="0.01" value={reviewForm.score} onChange={(event) => onReviewForm({ ...reviewForm, score: event.target.value })} /></label><label>Labels (comma-separated)<input value={reviewForm.labels} onChange={(event) => onReviewForm({ ...reviewForm, labels: event.target.value })} /></label><label>Notes<textarea value={reviewForm.notes} onChange={(event) => onReviewForm({ ...reviewForm, notes: event.target.value })} /></label>{reviewForm.review_stage === "adjudication" && <p className="muted">This records a final decision over all saved primary and secondary reviews.</p>}<button disabled={busy === "review-submit"}>Save review</button></form></article><article className="panel"><h2>Review agreement</h2>{reviewAgreement ? <><p><strong>{reviewAgreement.status.replaceAll("_", " ")}</strong> · {reviewAgreement.distinct_reviewer_count} reviewer(s)</p><p className="muted">Score mean {display(reviewAgreement.numeric_score.mean)} · spread {display(reviewAgreement.numeric_score.range)} · label agreement {percent(reviewAgreement.label_agreement)}</p><p className="muted">Primary {reviewAgreement.review_stage_counts.primary} · secondary {reviewAgreement.review_stage_counts.secondary} · adjudication {reviewAgreement.review_stage_counts.adjudication}</p></> : <p className="empty">Open a sample to load review agreement.</p>}<h3>Saved reviews</h3>{reviews.length === 0 ? <p className="empty">No human review has been saved for this attempt.</p> : <div className="review-list">{reviews.map((review) => <article className="review" key={review.id}><strong>{review.review_stage} · {review.reviewer_id} · {review.score ?? "no score"}</strong><p>{review.notes || "No notes"}</p><small>{review.labels.join(", ") || "No labels"} · {formatDate(review.created_at)}</small></article>)}</div>}</article></section><section className="grid two"><article className="panel"><h2>LLM-as-judge</h2><form className="form" onSubmit={onCreateJudgeAssessment}><label>Independent judge endpoint<select required value={judgeForm.endpoint_id} onChange={(event) => onJudgeForm({ ...judgeForm, endpoint_id: event.target.value })}><option value="">Select available endpoint</option>{endpoints.filter((endpoint) => endpoint.status === "available" && endpoint.id !== run.model_endpoint_id).map((endpoint) => <option key={endpoint.id} value={endpoint.id}>{endpoint.display_name} · {endpoint.model_name}</option>)}</select></label><label>Rubric (JSON)<textarea value={judgeForm.rubric} onChange={(event) => onJudgeForm({ ...judgeForm, rubric: event.target.value })} spellCheck={false} placeholder='{"criterion":"answer quality"}' /></label><button disabled={busy === "judge-submit"}>Request judge assessment</button></form></article><article className="panel"><h2>Judge evidence</h2>{judgeAssessments.length === 0 ? <p className="empty">No independent judge assessment has been recorded.</p> : <div className="review-list">{judgeAssessments.map((assessment) => <article className="review" key={assessment.id}><strong>{assessment.label || assessment.status} · {assessment.score ?? "--"}</strong><p>{assessment.rationale || assessment.error_message || "No rationale returned."}</p><small>{formatDate(assessment.created_at)}</small></article>)}</div>}</article></section></>}
    <section className="panel"><div className="section-title"><h2>Report artifacts</h2><div className="actions"><button onClick={() => onGenerateReport(run.id, "html")}>HTML</button><button className="secondary" onClick={() => onGenerateReport(run.id, "markdown")}>Markdown</button><button className="secondary" onClick={() => onGenerateReport(run.id, "pdf")}>PDF</button><button className="secondary" onClick={() => onGenerateReport(run.id, "json")}>JSON</button><button className="secondary" onClick={() => onGenerateReport(run.id, "csv")}>CSV</button><button className="secondary" onClick={() => onGenerateReport(run.id, "parquet")}>Parquet</button></div></div><ReportsTable reports={reports} /></section>
  </>;
}

function JudgeWorkflow({ selectedAttempt, attempts, endpoints, form, assessments, agreement, busy, onForm, onSubmit }: { selectedAttempt: SampleAttempt; attempts: SampleAttempt[]; endpoints: Endpoint[]; form: typeof initialJudge; assessments: JudgeAssessment[]; agreement: JudgeAgreement | null; busy: string | null; onForm: (value: typeof initialJudge) => void; onSubmit: (event: FormEvent) => void }) {
  const pairedAttempts = attempts.filter((attempt) => attempt.id !== selectedAttempt.id && attempt.sample_id === selectedAttempt.sample_id);
  return <section className="grid two"><article className="panel"><div className="section-title"><h2>Blinded pairwise judge</h2><span>Model identities are never sent to the judge.</span></div><form className="form" onSubmit={onSubmit}><label>Independent judge endpoint<select required value={form.endpoint_id} onChange={(event) => onForm({ ...form, endpoint_id: event.target.value })}><option value="">Select available endpoint</option>{endpoints.filter((endpoint) => endpoint.status === "available").map((endpoint) => <option key={endpoint.id} value={endpoint.id}>{endpoint.display_name} · {endpoint.model_name}</option>)}</select></label><label>Compare with matching sample attempt<select value={form.comparison_attempt_id} onChange={(event) => onForm({ ...form, comparison_attempt_id: event.target.value })}><option value="">Single-answer judge assessment</option>{pairedAttempts.map((attempt) => <option key={attempt.id} value={attempt.id}>{attempt.sample_id} · attempt {attempt.attempt_number} · {attempt.status}</option>)}</select></label><label>Or paste a sample attempt ID<input value={form.comparison_attempt_id} onChange={(event) => onForm({ ...form, comparison_attempt_id: event.target.value })} placeholder="Cross-run matching sample attempt ID" /></label>{form.comparison_attempt_id && <label><input type="checkbox" checked={form.swap_test} onChange={(event) => onForm({ ...form, swap_test: event.target.checked })} /> Run reverse-order swap test</label>}<label>Rubric (JSON)<textarea value={form.rubric} onChange={(event) => onForm({ ...form, rubric: event.target.value })} spellCheck={false} placeholder='{"criterion":"answer quality"}' /></label><button disabled={busy === "judge-submit"}>{form.comparison_attempt_id ? "Run blinded comparison" : "Request judge assessment"}</button></form></article><article className="panel"><h2>Judge agreement</h2>{agreement ? <><p><strong>{agreement.status.replaceAll("_", " ")}</strong> · {agreement.successful_assessment_count}/{agreement.assessment_count} succeeded</p><p className="muted">Score mean {display(agreement.scores.mean)} · spread {display(agreement.scores.range)} · {agreement.judge_endpoint_count} judge endpoint(s)</p><p className="muted">Decisions: {agreement.decisions.distinct.join(", ") || "none"} · swap groups {agreement.swap_test_group_count}</p></> : <p className="empty">Open a sample to load judge agreement.</p>}<h3>Judge evidence</h3>{assessments.length === 0 ? <p className="empty">No independent judge assessment has been recorded.</p> : <div className="review-list">{assessments.map((assessment) => <article className="review" key={assessment.id}><strong>{assessment.label || assessment.status} · {assessment.score ?? "--"}</strong><p>{assessment.rationale || assessment.error_message || "No rationale returned."}</p><small>{assessment.selected_answer ? `winner ${assessment.selected_answer} · ` : ""}{assessment.answer_order.join(" / ") || "single answer"} · {formatDate(assessment.created_at)}</small></article>)}</div>}</article></section>;
}

function AnalysisView({ analytics, completedRuns }: { analytics: AnalyticsMatrix | null; completedRuns: EvaluationRun[] }) {
  const [matrix, setMatrix] = useState<AnalyticsMatrix | null>(analytics);
  const [baselineRunId, setBaselineRunId] = useState(analytics?.baseline_run_id ?? "");
  useEffect(() => setMatrix(analytics), [analytics]);
  if (!matrix) return <section className="panel"><p className="empty">Loading analysis matrix...</p></section>;
  const titles: Record<keyof AnalyticsMatrix["heatmaps"], string> = { model_benchmark: "Model × benchmark", model_capability: "Model × capability", model_language: "Model × language", model_difficulty: "Model × difficulty", prompt_benchmark: "Prompt × benchmark", model_modality: "Model × modality" };
  async function selectBaseline(value: string) { setBaselineRunId(value); setMatrix(await api.analyticsMatrix(value || undefined)); }
  return <><section className="panel"><div className="section-title"><div><h2>Analysis heatmaps</h2><p className="muted">Every cell keeps its sample count, 95% confidence interval, latency, cost, and optional baseline delta.</p></div><label>Baseline run<select value={baselineRunId} onChange={(event) => void selectBaseline(event.target.value)}><option value="">No baseline</option>{completedRuns.map((run) => <option value={run.id} key={run.id}>{run.benchmark_id} · {run.id.slice(0, 8)}</option>)}</select></label></div></section><CapabilityChart cells={matrix.capability_matrix} />{(Object.keys(titles) as Array<keyof AnalyticsMatrix["heatmaps"]>).map((dimension) => <section className="panel" key={dimension}><div className="section-title"><h2>{titles[dimension]} heatmap</h2><span>{matrix.heatmaps[dimension].length} cells</span></div>{matrix.heatmaps[dimension].length === 0 ? <p className="empty">Complete runs to populate this analysis.</p> : <div className="table-wrap"><table><thead><tr><th>Row</th><th>Column</th><th>Score</th><th>Samples / 95% CI</th><th>Baseline / Δ</th><th>Errors</th><th>Latency</th><th>Cost</th></tr></thead><tbody>{matrix.heatmaps[dimension].map((cell) => <tr key={`${cell.x_key}-${cell.y_key}`}><td>{cell.x_label}</td><td>{cell.y_label}</td><td>{percent(cell.score)}</td><td>{cell.sample_count} · {cell.confidence_interval ? `${percent(cell.confidence_interval.lower)}–${percent(cell.confidence_interval.upper)}` : "--"}</td><td>{cell.baseline_score === null ? "--" : `${percent(cell.baseline_score)} / ${percent(cell.delta)}`}</td><td>{percent(cell.error_rate)}</td><td>{display(cell.average_latency_ms)} ms</td><td>{money(cell.estimated_cost, cell.currency)}</td></tr>)}</tbody></table></div>}</section>)}</>;
}

function CapabilityChart({ cells }: { cells: AnalyticsMatrix["capability_matrix"] }) {
  const entries = cells.filter((cell) => cell.accuracy !== null);
  const [selected, setSelected] = useState<string | null>(null);
  const height = Math.max(120, entries.length * 46 + 28);
  const active = entries.find((cell) => `${cell.model_endpoint_id}:${cell.capability}` === selected) ?? null;
  return <section className="panel"><div className="section-title"><div><h2>Interactive capability chart</h2><p className="muted">Click or use Enter on a bar to inspect a model-capability result.</p></div><span>{entries.length} scored cells</span></div>{entries.length === 0 ? <p className="empty">Complete a run to populate interactive score bars.</p> : <><div className="chart-scroll"><svg className="capability-chart" viewBox={`0 0 720 ${height}`} role="img" aria-label="Capability accuracy chart"><line x1="250" x2="670" y1="12" y2="12" className="chart-axis" />{entries.map((cell, index) => { const key = `${cell.model_endpoint_id}:${cell.capability}`; const score = cell.accuracy ?? 0; const y = 30 + index * 46; const isActive = key === selected; return <g key={key} className={isActive ? "chart-bar selected" : "chart-bar"} role="button" tabIndex={0} aria-pressed={isActive} aria-label={`${cell.model_endpoint_id} ${cell.capability}: ${percent(score)}`} onClick={() => setSelected(key)} onKeyDown={(event) => { if (event.key === "Enter" || event.key === " ") { event.preventDefault(); setSelected(key); } }}><title>{`${cell.model_endpoint_id} · ${cell.capability}: ${percent(score)}`}</title><text x="8" y={y + 17}>{cell.capability}</text><text x="242" y={y + 17} textAnchor="end">{cell.model_endpoint_id.slice(0, 8)}</text><rect x="250" y={y} width="420" height="26" rx="5" className="chart-track" /><rect x="250" y={y} width={Math.max(3, score * 420)} height="26" rx="5" className="chart-value" /><text x="680" y={y + 18}>{percent(score)}</text></g>; })}</svg></div>{active && <p className="muted" aria-live="polite">Selected {active.capability}: {percent(active.accuracy)} accuracy across {active.sample_count} samples, {percent(active.success_rate)} success, {percent(active.error_rate)} errors.</p>}</>}</section>;
}

function ComparisonView({ comparison }: { comparison: Comparison }) {
  return <div className="comparison-result"><div className="metric-grid"><Metric label="A-only correct" value={comparison.outcomes.run_a_only_correct} detail="sample outcomes" /><Metric label="B-only correct" value={comparison.outcomes.run_b_only_correct} detail="sample outcomes" /><Metric label="Latency difference" value={`${display(comparison.differences.average_latency_ms)} ms`} detail="A minus B" /><Metric label="Cost difference" value={display(comparison.differences.estimated_cost, 6)} detail="A minus B" /></div><div className="table-wrap"><table><thead><tr><th>Metric</th><th>Run A</th><th>Run B</th><th>A - B</th></tr></thead><tbody><tr><td>Accuracy</td><td>{percent(comparison.run_a_summary.samples.accuracy)}</td><td>{percent(comparison.run_b_summary.samples.accuracy)}</td><td>{percent(comparison.differences.accuracy)}</td></tr><tr><td>Success rate</td><td>{percent(comparison.run_a_summary.samples.success_rate)}</td><td>{percent(comparison.run_b_summary.samples.success_rate)}</td><td>{percent(comparison.differences.success_rate)}</td></tr><tr><td>P95 latency</td><td>{display(comparison.run_a_summary.latency_ms.p95)} ms</td><td>{display(comparison.run_b_summary.latency_ms.p95)} ms</td><td>{display(comparison.differences.p95_latency_ms)} ms</td></tr><tr><td>Output tokens</td><td>{display(comparison.run_a_summary.tokens.output)}</td><td>{display(comparison.run_b_summary.tokens.output)}</td><td>{display(comparison.differences.output_tokens)}</td></tr></tbody></table></div></div>;
}

function ReportsTable({ reports, onShare }: { reports: Report[]; onShare?: (report: Report) => void }) {
  const [shareForm, setShareForm] = useState(initialShare);
  const [shareLink, setShareLink] = useState<string | null>(null);

  async function createShare(report: Report) {
    if (onShare) {
      await onShare(report);
      return;
    }
    const days = Math.min(365, Math.max(1, Number(shareForm.days) || 7));
    const share = await api.createReportShare(report.id, {
      expires_at: new Date(Date.now() + days * 86_400_000).toISOString(),
      password: shareForm.password || undefined,
      allow_download: shareForm.allow_download,
      include_evidence: shareForm.include_evidence,
    });
    setShareLink(share.share_url);
  }

  return reports.length === 0 ? <p className="empty">No report artifacts for this run yet.</p> : <><section className="share-policy"><h3>Read-only sharing policy</h3><div className="field-row"><label>Expires in days<input type="number" min="1" max="365" value={shareForm.days} onChange={(event) => setShareForm({ ...shareForm, days: event.target.value })} /></label><label>Optional password<input type="password" value={shareForm.password} onChange={(event) => setShareForm({ ...shareForm, password: event.target.value })} placeholder="Required to open when set" /></label></div><div className="actions"><label><input type="checkbox" checked={shareForm.allow_download} onChange={(event) => setShareForm({ ...shareForm, allow_download: event.target.checked })} /> Allow download</label><label><input type="checkbox" checked={shareForm.include_evidence} onChange={(event) => setShareForm({ ...shareForm, include_evidence: event.target.checked })} /> Share raw evidence</label></div><p className="muted">Raw JSON, CSV, and Parquet reports require both controls. Share links can be revoked through the report API.</p>{shareLink && <a href={shareLink} target="_blank" rel="noreferrer">Open the newly created share link</a>}</section><div className="table-wrap"><table><thead><tr><th>Format</th><th>Generated</th><th>Version</th><th /></tr></thead><tbody>{reports.map((report) => <tr key={report.id}><td>{report.format}</td><td>{formatDate(report.generated_at)}</td><td>{report.generator_version}</td><td><div className="actions"><a href={api.reportDownloadUrl(report.id)} target="_blank" rel="noreferrer">Download</a><button className="secondary" onClick={() => void createShare(report)}>Share</button></div></td></tr>)}</tbody></table></div></>;
}

function fileAsDataUrl(file: File): Promise<string> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onerror = () => reject(reader.error ?? new Error("Unable to read selected file."));
    reader.onload = () => resolve(String(reader.result));
    reader.readAsDataURL(file);
  });
}
