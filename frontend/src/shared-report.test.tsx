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

  it("passes the visible Reports share policy to the controlled share handler", async () => {
    const user = userEvent.setup();
    const report: Report = { id: "report-id", run_id: "run-id", report_type: "single_model", format: "html", artifact_path: "ignored", generator_version: "test", generated_at: "2026-07-29T00:00:00Z" };
    const onShare = vi.fn().mockResolvedValue({ id: "share-id", report_id: report.id, expires_at: "2026-08-01T00:00:00Z", allow_download: true, revoked_at: null, created_at: "2026-07-29T00:00:00Z", share_url: "https://evaluation.example.test/shared-reports/token" });
    render(<ReportsTable reports={[report]} onShare={onShare} />);

    await user.clear(screen.getByLabelText("Expires in days"));
    await user.type(screen.getByLabelText("Expires in days"), "21");
    await user.type(screen.getByLabelText("Optional password"), "view-only-password");
    await user.click(screen.getByLabelText("Allow download"));
    await user.click(screen.getByLabelText("Share raw evidence"));
    await user.click(screen.getByRole("button", { name: "Share" }));

    expect(onShare).toHaveBeenCalledWith(report, {
      days: "21",
      password: "view-only-password",
      allow_download: true,
      include_evidence: true,
    });
    expect(screen.getByLabelText("Optional password")).toHaveValue("");
    expect(await screen.findByRole("link", { name: "Open the newly created share link" })).toHaveAttribute("href", "https://evaluation.example.test/shared-reports/token");
  });
});
