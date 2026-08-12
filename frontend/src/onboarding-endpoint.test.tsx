import { cleanup, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import App from "./App";
import { api, type Endpoint } from "./api";
import { LocaleProvider } from "./i18n/LocaleProvider";

const createdEndpoint: Endpoint = {
  api_key_mask: "••••test",
  api_key_max_concurrency: null,
  base_url: "https://provider.example/v1",
  currency: "USD",
  custom_headers: {},
  default_request_body: {},
  display_name: "First model",
  id: "endpoint-created",
  input_cost_per_million: null,
  input_tokens_per_minute: null,
  last_connection_error: null,
  max_concurrency: 1,
  model_name: "model-id",
  notes: null,
  output_cost_per_million: null,
  output_tokens_per_minute: null,
  protocol_profile: "openai_chat_completions",
  requests_per_minute: null,
  requests_per_second: null,
  status: "unverified",
  tags: [],
  timeout_seconds: 60,
  tokens_per_minute: null,
};

afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
  window.history.replaceState(null, "", "/");
});

describe("endpoint onboarding handoff", () => {
  it("selects a newly created endpoint and exposes connection testing", async () => {
    const user = userEvent.setup();
    vi.spyOn(api, "listEndpoints").mockResolvedValueOnce([]).mockResolvedValue([createdEndpoint]);
    vi.spyOn(api, "listRuns").mockResolvedValue([]);
    vi.spyOn(api, "dashboard").mockResolvedValue(null as never);
    vi.spyOn(api, "listPromptPackages").mockResolvedValue([]);
    vi.spyOn(api, "listDatasets").mockResolvedValue([]);
    vi.spyOn(api, "listBenchmarks").mockResolvedValue([]);
    vi.spyOn(api, "listTasks").mockResolvedValue([]);
    vi.spyOn(api, "analyticsMatrix").mockResolvedValue(null as never);
    vi.spyOn(api, "systemHealth").mockResolvedValue(null as never);
    vi.spyOn(api, "createEndpoint").mockResolvedValue(createdEndpoint);
    window.history.replaceState(null, "", "/models?tab=add-endpoint");

    render(<LocaleProvider><App /></LocaleProvider>);
    await user.type(screen.getByLabelText("Display name"), "First model");
    await user.type(screen.getByLabelText("Base URL"), createdEndpoint.base_url);
    await user.type(screen.getByLabelText("Model name"), createdEndpoint.model_name);
    await user.type(screen.getByLabelText("API key"), "secret-test-key");
    await user.click(screen.getByRole("button", { name: "Save encrypted endpoint" }));

    expect(await screen.findByRole("tab", { name: "Model inventory" })).toHaveAttribute("aria-selected", "true");
    expect(screen.getByRole("button", { name: "Select First model" })).toHaveAttribute("aria-pressed", "true");
    expect(screen.getByRole("button", { name: "Test connection" })).toBeVisible();
    expect(window.location.pathname).toBe("/models");
    expect(window.location.search).toBe("");
  });
});
