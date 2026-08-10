export const datasetMetricIds = [
  "default",
  "exact_match",
  "normalized_exact_match",
  "token_f1",
  "bleu",
  "rouge_l",
] as const;

export type DatasetMetricId = typeof datasetMetricIds[number];
export type DatasetScoringRule = { type: Exclude<DatasetMetricId, "default"> };

export function datasetScoringRuleFor(metric: DatasetMetricId): DatasetScoringRule | undefined {
  return metric === "default" ? undefined : { type: metric };
}
