import type { Dataset } from "../datasets/types";
import type { RunSummary } from "../runs/types";

export type ScatterQuery = {
  x_axis?: string;
  y_axis?: string;
  run_ids?: string[];
  date_from?: string;
  date_to?: string;
  model_endpoint_id?: string;
  dataset?: string;
  statuses?: string[];
  capability?: string;
  language?: string;
  evaluation_type?: Dataset["evaluation_type"];
  min_score?: number;
  max_score?: number;
  min_accuracy?: number;
  max_accuracy?: number;
  min_latency_ms?: number;
  max_latency_ms?: number;
  min_cost?: number;
  max_cost?: number;
  max_points?: number;
};

export type ScatterAxis = { metric_name: string; label: string; unit: string; profile: string };
export type ScatterPoint = {
  run_id: string;
  display_name: string;
  model_endpoint_id: string;
  model_name: string;
  dataset: string;
  benchmark_id: string;
  benchmark_version: string;
  status: string;
  created_at: string;
  capabilities: string[];
  languages: string[];
  evaluation_type: Dataset["evaluation_type"];
  x: number;
  y: number;
  x_metric: string;
  y_metric: string;
  x_availability_reason: string | null;
  y_availability_reason: string | null;
};
export type ScatterResponse = {
  x_axis: ScatterAxis;
  y_axis: ScatterAxis;
  selected_run_ids: string[];
  eligible_run_count: number;
  plottable_count: number;
  plotted_count: number;
  unavailable_count: number;
  unavailable_by_axis: { x: number; y: number; both: number };
  unavailable_reasons: Array<{ axis: "x" | "y"; reason: string; count: number }>;
  truncated_count: number;
  max_points: number;
  points: ScatterPoint[];
};

export type LeaderboardQuery = {
  dataset?: string;
  model_endpoint_id?: string;
  statuses?: string[];
  created_from?: string;
  created_to?: string;
  capability?: string;
  language?: string;
  evaluation_type?: Dataset["evaluation_type"];
  available_metric?: string;
  sort?: string;
  direction?: "asc" | "desc";
  page?: number;
  page_size?: number;
};
export type LeaderboardMetric = {
  metric_name: string;
  label: string;
  unit: string;
  value: number | null;
  sample_count: number;
  availability_reason: string | null;
};
export type LeaderboardRow = {
  run_id: string;
  display_name: string;
  model_endpoint_id: string;
  model_name: string;
  dataset: string;
  benchmark_id: string;
  benchmark_version: string;
  status: string;
  created_at: string;
  completed_at: string | null;
  capabilities: string[];
  languages: string[];
  evaluation_type: Dataset["evaluation_type"];
  score: number | null;
  primary_metric: string;
  average_latency_ms: number | null;
  p95_latency_ms: number | null;
  estimated_cost: number | null;
  sample_count: number;
  completed_samples: number;
  successful_samples: number;
  failed_samples: number;
  available_metrics: string[];
  named_metrics: Record<string, LeaderboardMetric>;
};
export type LeaderboardResponse = {
  items: LeaderboardRow[];
  total: number;
  page: number;
  page_size: number;
  total_pages: number;
  sort: string;
  direction: "asc" | "desc";
};

export type Dashboard = {
  runs: { active: number; completed: number; recent_completed: Array<{ id: string; display_name: string; benchmark_id: string; status: string; completed_samples: number; total_samples: number; completed_at: string | null }> };
  queue: { pending: number; leased: number };
  workers: { active: number };
  endpoints: { available: number; unavailable: number; total: number };
  datasets: { ready: number; blocked: number };
  quality: RunSummary;
  api: { request_error_rate: number | null; estimated_cost_by_currency: Record<string, number> };
  reports: number;
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
  runs: Record<"a" | "b", { id: string; display_name: string; model_endpoint_id: string; model_name: string; status: string; created_at: string | null }>;
  named_metrics: Array<{
    metric_name: string;
    label: string;
    unit: string;
    profile: string;
    run_a: { value: number | null; availability_reason: string | null; sample_count: number };
    run_b: { value: number | null; availability_reason: string | null; sample_count: number };
    delta: number | null;
  }>;
  metric_groups: Array<{ unit: string; metrics: Comparison["named_metrics"] }>;
  outcome_distribution: Array<{ outcome: keyof Comparison["outcomes"]; count: number }>;
};

export type Task = { id: string; run_id: string; parent_task_id: string | null; task_type: string; payload: Record<string, unknown>; status: string; priority: number; attempt_count: number; leased_by: string | null; lease_expires_at: string | null; next_retry_at: string | null; heartbeat_at: string | null; created_at: string; updated_at: string };
export type AnalyticsCell = { x_key: string; x_label: string; y_key: string; y_label: string; run_ids: string[]; score: number | null; sample_count: number; confidence_interval: { method: string; lower: number; upper: number } | null; success_rate: number | null; error_rate: number | null; average_latency_ms: number | null; estimated_cost: number | null; currency: string | null; baseline_score: number | null; delta: number | null };
export type AnalyticsMatrix = { baseline_run_id: string | null; heatmap: Array<{ run_id: string; model_endpoint_id: string; model_name: string; benchmark_id: string; benchmark_version: string; accuracy: number | null; success_rate: number | null; error_rate: number | null; average_latency_ms: number | null; estimated_cost: number | null; currency: string | null; required_capabilities: string[]; sample_count: number; confidence_interval: { method: string; lower: number; upper: number } | null }>; capability_matrix: Array<{ model_endpoint_id: string; capability: string; run_count: number; accuracy: number | null; success_rate: number | null; error_rate: number | null; average_latency_ms: number | null; estimated_cost: number | null; sample_count: number; confidence_interval: { method: string; lower: number; upper: number } | null; baseline_score: number | null; delta: number | null }>; heatmaps: Record<"model_benchmark" | "model_capability" | "model_language" | "model_difficulty" | "prompt_benchmark" | "model_modality", AnalyticsCell[]> };
export type SystemHealth = { status: string; database: string; schema_version: number; database_connected: boolean; disk: { available_bytes: number; total_bytes: number }; queue: { pending: number; active: number } };
