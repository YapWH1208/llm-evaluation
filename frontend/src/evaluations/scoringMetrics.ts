export const datasetMetricIds = [
  "default",
  "exact_match",
  "normalized_exact_match",
  "token_f1",
  "bleu",
  "rouge_l",
  "llm_judge",
] as const;

export type DatasetMetricId = typeof datasetMetricIds[number];
export type DatasetJudgeConfiguration = {
  judgeEndpointId: string;
  systemMessage: string;
};
export type DatasetScoringRule =
  | { type: Exclude<DatasetMetricId, "default" | "llm_judge"> }
  | { type: "llm_judge"; judge_endpoint_id: string; system_message: string };

export function datasetScoringRuleFor(
  metric: DatasetMetricId,
  judge: DatasetJudgeConfiguration | null = null,
): DatasetScoringRule | undefined {
  if (metric === "llm_judge") {
    const judgeEndpointId = judge?.judgeEndpointId.trim();
    const systemMessage = judge?.systemMessage.trim();
    return judgeEndpointId && systemMessage
      ? { type: "llm_judge", judge_endpoint_id: judgeEndpointId, system_message: systemMessage }
      : undefined;
  }
  return metric === "default" ? undefined : { type: metric };
}
