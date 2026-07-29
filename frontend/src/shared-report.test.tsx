import { cleanup, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import { api, type Report } from "./api";
import { ReportsTable, SharedReportPage } from "./App";

afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
});

describe("public report sharing", () => {
  it("keeps the password out of browser storage and the URL after opening a report", async () => {
    const user = userEvent.setup();
    vi.spyOn(api, "openSharedReport").mockResolvedValue("blob:shared-report");
    render(<SharedReportPage token="public-token" />);

    await user.type(screen.getByLabelText("Share password (if required)"), "view-only-password");
    await user.click(screen.getByRole("button", { name: "Open report" }));

    expect(api.openSharedReport).toHaveBeenCalledWith("public-token", "view-only-password");
    expect(screen.getByLabelText("Share password (if required)")).toHaveValue("");
    expect(window.location.href).not.toContain("view-only-password");
    expect(window.sessionStorage.getItem("view-only-password")).toBeNull();
    expect(await screen.findByRole("link", { name: "Open report in a new tab" })).toHaveAttribute("href", "blob:shared-report");
  });

  it("announces a generic failure for an unavailable or invalid share", async () => {
    const user = userEvent.setup();
    vi.spyOn(api, "openSharedReport").mockRejectedValue(new Error("denied"));
    render(<SharedReportPage token="public-token" />);

    await user.click(screen.getByRole("button", { name: "Open report" }));
    expect(await screen.findByText("The shared report could not be opened. Check the password, expiry, or link.")).toBeVisible();
  });

  it("downloads a report from an authenticated object URL", async () => {
    const user = userEvent.setup();
    const report: Report = { id: "report-id", run_id: "run-id", report_type: "single_model", format: "html", artifact_path: "ignored", generator_version: "test", generated_at: "2026-07-29T00:00:00Z" };
    vi.spyOn(api, "downloadReport").mockResolvedValue("blob:protected-report");
    const click = vi.spyOn(HTMLAnchorElement.prototype, "click").mockImplementation(() => undefined);
    render(<ReportsTable reports={[report]} />);

    await user.click(screen.getByRole("button", { name: "Download" }));
    expect(api.downloadReport).toHaveBeenCalledWith("report-id");
    expect(click).toHaveBeenCalledOnce();
  });
});
