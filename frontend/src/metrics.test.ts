import { describe, expect, it } from "vitest";

import { METRIC_DEFINITIONS, METRIC_PROFILE_VERSION, metricDefinition } from "./metrics";

describe("metric registry", () => {
  it("defines task-aware and operational metric labels in one typed source", () => {
    expect(METRIC_PROFILE_VERSION).toBe("1.1.0");
    expect(metricDefinition("pass@1")).toEqual({ label: "pass@1", unit: "ratio", profile: "code" });
    expect(metricDefinition("perplexity").unit).toBe("perplexity");
    expect(Object.keys(METRIC_DEFINITIONS)).toContain("score");
  });
});
