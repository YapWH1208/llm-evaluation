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
  PromptPackage,
  Report,
  ReportType,
  Review,
  RunSummary,
  SampleAttempt,
  SystemHealth,
  Task,
  User,
} from "./api";

type View = "dashboard" | "models" | "capabilities" | "workspace" | "benchmarks" | "datasets" | "suites" | "runs" | "queue" | "workers" | "analysis" | "compare" | "reports" | "reviews" | "users" | "settings";
type Theme = "dark" | "light";

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
const initialDataset = { dataset_id: "", version: "1", source_url: "", license_text: "" };
const initialSuite = { name: "", version: "1", description: "", benchmarks: "text-quick-check@1.0.0", default_request_body: "{}", default_prompt_overrides: "{}", weight_configuration: "{}" };
const initialReview = { reviewer_id: "local-reviewer", score: "", labels: "", notes: "" };
const initialMultimodal = { endpoint_id: "", prompt: "", reference_answer: "", sample_id: "custom-sample", asset_id: "" };
const initialUser = { email: "", display_name: "", role: "viewer", max_concurrency: "" };

function formatDate(value: string | null) {
  return value ? new Intl.DateTimeFormat(undefined, { dateStyle: "medium", timeStyle: "short" }).format(new Date(value)) : "Not recorded";
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

export default function App() {
  const [view, setView] = useState<View>("dashboard");
  const [theme, setTheme] = useState<Theme>(() => window.localStorage.getItem("lle-theme") === "light" ? "light" : "dark");
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
  const [selectedAttempt, setSelectedAttempt] = useState<SampleAttempt | null>(null);
  const [reviews, setReviews] = useState<Review[]>([]);
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
  const [runRequestBody, setRunRequestBody] = useState("{}");
  const [runMaxConcurrency, setRunMaxConcurrency] = useState("");
  const [reportType, setReportType] = useState<ReportType>("single_model");
  const [relatedReportRunId, setRelatedReportRunId] = useState("");
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

  async function createRun(endpointId: string) {
    setBusy(`run-${endpointId}`);
    try {
      const run = await api.createRun(endpointId, selectedPromptId || undefined, parseJsonObject(runRequestBody, "Run Request Body override"), optionalNumber(runMaxConcurrency));
      await selectRun(run.id);
      setView("runs");
      setNotice("Text Quick Check queued with an immutable configuration snapshot.");
      await refresh();
    } catch (error) { showError(error); } finally { setBusy(null); }
  }

  async function changeRun(run: EvaluationRun, action: "execute" | "pause" | "resume" | "cancel" | "clone" | "retry") {
    setBusy(`${action}-${run.id}`);
    try {
      const result = action === "execute" ? await api.executeRun(run.id)
        : action === "pause" ? await api.pauseRun(run.id)
          : action === "resume" ? await api.resumeRun(run.id)
            : action === "cancel" ? await api.cancelRun(run.id)
              : action === "clone" ? await api.cloneRun(run.id)
                : await api.retryFailedRun(run.id);
      setNotice(action === "clone" ? "Run cloned with a new immutable configuration snapshot." : action === "retry" ? "Failed samples were queued as new attempts." : `Run ${action === "execute" ? "executed" : action + "d"}.`);
      await selectRun(result.id);
      await refresh();
    } catch (error) { showError(error); } finally { setBusy(null); }
  }

  async function selectRun(runId: string) {
    setSelectedRun(runId);
    setSelectedAttempt(null);
    try {
      const [nextAttempts, nextSummary, nextReports] = await Promise.all([
        api.listAttempts(runId), api.getRunSummary(runId), api.listReports(runId),
      ]);
      setAttempts(nextAttempts);
      setRunSummary(nextSummary);
      setReports(nextReports);
    } catch (error) { showError(error); }
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
      const share = await api.createReportShare(report.id);
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
      await api.createDataset({ ...datasetForm, source_url: datasetForm.source_url || null, license_text: datasetForm.license_text || null });
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
    try { setReviews(await api.listReviews(attempt.id)); } catch (error) { showError(error); } finally { setBusy(null); }
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
        score: reviewForm.score === "" ? null : Number(reviewForm.score),
        labels,
        notes: reviewForm.notes || null,
      });
      setReviewForm(initialReview);
      setReviews(await api.listReviews(selectedAttempt.id));
      setNotice("Human review saved separately from automated results.");
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
          <button className={view === item ? "tab selected" : "tab"} key={item} onClick={() => setView(item)}>{item}</button>
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
              <label>Protocol profile<select value={form.protocol_profile} onChange={(event) => setForm({ ...form, protocol_profile: event.target.value as "openai_chat_completions" | "openai_responses" })}><option value="openai_chat_completions">OpenAI-compatible Chat Completions</option><option value="openai_responses">OpenAI-compatible Responses API</option></select></label>
              <label>API key<input required type="password" value={form.api_key} onChange={(event) => setForm({ ...form, api_key: event.target.value })} placeholder="Stored encrypted" /></label>
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
            <div className="actions"><button className="secondary" disabled={busy === `test-${endpoint.id}`} onClick={() => void testEndpoint(endpoint.id)}>Test connection</button><button className="secondary" disabled={busy === `capabilities-${endpoint.id}`} onClick={() => void probeCapabilities(endpoint.id)}>Probe capabilities</button><button disabled={endpoint.status !== "available" || busy === `run-${endpoint.id}`} onClick={() => void createRun(endpoint.id)}>Queue Quick Check</button></div>
            {capabilities[endpoint.id] && <div className="capability-list">{capabilities[endpoint.id].map((item) => <label key={item.id}>{item.capability_key}<select value={item.user_declared_status} disabled={busy === `declare-${endpoint.id}-${item.capability_key}`} onChange={(event) => void declareCapability(endpoint.id, item, event.target.value as "supported" | "unsupported" | "unknown")}><option value="unknown">User: unknown</option><option value="supported">User: supported</option><option value="unsupported">User: unsupported</option></select><small>{item.auto_detection_status} · {item.effective_status}</small></label>)}</div>}
          </article>)}</div>}
        </section>
      </>}

      {view === "capabilities" && <section className="panel"><div className="section-title"><h2>Model capabilities</h2><span>Detection evidence and user declarations remain separate.</span></div>{endpoints.length === 0 ? <p className="empty">Add a model endpoint before probing capabilities.</p> : <div className="cards">{endpoints.map((endpoint) => <article className="card" key={endpoint.id}><h3>{endpoint.display_name}</h3><div className="actions"><button className="secondary" disabled={busy === `capabilities-${endpoint.id}`} onClick={() => void probeCapabilities(endpoint.id)}>Probe capabilities</button></div>{capabilities[endpoint.id] ? <div className="capability-list">{capabilities[endpoint.id].map((item) => <label key={item.id}>{item.capability_key}<select value={item.user_declared_status} onChange={(event) => void declareCapability(endpoint.id, item, event.target.value as "supported" | "unsupported" | "unknown")}><option value="unknown">User: unknown</option><option value="supported">User: supported</option><option value="unsupported">User: unsupported</option></select><small>{item.auto_detection_status} · {item.effective_status}</small></label>)}</div> : <p className="muted">No probe result loaded yet.</p>}</article>)}</div>}</section>}

      {view === "benchmarks" && <section className="panel"><div className="section-title"><h2>Benchmarks</h2><span>{benchmarks.length} registered versions</span></div><div className="table-wrap"><table><thead><tr><th>Benchmark</th><th>Version</th><th>Source</th><th>Status</th><th>Modalities</th></tr></thead><tbody>{benchmarks.map((benchmark) => <tr key={benchmark.id}><td>{benchmark.display_name}</td><td>{benchmark.version}</td><td>{benchmark.source}</td><td><span className={`badge ${benchmark.status}`}>{benchmark.status}</span></td><td>{Array.isArray(benchmark.manifest.modalities) ? benchmark.manifest.modalities.join(", ") : "--"}</td></tr>)}</tbody></table></div></section>}

      {view === "datasets" && <section className="panel"><div className="section-title"><h2>Datasets</h2><span>{datasets.length} tracked revisions</span></div>{datasets.length === 0 ? <p className="empty">Register datasets from the Workspace catalog.</p> : <div className="cards">{datasets.map((dataset) => <article className="card" key={dataset.id}><h3>{dataset.dataset_id} v{dataset.version}</h3><p className="muted">{dataset.source_url || "No source URL"}</p><span className={`badge ${dataset.status}`}>{dataset.status}</span>{dataset.status !== "ready" && <button disabled={busy === `dataset-${dataset.id}`} onClick={() => void prepareDataset(dataset)}>{dataset.license_text && !dataset.license_accepted_at ? "Accept license" : "Download and verify"}</button>}</article>)}</div>}</section>}

      {view === "suites" && <section className="panel"><div className="section-title"><h2>Evaluation suites</h2><span>{suites.length} versioned suites</span></div>{suites.length === 0 ? <p className="empty">Create a suite from the Workspace catalog.</p> : <div className="cards">{suites.map((suite) => <article className="card" key={suite.id}><h3>{suite.name} v{suite.version}</h3><p className="muted">{suite.benchmark_list.map((item) => `${item.benchmark_id ?? "benchmark"}@${item.version ?? ""}`).join(", ")}</p>{endpoints.filter((endpoint) => endpoint.status === "available").map((endpoint) => <button key={endpoint.id} disabled={busy === `suite-${suite.id}`} onClick={() => void queueSuite(suite.id, endpoint.id)}>Queue on {endpoint.display_name}</button>)}</article>)}</div>}</section>}

      {view === "workspace" && <>
        <section className="grid two">
          <article className="panel"><h2>Create prompt package</h2><form onSubmit={createPrompt} className="form"><label>Name<input required value={promptForm.name} onChange={(event) => setPromptForm({ ...promptForm, name: event.target.value })} /></label><label>Version<input required value={promptForm.version} onChange={(event) => setPromptForm({ ...promptForm, version: event.target.value })} /></label><label>Prompt type<select value={promptForm.prompt_type} onChange={(event) => setPromptForm({ ...promptForm, prompt_type: event.target.value })}><option value="official">Official prompt</option><option value="platform_default">Platform default</option><option value="user_custom">User custom</option><option value="benchmark_variant">Benchmark variant</option><option value="language_specific">Language-specific</option></select></label><label>System message<textarea value={promptForm.system_message} onChange={(event) => setPromptForm({ ...promptForm, system_message: event.target.value })} /></label><label>User template<textarea required value={promptForm.user_template} onChange={(event) => setPromptForm({ ...promptForm, user_template: event.target.value })} placeholder="{{ question }}, {{ context }}, {{ image }}, {{ audio }}, {{ video }}, {{ language }}" /></label><label>Few-shot examples (JSON array)<textarea value={promptForm.few_shot_examples} onChange={(event) => setPromptForm({ ...promptForm, few_shot_examples: event.target.value })} spellCheck={false} /></label><label>Output format (JSON)<textarea value={promptForm.output_format} onChange={(event) => setPromptForm({ ...promptForm, output_format: event.target.value })} spellCheck={false} /></label><label>Response parser (JSON)<textarea value={promptForm.response_parser} onChange={(event) => setPromptForm({ ...promptForm, response_parser: event.target.value })} spellCheck={false} /></label><label>Scoring rule (JSON)<textarea value={promptForm.scoring_rule} onChange={(event) => setPromptForm({ ...promptForm, scoring_rule: event.target.value })} spellCheck={false} /></label><label>Change log<textarea value={promptForm.change_log} onChange={(event) => setPromptForm({ ...promptForm, change_log: event.target.value })} /></label><button disabled={busy === "prompt"}>Save versioned prompt</button></form></article>
          <article className="panel"><h2>Register dataset version</h2><form onSubmit={createDataset} className="form"><label>Dataset ID<input required value={datasetForm.dataset_id} onChange={(event) => setDatasetForm({ ...datasetForm, dataset_id: event.target.value })} /></label><label>Version<input required value={datasetForm.version} onChange={(event) => setDatasetForm({ ...datasetForm, version: event.target.value })} /></label><label>Source URL<input type="url" value={datasetForm.source_url} onChange={(event) => setDatasetForm({ ...datasetForm, source_url: event.target.value })} /></label><label>License text<textarea value={datasetForm.license_text} onChange={(event) => setDatasetForm({ ...datasetForm, license_text: event.target.value })} /></label><button disabled={busy === "dataset"}>Register dataset</button></form></article>
        </section>
        <section className="grid two"><article className="panel"><h2>Custom multimodal quick check</h2><form className="form" onSubmit={createMultimodalRun}><label>Endpoint<select required value={multimodalForm.endpoint_id} onChange={(event) => setMultimodalForm({ ...multimodalForm, endpoint_id: event.target.value })}><option value="">Select available endpoint</option>{endpoints.filter((endpoint) => endpoint.status === "available").map((endpoint) => <option key={endpoint.id} value={endpoint.id}>{endpoint.display_name} · {endpoint.model_name}</option>)}</select></label><label>Sample ID<input required value={multimodalForm.sample_id} onChange={(event) => setMultimodalForm({ ...multimodalForm, sample_id: event.target.value })} /></label><label>Prompt<textarea required value={multimodalForm.prompt} onChange={(event) => setMultimodalForm({ ...multimodalForm, prompt: event.target.value })} placeholder="Describe or answer a question about the attached media." /></label><label>Expected text answer<textarea required value={multimodalForm.reference_answer} onChange={(event) => setMultimodalForm({ ...multimodalForm, reference_answer: event.target.value })} /></label><label>Uploaded media<select required value={multimodalForm.asset_id} onChange={(event) => setMultimodalForm({ ...multimodalForm, asset_id: event.target.value })}><option value="">Upload an asset first</option>{uploadedAssets.map((asset) => <option key={asset.id} value={asset.id}>{asset.original_filename} · {asset.media_kind}</option>)}</select></label><button disabled={busy === "multimodal-run"}>Queue multimodal run</button></form></article><article className="panel"><h2>Media asset upload</h2><p className="muted">Files are validated by MIME signature, content-addressed, and stored outside browser memory before they enter a run snapshot.</p><label className="file-picker">Choose image, audio, video, or PDF<input type="file" accept="image/png,image/jpeg,image/gif,image/webp,audio/wav,audio/mpeg,video/mp4,video/webm,application/pdf" onChange={(event) => void uploadAsset(event)} /></label>{busy === "asset-upload" && <p className="muted">Uploading and validating asset...</p>}{uploadedAssets.length > 0 && <div className="asset-list">{uploadedAssets.map((asset) => <button className={multimodalForm.asset_id === asset.id ? "asset selected" : "asset"} key={asset.id} onClick={() => setMultimodalForm({ ...multimodalForm, asset_id: asset.id })}><strong>{asset.original_filename}</strong><span>{asset.media_kind} · {display(asset.size_bytes)} bytes</span></button>)}</div>}</article></section>
        <section className="grid two"><article className="panel"><h2>Create evaluation suite</h2><form onSubmit={createSuite} className="form"><label>Name<input required value={suiteForm.name} onChange={(event) => setSuiteForm({ ...suiteForm, name: event.target.value })} /></label><label>Version<input required value={suiteForm.version} onChange={(event) => setSuiteForm({ ...suiteForm, version: event.target.value })} /></label><label>Benchmarks (id@version)<input required value={suiteForm.benchmarks} onChange={(event) => setSuiteForm({ ...suiteForm, benchmarks: event.target.value })} /></label><label>Suite default Request Body (JSON)<textarea value={suiteForm.default_request_body} onChange={(event) => setSuiteForm({ ...suiteForm, default_request_body: event.target.value })} spellCheck={false} /></label><label>Prompt overrides (JSON)<textarea value={suiteForm.default_prompt_overrides} onChange={(event) => setSuiteForm({ ...suiteForm, default_prompt_overrides: event.target.value })} spellCheck={false} /></label><label>Weight configuration (JSON)<textarea value={suiteForm.weight_configuration} onChange={(event) => setSuiteForm({ ...suiteForm, weight_configuration: event.target.value })} spellCheck={false} /></label><label>Description<textarea value={suiteForm.description} onChange={(event) => setSuiteForm({ ...suiteForm, description: event.target.value })} /></label><button disabled={busy === "suite"}>Save suite</button></form></article><article className="panel"><h2>Evaluation suites</h2>{suites.length === 0 ? <p className="empty">No suites have been created.</p> : <div className="cards">{suites.map((suite) => <article className="card" key={suite.id}><h3>{suite.name} v{suite.version}</h3><p className="muted">{suite.benchmark_list.map((item) => `${item.benchmark_id ?? "benchmark"}@${item.version ?? ""}`).join(", ")}</p>{endpoints.filter((endpoint) => endpoint.status === "available").map((endpoint) => <button key={endpoint.id} disabled={busy === `suite-${suite.id}`} onClick={() => void queueSuite(suite.id, endpoint.id)}>Queue on {endpoint.display_name}</button>)}</article>)}</div>}</article></section>
        <section className="panel"><div className="section-title"><h2>Benchmark registry</h2><span>{benchmarks.length} registered</span></div><div className="table-wrap"><table><thead><tr><th>Benchmark</th><th>Version</th><th>Source</th><th>Status</th></tr></thead><tbody>{benchmarks.map((benchmark) => <tr key={benchmark.id}><td>{benchmark.display_name}</td><td>{benchmark.version}</td><td>{benchmark.source}</td><td><span className={`badge ${benchmark.status}`}>{benchmark.status}</span></td></tr>)}</tbody></table></div></section>
        <section className="panel"><div className="section-title"><h2>Dataset cache</h2><span>{datasets.length} registered</span></div>{datasets.length === 0 ? <p className="empty">Register a dataset version to manage downloads and licenses.</p> : <div className="cards">{datasets.map((dataset) => <article className="card" key={dataset.id}><div><h3>{dataset.dataset_id} v{dataset.version}</h3><p className="muted">{dataset.source_url || "No source URL"}</p>{dataset.error_message && <p className="error">{dataset.error_message}</p>}</div><span className={`badge ${dataset.status}`}>{dataset.status}</span>{dataset.status !== "ready" && <div className="actions"><button disabled={busy === `dataset-${dataset.id}`} onClick={() => void prepareDataset(dataset)}>{dataset.license_text && !dataset.license_accepted_at ? "Accept license" : "Download and verify"}</button></div>}</article>)}</div>}</section>
      </>}

      {view === "runs" && <>
        <section className="panel"><div className="section-title"><h2>Evaluation runs</h2><span>{runs.length} total</span></div>{runs.length === 0 ? <p className="empty">Verify a model endpoint to create the first run.</p> : <div className="run-list">{runs.map((run) => <article className={`run ${selectedRun === run.id ? "selected" : ""}`} key={run.id}><button className="run-summary" onClick={() => void selectRun(run.id)}><strong>{run.benchmark_id} v{run.benchmark_version}</strong><span>{run.status} · {run.completed_samples}/{run.total_samples} samples · {formatDate(run.created_at)}</span></button><div className="actions"><button className="secondary" onClick={() => void selectRun(run.id)}>Inspect</button>{run.status === "queued" && <button disabled={busy === `execute-${run.id}`} onClick={() => void changeRun(run, "execute")}>Execute</button>}{["queued", "running"].includes(run.status) && <button className="secondary" disabled={busy === `pause-${run.id}`} onClick={() => void changeRun(run, "pause")}>Pause</button>}{run.status === "paused" && <button disabled={busy === `resume-${run.id}`} onClick={() => void changeRun(run, "resume")}>Resume</button>}{run.status.startsWith("completed") && <button className="secondary" disabled={busy === `clone-${run.id}`} onClick={() => void changeRun(run, "clone")}>Clone</button>}{run.status === "completed_with_errors" && <button disabled={busy === `retry-${run.id}`} onClick={() => void changeRun(run, "retry")}>Retry failed</button>}{!["completed", "completed_with_errors", "cancelled"].includes(run.status) && <button className="danger" disabled={busy === `cancel-${run.id}`} onClick={() => void changeRun(run, "cancel")}>Cancel</button>}</div></article>)}</div>}</section>
        {selectedRunInfo && <RunDetail run={selectedRunInfo} summary={runSummary} attempts={attempts} reports={reports} selectedAttempt={selectedAttempt} reviews={reviews} reviewForm={reviewForm} busy={busy} onReviewForm={setReviewForm} onReview={openReview} onCreateReview={createReview} onGenerateReport={generateReport} />}
      </>}

      {view === "queue" && <section className="panel"><div className="section-title"><h2>Task queue</h2><span>{tasks.length} tasks loaded</span></div>{tasks.length === 0 ? <p className="empty">No queued work exists.</p> : <div className="table-wrap"><table><thead><tr><th>Task</th><th>Run</th><th>Status</th><th>Priority</th><th>Attempts</th><th>Worker</th><th>Created</th></tr></thead><tbody>{tasks.map((task) => <tr key={task.id}><td>{task.task_type}</td><td>{task.run_id.slice(0, 8)}</td><td><span className={`badge ${task.status}`}>{task.status}</span></td><td><div className="actions"><span>{task.priority}</span><button className="secondary" disabled={busy === `task-${task.id}` || !["pending", "retry_scheduled"].includes(task.status)} onClick={() => void updateTaskPriority(task, task.priority - 10)}>-10</button><button disabled={busy === `task-${task.id}` || !["pending", "retry_scheduled"].includes(task.status)} onClick={() => void updateTaskPriority(task, task.priority + 10)}>+10</button></div></td><td>{task.attempt_count}</td><td>{task.leased_by ?? "--"}</td><td>{formatDate(task.created_at)}</td></tr>)}</tbody></table></div>}</section>}

      {view === "workers" && <section className="panel"><div className="section-title"><h2>Workers</h2><span>Live updates are streamed from the worker event channel.</span></div>{tasks.length === 0 ? <p className="empty">No worker leases are active.</p> : <div className="table-wrap"><table><thead><tr><th>Worker</th><th>Task</th><th>Run</th><th>State</th><th>Lease expiry</th></tr></thead><tbody>{tasks.filter((task) => ["leased", "running"].includes(task.status)).map((task) => <tr key={task.id}><td>{task.leased_by ?? "--"}</td><td>{task.task_type}</td><td>{task.run_id.slice(0, 8)}</td><td><span className={`badge ${task.status}`}>{task.status}</span></td><td>{formatDate(task.lease_expires_at)}</td></tr>)}</tbody></table></div>}</section>}

      {view === "analysis" && <AnalysisView analytics={analytics} />}

      {view === "compare" && <section className="panel"><h2>Model and run comparison</h2><p className="muted">Runs must use the same benchmark version. Differences are run A minus run B.</p><form className="comparison-form" onSubmit={compareRuns}><label>Run A<select required value={comparisonRunA} onChange={(event) => setComparisonRunA(event.target.value)}><option value="">Select completed run</option>{completedRuns.map((run) => <option key={run.id} value={run.id}>{run.benchmark_id} · {run.id.slice(0, 8)} · {formatDate(run.completed_at)}</option>)}</select></label><label>Run B<select required value={comparisonRunB} onChange={(event) => setComparisonRunB(event.target.value)}><option value="">Select completed run</option>{completedRuns.map((run) => <option key={run.id} value={run.id}>{run.benchmark_id} · {run.id.slice(0, 8)} · {formatDate(run.completed_at)}</option>)}</select></label><button disabled={busy === "compare"}>Compare</button></form>{comparison && <ComparisonView comparison={comparison} />}</section>}

      {view === "reports" && <section className="panel"><h2>Reports</h2>{selectedRunInfo ? <><p>Generate a portable report for <strong>{selectedRunInfo.benchmark_id}</strong>, or download previous artifacts.</p><div className="comparison-form"><label>Report type<select value={reportType} onChange={(event) => setReportType(event.target.value as ReportType)}><option value="single_model">Single-model complete</option><option value="multi_model_comparison">Multi-model comparison</option><option value="regression">Regression</option><option value="prompt_comparison">Prompt comparison</option><option value="benchmark">Benchmark</option><option value="reliability">Reliability</option><option value="cost">Cost</option><option value="human_review">Human review</option></select></label>{["multi_model_comparison", "regression", "prompt_comparison"].includes(reportType) && <label>Related completed run<select value={relatedReportRunId} onChange={(event) => setRelatedReportRunId(event.target.value)}><option value="">Select run</option>{completedRuns.filter((run) => run.id !== selectedRunInfo.id).map((run) => <option key={run.id} value={run.id}>{run.benchmark_id} · {run.id.slice(0, 8)}</option>)}</select></label>}</div><div className="actions"><button onClick={() => void generateReport(selectedRunInfo.id, "html")}>Generate HTML</button><button className="secondary" onClick={() => void generateReport(selectedRunInfo.id, "markdown")}>Generate Markdown</button><button className="secondary" onClick={() => void generateReport(selectedRunInfo.id, "pdf")}>Generate PDF</button><button className="secondary" onClick={() => void generateReport(selectedRunInfo.id, "json")}>Generate JSON</button><button className="secondary" onClick={() => void generateReport(selectedRunInfo.id, "csv")}>Generate CSV</button><button className="secondary" onClick={() => void generateReport(selectedRunInfo.id, "parquet")}>Generate Parquet</button></div><ReportsTable reports={reports} onShare={shareReport} /></> : <p className="empty">Choose a run in the Runs page before generating a report.</p>}</section>}

      {view === "reviews" && <section className="panel"><div className="section-title"><h2>Human review</h2><span>Reviewer scores remain separate from deterministic and judge evidence.</span></div>{selectedRunInfo ? <RunDetail run={selectedRunInfo} summary={runSummary} attempts={attempts} reports={[]} selectedAttempt={selectedAttempt} reviews={reviews} reviewForm={reviewForm} busy={busy} onReviewForm={setReviewForm} onReview={openReview} onCreateReview={createReview} onGenerateReport={generateReport} /> : <p className="empty">Select a run and sample from the Runs page to review it.</p>}</section>}

      {view === "users" && <section className="grid two"><article className="panel"><h2>Create user</h2><form className="form" onSubmit={createUser}><label>Email<input required type="email" value={userForm.email} onChange={(event) => setUserForm({ ...userForm, email: event.target.value })} /></label><label>Display name<input required value={userForm.display_name} onChange={(event) => setUserForm({ ...userForm, display_name: event.target.value })} /></label><label>Role<select value={userForm.role} onChange={(event) => setUserForm({ ...userForm, role: event.target.value })}><option value="viewer">Viewer</option><option value="reviewer">Reviewer</option><option value="evaluator">Evaluator</option><option value="admin">Admin</option></select></label><label>User concurrency cap<input type="number" min="1" max="1000" value={userForm.max_concurrency} onChange={(event) => setUserForm({ ...userForm, max_concurrency: event.target.value })} placeholder="Unlimited" /></label><button disabled={busy === "user"}>Create API-token user</button></form></article><article className="panel"><h2>Users and audit trail</h2>{users.length === 0 ? <p className="empty">User administration needs an administrator bearer token when server authentication is enabled.</p> : <div className="table-wrap"><table><thead><tr><th>User</th><th>Role</th><th>Cap</th><th>Status</th><th>Created</th></tr></thead><tbody>{users.map((user) => <tr key={user.id}><td>{user.display_name}<br /><small>{user.email}</small></td><td>{user.role}</td><td>{user.max_concurrency ?? "∞"}</td><td>{user.status}</td><td>{formatDate(user.created_at)}</td></tr>)}</tbody></table></div>}<h3>Recent audit events</h3>{auditEvents.length === 0 ? <p className="empty">No events available.</p> : <div className="table-wrap"><table><thead><tr><th>Action</th><th>Entity</th><th>When</th></tr></thead><tbody>{auditEvents.slice(0, 12).map((event) => <tr key={event.id}><td>{event.action}</td><td>{event.entity_type}</td><td>{formatDate(event.created_at)}</td></tr>)}</tbody></table></div>}</article></section>}

      {view === "settings" && <section className="grid two"><article className="panel"><h2>System settings</h2><p className="muted">Runtime settings are configured through the deployment environment; sensitive values never return to the browser.</p><dl><dt>Database</dt><dd>{systemHealth?.database ?? "Unavailable"}</dd><dt>Schema version</dt><dd>{systemHealth?.schema_version ?? "--"}</dd><dt>Health</dt><dd>{systemHealth?.status ?? "Unavailable"}</dd><dt>Theme</dt><dd>{theme}</dd></dl><label>Administrator or user bearer token<input type="password" value={apiToken} onChange={(event) => setApiToken(event.target.value)} placeholder="Optional when server auth is enabled" /></label><div className="actions"><button onClick={() => { api.setBearerToken(apiToken); void refresh().catch(showError); }}>Save token</button><button className="secondary" onClick={() => { setApiToken(""); api.setBearerToken(""); void refresh().catch(showError); }}>Clear token</button></div></article><article className="panel"><h2>SQLite operating guidance</h2><p>SQLite is suitable for local or small-team use. Use PostgreSQL or MongoDB for multi-process, distributed worker deployments; configure global worker ceilings with deployment environment settings.</p><button className="secondary" onClick={() => setTheme(theme === "dark" ? "light" : "dark")}>Switch to {theme === "dark" ? "light" : "dark"} mode</button></article></section>}
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

function RunDetail({ run, summary, attempts, reports, selectedAttempt, reviews, reviewForm, busy, onReviewForm, onReview, onCreateReview, onGenerateReport }: { run: EvaluationRun; summary: RunSummary | null; attempts: SampleAttempt[]; reports: Report[]; selectedAttempt: SampleAttempt | null; reviews: Review[]; reviewForm: typeof initialReview; busy: string | null; onReviewForm: (value: typeof initialReview) => void; onReview: (attempt: SampleAttempt) => void; onCreateReview: (event: FormEvent) => void; onGenerateReport: (runId: string, format: "html" | "json" | "csv" | "parquet" | "markdown" | "pdf") => void }) {
  return <>
    <section className="panel"><div className="section-title"><h2>Run executive summary</h2><span>{run.id.slice(0, 8)}</span></div>{summary ? <div className="metric-grid"><Metric label="Completion" value={`${summary.samples.completed}/${summary.samples.total}`} detail={percent(summary.samples.completion_rate)} /><Metric label="Accuracy" value={percent(summary.samples.accuracy)} detail={percent(summary.samples.success_rate) + " success rate"} /><Metric label="Latency" value={`${display(summary.latency_ms.average)} ms`} detail={`P50 ${display(summary.latency_ms.p50)} · P95 ${display(summary.latency_ms.p95)}`} /><Metric label="Cost" value={money(summary.cost.estimated, summary.cost.currency)} detail={`${summary.tokens.input} input / ${summary.tokens.output} output tokens`} /></div> : <p className="empty">Loading summary...</p>}</section>
    <section className="panel"><div className="section-title"><h2>Sample evidence</h2><span>{attempts.length} attempts</span></div>{attempts.length === 0 ? <p className="empty">This run has no saved attempts yet.</p> : attempts.map((attempt) => <details className="attempt" key={attempt.id}><summary><span>{attempt.sample_id} · attempt {attempt.attempt_number}</span><span className={`badge ${attempt.status}`}>{attempt.status}</span><span>score {attempt.score ?? "--"}</span><span>{display(attempt.latency_ms)} ms · {display(attempt.input_tokens)}/{display(attempt.output_tokens)} tokens · {display(attempt.estimated_cost, 6)}</span></summary><div className="evidence"><pre>{JSON.stringify({ input: attempt.input_snapshot, request: attempt.request_snapshot, reference: attempt.reference_snapshot, prediction: attempt.parsed_prediction }, null, 2)}</pre><pre>{attempt.raw_response ?? attempt.error_message ?? "No response captured."}</pre></div><div className="actions"><button className="secondary" onClick={() => void onReview(attempt)}>Human review</button></div></details>)}</section>
    {selectedAttempt && <section className="grid two"><article className="panel"><h2>Human review: {selectedAttempt.sample_id}</h2><form className="form" onSubmit={onCreateReview}><label>Reviewer ID<input required value={reviewForm.reviewer_id} onChange={(event) => onReviewForm({ ...reviewForm, reviewer_id: event.target.value })} /></label><label>Score<input type="number" min="0" max="1" step="0.01" value={reviewForm.score} onChange={(event) => onReviewForm({ ...reviewForm, score: event.target.value })} /></label><label>Labels (comma-separated)<input value={reviewForm.labels} onChange={(event) => onReviewForm({ ...reviewForm, labels: event.target.value })} /></label><label>Notes<textarea value={reviewForm.notes} onChange={(event) => onReviewForm({ ...reviewForm, notes: event.target.value })} /></label><button disabled={busy === "review-submit"}>Save review</button></form></article><article className="panel"><h2>Saved reviews</h2>{reviews.length === 0 ? <p className="empty">No human review has been saved for this attempt.</p> : <div className="review-list">{reviews.map((review) => <article className="review" key={review.id}><strong>{review.reviewer_id} · {review.score ?? "no score"}</strong><p>{review.notes || "No notes"}</p><small>{review.labels.join(", ") || "No labels"} · {formatDate(review.created_at)}</small></article>)}</div>}</article></section>}
    <section className="panel"><div className="section-title"><h2>Report artifacts</h2><div className="actions"><button onClick={() => onGenerateReport(run.id, "html")}>HTML</button><button className="secondary" onClick={() => onGenerateReport(run.id, "markdown")}>Markdown</button><button className="secondary" onClick={() => onGenerateReport(run.id, "pdf")}>PDF</button><button className="secondary" onClick={() => onGenerateReport(run.id, "json")}>JSON</button><button className="secondary" onClick={() => onGenerateReport(run.id, "csv")}>CSV</button><button className="secondary" onClick={() => onGenerateReport(run.id, "parquet")}>Parquet</button></div></div><ReportsTable reports={reports} /></section>
  </>;
}

function AnalysisView({ analytics }: { analytics: AnalyticsMatrix | null }) {
  if (!analytics) return <section className="panel"><p className="empty">Loading analysis matrix...</p></section>;
  return <><section className="panel"><div className="section-title"><h2>Model × benchmark heatmap</h2><span>{analytics.heatmap.length} completed runs</span></div>{analytics.heatmap.length === 0 ? <p className="empty">Complete runs to populate the heatmap.</p> : <div className="table-wrap"><table><thead><tr><th>Model</th><th>Benchmark</th><th>Accuracy</th><th>Success</th><th>Errors</th><th>Average latency</th><th>Estimated cost</th></tr></thead><tbody>{analytics.heatmap.map((cell) => <tr key={cell.run_id}><td>{cell.model_name}</td><td>{cell.benchmark_id} v{cell.benchmark_version}</td><td>{percent(cell.accuracy)}</td><td>{percent(cell.success_rate)}</td><td>{percent(cell.error_rate)}</td><td>{display(cell.average_latency_ms)} ms</td><td>{money(cell.estimated_cost, cell.currency)}</td></tr>)}</tbody></table></div>}</section><section className="panel"><div className="section-title"><h2>Capability matrix</h2><span>Aggregated from benchmark requirements</span></div>{analytics.capability_matrix.length === 0 ? <p className="empty">No capability evidence is available yet.</p> : <div className="table-wrap"><table><thead><tr><th>Endpoint</th><th>Capability</th><th>Runs</th><th>Accuracy</th><th>Average latency</th><th>Estimated cost</th></tr></thead><tbody>{analytics.capability_matrix.map((cell) => <tr key={`${cell.model_endpoint_id}-${cell.capability}`}><td>{cell.model_endpoint_id.slice(0, 8)}</td><td>{cell.capability}</td><td>{cell.run_count}</td><td>{percent(cell.accuracy)}</td><td>{display(cell.average_latency_ms)} ms</td><td>{display(cell.estimated_cost, 6)}</td></tr>)}</tbody></table></div>}</section></>;
}

function ComparisonView({ comparison }: { comparison: Comparison }) {
  return <div className="comparison-result"><div className="metric-grid"><Metric label="A-only correct" value={comparison.outcomes.run_a_only_correct} detail="sample outcomes" /><Metric label="B-only correct" value={comparison.outcomes.run_b_only_correct} detail="sample outcomes" /><Metric label="Latency difference" value={`${display(comparison.differences.average_latency_ms)} ms`} detail="A minus B" /><Metric label="Cost difference" value={display(comparison.differences.estimated_cost, 6)} detail="A minus B" /></div><div className="table-wrap"><table><thead><tr><th>Metric</th><th>Run A</th><th>Run B</th><th>A - B</th></tr></thead><tbody><tr><td>Accuracy</td><td>{percent(comparison.run_a_summary.samples.accuracy)}</td><td>{percent(comparison.run_b_summary.samples.accuracy)}</td><td>{percent(comparison.differences.accuracy)}</td></tr><tr><td>Success rate</td><td>{percent(comparison.run_a_summary.samples.success_rate)}</td><td>{percent(comparison.run_b_summary.samples.success_rate)}</td><td>{percent(comparison.differences.success_rate)}</td></tr><tr><td>P95 latency</td><td>{display(comparison.run_a_summary.latency_ms.p95)} ms</td><td>{display(comparison.run_b_summary.latency_ms.p95)} ms</td><td>{display(comparison.differences.p95_latency_ms)} ms</td></tr><tr><td>Output tokens</td><td>{display(comparison.run_a_summary.tokens.output)}</td><td>{display(comparison.run_b_summary.tokens.output)}</td><td>{display(comparison.differences.output_tokens)}</td></tr></tbody></table></div></div>;
}

function ReportsTable({ reports, onShare }: { reports: Report[]; onShare?: (report: Report) => void }) {
  return reports.length === 0 ? <p className="empty">No report artifacts for this run yet.</p> : <div className="table-wrap"><table><thead><tr><th>Format</th><th>Generated</th><th>Version</th><th /></tr></thead><tbody>{reports.map((report) => <tr key={report.id}><td>{report.format}</td><td>{formatDate(report.generated_at)}</td><td>{report.generator_version}</td><td><div className="actions"><a href={api.reportDownloadUrl(report.id)} target="_blank" rel="noreferrer">Download</a>{onShare && !["json", "csv", "parquet"].includes(report.format) && <button className="secondary" onClick={() => void onShare(report)}>Share</button>}</div></td></tr>)}</tbody></table></div>;
}

function fileAsDataUrl(file: File): Promise<string> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onerror = () => reject(reader.error ?? new Error("Unable to read selected file."));
    reader.onload = () => resolve(String(reader.result));
    reader.readAsDataURL(file);
  });
}
