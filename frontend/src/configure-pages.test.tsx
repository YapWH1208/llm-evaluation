import { cleanup, render, screen } from "@testing-library/react";
import { useState } from "react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import { Benchmark, Capability, Endpoint, PromptPackage } from "./api";
import { Guide } from "./components/Guide";
import { CapabilitiesPage, EndpointForm, ModelsPage } from "./components/pages/EndpointPages";

afterEach(cleanup);

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

const secondEndpoint: Endpoint = { ...endpoint, display_name: "Vision model", id: "endpoint-2", model_name: "vision-model" };

const form: EndpointForm = {
  api_key: "",
  api_key_max_concurrency: "",
  base_url: "",
  currency: "USD",
  custom_headers: "{}",
  default_request_body: "{}",
  display_name: "",
  input_cost_per_million: "",
  input_tokens_per_minute: "",
  max_concurrency: "1",
  model_name: "",
  notes: "",
  output_cost_per_million: "",
  output_tokens_per_minute: "",
  protocol_profile: "openai_chat_completions",
  requests_per_minute: "",
  requests_per_second: "",
  tags: "",
  timeout_seconds: "60",
  tokens_per_minute: "",
};

const benchmark: Benchmark = { created_at: "2026-08-08T00:00:00Z", display_name: "Quick check", id: "benchmark-1", benchmark_id: "quick-check", manifest: {}, source: "builtin", status: "enabled", version: "1" };
const prompt: PromptPackage = { created_at: "2026-08-08T00:00:00Z", id: "prompt-1", name: "Baseline", prompt_type: "user_custom", system_message: null, user_template: "{{ question }}", version: "1" };
const capability: Capability = { auto_detection_status: "supported", capability_key: "vision", effective_status: "supported", id: "capability-1", user_declared_status: "unknown" };

function modelProps(overrides: Partial<React.ComponentProps<typeof ModelsPage>> = {}) {
  return {
    benchmarks: [benchmark],
    busy: null,
    capabilities: { [endpoint.id]: [capability] },
    editingEndpointId: null,
    endpoints: [endpoint],
    form,
    onCancelEdit: vi.fn(),
    onDeclare: vi.fn(),
    onEdit: vi.fn(),
    onFormChange: vi.fn(),
    onProbe: vi.fn(),
    onQueue: vi.fn(),
    onRunConfigChange: vi.fn(),
    onSubmit: vi.fn((event) => event.preventDefault()),
    onTest: vi.fn(),
    prompts: [prompt],
    runConfig: { benchmark: "quick-check@1", maxConcurrency: "", promptId: "", requestBody: "{}" },
    testRequests: {},
    ...overrides,
  };
}

function StatefulModelsPage() {
  const [currentForm, setCurrentForm] = useState(form);
  return <ModelsPage {...modelProps({ form: currentForm, onFormChange: setCurrentForm })} />;
}

describe("configure workspace pages", () => {
  it("keeps the endpoint editor fields and inventory actions connected", async () => {
    const user = userEvent.setup();
    const props = modelProps();
    render(<ModelsPage {...props} />);

    expect(screen.getByRole("heading", { level: 1, name: "Models" })).toBeVisible();
    expect(screen.getByLabelText("Base URL")).toBeVisible();
    expect(screen.getByLabelText("Default request body (JSON)")).toBeVisible();
    expect(screen.getByLabelText("Run concurrency cap")).toBeVisible();

    await user.type(screen.getByLabelText("Display name"), "Staging");
    await user.click(screen.getByRole("button", { name: "Test connection" }));
    await user.click(screen.getByRole("button", { name: "Probe capabilities" }));

    expect(props.onFormChange).toHaveBeenCalled();
    expect(props.onTest).toHaveBeenCalledWith(endpoint.id);
    expect(props.onProbe).toHaveBeenCalledWith(endpoint.id);
  });

  it("keeps an editor change visible through the controlled form state", async () => {
    const user = userEvent.setup();
    render(<StatefulModelsPage />);

    await user.type(screen.getByLabelText("Display name"), "Staging");

    expect(screen.getByLabelText("Display name")).toHaveValue("Staging");
  });

  it("uses an endpoint selection inspector while preserving capability declarations", async () => {
    const user = userEvent.setup();
    const onDeclare = vi.fn();
    render(<CapabilitiesPage busy={null} capabilities={{ [endpoint.id]: [capability], [secondEndpoint.id]: [capability] }} endpoints={[endpoint, secondEndpoint]} onDeclare={onDeclare} onProbe={vi.fn()} />);

    expect(screen.getByRole("heading", { level: 1, name: "Capabilities" })).toBeVisible();
    await user.click(screen.getByRole("button", { name: /Inspect Vision model/ }));
    expect(screen.getByRole("heading", { level: 2, name: "Vision model" })).toBeVisible();

    await user.selectOptions(screen.getByLabelText("vision declaration"), "supported");
    expect(onDeclare).toHaveBeenCalledWith(secondEndpoint.id, capability, "supported");
    expect(screen.getByText("Detected: supported")).toBeVisible();
    expect(screen.getByText("Effective: supported")).toBeVisible();
  });

  it("routes an actionable guide step through the supplied view callback", async () => {
    const user = userEvent.setup();
    const onOpenView = vi.fn();
    render(<Guide onOpenView={onOpenView} />);

    await user.click(screen.getByRole("button", { name: "Open Models" }));

    expect(onOpenView).toHaveBeenCalledWith("models");
  });
});
