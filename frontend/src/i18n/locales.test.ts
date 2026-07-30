import { describe, expect, it } from "vitest";

import { catalogs, isLocale, localeIds, resolveLocale } from "./catalog";

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
});
