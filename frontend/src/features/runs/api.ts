import { request, subscribeToEvents } from "../../shared/api/client";
import type { AggregateMetric, EvaluationRun, RunLogEntry, RunPreflight, RunSummary, SampleAttempt } from "./types";

export const runsApi = {
  list: () => request<EvaluationRun[]>("/evaluation-runs"),
  create: (modelEndpointId: string, promptPackageId?: string, requestBodyOverride: Record<string, unknown> = {}, maxConcurrency: number | null = null, benchmarkId = "text-quick-check", benchmarkVersion = "1.0.0", sampleLimit: number | null = null) => request<EvaluationRun>("/evaluation-runs", { method: "POST", body: JSON.stringify({ model_endpoint_id: modelEndpointId, prompt_package_id: promptPackageId || null, request_body_override: requestBodyOverride, max_concurrency: maxConcurrency, benchmark_id: benchmarkId, benchmark_version: benchmarkVersion, sample_limit: sampleLimit }) }),
  validate: (modelEndpointId: string, promptPackageId?: string, requestBodyOverride: Record<string, unknown> = {}, maxConcurrency: number | null = null, benchmarkId = "text-quick-check", benchmarkVersion = "1.0.0", sampleLimit: number | null = null) => request<RunPreflight>("/evaluation-runs/validate", { method: "POST", body: JSON.stringify({ model_endpoint_id: modelEndpointId, prompt_package_id: promptPackageId || null, request_body_override: requestBodyOverride, max_concurrency: maxConcurrency, benchmark_id: benchmarkId, benchmark_version: benchmarkVersion, sample_limit: sampleLimit }) }),
  createDataset: (body: Record<string, unknown>) => request<EvaluationRun>("/evaluation-runs/dataset", { method: "POST", body: JSON.stringify(body) }),
  validateDataset: (body: Record<string, unknown>) => request<RunPreflight>("/evaluation-runs/dataset/preflight", { method: "POST", body: JSON.stringify(body) }),
  execute: (runId: string) => request<EvaluationRun>(`/evaluation-runs/${runId}/execute`, { method: "POST" }),
  pause: (runId: string) => request<EvaluationRun>(`/evaluation-runs/${runId}/pause`, { method: "POST" }),
  resume: (runId: string) => request<EvaluationRun>(`/evaluation-runs/${runId}/resume`, { method: "POST" }),
  cancel: (runId: string) => request<EvaluationRun>(`/evaluation-runs/${runId}/cancel`, { method: "POST" }),
  clone: (runId: string) => request<EvaluationRun>(`/evaluation-runs/${runId}/clone`, { method: "POST" }),
  rerunBenchmark: (runId: string) => request<EvaluationRun>(`/evaluation-runs/${runId}/rerun-benchmark`, { method: "POST" }),
  updateConcurrency: (runId: string, maxConcurrency: number | null) => request<EvaluationRun>(`/evaluation-runs/${runId}/scheduling`, { method: "PATCH", body: JSON.stringify({ max_concurrency: maxConcurrency }) }),
  retryFailed: (runId: string) => request<EvaluationRun>(`/evaluation-runs/${runId}/retry-failed`, { method: "POST" }),
  archive: (runId: string) => request<EvaluationRun>(`/evaluation-runs/${runId}/archive`, { method: "POST" }),
  remove: (runId: string) => request<void>(`/evaluation-runs/${runId}`, { method: "DELETE" }),
  listAttempts: (runId: string, offset = 0, limit = 200) => request<SampleAttempt[]>(`/evaluation-runs/${runId}/attempts?offset=${offset}&limit=${limit}`),
  summary: (runId: string) => request<RunSummary>(`/evaluation-runs/${runId}/summary`),
  metrics: (runId: string) => request<AggregateMetric[]>(`/analytics/runs/${encodeURIComponent(runId)}/metrics`),
  logs: (runId: string, offset = 0, limit = 200) => request<RunLogEntry[]>(`/evaluation-runs/${runId}/logs?offset=${offset}&limit=${limit}`),
  subscribe: (runId: string, onEvent: () => void) => subscribeToEvents(`/evaluation-runs/${runId}/events`, "run", onEvent),
};

export type { AggregateMetric, EvaluationRun, RunLogEntry, RunPreflight, RunSummary, SampleAttempt } from "./types";
