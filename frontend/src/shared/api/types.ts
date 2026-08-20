export type Endpoint = {
  id: string;
  display_name: string;
  base_url: string;
  model_name: string;
  protocol_profile: "openai_chat_completions" | "openai_responses" | "anthropic_messages" | "gemini_generate_content" | "azure_openai_chat_completions" | "ollama_chat" | "custom_http_json";
  api_key_mask: string;
  custom_headers: Record<string, string>;
  default_request_body: Record<string, unknown>;
  timeout_seconds: number;
  status: "unverified" | "available" | "unavailable";
  max_concurrency: number;
  requests_per_second: number | null;
  requests_per_minute: number | null;
  tokens_per_minute: number | null;
  input_tokens_per_minute: number | null;
  output_tokens_per_minute: number | null;
  input_cost_per_million: number | null;
  output_cost_per_million: number | null;
  currency: string;
  tags: string[];
  notes: string | null;
  last_connection_error: string | null;
  api_key_max_concurrency: number | null;
};

export type ConnectionTest = {
  success: boolean;
  status: Endpoint["status"];
  message: string;
  provider_status_code: number | null;
  tested_at: string;
  request: { method: "POST"; url: string; body: Record<string, unknown> };
};

export type EvaluationRun = {
  id: string;
  display_name: string;
  model_endpoint_id: string;
  created_by: string | null;
  max_concurrency: number | null;
  benchmark_id: string;
  benchmark_version: string;
  configuration_snapshot?: Record<string, unknown>;
  status: string;
  total_samples: number;
  completed_samples: number;
  successful_samples: number;
  failed_samples: number;
  created_at: string;
  started_at: string | null;
  completed_at: string | null;
  archived_at: string | null;
};

export type RunPreflight = {
  can_queue: boolean;
  issues: string[];
  sample_count: number;
  estimated_requests: number;
  estimated_input_tokens: number;
  estimated_output_tokens: number;
  estimated_cost: number | null;
  currency: string | null;
  judge_estimate: {
    estimated_requests: number;
    estimated_input_tokens: number;
    estimated_output_tokens: number;
    estimated_cost: number | null;
    currency: string | null;
  } | null;
  compatibility: { required: string[]; unsupported: string[]; unverified: string[] };
  datasets: Array<Record<string, unknown>>;
  request_body_evidence: Record<string, unknown> | null;
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
  metric_evidence?: Record<string, unknown> | null;
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
  sample_metadata: Record<string, string>;
  judge_disagreement: boolean;
  human_review_status: "unreviewed" | "reviewed" | "adjudicated";
};
export type AggregateMetric = {
  id: string;
  run_id: string;
  benchmark_id: string;
  model_endpoint_id: string;
  metric_name: string;
  metric_label: string;
  metric_value: number | null;
  availability_reason: string | null;
  sample_count: number;
  confidence_interval: { method: string; lower: number; upper: number } | null;
  aggregation_version: string;
  profile_version: string;
  unit: import("../../metrics").MetricUnit;
  profile: import("../../metrics").MetricProfile;
  required_evidence: string[];
  created_at: string;
};
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

export type RunSummary = {
  samples: { total: number; completed: number; successful: number; failed: number; completion_rate: number | null; success_rate: number | null; accuracy: number | null };
  errors: { total: number; rate: number | null; api_errors: number; api_error_rate: number | null; parser_errors: number; parser_error_rate: number | null; by_type: Record<string, number> };
  latency_ms: { measured_samples: number; average: number | null; p50: number | null; p95: number | null; p99: number | null };
  tokens: { measured_samples: number; input: number; output: number; total: number };
  cost: { measured_samples: number; estimated: number | null; actual: number | null; currency: string | null };
  insights: { capabilities: Array<{ capability: string; score: number | null; sample_count: number }>; strongest_capability: { capability: string; score: number; sample_count: number } | null; weakest_capability: { capability: string; score: number; sample_count: number } | null; significant_anomalies: Array<{ kind: string; value: number; threshold: number }>; major_regressions: Array<{ metric: string; delta: number; baseline: number; current: number }> };
};

export type RunLogEntry = {
  timestamp: string;
  level: string;
  event: string;
  message: string;
  task_id: string | null;
  sample_attempt_id: string | null;
  details: Record<string, unknown>;
};

export type Report = { id: string; run_id: string; report_type: string; format: string; artifact_path: string; generator_version: string; generated_at: string };
export type ReportFormat = "html" | "json" | "csv" | "markdown";
export type ReportType = "single_model" | "multi_model_comparison" | "regression" | "prompt_comparison" | "benchmark" | "reliability" | "cost" | "human_review";
export type Benchmark = { id: string; benchmark_id: string; version: string; display_name: string; manifest: Record<string, unknown>; status: string; source: string; created_at: string };
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

export type PromptPackage = {
  id: string;
  name: string;
  version: string;
  prompt_type: string;
  system_message: string | null;
  user_template: string;
  few_shot_examples: unknown[];
  output_format: Record<string, unknown> | null;
  response_parser: Record<string, unknown> | null;
  scoring_rule: Record<string, unknown> | null;
  change_log: string | null;
  created_at: string;
};

export type Dataset = {
  id: string;
  dataset_id: string;
  version: string;
  revision: string;
  source_url: string | null;
  credential_binding_id: string | null;
  checksum: string | null;
  local_path: string | null;
  size_bytes: number | null;
  license_text: string | null;
  license_accepted_at: string | null;
  status: string;
  error_message: string | null;
  input_field: string | null;
  reference_field: string | null;
  capabilities: string[];
  languages: string[];
  evaluation_type: "classification" | "generation" | "code" | "language_modeling" | "custom";
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

export type Review = { id: string; sample_attempt_id: string; reviewer_id: string; rubric: Record<string, unknown> | null; score: number | null; labels: string[]; notes: string | null; review_stage: "primary" | "secondary" | "adjudication"; adjudicates_review_ids: string[]; created_at: string };
export type ReviewAgreement = { sample_attempt_id: string; review_count: number; distinct_reviewer_count: number; review_stage_counts: { primary: number; secondary: number; adjudication: number }; numeric_score: { count: number; mean: number | null; standard_deviation: number | null; range: number | null }; label_agreement: number | null; status: string; adjudication_review_id: string | null };
export type JudgeAssessment = { id: string; sample_attempt_id: string; judge_endpoint_id: string; comparison_sample_attempt_id: string | null; rubric: Record<string, unknown>; answer_order: string[]; swap_test_group_id: string | null; selected_answer: string | null; score: number | null; label: string | null; rationale: string | null; raw_response: string | null; input_tokens: number | null; output_tokens: number | null; estimated_cost: number | null; status: string; error_message: string | null; created_at: string };
export type JudgeAgreement = { status: string; assessment_count: number; successful_assessment_count: number; judge_endpoint_count: number; scores: { mean: number | null; range: number | null }; decisions: { distinct: string[]; count: number }; swap_test_group_count: number };
export type Task = { id: string; run_id: string; parent_task_id: string | null; task_type: string; payload: Record<string, unknown>; status: string; priority: number; attempt_count: number; leased_by: string | null; lease_expires_at: string | null; next_retry_at: string | null; heartbeat_at: string | null; created_at: string; updated_at: string };
export type AnalyticsCell = { x_key: string; x_label: string; y_key: string; y_label: string; run_ids: string[]; score: number | null; sample_count: number; confidence_interval: { method: string; lower: number; upper: number } | null; success_rate: number | null; error_rate: number | null; average_latency_ms: number | null; estimated_cost: number | null; currency: string | null; baseline_score: number | null; delta: number | null };
export type AnalyticsMatrix = { baseline_run_id: string | null; heatmap: Array<{ run_id: string; model_endpoint_id: string; model_name: string; benchmark_id: string; benchmark_version: string; accuracy: number | null; success_rate: number | null; error_rate: number | null; average_latency_ms: number | null; estimated_cost: number | null; currency: string | null; required_capabilities: string[]; sample_count: number; confidence_interval: { method: string; lower: number; upper: number } | null }>; capability_matrix: Array<{ model_endpoint_id: string; capability: string; run_count: number; accuracy: number | null; success_rate: number | null; error_rate: number | null; average_latency_ms: number | null; estimated_cost: number | null; sample_count: number; confidence_interval: { method: string; lower: number; upper: number } | null; baseline_score: number | null; delta: number | null }>; heatmaps: Record<"model_benchmark" | "model_capability" | "model_language" | "model_difficulty" | "prompt_benchmark" | "model_modality", AnalyticsCell[]> };
export type SystemHealth = { status: string; database: string; schema_version: number; database_connected: boolean; disk: { available_bytes: number; total_bytes: number }; queue: { pending: number; active: number } };

const apiBase = import.meta.env.VITE_API_BASE_URL ?? "http://127.0.0.1:8000/api/v1";
const publicApiBase = import.meta.env.VITE_PUBLIC_API_BASE_URL ?? apiBase.replace(/\/api\/v1$/, "");
