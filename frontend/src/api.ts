export type Endpoint = {
  id: string;
  display_name: string;
  base_url: string;
  model_name: string;
  protocol_profile: "openai_chat_completions" | "openai_responses";
  api_key_mask: string;
  status: "unverified" | "available" | "unavailable";
  max_concurrency: number;
  requests_per_minute: number | null;
  tokens_per_minute: number | null;
  input_cost_per_million: number | null;
  output_cost_per_million: number | null;
  currency: string;
  last_connection_error: string | null;
};

export type EvaluationRun = {
  id: string;
  model_endpoint_id: string;
  benchmark_id: string;
  benchmark_version: string;
  status: string;
  total_samples: number;
  completed_samples: number;
  successful_samples: number;
  failed_samples: number;
  created_at: string;
  started_at: string | null;
  completed_at: string | null;
};

export type SampleAttempt = {
  id: string;
  sample_id: string;
  attempt_number: number;
  input_snapshot: Record<string, unknown>;
  reference_snapshot: Record<string, unknown>;
  request_snapshot: Record<string, unknown> | null;
  raw_response: string | null;
  parsed_prediction: string | null;
  score: number | null;
  latency_ms: number | null;
  input_tokens: number | null;
  output_tokens: number | null;
  estimated_cost: number | null;
  error_type: string | null;
  error_message: string | null;
  status: string;
  created_at: string;
  completed_at: string | null;
};

export type RunSummary = {
  samples: { total: number; completed: number; successful: number; failed: number; completion_rate: number | null; success_rate: number | null; accuracy: number | null };
  errors: { total: number; rate: number | null; api_errors: number; api_error_rate: number | null; parser_errors: number; parser_error_rate: number | null; by_type: Record<string, number> };
  latency_ms: { measured_samples: number; average: number | null; p50: number | null; p95: number | null; p99: number | null };
  tokens: { measured_samples: number; input: number; output: number; total: number };
  cost: { measured_samples: number; estimated: number | null; actual: number | null; currency: string | null };
};

export type Report = { id: string; run_id: string; report_type: string; format: string; artifact_path: string; generator_version: string; generated_at: string };
export type Benchmark = { id: string; benchmark_id: string; version: string; display_name: string; manifest: Record<string, unknown>; status: string; source: string; created_at: string };
export type Dashboard = {
  runs: { active: number; completed: number; recent_completed: Array<{ id: string; benchmark_id: string; status: string; completed_samples: number; total_samples: number; completed_at: string | null }> };
  queue: { pending: number; leased: number };
  workers: { active: number };
  endpoints: { available: number; unavailable: number; total: number };
  datasets: { ready: number; blocked: number };
  quality: RunSummary;
  api: { request_error_rate: number | null; estimated_cost_by_currency: Record<string, number> };
  reports: number;
};

export type PromptPackage = {
  id: string;
  name: string;
  version: string;
  prompt_type: string;
  system_message: string | null;
  user_template: string;
  created_at: string;
};

export type Dataset = {
  id: string;
  dataset_id: string;
  version: string;
  revision: string;
  source_url: string | null;
  license_text: string | null;
  license_accepted_at: string | null;
  status: string;
  error_message: string | null;
};

export type Capability = {
  id: string;
  capability_key: string;
  user_declared_status: string;
  auto_detection_status: string;
  effective_status: string;
};

export type Comparison = {
  run_a: string;
  run_b: string;
  benchmark: { id: string; version: string };
  shared_samples: number;
  outcomes: { both_correct: number; run_a_only_correct: number; run_b_only_correct: number; both_incorrect: number };
  run_a_summary: RunSummary;
  run_b_summary: RunSummary;
  differences: { accuracy: number | null; success_rate: number | null; error_rate: number | null; average_latency_ms: number | null; p95_latency_ms: number | null; estimated_cost: number | null; output_tokens: number };
};

export type Review = { id: string; sample_attempt_id: string; reviewer_id: string; rubric: Record<string, unknown> | null; score: number | null; labels: unknown[]; notes: string | null; created_at: string };
export type Asset = { id: string; original_filename: string; media_kind: "image" | "audio" | "video" | "file"; mime_type: string; size_bytes: number; sha256: string; created_at: string };
export type Task = { id: string; run_id: string; task_type: string; payload: Record<string, unknown>; status: string; priority: number; attempt_count: number; leased_by: string | null; lease_expires_at: string | null; next_retry_at: string | null; heartbeat_at: string | null; created_at: string; updated_at: string };
export type AnalyticsMatrix = { heatmap: Array<{ run_id: string; model_endpoint_id: string; model_name: string; benchmark_id: string; benchmark_version: string; accuracy: number | null; success_rate: number | null; error_rate: number | null; average_latency_ms: number | null; estimated_cost: number | null; currency: string | null; required_capabilities: string[] }>; capability_matrix: Array<{ model_endpoint_id: string; capability: string; run_count: number; accuracy: number | null; success_rate: number | null; error_rate: number | null; average_latency_ms: number | null; estimated_cost: number | null }> };
export type ReportShare = { id: string; report_id: string; expires_at: string; allow_download: boolean; revoked_at: string | null; created_at: string; share_url: string | null };

const apiBase = import.meta.env.VITE_API_BASE_URL ?? "http://127.0.0.1:8000/api/v1";

export class ApiError extends Error {
  constructor(message: string, readonly status: number) {
    super(message);
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${apiBase}${path}`, {
    headers: { "Content-Type": "application/json", ...init?.headers },
    ...init,
  });
  if (!response.ok) {
    const payload = await response.json().catch(() => null);
    const detail = typeof payload?.detail === "string" ? payload.detail : "Request failed.";
    throw new ApiError(detail, response.status);
  }
  if (response.status === 204) return undefined as T;
  return response.json() as Promise<T>;
}

export const api = {
  listEndpoints: () => request<Endpoint[]>("/model-endpoints"),
  createEndpoint: (body: Record<string, unknown>) => request<Endpoint>("/model-endpoints", { method: "POST", body: JSON.stringify(body) }),
  testEndpoint: (endpointId: string) => request<{ success: boolean; status: Endpoint["status"]; message: string }>(`/model-endpoints/${endpointId}/connection-test`, { method: "POST" }),
  listRuns: () => request<EvaluationRun[]>("/evaluation-runs"),
  createRun: (modelEndpointId: string, promptPackageId?: string) => request<EvaluationRun>("/evaluation-runs", { method: "POST", body: JSON.stringify({ model_endpoint_id: modelEndpointId, prompt_package_id: promptPackageId || null }) }),
  createCustomMultimodalRun: (body: Record<string, unknown>) => request<EvaluationRun>("/evaluation-runs/custom-multimodal", { method: "POST", body: JSON.stringify(body) }),
  executeRun: (runId: string) => request<EvaluationRun>(`/evaluation-runs/${runId}/execute`, { method: "POST" }),
  pauseRun: (runId: string) => request<EvaluationRun>(`/evaluation-runs/${runId}/pause`, { method: "POST" }),
  resumeRun: (runId: string) => request<EvaluationRun>(`/evaluation-runs/${runId}/resume`, { method: "POST" }),
  cancelRun: (runId: string) => request<EvaluationRun>(`/evaluation-runs/${runId}/cancel`, { method: "POST" }),
  cloneRun: (runId: string) => request<EvaluationRun>(`/evaluation-runs/${runId}/clone`, { method: "POST" }),
  retryFailedRun: (runId: string) => request<EvaluationRun>(`/evaluation-runs/${runId}/retry-failed`, { method: "POST" }),
  listAttempts: (runId: string) => request<SampleAttempt[]>(`/evaluation-runs/${runId}/attempts`),
  getRunSummary: (runId: string) => request<RunSummary>(`/evaluation-runs/${runId}/summary`),
  runEventsUrl: (runId: string) => `${apiBase}/evaluation-runs/${runId}/events`,
  createReport: (runId: string, format: "html" | "json" | "csv" | "parquet" | "markdown" | "pdf") => request<Report>("/reports", { method: "POST", body: JSON.stringify({ run_id: runId, format }) }),
  listReports: (runId: string) => request<Report[]>(`/reports/run/${runId}`),
  createReportShare: (reportId: string, body: Record<string, unknown> = {}) => request<ReportShare>(`/reports/${reportId}/shares`, { method: "POST", body: JSON.stringify(body) }),
  reportDownloadUrl: (reportId: string) => `${apiBase}/reports/${reportId}/download`,
  dashboard: () => request<Dashboard>("/dashboard"),
  compare: (runA: string, runB: string) => request<Comparison>(`/comparisons?run_a=${encodeURIComponent(runA)}&run_b=${encodeURIComponent(runB)}`),
  listBenchmarks: () => request<Benchmark[]>("/benchmarks"),
  listPromptPackages: () => request<PromptPackage[]>("/prompt-packages"),
  createPromptPackage: (body: Record<string, unknown>) => request<PromptPackage>("/prompt-packages", { method: "POST", body: JSON.stringify(body) }),
  listDatasets: () => request<Dataset[]>("/datasets"),
  createDataset: (body: Record<string, unknown>) => request<Dataset>("/datasets", { method: "POST", body: JSON.stringify(body) }),
  acceptDatasetLicense: (datasetId: string) => request<Dataset>(`/datasets/${datasetId}/accept-license`, { method: "POST" }),
  downloadDataset: (datasetId: string) => request<Dataset>(`/datasets/${datasetId}/download`, { method: "POST" }),
  listCapabilities: (endpointId: string) => request<Capability[]>(`/model-endpoints/${endpointId}/capabilities`),
  detectCapabilities: (endpointId: string) => request<Capability[]>(`/model-endpoints/${endpointId}/capabilities/detect`, { method: "POST" }),
  declareCapability: (endpointId: string, capabilityKey: string, userDeclaredStatus: "supported" | "unsupported" | "unknown") => request<Capability>(`/model-endpoints/${endpointId}/capabilities`, { method: "PUT", body: JSON.stringify({ capability_key: capabilityKey, user_declared_status: userDeclaredStatus }) }),
  createReview: (body: Record<string, unknown>) => request<Review>("/reviews", { method: "POST", body: JSON.stringify(body) }),
  listReviews: (attemptId: string) => request<Review[]>(`/reviews/sample/${attemptId}`),
  uploadAsset: (body: { filename: string; mime_type: string; base64_data: string }) => request<Asset>("/assets", { method: "POST", body: JSON.stringify(body) }),
  listTasks: () => request<Task[]>("/tasks"),
  updateTaskPriority: (taskId: string, priority: number) => request<Task>(`/tasks/${taskId}`, { method: "PATCH", body: JSON.stringify({ priority }) }),
  analyticsMatrix: () => request<AnalyticsMatrix>("/analytics/matrix"),
};
