import { describe, expect, it } from "vitest";

import { datasetMetricIds, datasetScoringRuleFor } from "./scoringMetrics";

describe("dataset scoring metric presets", () => {
  it("maps the approved metric choices to API scoring rules", () => {
    expect(datasetMetricIds).toEqual([
      "default",
      "exact_match",
      "normalized_exact_match",
      "token_f1",
      "bleu",
      "rouge_l",
    ]);
    expect(datasetScoringRuleFor("default")).toBeUndefined();
    expect(datasetScoringRuleFor("exact_match")).toEqual({ type: "exact_match" });
    expect(datasetScoringRuleFor("normalized_exact_match")).toEqual({ type: "normalized_exact_match" });
    expect(datasetScoringRuleFor("token_f1")).toEqual({ type: "token_f1" });
    expect(datasetScoringRuleFor("bleu")).toEqual({ type: "bleu" });
    expect(datasetScoringRuleFor("rouge_l")).toEqual({ type: "rouge_l" });
  });
});
