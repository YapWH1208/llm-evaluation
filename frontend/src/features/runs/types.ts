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
