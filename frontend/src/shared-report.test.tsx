import { cleanup, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import { reportsApi, type Report } from "./features/reports/api";
import { openSharedReport, SharedReportPage } from "./components/pages/SystemPages";
import { ReportsTable } from "./features/reports/ReportsTable";
import { LocaleProvider } from "./i18n/LocaleProvider";

afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
});

const report: Report = { id: "report-id", run_id: "run-id", report_type: "single_model", format: "html", artifact_path: "ignored", generator_version: "test", generated_at: "2026-07-29T00:00:00Z" };

describe("public report sharing", () => {
  it("honors the saved light-theme preference without requiring the authenticated application shell", () => {
    window.localStorage.setItem("lle-theme", "light");
    render(<LocaleProvider><SharedReportPage token="public-token" /></LocaleProvider>);

    expect(document.documentElement).toHaveAttribute("data-theme", "light");
  });

  it("keeps the discovery-token request scoped to the supplied public credentials", async () => {
    vi.spyOn(reportsApi, "openShared").mockResolvedValue("blob:shared-report");

    await expect(openSharedReport("public-token", "view-only-password")).resolves.toBe("blob:shared-report");
    expect(reportsApi.openShared).toHaveBeenCalledWith("public-token", "view-only-password");
  });

  it("keeps the password out of browser storage and the URL after opening a report", async () => {
    const user = userEvent.setup();
    vi.spyOn(reportsApi, "openShared").mockResolvedValue("blob:shared-report");
    render(<LocaleProvider><SharedReportPage token="public-token" /></LocaleProvider>);

    await user.type(screen.getByLabelText("Share password (if required)"), "view-only-password");
    await user.click(screen.getByRole("button", { name: "Open report" }));

    expect(reportsApi.openShared).toHaveBeenCalledWith("public-token", "view-only-password");
    expect(screen.getByLabelText("Share password (if required)")).toHaveValue("");
    expect(window.location.href).not.toContain("view-only-password");
    expect(window.sessionStorage.getItem("view-only-password")).toBeNull();
    expect(await screen.findByRole("link", { name: "Open report in a new tab" })).toHaveAttribute("href", "blob:shared-report");
  });

  it("announces a generic failure for an unavailable or invalid share", async () => {
    const user = userEvent.setup();
    vi.spyOn(reportsApi, "openShared").mockRejectedValue(new Error("denied"));
    render(<LocaleProvider><SharedReportPage token="public-token" /></LocaleProvider>);

    await user.click(screen.getByRole("button", { name: "Open report" }));
    expect(await screen.findByText("The shared report could not be opened. Check the password, expiry, or link.")).toBeVisible();
  });

  it("downloads a report from an authenticated object URL", async () => {
    const user = userEvent.setup();
    vi.spyOn(reportsApi, "download").mockResolvedValue("blob:protected-report");
    const click = vi.spyOn(HTMLAnchorElement.prototype, "click").mockImplementation(() => undefined);
    render(<LocaleProvider><ReportsTable onDelete={vi.fn()} reports={[report]} /></LocaleProvider>);

    await user.click(screen.getByRole("button", { name: "Download" }));
    expect(reportsApi.download).toHaveBeenCalledWith("report-id");
    expect(click).toHaveBeenCalledOnce();
  });

  it("deletes a report through the table action", async () => {
    const user = userEvent.setup();
    const onDelete = vi.fn();
    render(<LocaleProvider><ReportsTable onDelete={onDelete} reports={[report]} /></LocaleProvider>);

    await user.click(screen.getByRole("button", { name: "Delete" }));
    expect(onDelete).toHaveBeenCalledWith(report);
  });
});
