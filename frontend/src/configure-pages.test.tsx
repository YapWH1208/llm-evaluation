import { cleanup, render, screen, within } from "@testing-library/react";
import { useState } from "react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import { Capability, Endpoint } from "./shared/api";
import { Guide } from "./components/Guide";
import { CapabilityDeclarations, EndpointForm, ModelsPage, updateEndpointForm } from "./components/pages/EndpointPages";
import { LocaleProvider } from "./i18n/LocaleProvider";

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
const stagingEndpoint: Endpoint = {
  ...endpoint,
  api_key_mask: "••••5678",
  base_url: "https://staging.example/v1",
  display_name: "Staging model",
  id: "endpoint-2",
  model_name: "staging-model",
  status: "unverified",
};

function modelProps(overrides: Partial<React.ComponentProps<typeof ModelsPage>> = {}) {
  return {
    activeTab: "model-inventory" as const,
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
    onTabChange: vi.fn(),
    onTest: vi.fn(),
    testRequests: {},
    ...overrides,
  };
}

function StatefulModelsPage() {
  const [currentForm, setCurrentForm] = useState(form);
  return <ModelsPage {...modelProps({ activeTab: "add-endpoint", form: currentForm, onFormChange: setCurrentForm })} />;
}

describe("configure workspace pages", () => {
  it("updates only the named endpoint form field", () => {
    expect(updateEndpointForm(form, "display_name", "Staging")).toEqual(expect.objectContaining({ display_name: "Staging", model_name: "" }));
  });

  it("shows only the approved master-detail inventory on the inventory tab", async () => {
    const user = userEvent.setup();
    const props = modelProps({ endpoints: [endpoint, stagingEndpoint] });
    const { rerender } = render(<ModelsPage {...props} />);

    expect(screen.getByRole("heading", { level: 1, name: "Models" })).toBeVisible();
    expect(screen.getByRole("tab", { name: "Model inventory" })).toHaveAttribute("aria-selected", "true");
    expect(screen.queryByLabelText("Base URL")).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Select Production model" })).toHaveAttribute("aria-pressed", "true");
    expect(screen.getByRole("button", { name: "Select Staging model" })).toHaveAttribute("aria-pressed", "false");

    let inspector = screen.getByRole("region", { name: "Selected model endpoint" });
    expect(within(inspector).getByRole("heading", { name: "Production model" })).toBeVisible();
    expect(within(inspector).getByText(endpoint.base_url)).toBeVisible();
    expect(within(inspector).queryByText(stagingEndpoint.base_url)).not.toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Select Staging model" }));
    inspector = screen.getByRole("region", { name: "Selected model endpoint" });
    expect(within(inspector).getByRole("heading", { name: "Staging model" })).toBeVisible();
    expect(within(inspector).getByText(stagingEndpoint.base_url)).toBeVisible();

    await user.click(within(inspector).getByRole("button", { name: "Test connection" }));
    await user.click(within(inspector).getByRole("button", { name: "Probe capabilities" }));

    expect(props.onTest).toHaveBeenCalledWith(stagingEndpoint.id);
    expect(props.onProbe).toHaveBeenCalledWith(stagingEndpoint.id);

    rerender(<ModelsPage {...props} endpoints={[endpoint]} />);
    expect(screen.getByRole("button", { name: "Select Production model" })).toHaveAttribute("aria-pressed", "true");
    expect(within(screen.getByRole("region", { name: "Selected model endpoint" })).getByRole("heading", { name: "Production model" })).toBeVisible();
  });

  it("offers endpoint creation directly from the empty model inventory", async () => {
    const user = userEvent.setup();
    const props = modelProps({ endpoints: [] });
    render(<ModelsPage {...props} />);

    await user.click(screen.getByRole("button", { name: "Add model endpoint" }));

    expect(props.onTabChange).toHaveBeenCalledWith("add-endpoint");
  });

  it("shows only the endpoint form on the add-endpoint tab", async () => {
    const user = userEvent.setup();
    const props = modelProps({ activeTab: "add-endpoint" });
    render(<ModelsPage {...props} />);

    expect(screen.getByRole("tab", { name: "Add endpoint" })).toHaveAttribute("aria-selected", "true");
    expect(screen.getByRole("heading", { name: "Add model endpoint" })).toBeVisible();
    expect(screen.getByLabelText("Base URL")).toBeVisible();
    expect(screen.getByText("Required fields are marked; everything else is optional.")).toBeVisible();
    expect(screen.getByLabelText("Default request body (JSON)")).not.toBeVisible();
    expect(screen.queryByRole("heading", { name: "Endpoint inventory" })).not.toBeInTheDocument();

    await user.click(screen.getByText("Advanced settings (optional)"));
    expect(screen.getByLabelText("Default request body (JSON)")).toBeVisible();

    await user.type(screen.getByLabelText("Display name"), "Staging");
    expect(props.onFormChange).toHaveBeenCalled();
    await user.click(screen.getByRole("tab", { name: "Model inventory" }));
    expect(props.onTabChange).toHaveBeenCalledWith("model-inventory");
  });

  it("keeps an editor change visible through the controlled form state", async () => {
    const user = userEvent.setup();
    render(<StatefulModelsPage />);

    await user.type(screen.getByLabelText("Display name"), "Staging");

    expect(screen.getByLabelText("Display name")).toHaveValue("Staging");
  });

  it("preserves advanced endpoint values while disclosure is toggled", async () => {
    const user = userEvent.setup();
    render(<StatefulModelsPage />);

    await user.click(screen.getByText("Advanced settings (optional)"));
    await user.type(screen.getByLabelText("Notes"), "Keep this value");
    await user.click(screen.getByText("Advanced settings (optional)"));
    await user.click(screen.getByText("Advanced settings (optional)"));

    expect(screen.getByLabelText("Notes")).toHaveValue("Keep this value");
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
    render(<LocaleProvider><Guide onOpenView={onOpenView} /></LocaleProvider>);

    await user.click(screen.getByRole("button", { name: "Open Models" }));

    expect(onOpenView).toHaveBeenCalledWith("models", { tab: "add-endpoint" });
  });
});
