import { afterEach, describe, expect, it } from "vitest";

import { formatWorkspaceDate, formatWorkspaceMoney, formatWorkspaceNumber, formatWorkspacePercent } from "./formatters";

afterEach(() => {
  document.documentElement.lang = "en";
});

describe("workspace locale formatters", () => {
  it("uses the selected locale for dates, numbers, percentages, and empty values", () => {
    document.documentElement.lang = "fr";

    expect(formatWorkspaceDate(null)).toBe("Non enregistré");
    expect(formatWorkspaceNumber(1234.5, 1)).toContain("234,5");
    expect(formatWorkspacePercent(0.456)).toMatch(/45,6\s?%/);
    expect(formatWorkspaceMoney(null, "USD")).toBe("Non configuré");
  });

  it("switches formatting without changing currency values or null sentinels", () => {
    document.documentElement.lang = "ja";

    expect(formatWorkspaceNumber(null)).toBe("--");
    expect(formatWorkspacePercent(null)).toBe("--");
    expect(formatWorkspaceMoney(1.25, "USD")).toContain("USD");
  });
});
