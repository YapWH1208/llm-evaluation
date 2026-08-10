import { cleanup, render, screen } from "@testing-library/react";
import { useState } from "react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import { Capability, Endpoint } from "./api";
import { Guide } from "./components/Guide";
import { CapabilityDeclarations, EndpointForm, ModelsPage, updateEndpointForm } from "./components/pages/EndpointPages";

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

const capability: Capability = { auto_detection_status: "supported", capability_key: "vision", effective_status: "supported", id: "capability-1", user_declared_status: "unknown" };

function modelProps(overrides: Partial<React.ComponentProps<typeof ModelsPage>> = {}) {
  return {
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
    onSubmit: vi.fn((event) => event.preventDefault()),
    onTest: vi.fn(),
    testRequests: {},
    ...overrides,
  };
}

function StatefulModelsPage() {
  const [currentForm, setCurrentForm] = useState(form);
  return <ModelsPage {...modelProps({ form: currentForm, onFormChange: setCurrentForm })} />;
}

describe("configure workspace pages", () => {
  it("updates only the named endpoint form field", () => {
    expect(updateEndpointForm(form, "display_name", "Staging")).toEqual(expect.objectContaining({ display_name: "Staging", model_name: "" }));
  });

  it("keeps the endpoint editor fields and inventory actions connected", async () => {
    const user = userEvent.setup();
    const props = modelProps();
    render(<ModelsPage {...props} />);

    expect(screen.getByRole("heading", { level: 1, name: "Models" })).toBeVisible();
    expect(screen.getByLabelText("Base URL")).toBeVisible();
    expect(screen.getByLabelText("Default request body (JSON)")).toBeVisible();
    expect(screen.queryByLabelText("Run concurrency cap")).not.toBeInTheDocument();
    expect(screen.queryByRole("heading", { name: "Run configuration" })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Queue selected benchmark" })).not.toBeInTheDocument();

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


  it("shows detected and effective state beside each declaration control", () => {
    render(<CapabilityDeclarations busy={null} capabilities={[capability]} endpointId={endpoint.id} onDeclare={vi.fn()} />);

    expect(screen.getByText("Detected: supported")).toBeVisible();
    expect(screen.getByText("Effective: supported")).toBeVisible();
    expect(screen.getByLabelText("vision declaration")).toHaveValue("unknown");
  });

  it("routes an actionable guide step through the supplied view callback", async () => {
    const user = userEvent.setup();
    const onOpenView = vi.fn();
    render(<Guide onOpenView={onOpenView} />);

    await user.click(screen.getByRole("button", { name: "Open Models" }));

    expect(onOpenView).toHaveBeenCalledWith("models");
  });
});
