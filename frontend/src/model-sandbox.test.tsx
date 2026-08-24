import { cleanup, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import { EndpointsRoute } from "./features/endpoints/EndpointsRoute";
import { endpointsApi, type Endpoint } from "./features/endpoints/api";
import { LocaleProvider } from "./i18n/LocaleProvider";

const endpoint: Endpoint = {
  api_key_mask: "••••test",
  api_key_max_concurrency: null,
  base_url: "https://provider.example/v1",
  context_length: null,
  currency: "USD",
  custom_headers: {},
  default_request_body: {},
  display_name: "Sandbox model",
  id: "endpoint-1",
  input_cost_per_million: null,
  input_tokens_per_minute: null,
  last_connection_error: null,
  max_concurrency: 1,
  max_output_tokens: null,
  model_name: "example-model",
  notes: null,
  output_cost_per_million: null,
  output_tokens_per_minute: null,
  protocol_profile: "openai_chat_completions",
  reasoning_effort: null,
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
});

describe("model sandbox", () => {
  it("sends a bounded text test and renders safe evidence and failures", async () => {
    const user = userEvent.setup();
    const navigate = vi.fn();
    vi.spyOn(endpointsApi, "list").mockResolvedValue([endpoint]);
    const sandbox = vi.spyOn(endpointsApi, "sandbox")
      .mockResolvedValueOnce({ success: true, mode: "text", protocol_profile: endpoint.protocol_profile, request: { model: endpoint.model_name }, final_text: "Hello.", tool_calls: [], latency_ms: 12.5, usage: { input_tokens: 3, output_tokens: 2 }, provider_status_code: 200, error_type: null, error_message: null })
      .mockResolvedValueOnce({ success: false, mode: "tool", protocol_profile: endpoint.protocol_profile, request: { model: endpoint.model_name }, final_text: null, tool_calls: [], latency_ms: 8, usage: { input_tokens: null, output_tokens: null }, provider_status_code: 400, error_type: "unsupported_tool_calling", error_message: "This provider does not support tool calls." });
    vi.spyOn(window, "confirm").mockReturnValue(true);

    render(<LocaleProvider><EndpointsRoute activeTab="sandbox" navigate={navigate} reportError={vi.fn()} routeSearch="?tab=sandbox&endpoint=endpoint-1" showNotice={vi.fn()} /></LocaleProvider>);

    await user.type(await screen.findByLabelText("User prompt"), "Say hello.");
    await user.type(screen.getByLabelText("System prompt (optional)"), "Be concise.");
    await user.click(screen.getByRole("button", { name: "Run sandbox" }));

    await waitFor(() => expect(sandbox).toHaveBeenNthCalledWith(1, endpoint.id, { mode: "text", user_prompt: "Say hello.", system_prompt: "Be concise." }));
    expect(await screen.findByText("Hello.")).toBeVisible();
    expect(screen.getByText(/"model": "example-model"/)).toBeVisible();

    await user.click(screen.getByRole("radio", { name: "Tool-calling test" }));
    await user.click(screen.getByRole("button", { name: "Run sandbox" }));

    await waitFor(() => expect(sandbox).toHaveBeenNthCalledWith(2, endpoint.id, { mode: "tool", user_prompt: undefined, system_prompt: undefined }));
    expect(await screen.findByRole("alert")).toHaveTextContent("This provider does not support tool calls.");
    expect(navigate).not.toHaveBeenCalled();
  });
});
