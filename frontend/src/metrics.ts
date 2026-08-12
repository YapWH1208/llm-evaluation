export const METRIC_PROFILE_VERSION = "1.1.0";

export const METRIC_DEFINITIONS = {
  score: { label: "Primary score", unit: "ratio", profile: "all" },
  accuracy: { label: "Accuracy", unit: "ratio", profile: "classification" },
  precision_macro: { label: "Macro precision", unit: "ratio", profile: "classification" },
  recall_macro: { label: "Macro recall", unit: "ratio", profile: "classification" },
  f1_macro: { label: "Macro F1", unit: "ratio", profile: "classification" },
  exact_match: { label: "Exact match", unit: "ratio", profile: "generation" },
  normalized_exact_match: { label: "Normalized exact match", unit: "ratio", profile: "generation" },
  token_f1: { label: "Token F1", unit: "ratio", profile: "generation" },
  bleu: { label: "BLEU", unit: "ratio", profile: "generation" },
  rouge_l: { label: "ROUGE-L", unit: "ratio", profile: "generation" },
  llm_judge: { label: "LLM-as-judge", unit: "ratio", profile: "all" },
  "pass@1": { label: "pass@1", unit: "ratio", profile: "code" },
  perplexity: { label: "Perplexity", unit: "perplexity", profile: "language_modeling" },
  completion_rate: { label: "Completion rate", unit: "ratio", profile: "operational" },
  success_rate: { label: "Success rate", unit: "ratio", profile: "operational" },
  error_rate: { label: "Error rate", unit: "ratio", profile: "operational" },
  average_latency_ms: { label: "Average latency", unit: "milliseconds", profile: "operational" },
  p50_latency_ms: { label: "p50 latency", unit: "milliseconds", profile: "operational" },
  p95_latency_ms: { label: "p95 latency", unit: "milliseconds", profile: "operational" },
  p99_latency_ms: { label: "p99 latency", unit: "milliseconds", profile: "operational" },
  input_tokens: { label: "Input tokens", unit: "tokens", profile: "operational" },
  output_tokens: { label: "Output tokens", unit: "tokens", profile: "operational" },
  estimated_cost: { label: "Estimated cost", unit: "currency", profile: "operational" },
} as const;

export type MetricId = keyof typeof METRIC_DEFINITIONS;
export type MetricUnit = (typeof METRIC_DEFINITIONS)[MetricId]["unit"];
export type MetricProfile = (typeof METRIC_DEFINITIONS)[MetricId]["profile"];

export function metricDefinition(metricId: MetricId) {
  return METRIC_DEFINITIONS[metricId];
}
