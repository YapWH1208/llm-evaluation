import { describe, expect, it } from "vitest";

import { formatWorkspaceBytes, formatWorkspaceDate, formatWorkspaceMoney, formatWorkspaceNumber, formatWorkspacePercent } from "./formatters";

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

  it("formats bytes as localized human-readable storage", () => {
    expect(formatWorkspaceBytes("en", 1_572_864)).toBe("1.5 MB");
    expect(formatWorkspaceBytes("fr", 1_572_864)).toMatch(/^1,5\sMB$/);
    expect(formatWorkspaceBytes("en", 128)).toBe("128 B");
    expect(formatWorkspaceBytes("en", null)).toBe("--");
  });
});
