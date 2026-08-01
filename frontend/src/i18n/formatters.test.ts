import { describe, expect, it } from "vitest";

import { formatWorkspaceDate, formatWorkspaceMoney, formatWorkspaceNumber, formatWorkspacePercent } from "./formatters";

describe("workspace locale formatters", () => {
  it("uses the selected locale for dates, numbers, percentages, and empty values", () => {
    expect(formatWorkspaceDate("fr", null)).toBe("Non enregistré");
    expect(formatWorkspaceNumber("fr", 1234.5, 1)).toContain("234,5");
    expect(formatWorkspacePercent("fr", 0.456)).toMatch(/45,6\s?%/);
    expect(formatWorkspaceMoney("fr", null, "USD")).toBe("Non configuré");
  });

  it("switches formatting without changing currency values or null sentinels", () => {
    expect(formatWorkspaceNumber("ja", null)).toBe("--");
    expect(formatWorkspacePercent("ja", null)).toBe("--");
    expect(formatWorkspaceMoney("ja", 1.25, "USD")).toContain("USD");
  });
});
