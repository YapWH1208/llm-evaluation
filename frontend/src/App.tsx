import { ChangeEvent, FormEvent, useCallback, useEffect, useMemo, useState } from "react";
import {
  api,
  ApiError,
  AnalyticsMatrix,
  Benchmark,
  Capability,
  Comparison,
  Dashboard,
  Dataset,
  Endpoint,
  EvaluationRun,
  JudgeAssessment,
  JudgeAgreement,
  PromptPackage,
  Report,
  ReportShare,
  Review,
  ReviewAgreement,
  RunPreflight,
  RunSummary,
  RunLogEntry,
  SampleAttempt,
  SystemHealth,
  Task,
} from "./api";
import { AppShell } from "./components/AppShell";
import { OverviewDashboard } from "./components/OverviewDashboard";
import { Guide } from "./components/Guide";
import { DatasetRegistrationForm } from "./components/datasets/DatasetRegistrationForm";
import { DatasetsPage } from "./components/pages/CatalogPages";
import { ModelsPage, type EndpointForm } from "./components/pages/EndpointPages";
import { AnalysisPage } from "./components/pages/InsightsPages";
import { RunsPage } from "./components/pages/OperationsPages";
import { SettingsPage } from "./components/pages/SystemPages";
import { datasetMetricIds, datasetScoringRuleFor, type DatasetMetricId } from "./evaluations/scoringMetrics";
import type { View } from "./dashboard/navigation";
import { workspacePath, workspaceRoute } from "./dashboard/routing";
import { reportCopy, type TranslationKey } from "./i18n/catalog";
import { translateStaticTemplate } from "./i18n/operationalCopy";
import { useTranslation } from "./i18n/LocaleProvider";
import { StaticCopy } from "./i18n/StaticCopy";
import "./evidence.css";

export { SharedReportPage } from "./components/pages/SystemPages";

type Theme = "dark" | "light";
const initialEndpoint: EndpointForm = {
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
  timeout_seconds: "60",
  max_concurrency: "1",
  api_key_max_concurrency: "",
  requests_per_second: "",
  requests_per_minute: "",
  tokens_per_minute: "",
  input_tokens_per_minute: "",
  output_tokens_per_minute: "",
};
const initialDataset = { dataset_id: "", version: "1", revision: "main", source_url: "", checksum: "", credential_binding_id: "", license_text: "", input_field: "", reference_field: "" };
const initialDatasetRun = { dataset_version_id: "", prompt_package_id: "", input_field: "", reference_field: "", sample_limit: "100", model_endpoint_id: "", metric: "default" as DatasetMetricId };
const initialReview = { reviewer_id: "local-reviewer", rubric: "{}", score: "", labels: "", notes: "", review_stage: "primary" as "primary" | "secondary" | "adjudication" };
const initialJudge = { endpoint_id: "", rubric: "{}", comparison_attempt_id: "", swap_test: true };
const initialShare = { days: "7", password: "", allow_download: false, include_evidence: false };

const datasetMetricLabelKeys = {
  default: "datasetRun.metricDefault",
  exact_match: "datasetRun.metricExactMatch",
  normalized_exact_match: "datasetRun.metricNormalizedExactMatch",
  token_f1: "datasetRun.metricTokenF1",
  bleu: "datasetRun.metricBleu",
  rouge_l: "datasetRun.metricRougeL",
} as const satisfies Record<DatasetMetricId, TranslationKey>;

function datasetRunPayload(form: typeof initialDatasetRun) {
  const scoringRule = datasetScoringRuleFor(form.metric);
  return {
    model_endpoint_id: form.model_endpoint_id,
    dataset_version_id: form.dataset_version_id,
    prompt_package_id: form.prompt_package_id || null,
    input_field: form.prompt_package_id ? null : form.input_field,
    reference_field: form.reference_field,
    sample_limit: Number(form.sample_limit) || 100,
    ...(scoringRule ? { scoring_rule: scoringRule } : {}),
  };
}

function optionalNumber(value: string) {
  return value.trim() === "" ? null : Number(value);
}

function parseJsonObject(value: string, label: string): Record<string, unknown> {
  const parsed: unknown = JSON.parse(value);
  if (!parsed || Array.isArray(parsed) || typeof parsed !== "object") throw new Error(`${label} must be a JSON object.`);
  return parsed as Record<string, unknown>;
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
  const { formatCurrency: money, formatNumber: display, formatPercent: percent, locale, setLocale, t } = useTranslation();
  const [view, setRoutedView] = useState<View>(() => workspaceRoute(window.location.pathname).view);
  const [theme, setTheme] = useState<Theme>(() => window.localStorage.getItem("lle-theme") === "light" ? "light" : "dark");
  const [apiToken, setApiToken] = useState(() => window.sessionStorage.getItem("lle-api-token") ?? "");
  const [endpoints, setEndpoints] = useState<Endpoint[]>([]);
  const [runs, setRuns] = useState<EvaluationRun[]>([]);
  const [dashboard, setDashboard] = useState<Dashboard | null>(null);
  const [prompts, setPrompts] = useState<PromptPackage[]>([]);
  const [datasets, setDatasets] = useState<Dataset[]>([]);
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
  const [editingEndpointId, setEditingEndpointId] = useState<string | null>(null);
  const [testRequests, setTestRequests] = useState<Record<string, { method: "POST"; url: string; body: Record<string, unknown> }>>({});
  const [datasetForm, setDatasetForm] = useState(initialDataset);
  const [datasetRunForm, setDatasetRunForm] = useState(initialDatasetRun);
  const [datasetRunFields, setDatasetRunFields] = useState<string[]>([]);
  const [datasetRunFieldsError, setDatasetRunFieldsError] = useState<string | null>(null);
  const [datasetRunFieldsLoading, setDatasetRunFieldsLoading] = useState(false);
  const [datasetRunSchemaRequest, setDatasetRunSchemaRequest] = useState(0);
  const [datasetHandoffId, setDatasetHandoffId] = useState<string | null>(null);
  const [reviewForm, setReviewForm] = useState(initialReview);
  const [tasks, setTasks] = useState<Task[]>([]);
  const [analytics, setAnalytics] = useState<AnalyticsMatrix | null>(null);
  const [systemHealth, setSystemHealth] = useState<SystemHealth | null>(null);
  const [selectedPromptId, setSelectedPromptId] = useState("");
  const [selectedBenchmark, setSelectedBenchmark] = useState("text-quick-check@1.0.0");
  const [selectedQuickStartBenchmark, setSelectedQuickStartBenchmark] = useState("text-quick-check@1.0.0");
  const [quickStartSampleLimit, setQuickStartSampleLimit] = useState("3");
  const [launchPreflight, setLaunchPreflight] = useState<{ kind: "quick-start" | "dataset"; result: RunPreflight } | null>(null);
  const [runRequestBody, setRunRequestBody] = useState("{}");
  const [runMaxConcurrency, setRunMaxConcurrency] = useState("");
  const [runConcurrencyEdits, setRunConcurrencyEdits] = useState<Record<string, string>>({});
  const [busy, setBusy] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);

  const navigate = useCallback((nextView: View, options: { replace?: boolean } = {}) => {
    const pathname = workspacePath(nextView);
    if (window.location.pathname !== pathname) {
      window.history[options.replace ? "replaceState" : "pushState"](null, "", pathname);
    }
    setRoutedView(nextView);
  }, []);

  useEffect(() => {
    const syncRoute = () => {
      const route = workspaceRoute(window.location.pathname);
      if (route.replace) window.history.replaceState(null, "", `${route.pathname}${window.location.search}${window.location.hash}`);
      setRoutedView(route.view);
    };
    syncRoute();
    window.addEventListener("popstate", syncRoute);
    return () => window.removeEventListener("popstate", syncRoute);
  }, []);

  const refresh = useCallback(async () => {
    const [nextEndpoints, nextRuns, nextDashboard, nextPrompts, nextDatasets, nextBenchmarks, nextTasks, nextAnalytics, nextSystemHealth] = await Promise.all([
      api.listEndpoints(), api.listRuns(), api.dashboard(), api.listPromptPackages(), api.listDatasets(), api.listBenchmarks(), api.listTasks(), api.analyticsMatrix(), api.systemHealth().catch(() => null),
    ]);
    setEndpoints(nextEndpoints);
    setRuns(nextRuns);
    setDashboard(nextDashboard);
    setPrompts(nextPrompts);
    setDatasets(nextDatasets);
    setBenchmarks(nextBenchmarks);
    setTasks(nextTasks);
    setAnalytics(nextAnalytics);
    setSystemHealth(nextSystemHealth);
  }, []);

  useEffect(() => { void refresh().catch(showError); }, [refresh]);

  useEffect(() => {
    document.documentElement.dataset.theme = theme;
    window.localStorage.setItem("lle-theme", theme);
  }, [theme]);

  const completedRuns = useMemo(() => runs.filter((run) => run.status.startsWith("completed")), [runs]);
  const selectedRunInfo = runs.find((run) => run.id === selectedRun) ?? null;
  const availableEndpoints = useMemo(() => endpoints.filter((endpoint) => endpoint.status === "available"), [endpoints]);
  const quickStartBenchmarks = useMemo(() => benchmarks.filter((benchmark) => benchmark.source === "builtin" && ["available", "enabled"].includes(benchmark.status)), [benchmarks]);
  const selectedQuickStart = quickStartBenchmarks.find((benchmark) => `${benchmark.benchmark_id}@${benchmark.version}` === selectedQuickStartBenchmark) ?? quickStartBenchmarks[0] ?? null;
  const selectedDatasetForRun = datasets.find((dataset) => dataset.id === datasetRunForm.dataset_version_id) ?? null;
  const datasetRunFieldsCollide = useMemo(() => Boolean(datasetRunForm.input_field) && datasetRunForm.input_field === datasetRunForm.reference_field, [datasetRunForm.input_field, datasetRunForm.reference_field]);

  useEffect(() => {
    if (!selectedQuickStart) return;
    const benchmarkKey = `${selectedQuickStart.benchmark_id}@${selectedQuickStart.version}`;
    if (benchmarkKey !== selectedQuickStartBenchmark) setSelectedQuickStartBenchmark(benchmarkKey);
    const manifestCount = Number(selectedQuickStart.manifest.sample_count);
    setQuickStartSampleLimit(Number.isFinite(manifestCount) && manifestCount > 0 ? String(manifestCount) : "1");
  }, [selectedQuickStart?.id]);

  useEffect(() => {
    const datasetId = datasetRunForm.dataset_version_id;
    if (!datasetId) {
      setDatasetRunFields([]);
      setDatasetRunFieldsError(null);
      setDatasetRunFieldsLoading(false);
      return;
    }
    let disposed = false;
    setDatasetRunFields([]);
    setDatasetRunFieldsError(null);
    setDatasetRunFieldsLoading(true);
    void api.previewDataset(datasetId, 50).then((preview) => {
      if (disposed) return;
      const fields = Array.from(new Set(preview.fields.map(String).filter(Boolean)));
      const dataset = datasets.find((item) => item.id === datasetId);
      const inputField = dataset?.input_field && fields.includes(dataset.input_field) ? dataset.input_field : fields[0] ?? "";
      const referenceField = dataset?.reference_field && fields.includes(dataset.reference_field) ? dataset.reference_field : fields.find((field) => field !== inputField) ?? "";
      setDatasetRunFields(fields);
      setDatasetRunFieldsError(fields.length === 0 ? t("runLauncher.schemaEmpty") : referenceField ? null : t("runLauncher.schemaReferenceRequired"));
      setDatasetRunForm((current) => current.dataset_version_id === datasetId ? { ...current, input_field: inputField, reference_field: referenceField } : current);
    }).catch((error: unknown) => {
      if (disposed) return;
      setDatasetRunFieldsError(error instanceof Error ? error.message : t("runLauncher.schemaEmpty"));
      setDatasetRunForm((current) => current.dataset_version_id === datasetId ? { ...current, input_field: "", reference_field: "" } : current);
    }).finally(() => { if (!disposed) setDatasetRunFieldsLoading(false); });
    return () => { disposed = true; };
  }, [datasetRunForm.dataset_version_id, datasetRunSchemaRequest, selectedDatasetForRun?.input_field, selectedDatasetForRun?.reference_field]);

  useEffect(() => {
    if (!selectedRun || !selectedRunInfo || !["queued", "running"].includes(selectedRunInfo.status)) return;
    const update = () => {
      void selectRun(selectedRun);
      void refresh();
    };
    return api.subscribeToRunEvents(selectedRun, update);
  }, [selectedRun, selectedRunInfo?.status]);

  function showNotice(template: string, values?: Record<string, string | number>) {
    setNotice(translateStaticTemplate(locale, template, values));
  }

  function showError(error: unknown) {
    if (error instanceof ApiError || error instanceof Error) {
      setNotice(error.message);
      return;
    }
    showNotice("Unable to reach the evaluation service.");
  }

  function editEndpoint(endpoint: Endpoint) {
    setEditingEndpointId(endpoint.id);
    setForm({
      display_name: endpoint.display_name,
      base_url: endpoint.base_url,
      model_name: endpoint.model_name,
      protocol_profile: endpoint.protocol_profile,
      api_key: "",
      custom_headers: JSON.stringify(endpoint.custom_headers, null, 2),
      default_request_body: JSON.stringify(endpoint.default_request_body, null, 2),
      timeout_seconds: String(endpoint.timeout_seconds),
      max_concurrency: String(endpoint.max_concurrency),
      api_key_max_concurrency: endpoint.api_key_max_concurrency === null ? "" : String(endpoint.api_key_max_concurrency),
      requests_per_second: endpoint.requests_per_second === null ? "" : String(endpoint.requests_per_second),
      requests_per_minute: endpoint.requests_per_minute === null ? "" : String(endpoint.requests_per_minute),
      tokens_per_minute: endpoint.tokens_per_minute === null ? "" : String(endpoint.tokens_per_minute),
      input_tokens_per_minute: endpoint.input_tokens_per_minute === null ? "" : String(endpoint.input_tokens_per_minute),
      output_tokens_per_minute: endpoint.output_tokens_per_minute === null ? "" : String(endpoint.output_tokens_per_minute),
      input_cost_per_million: endpoint.input_cost_per_million === null ? "" : String(endpoint.input_cost_per_million),
      output_cost_per_million: endpoint.output_cost_per_million === null ? "" : String(endpoint.output_cost_per_million),
      currency: endpoint.currency,
      tags: endpoint.tags.join(", "),
      notes: endpoint.notes ?? "",
    });
  }

  function cancelEndpointEdit() {
    setEditingEndpointId(null);
    setForm(initialEndpoint);
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
      const endpointPayload: Record<string, unknown> = {
        ...form,
        default_request_body: defaultRequestBody,
        custom_headers: customHeaders,
        tags: form.tags.split(",").map((tag) => tag.trim()).filter(Boolean),
        notes: form.notes || null,
        timeout_seconds: Number(form.timeout_seconds),
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
      };
      if (editingEndpointId) {
        if (!form.api_key.trim()) delete endpointPayload.api_key;
        await api.updateEndpoint(editingEndpointId, endpointPayload);
        setTestRequests((current) => {
          const { [editingEndpointId]: _removed, ...remaining } = current;
          return remaining;
        });
        showNotice("Model configuration saved. Test its connection before starting a run.");
      } else {
        await api.createEndpoint(endpointPayload);
        showNotice("Endpoint saved. Test its connection before starting a run.");
      }
      cancelEndpointEdit();
      await refresh();
    } catch (error) { showError(error); } finally { setBusy(null); }
  }

  async function testEndpoint(id: string) {
    setBusy(`test-${id}`);
    try {
      const result = await api.testEndpoint(id);
      setTestRequests((current) => ({ ...current, [id]: result.request }));
      setNotice(result.message);
      await refresh();
    } catch (error) { showError(error); } finally { setBusy(null); }
  }

  async function probeCapabilities(endpointId: string) {
    if (!window.confirm(translateStaticTemplate(locale, "Capability probing sends small requests to this provider and may incur API charges. Continue?"))) return;
    setBusy(`capabilities-${endpointId}`);
    try {
      const detected = await api.detectCapabilities(endpointId);
      setCapabilities((current) => ({ ...current, [endpointId]: detected }));
      showNotice("Capability probe completed. Declared capability settings were not changed.");
    } catch (error) { showError(error); } finally { setBusy(null); }
  }

  async function declareCapability(endpointId: string, capability: Capability, status: "supported" | "unsupported" | "unknown") {
    setBusy(`declare-${endpointId}-${capability.capability_key}`);
    try {
      const updated = await api.declareCapability(endpointId, capability.capability_key, status);
      setCapabilities((current) => ({ ...current, [endpointId]: (current[endpointId] ?? []).map((item) => item.capability_key === updated.capability_key ? updated : item) }));
      showNotice("User capability declaration saved alongside detection evidence.");
    } catch (error) { showError(error); } finally { setBusy(null); }
  }

  async function preflightRun(endpointId: string, sampleLimit: number | null = null, benchmarkKey = selectedBenchmark) {
    setLaunchPreflight(null);
    setBusy("preflight-quick-start");
    try {
      const [benchmarkId, benchmarkVersion] = benchmarkKey.split("@", 2);
      const preflight = await api.validateRun(endpointId, selectedPromptId || undefined, parseJsonObject(runRequestBody, "Run Request Body override"), optionalNumber(runMaxConcurrency), benchmarkId, benchmarkVersion, sampleLimit);
      setLaunchPreflight({ kind: "quick-start", result: preflight });
      const cost = preflight.estimated_cost === null ? translateStaticTemplate(locale, "cost not configured") : `${display(preflight.estimated_cost, 6)} ${preflight.currency ?? ""}`;
      showNotice(preflight.can_queue ? "Preflight ready: {{samples}} samples, {{requests}} requests, {{tokens}} estimated tokens, {{cost}}." : "Preflight blocked: {{issues}}", preflight.can_queue
        ? { samples: preflight.sample_count, requests: preflight.estimated_requests, tokens: preflight.estimated_input_tokens + preflight.estimated_output_tokens, cost }
        : { issues: preflight.issues.join(" ") });
    } catch (error) { showError(error); } finally { setBusy(null); }
  }

  async function createRun(endpointId: string, sampleLimit: number | null = null, benchmarkKey = selectedBenchmark) {
    setBusy(`run-${endpointId}`);
    try {
      const [benchmarkId, benchmarkVersion] = benchmarkKey.split("@", 2);
      const run = await api.createRun(endpointId, selectedPromptId || undefined, parseJsonObject(runRequestBody, "Run Request Body override"), optionalNumber(runMaxConcurrency), benchmarkId, benchmarkVersion, sampleLimit);
      await selectRun(run.id);
      navigate("runs");
      showNotice("{{benchmark}} queued with an immutable configuration snapshot.", { benchmark: `${benchmarkId}@${benchmarkVersion}` });
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
      if (action === "clone") showNotice("Run cloned with a new immutable configuration snapshot.");
      else if (action === "rerun") showNotice("Benchmark rerun queued with a link to its source run.");
      else if (action === "retry") showNotice("Failed samples were queued as new attempts.");
      else if (action === "archive") showNotice("Run archived. Its evidence remains available through the API until deleted.");
      else {
        const actionResult = action === "execute" ? "executed" : action === "pause" ? "paused" : action === "resume" ? "resumed" : "cancelled";
        showNotice("Run {{action}}.", { action: translateStaticTemplate(locale, actionResult) });
      }
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
      showNotice("Run concurrency ceiling updated for future task claims; its evaluation snapshot remains unchanged.");
      await refresh();
    } catch (error) { showError(error); } finally { setBusy(null); }
  }


  async function pauseDataset(dataset: Dataset) {
    setBusy(`dataset-${dataset.id}`);
    try {
      await api.pauseDataset(dataset.id);
      showNotice("{{dataset}} download paused.", { dataset: dataset.dataset_id });
      await refresh();
    } catch (error) { showError(error); } finally { setBusy(null); }
  }

  async function selectRun(runId: string) {
    setSelectedRun(runId);
    setSelectedAttempt(null);
    setAttempts([]);
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
      const report = await api.createReport(runId, format, "single_model", []);
      showNotice("{{format}} {{reportType}} report generated.", { format: format.toUpperCase(), reportType: translateStaticTemplate(locale, "single model") });
      const reportUrl = await api.downloadReport(report.id);
      window.open(reportUrl, "_blank", "noopener,noreferrer");
      window.setTimeout(() => URL.revokeObjectURL(reportUrl), 60_000);
      if (selectedRun === runId) await selectRun(runId);
      await refresh();
    } catch (error) { showError(error); } finally { setBusy(null); }
  }



  async function createDataset(event: FormEvent) {
    event.preventDefault();
    setBusy("dataset");
    try {
      await api.createDataset({ ...datasetForm, source_url: datasetForm.source_url || null, checksum: datasetForm.checksum || null, credential_binding_id: datasetForm.credential_binding_id || null, license_text: datasetForm.license_text || null, input_field: datasetForm.input_field || null, reference_field: datasetForm.reference_field || null });
      setDatasetForm(initialDataset);
      showNotice("Dataset version registered.");
      await refresh();
    } catch (error) { showError(error); } finally { setBusy(null); }
  }



  async function queueDatasetRun() {
    setBusy("dataset-run");
    try {
      await api.createDatasetRun(datasetRunPayload(datasetRunForm));
      setNotice(t("datasetRun.queued"));
      setDatasetRunForm({ ...initialDatasetRun, model_endpoint_id: datasetRunForm.model_endpoint_id });
      setDatasetHandoffId(null);
      setLaunchPreflight(null);
      await refresh();
    } catch (error) {
      showError(error);
    } finally {
      setBusy(null);
    }
  }

  async function preflightDatasetRun() {
    setLaunchPreflight(null);
    setBusy("preflight-dataset");
    try {
      const result = await api.validateDatasetRun(datasetRunPayload(datasetRunForm));
      setLaunchPreflight({ kind: "dataset", result });
      showNotice(result.can_queue ? "Preflight ready: {{samples}} samples." : "Preflight blocked: {{issues}}", result.can_queue ? { samples: result.sample_count } : { issues: result.issues.join(" ") });
    } catch (error) {
      showError(error);
    } finally {
      setBusy(null);
    }
  }

  function startDatasetEvaluation(dataset: Dataset) {
    setDatasetRunForm((current) => ({ ...current, dataset_version_id: dataset.id, input_field: "", reference_field: "" }));
    setDatasetRunSchemaRequest((current) => current + 1);
    setDatasetHandoffId(dataset.id);
    setLaunchPreflight(null);
    navigate("runs");
  }




  async function prepareDataset(dataset: Dataset) {
    setBusy(`dataset-${dataset.id}`);
    try {
      if (dataset.license_text && !dataset.license_accepted_at) {
        await api.acceptDatasetLicense(dataset.id);
        showNotice("License accepted. The dataset can now be downloaded.");
      } else {
        await api.downloadDataset(dataset.id);
        showNotice("Dataset downloaded, verified, and cached.");
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
      showNotice("Dataset upload checksum verified and stored in the local dataset cache.");
      await refresh();
    } catch (error) { showError(error); } finally { setBusy(null); }
  }

  async function validateDataset(dataset: Dataset) {
    setBusy(`dataset-validate-${dataset.id}`);
    try { await api.validateDataset(dataset.id); showNotice("Dataset cache checksum and size were verified."); await refresh(); }
    catch (error) { showError(error); } finally { setBusy(null); }
  }

  async function clearDatasetCache(dataset: Dataset) {
    if (!window.confirm(translateStaticTemplate(locale, "Remove the cached data for {{dataset}} v{{version}}? The registered version will remain.", { dataset: dataset.dataset_id, version: dataset.version }))) return;
    setBusy(`dataset-clear-${dataset.id}`);
    try { await api.clearDatasetCache(dataset.id); showNotice("Dataset cache removed. You can download or upload it again."); await refresh(); }
    catch (error) { showError(error); } finally { setBusy(null); }
  }

  async function updateDatasetRecord(dataset: Dataset, payload: Record<string, string>) {
    setBusy(`dataset-edit-${dataset.id}`);
    try { await api.updateDataset(dataset.id, { ...payload, source_url: payload.source_url || null, checksum: payload.checksum || null, license_text: payload.license_text || null, credential_binding_id: payload.credential_binding_id || null, input_field: payload.input_field || null, reference_field: payload.reference_field || null }); showNotice("Dataset version updated."); await refresh(); }
    catch (error) { showError(error); }
    finally { setBusy(null); }
  }

  async function deleteDatasetRecord(dataset: Dataset) {
    if (!window.confirm(translateStaticTemplate(locale, "Delete dataset version?"))) return;
    setBusy(`dataset-delete-${dataset.id}`);
    try { await api.deleteDataset(dataset.id); showNotice("Dataset version deleted."); await refresh(); }
    catch (error) { showError(error); }
    finally { setBusy(null); }
  }

  async function compareRuns(event: FormEvent) {
    event.preventDefault();
    if (!comparisonRunA || !comparisonRunB || comparisonRunA === comparisonRunB) {
      showNotice("Choose two different runs from the same benchmark version.");
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
      showNotice("Human review saved separately from automated results.");
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
      showNotice(judgeForm.comparison_attempt_id.trim() ? "Blinded pairwise judge evidence and swap-test results saved." : "Independent LLM-as-judge assessment saved with rationale evidence.");
    } catch (error) { showError(error); } finally { setBusy(null); }
  }

  return (
    <AppShell
      completedRunCount={dashboard?.runs.completed ?? 0}
      locale={locale}
      notice={notice}
      systemHealth={systemHealth}
      theme={theme}
      view={view}
      onDismissNotice={() => setNotice(null)}
      onLocaleChange={setLocale}
      onThemeToggle={() => setTheme(theme === "dark" ? "light" : "dark")}
      onViewChange={navigate}
    >
      <StaticCopy>

      {view === "dashboard" && <OverviewDashboard analytics={analytics} dashboard={dashboard} endpoints={endpoints} runs={runs} systemHealth={systemHealth} tasks={tasks} onInspectRun={(runId) => { void selectRun(runId); navigate("runs"); }} onOpenView={navigate} />}
      {view === "guide" && <Guide onOpenView={navigate} />}

      {view === "models" && <ModelsPage
        busy={busy}
        capabilities={capabilities}
        editingEndpointId={editingEndpointId}
        endpoints={endpoints}
        form={form}
        onCancelEdit={cancelEndpointEdit}
        onDeclare={(endpointId, capability, status) => void declareCapability(endpointId, capability, status)}
        onEdit={editEndpoint}
        onFormChange={setForm}
        onProbe={(endpointId) => void probeCapabilities(endpointId)}
        onSubmit={createEndpoint}
        onTest={(endpointId) => void testEndpoint(endpointId)}
        testRequests={testRequests}
      />}

      {view === "datasets" && <DatasetsPage busy={busy} datasets={datasets} onClear={clearDatasetCache} onDelete={deleteDatasetRecord} onPause={pauseDataset} onPrepare={prepareDataset} onStartEvaluation={startDatasetEvaluation} onUpdate={updateDatasetRecord} onUpload={uploadDataset} onValidate={validateDataset} registration={<DatasetRegistrationForm busy={busy === "dataset"} onChange={setDatasetForm} onSubmit={createDataset} values={datasetForm} />} />}


      {view === "runs" && <RunsPage
        inspector={selectedRunInfo && <RunDetail run={selectedRunInfo} summary={runSummary} logs={runLogs} attempts={attempts} reports={reports} selectedAttempt={selectedAttempt} reviews={reviews} reviewAgreement={reviewAgreement} judgeAssessments={judgeAssessments} judgeAgreement={judgeAgreement} judgeForm={judgeForm} endpoints={endpoints} reviewForm={reviewForm} busy={busy} onJudgeForm={setJudgeForm} onReviewForm={setReviewForm} onReview={openReview} onLoadMoreAttempts={loadMoreAttempts} onCreateJudgeAssessment={createJudgeAssessment} onCreateReview={createReview} onGenerateReport={generateReport} />}
        launcher={<form className="form workspace-run-launcher" onSubmit={(event) => { event.preventDefault(); void queueDatasetRun(); }}>
          <label>{t("datasetRun.dataset")}<select required value={datasetRunForm.dataset_version_id} onChange={(event) => { setDatasetHandoffId(null); setLaunchPreflight(null); setDatasetRunForm((current) => ({ ...current, dataset_version_id: event.target.value, input_field: "", reference_field: "" })); }}><option value="">—</option>{datasets.filter((dataset) => dataset.status === "ready").map((dataset) => <option data-i18n-preserve key={dataset.id} value={dataset.id}>{dataset.dataset_id} v{dataset.version}</option>)}</select></label>
          {datasetHandoffId === datasetRunForm.dataset_version_id && <p className="workspace-launch-note">{t("runLauncher.datasetHandoff")}</p>}
          {datasets.some((dataset) => dataset.status !== "ready") && <p className="muted">{t("datasetRun.nonReadyHint")}</p>}
          {datasetRunFieldsLoading && <p className="muted">{t("runLauncher.schemaLoading")}</p>}
          {datasetRunFieldsError && <p className="error" role="alert" data-i18n-preserve>{datasetRunFieldsError}</p>}
          {datasetRunFieldsCollide && <p className="error" role="alert">{t("runLauncher.schemaDistinctFields")}</p>}
          {datasetRunFieldsError && <div className="actions"><button type="button" onClick={() => { setLaunchPreflight(null); setDatasetRunSchemaRequest((current) => current + 1); }}>{t("runLauncher.schemaRetry")}</button></div>}
          <div className="workspace-field-grid workspace-field-grid--two">
            <label>{t("datasetRun.inputField")}<select disabled={datasetRunFieldsLoading || datasetRunFields.length === 0 || Boolean(datasetRunForm.prompt_package_id)} required value={datasetRunForm.input_field} onChange={(event) => { setLaunchPreflight(null); setDatasetRunForm({ ...datasetRunForm, input_field: event.target.value }); }}>{datasetRunFields.length === 0 && <option value="">—</option>}{datasetRunFields.map((field) => <option data-i18n-preserve key={field} value={field}>{field}</option>)}</select></label>
            <label>{t("datasetRun.referenceField")}<select disabled={datasetRunFieldsLoading || datasetRunFields.length === 0} required value={datasetRunForm.reference_field} onChange={(event) => { setLaunchPreflight(null); setDatasetRunForm({ ...datasetRunForm, reference_field: event.target.value }); }}>{datasetRunFields.length === 0 && <option value="">—</option>}{datasetRunFields.map((field) => <option data-i18n-preserve key={field} value={field}>{field}</option>)}</select></label>
          </div>
          <label>{t("datasetRun.promptPackage")}<select value={datasetRunForm.prompt_package_id} onChange={(event) => { setLaunchPreflight(null); setDatasetRunForm({ ...datasetRunForm, prompt_package_id: event.target.value }); }}><option value="">—</option>{prompts.map((prompt) => <option data-i18n-preserve key={prompt.id} value={prompt.id}>{prompt.name} v{prompt.version}</option>)}</select></label>
          <label>{t("datasetRun.metric")}<select value={datasetRunForm.metric} onChange={(event) => { setLaunchPreflight(null); setDatasetRunForm({ ...datasetRunForm, metric: event.target.value as DatasetMetricId }); }}>{datasetMetricIds.map((metric) => <option key={metric} value={metric}>{t(datasetMetricLabelKeys[metric])}</option>)}</select></label>
          <p className="muted">{t("datasetRun.metricDefaultHint")}</p>
          <label>{t("datasetRun.sampleLimit")}<input required type="number" min={1} max={10000} value={datasetRunForm.sample_limit} onChange={(event) => { setLaunchPreflight(null); setDatasetRunForm({ ...datasetRunForm, sample_limit: event.target.value }); }} /></label>
          <button className="primary" disabled={busy === "dataset-run" || datasetRunFieldsLoading || Boolean(datasetRunFieldsError) || datasetRunFieldsCollide || !datasetRunForm.model_endpoint_id || !datasetRunForm.dataset_version_id || (!datasetRunForm.input_field && !datasetRunForm.prompt_package_id) || !datasetRunForm.reference_field}>{t("datasetRun.queue")}</button>
        </form>}
        onSelect={(runId) => void selectRun(runId)}
        preflight={<div className="workspace-run-context-controls">
          <label>{t("datasetRun.endpoint")}<select required value={datasetRunForm.model_endpoint_id} onChange={(event) => { setLaunchPreflight(null); setDatasetRunForm({ ...datasetRunForm, model_endpoint_id: event.target.value }); }}><option value="">—</option>{availableEndpoints.map((endpoint) => <option data-i18n-preserve key={endpoint.id} value={endpoint.id}>{endpoint.display_name}</option>)}</select></label>
          <div className="actions workspace-preflight-actions"><button className="secondary" disabled={!datasetRunForm.model_endpoint_id || !selectedQuickStart || busy === "preflight-quick-start"} onClick={() => void preflightRun(datasetRunForm.model_endpoint_id, Number(quickStartSampleLimit) || 1, selectedQuickStartBenchmark)} type="button">{t("runLauncher.preflightQuickStart")}</button><button className="secondary" disabled={!datasetRunForm.model_endpoint_id || datasetRunFieldsLoading || Boolean(datasetRunFieldsError) || datasetRunFieldsCollide || !datasetRunForm.dataset_version_id || (!datasetRunForm.input_field && !datasetRunForm.prompt_package_id) || !datasetRunForm.reference_field || busy === "preflight-dataset"} onClick={() => void preflightDatasetRun()} type="button">{t("runLauncher.preflightDataset")}</button></div>
          <div aria-live="polite" className={`workspace-preflight-state ${launchPreflight?.result.can_queue ? "is-ready" : launchPreflight ? "is-blocked" : ""}`} role="status"><strong>{busy === "preflight-quick-start" || busy === "preflight-dataset" ? t("runLauncher.checking") : launchPreflight?.result.can_queue ? t("runLauncher.ready") : launchPreflight ? t("runLauncher.blocked") : t("runLauncher.notChecked")}</strong>{launchPreflight && !launchPreflight.result.can_queue && <span data-i18n-preserve>{launchPreflight.result.issues.join(" ")}</span>}</div>
        </div>}
        quickStartLauncher={<form className="form workspace-run-launcher" onSubmit={(event) => { event.preventDefault(); if (selectedQuickStart) void createRun(datasetRunForm.model_endpoint_id, Number(quickStartSampleLimit) || 1, selectedQuickStartBenchmark); }}>
          <label>{t("runLauncher.quickStartBenchmark")}<select aria-label={t("runLauncher.quickStartBenchmark")} required value={selectedQuickStart ? `${selectedQuickStart.benchmark_id}@${selectedQuickStart.version}` : ""} onChange={(event) => { const benchmark = quickStartBenchmarks.find((item) => `${item.benchmark_id}@${item.version}` === event.target.value); setSelectedQuickStartBenchmark(event.target.value); setQuickStartSampleLimit(String(Number(benchmark?.manifest.sample_count) || 1)); setLaunchPreflight(null); }}><option value="">—</option>{quickStartBenchmarks.map((benchmark) => <option data-i18n-preserve key={benchmark.id} value={`${benchmark.benchmark_id}@${benchmark.version}`}>{benchmark.display_name}</option>)}</select></label>
          {selectedQuickStart && <div className="workspace-modality-tags">{(Array.isArray(selectedQuickStart.manifest.modalities) ? selectedQuickStart.manifest.modalities : []).map((modality) => <span className="badge" data-i18n-preserve key={String(modality)}>{String(modality)}</span>)}</div>}
          <label>{t("datasetRun.promptPackage")}<select value={selectedPromptId} onChange={(event) => { setSelectedPromptId(event.target.value); setLaunchPreflight(null); }}><option value="">—</option>{prompts.map((prompt) => <option data-i18n-preserve key={prompt.id} value={prompt.id}>{prompt.name} v{prompt.version}</option>)}</select></label>
          <label>{t("datasetRun.sampleLimit")}<input min={1} max={10000} required type="number" value={quickStartSampleLimit} onChange={(event) => { setQuickStartSampleLimit(event.target.value); setLaunchPreflight(null); }} /></label>
          <p className="workspace-launch-note">{t("runLauncher.offlineHint")}</p>
          <button className="primary" disabled={!datasetRunForm.model_endpoint_id || !selectedQuickStart || busy === `run-${datasetRunForm.model_endpoint_id}`}>{t("runLauncher.queueQuickStart")}</button>
        </form>}
        renderActions={(run) => <><button className="secondary" onClick={() => void selectRun(run.id)} type="button">Inspect</button>{!["completed", "completed_with_errors", "cancelled", "failed"].includes(run.status) && <><label className="compact-field">Run cap<input type="number" min="1" max="1000" value={runConcurrencyEdits[run.id] ?? (run.max_concurrency?.toString() ?? "")} onChange={(event) => setRunConcurrencyEdits((current) => ({ ...current, [run.id]: event.target.value }))} placeholder="Endpoint" /></label><button className="secondary" disabled={busy === `run-cap-${run.id}`} onClick={() => void updateRunConcurrency(run)} type="button">Set cap</button></>}{run.status === "queued" && <button disabled={busy === `execute-${run.id}`} onClick={() => void changeRun(run, "execute")} type="button">Execute</button>}{["queued", "running"].includes(run.status) && <button className="secondary" disabled={busy === `pause-${run.id}`} onClick={() => void changeRun(run, "pause")} type="button">Pause</button>}{run.status === "paused" && <button disabled={busy === `resume-${run.id}`} onClick={() => void changeRun(run, "resume")} type="button">Resume</button>}{run.status.startsWith("completed") && <><button className="secondary" disabled={busy === `clone-${run.id}`} onClick={() => void changeRun(run, "clone")} type="button">Clone</button><button className="secondary" disabled={busy === `rerun-${run.id}`} onClick={() => void changeRun(run, "rerun")} type="button">Rerun benchmark</button></>}{run.status === "completed_with_errors" && <button disabled={busy === `retry-${run.id}`} onClick={() => void changeRun(run, "retry")} type="button">Retry failed</button>}{["completed", "completed_with_errors", "cancelled", "failed"].includes(run.status) && <button className="secondary" disabled={busy === `archive-${run.id}`} onClick={() => void changeRun(run, "archive")} type="button">Archive</button>}{!["completed", "completed_with_errors", "cancelled", "failed"].includes(run.status) && <button className="danger" disabled={busy === `cancel-${run.id}`} onClick={() => void changeRun(run, "cancel")} type="button">Cancel</button>}</>}
        runs={runs}
        selectedRunId={selectedRun}
      />}

      {view === "analysis" && <AnalysisPage analytics={analytics} busy={busy} comparison={comparison} completedRuns={completedRuns} onRunAChange={setComparisonRunA} onRunBChange={setComparisonRunB} onSelectBaseline={(runId) => api.analyticsMatrix(runId || undefined)} onSubmitComparison={compareRuns} runA={comparisonRunA} runB={comparisonRunB} />}
      {view === "settings" && <SettingsPage apiToken={apiToken} locale={locale} onApiTokenChange={setApiToken} onClearToken={() => { setApiToken(""); api.setBearerToken(""); void refresh().catch(showError); }} onLocaleChange={setLocale} onSaveToken={() => { api.setBearerToken(apiToken); void refresh().catch(showError); }} onToggleTheme={() => setTheme(theme === "dark" ? "light" : "dark")} systemHealth={systemHealth} theme={theme} />}
      </StaticCopy>
    </AppShell>
  );
}

function Metric({ label, value, detail }: { label: string; value: string | number; detail: string }) {
  return <div className="metric-card"><span>{label}</span><strong>{value}</strong><small>{detail}</small></div>;
}

function SampleEvidenceBrowser({ attempts, onReview, onLoadMore, loadingMore }: { attempts: SampleAttempt[]; onReview: (attempt: SampleAttempt) => void; onLoadMore: () => Promise<void>; loadingMore: boolean }) {
  const { formatNumber: display } = useTranslation();
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
  const { formatCurrency: money, formatDate, formatNumber: display, formatPercent: percent, t } = useTranslation();
  const runRule = run.configuration_snapshot?.scoring_rule;
  const attemptRule = selectedAttempt?.reference_snapshot.scoring;
  const frozenScoringType = (
    runRule && typeof runRule === "object" && !Array.isArray(runRule) && typeof (runRule as Record<string, unknown>).type === "string"
      ? String((runRule as Record<string, unknown>).type)
      : attemptRule && typeof attemptRule === "object" && !Array.isArray(attemptRule) && typeof (attemptRule as Record<string, unknown>).type === "string"
        ? String((attemptRule as Record<string, unknown>).type)
        : null
  );
  const frozenMetricKey = frozenScoringType ? datasetMetricLabelKeys[frozenScoringType as DatasetMetricId] : undefined;
  return <>
    <section className="panel"><div className="section-title"><h2>Run executive summary</h2><span>{run.id.slice(0, 8)}</span></div>{frozenScoringType && <p className="muted"><span>{t("datasetRun.effectiveMetric")}</span> <strong>{frozenMetricKey ? t(frozenMetricKey) : frozenScoringType}</strong></p>}{summary ? <div className="metric-grid"><Metric label="Completion" value={`${summary.samples.completed}/${summary.samples.total}`} detail={percent(summary.samples.completion_rate)} /><Metric label="Accuracy" value={percent(summary.samples.accuracy)} detail={percent(summary.samples.success_rate) + " success rate"} /><Metric label="Latency" value={`${display(summary.latency_ms.average)} ms`} detail={`P50 ${display(summary.latency_ms.p50)} · P95 ${display(summary.latency_ms.p95)}`} /><Metric label="Cost" value={money(summary.cost.estimated, summary.cost.currency)} detail={`${summary.tokens.input} input / ${summary.tokens.output} output tokens`} /></div> : <p className="empty">Loading summary...</p>}</section>
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
  const { formatDate, formatNumber: display, formatPercent: percent } = useTranslation();
  const pairedAttempts = attempts.filter((attempt) => attempt.id !== selectedAttempt.id && attempt.sample_id === selectedAttempt.sample_id);
  return <section className="grid two"><article className="panel"><div className="section-title"><h2>Blinded pairwise judge</h2><span>Model identities are never sent to the judge.</span></div><form className="form" onSubmit={onSubmit}><label>Independent judge endpoint<select required value={form.endpoint_id} onChange={(event) => onForm({ ...form, endpoint_id: event.target.value })}><option value="">Select available endpoint</option>{endpoints.filter((endpoint) => endpoint.status === "available").map((endpoint) => <option key={endpoint.id} value={endpoint.id}>{endpoint.display_name} · {endpoint.model_name}</option>)}</select></label><label>Compare with matching sample attempt<select value={form.comparison_attempt_id} onChange={(event) => onForm({ ...form, comparison_attempt_id: event.target.value })}><option value="">Single-answer judge assessment</option>{pairedAttempts.map((attempt) => <option key={attempt.id} value={attempt.id}>{attempt.sample_id} · attempt {attempt.attempt_number} · {attempt.status}</option>)}</select></label><label>Or paste a sample attempt ID<input value={form.comparison_attempt_id} onChange={(event) => onForm({ ...form, comparison_attempt_id: event.target.value })} placeholder="Cross-run matching sample attempt ID" /></label>{form.comparison_attempt_id && <label><input type="checkbox" checked={form.swap_test} onChange={(event) => onForm({ ...form, swap_test: event.target.checked })} /> Run reverse-order swap test</label>}<label>Rubric (JSON)<textarea value={form.rubric} onChange={(event) => onForm({ ...form, rubric: event.target.value })} spellCheck={false} placeholder='{"criterion":"answer quality"}' /></label><button disabled={busy === "judge-submit"}>{form.comparison_attempt_id ? "Run blinded comparison" : "Request judge assessment"}</button></form></article><article className="panel"><h2>Judge agreement</h2>{agreement ? <><p><strong>{agreement.status.replaceAll("_", " ")}</strong> · {agreement.successful_assessment_count}/{agreement.assessment_count} succeeded</p><p className="muted">Score mean {display(agreement.scores.mean)} · spread {display(agreement.scores.range)} · {agreement.judge_endpoint_count} judge endpoint(s)</p><p className="muted">Decisions: {agreement.decisions.distinct.join(", ") || "none"} · swap groups {agreement.swap_test_group_count}</p></> : <p className="empty">Open a sample to load judge agreement.</p>}<h3>Judge evidence</h3>{assessments.length === 0 ? <p className="empty">No independent judge assessment has been recorded.</p> : <div className="review-list">{assessments.map((assessment) => <article className="review" key={assessment.id}><strong>{assessment.label || assessment.status} · {assessment.score ?? "--"}</strong><p>{assessment.rationale || assessment.error_message || "No rationale returned."}</p><small>{assessment.selected_answer ? `winner ${assessment.selected_answer} · ` : ""}{assessment.answer_order.join(" / ") || "single answer"} · {formatDate(assessment.created_at)}</small></article>)}</div>}</article></section>;
}

export function ReportsTable({ reports, onShare }: { reports: Report[]; onShare?: (report: Report, form: typeof initialShare) => Promise<ReportShare> }) {
  const { formatDate, locale } = useTranslation();
  const copy = reportCopy[locale];
  const [shareForm, setShareForm] = useState(initialShare);
  const [shareLink, setShareLink] = useState<string | null>(null);
  const [downloadError, setDownloadError] = useState<string | null>(null);

  async function createShare(report: Report) {
    setDownloadError(null);
    try {
      const form = shareForm;
      const days = Math.min(365, Math.max(1, Number(form.days) || 7));
      const share = onShare
        ? await onShare(report, form)
        : await api.createReportShare(report.id, {
          expires_at: new Date(Date.now() + days * 86_400_000).toISOString(),
          password: form.password || undefined,
          allow_download: form.allow_download,
          include_evidence: form.include_evidence,
        });
      setShareLink(share.share_url);
      // The one-time value is no longer needed after the server receives it.
      setShareForm({ ...form, password: "" });
    } catch (error) {
      setDownloadError(error instanceof Error ? error.message : copy.shareCreateFailed);
    }
  }

  async function downloadReport(report: Report) {
    setDownloadError(null);
    try {
      const objectUrl = await api.downloadReport(report.id);
      const link = document.createElement("a");
      link.href = objectUrl;
      link.download = `evaluation-report.${report.format === "markdown" ? "md" : report.format}`;
      link.click();
      window.setTimeout(() => URL.revokeObjectURL(objectUrl), 0);
    } catch (error) {
      setDownloadError(error instanceof Error ? error.message : copy.downloadFailed);
    }
  }

  return reports.length === 0 ? <p className="empty">{copy.noArtifacts}</p> : <><section className="share-policy"><h3>{copy.readOnlyPolicy}</h3><div className="field-row"><label>{copy.expiresInDays}<input type="number" min="1" max="365" value={shareForm.days} onChange={(event) => setShareForm({ ...shareForm, days: event.target.value })} /></label><label>{copy.optionalPassword}<input type="password" value={shareForm.password} onChange={(event) => setShareForm({ ...shareForm, password: event.target.value })} placeholder={copy.passwordPlaceholder} /></label></div><div className="actions"><label><input type="checkbox" checked={shareForm.allow_download} onChange={(event) => setShareForm({ ...shareForm, allow_download: event.target.checked })} /> {copy.allowDownload}</label><label><input type="checkbox" checked={shareForm.include_evidence} onChange={(event) => setShareForm({ ...shareForm, include_evidence: event.target.checked })} /> {copy.shareRawEvidence}</label></div><p className="muted">{copy.policyDescription}</p>{shareLink && <a href={shareLink} target="_blank" rel="noreferrer">{copy.openShare}</a>}</section>{downloadError && <p className="error" role="alert">{downloadError}</p>}<div className="table-wrap"><table><thead><tr><th>{copy.format}</th><th>{copy.generated}</th><th>{copy.version}</th><th /></tr></thead><tbody>{reports.map((report) => <tr key={report.id}><td>{report.format}</td><td>{formatDate(report.generated_at)}</td><td>{report.generator_version}</td><td><div className="actions"><button className="secondary" onClick={() => void downloadReport(report)}>{copy.download}</button><button className="secondary" onClick={() => void createShare(report)}>{copy.share}</button></div></td></tr>)}</tbody></table></div></>;
}

function fileAsDataUrl(file: File): Promise<string> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onerror = () => reject(reader.error ?? new Error("Unable to read selected file."));
    reader.onload = () => resolve(String(reader.result));
    reader.readAsDataURL(file);
  });
}
