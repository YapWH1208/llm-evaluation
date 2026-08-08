import { describe, expect, it } from "vitest";

import { catalogs, isLocale, localeIds, navigationCopy, overviewCopy, resolveLocale } from "./catalog";
import { translateStaticTemplate } from "./operationalCopy";

const analyticsOverviewKeys = [
  "dashboardTitle",
  "dashboardDescription",
  "performanceSummary",
  "successRate",
  "evaluationTrend",
  "limitedHistory",
  "noHistory",
  "modelBenchmarkComparison",
  "model",
  "benchmark",
  "sampleCount",
  "latencyCostErrors",
  "latency",
  "cost",
  "errorRate",
  "recentEvaluations",
  "progress",
  "started",
  "systemReadiness",
  "operational",
  "attentionNeeded",
  "unknownValue",
] as const;

describe("workspace locale catalog", () => {
  it("ships the requested locales with the complete English key set", () => {
    expect(localeIds).toEqual(["en", "zh-CN", "fr", "de", "ru", "ja", "ko", "ms"]);
    const englishKeys = Object.keys(catalogs.en).sort();

    for (const locale of localeIds) {
      expect(Object.keys(catalogs[locale]).sort()).toEqual(englishKeys);
      expect(Object.values(catalogs[locale]).every(Boolean)).toBe(true);
    }
  });

  it("accepts only shipped locale identifiers and falls back to English", () => {
    expect(isLocale("fr")).toBe(true);
    expect(isLocale("es")).toBe(false);
    expect(resolveLocale("zh-CN")).toBe("zh-CN");
    expect(resolveLocale("unsupported")).toBe("en");
    expect(resolveLocale(null)).toBe("en");
  });

  it("keeps corrected French worker language and localized templates intact", () => {
    expect(navigationCopy.fr.items.workers).toEqual({ label: "Agents", description: "Baux et agents actifs" });
    expect(overviewCopy.fr.workers).toBe("Agents");
    expect(translateStaticTemplate("fr", "configured")).toBe("configuré");
    expect(translateStaticTemplate("ja", "{{benchmark}} queued with an immutable configuration snapshot.", { benchmark: "benchmark-a" })).toContain("benchmark-a");
    expect(translateStaticTemplate("ja", "{{benchmark}} queued with an immutable configuration snapshot.", { benchmark: "benchmark-a" })).not.toContain("queued");
  });

  it("provides non-empty analytics dashboard terminology in every shipped locale", () => {
    for (const locale of localeIds) {
      for (const key of analyticsOverviewKeys) {
        expect(overviewCopy[locale][key].trim(), `${locale}.${key}`).not.toBe("");
      }
    }
  });
});
