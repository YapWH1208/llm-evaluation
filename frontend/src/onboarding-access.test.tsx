import { cleanup, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import App from "./App";
import { api, ApiError } from "./api";
import { LocaleProvider } from "./i18n/LocaleProvider";

function mockWorkspaceLoad() {
  vi.spyOn(api, "listRuns").mockResolvedValue([]);
  vi.spyOn(api, "dashboard").mockResolvedValue(null as never);
  vi.spyOn(api, "listPromptPackages").mockResolvedValue([]);
  vi.spyOn(api, "listDatasets").mockResolvedValue([]);
  vi.spyOn(api, "listBenchmarks").mockResolvedValue([]);
  vi.spyOn(api, "listTasks").mockResolvedValue([]);
  vi.spyOn(api, "analyticsMatrix").mockResolvedValue(null as never);
  vi.spyOn(api, "systemHealth").mockResolvedValue(null as never);
}

afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
  api.setBearerToken("");
  window.history.replaceState(null, "", "/");
});

describe("protected workspace onboarding", () => {
  it("keeps access recovery visible and deep-links to the token control", async () => {
    const user = userEvent.setup();
    mockWorkspaceLoad();
    vi.spyOn(api, "listEndpoints")
      .mockRejectedValueOnce(new ApiError("Valid bearer token required.", 401))
      .mockResolvedValue([]);

    render(<LocaleProvider><App /></LocaleProvider>);

    expect(await screen.findByRole("heading", { name: "Workspace access required" })).toBeVisible();
    expect(screen.queryByText("Valid bearer token required.")).not.toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "Enter access token" }));

    expect(window.location.pathname).toBe("/settings");
    expect(window.location.search).toBe("?tab=access");
    expect(screen.getByLabelText("Administrator or user bearer token")).toBeVisible();

    await user.type(screen.getByLabelText("Administrator or user bearer token"), "test-token");
    await user.click(screen.getByRole("button", { name: "Save token" }));

    await waitFor(() => expect(screen.queryByRole("heading", { name: "Workspace access required" })).not.toBeInTheDocument());
    expect(window.sessionStorage.getItem("lle-api-token")).toBe("test-token");
  });

  it("does not dismiss recovery when a replacement token is rejected", async () => {
    const user = userEvent.setup();
    mockWorkspaceLoad();
    vi.spyOn(api, "listEndpoints").mockRejectedValue(new ApiError("Valid bearer token required.", 401));

    render(<LocaleProvider><App /></LocaleProvider>);

    await user.click(await screen.findByRole("button", { name: "Enter access token" }));
    await user.type(screen.getByLabelText("Administrator or user bearer token"), "invalid-token");
    await user.click(screen.getByRole("button", { name: "Save token" }));

    expect(await screen.findByRole("heading", { name: "Workspace access required" })).toBeVisible();
  });
});
