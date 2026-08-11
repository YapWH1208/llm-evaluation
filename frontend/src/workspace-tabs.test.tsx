import { cleanup, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import App from "./App";
import { api, type Endpoint } from "./api";
import { LocaleProvider } from "./i18n/LocaleProvider";

const endpoint: Endpoint = {
  api_key_mask: "••••1234",
  api_key_max_concurrency: null,
  base_url: "https://provider.example/v1",
  currency: "USD",
  custom_headers: {},
  default_request_body: {},
  display_name: "Production model",
  id: "endpoint-1",
  input_cost_per_million: 1.5,
  input_tokens_per_minute: null,
  last_connection_error: null,
  max_concurrency: 2,
  model_name: "example-model",
  notes: null,
  output_cost_per_million: 3,
  output_tokens_per_minute: null,
  protocol_profile: "openai_chat_completions",
  requests_per_minute: null,
  requests_per_second: null,
  status: "available",
  tags: ["production"],
  timeout_seconds: 60,
  tokens_per_minute: null,
};

function mockWorkspace() {
  vi.spyOn(api, "listEndpoints").mockResolvedValue([endpoint]);
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
  window.history.replaceState(null, "", "/dashboard");
});

describe("workspace tab routing", () => {
  it("moves an endpoint edit from inventory to its URL-backed form tab", async () => {
    mockWorkspace();
    window.history.replaceState(null, "", "/models");
    const user = userEvent.setup();
    render(<LocaleProvider><App /></LocaleProvider>);

    await user.click(await screen.findByRole("button", { name: "Edit configuration" }));

    await waitFor(() => expect(window.location.pathname).toBe("/models"));
    expect(window.location.search).toBe("?tab=add-endpoint");
    expect(screen.getByRole("tab", { name: "Add endpoint" })).toHaveAttribute("aria-selected", "true");
    expect(screen.getByRole("heading", { name: "Edit model endpoint" })).toBeVisible();
    expect(screen.getByLabelText("Display name")).toHaveValue("Production model");
  });
});
