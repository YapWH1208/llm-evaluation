export type Endpoint = {
  id: string;
  display_name: string;
  base_url: string;
  model_name: string;
  api_key_mask: string;
  status: "unverified" | "available" | "unavailable";
  max_concurrency: number;
  requests_per_minute: number | null;
  tokens_per_minute: number | null;
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
  error_type: string | null;
  error_message: string | null;
  status: string;
};

export type Report = { id: string; run_id: string; report_type: string; format: string; artifact_path: string; generated_at: string };
export type Dashboard = {
  runs: { active: number; completed: number };
  queue: { pending: number; leased: number };
  endpoints: { available: number; unavailable: number; total: number };
  datasets: { ready: number; blocked: number };
  reports: number;
};

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
  createEndpoint: (body: Record<string, unknown>) =>
    request<Endpoint>("/model-endpoints", { method: "POST", body: JSON.stringify(body) }),
  testEndpoint: (endpointId: string) =>
    request<{ success: boolean; status: Endpoint["status"]; message: string }>(
      `/model-endpoints/${endpointId}/connection-test`,
      { method: "POST" },
    ),
  listRuns: () => request<EvaluationRun[]>("/evaluation-runs"),
  createRun: (modelEndpointId: string) =>
    request<EvaluationRun>("/evaluation-runs", {
      method: "POST",
      body: JSON.stringify({ model_endpoint_id: modelEndpointId }),
    }),
  executeRun: (runId: string) =>
    request<EvaluationRun>(`/evaluation-runs/${runId}/execute`, { method: "POST" }),
  listAttempts: (runId: string) => request<SampleAttempt[]>(`/evaluation-runs/${runId}/attempts`),
  createReport: (runId: string, format: "html" | "json" | "csv") => request<Report>("/reports", { method: "POST", body: JSON.stringify({ run_id: runId, format }) }),
  reportDownloadUrl: (reportId: string) => `${apiBase}/reports/${reportId}/download`,
  dashboard: () => request<Dashboard>("/dashboard"),
};
