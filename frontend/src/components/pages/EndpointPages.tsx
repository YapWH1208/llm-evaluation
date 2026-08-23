import { type FormEvent, type ReactNode, useEffect, useState } from "react";

import type { Capability, Endpoint } from "../../features/endpoints/api";
import type { WorkspaceTabFor } from "../../dashboard/routing";
import { endpointWorkspaceCopy, firstEvaluationCopy, formCopy, workspacePageTabCopy, type Locale } from "../../i18n/catalog";
import { PageHeader } from "../workspace/PageHeader";
import { WorkspacePanel } from "../workspace/WorkspacePanel";
import { WorkspaceTabs, workspaceTabId, workspaceTabPanelId } from "../workspace/WorkspaceTabs";

export type EndpointForm = {
  api_key: string;
  api_key_max_concurrency: string;
  base_url: string;
  currency: string;
  custom_headers: string;
  default_request_body: string;
  display_name: string;
  input_cost_per_million: string;
  input_tokens_per_minute: string;
  context_length: string;
  max_concurrency: string;
  max_output_tokens: string;
  model_name: string;
  notes: string;
  output_cost_per_million: string;
  output_tokens_per_minute: string;
  protocol_profile: Endpoint["protocol_profile"];
  requests_per_minute: string;
  requests_per_second: string;
  reasoning_effort: "" | "low" | "medium" | "high";
  tags: string;
  timeout_seconds: string;
  tokens_per_minute: string;
};

type CapabilityStatus = "supported" | "unsupported" | "unknown";

export function updateEndpointForm<K extends keyof EndpointForm>(form: EndpointForm, key: K, value: EndpointForm[K]): EndpointForm {
  return { ...form, [key]: value };
}

type ModelsPageProps = {
  activeTab: WorkspaceTabFor<"models">;
  busy: string | null;
  capabilities: Record<string, Capability[]>;
  editingEndpointId: string | null;
  endpoints: Endpoint[];
  form: EndpointForm;
  locale?: Locale;
  onCancelEdit: () => void;
  onDeclare: (endpointId: string, capability: Capability, status: CapabilityStatus) => void;
  onEdit: (endpoint: Endpoint) => void;
  onOpenSandbox?: (endpointId: string) => void;
  onFormChange: (form: EndpointForm) => void;
  onProbe: (endpointId: string) => void;
  onSubmit: (event: FormEvent<HTMLFormElement>) => void;
  onTabChange: (tab: WorkspaceTabFor<"models">) => void;
  onTest: (endpointId: string) => void;
  onPreferredEndpointConsumed?: () => void;
  preferredEndpointId?: string | null;
  testRequests: Record<string, { method: "POST"; url: string; body: Record<string, unknown> }>;
  sandbox?: ReactNode;
};

type EndpointFormPanelProps = Pick<ModelsPageProps, "busy" | "editingEndpointId" | "form" | "locale" | "onCancelEdit" | "onFormChange" | "onSubmit">;

export function EndpointFormPanel({ busy, editingEndpointId, form, locale = "en", onCancelEdit, onFormChange, onSubmit }: EndpointFormPanelProps) {
  const copy = formCopy[locale];
  const endpointCopy = endpointWorkspaceCopy[locale];
  const apiKeyRequired = !editingEndpointId && form.protocol_profile !== "ollama_chat";
  return (
    <WorkspacePanel description="Connection, rate-limit, and cost settings remain editable without exposing stored credentials." title={editingEndpointId ? "Edit model endpoint" : "Add model endpoint"}>
      <form className="form" onSubmit={onSubmit}>
            <p className="workspace-form-requirements">{copy.requirements}</p>
            <label><span>Display name <small>{copy.optional}</small></span><input aria-label="Display name" onChange={(event) => onFormChange(updateEndpointForm(form, "display_name", event.target.value))} placeholder="My local model" value={form.display_name} /></label>
            <label><span>Base URL <small>{copy.required}</small></span><input aria-label="Base URL" onChange={(event) => onFormChange(updateEndpointForm(form, "base_url", event.target.value))} placeholder="https://provider.example/v1" required type="url" value={form.base_url} /></label>
            <label><span>Model name <small>{copy.required}</small></span><input aria-label="Model name" onChange={(event) => onFormChange(updateEndpointForm(form, "model_name", event.target.value))} placeholder="model-id" required value={form.model_name} /></label>
            <label><span>Protocol profile <small>{copy.required}</small></span><select aria-label="Protocol profile" onChange={(event) => onFormChange(updateEndpointForm(form, "protocol_profile", event.target.value as Endpoint["protocol_profile"]))} value={form.protocol_profile}><option value="openai_chat_completions">OpenAI-compatible Chat Completions</option><option value="openai_responses">OpenAI-compatible Responses API</option><option value="anthropic_messages">Anthropic Messages</option><option value="gemini_generate_content">Gemini GenerateContent</option><option value="azure_openai_chat_completions">Azure OpenAI Chat Completions</option><option value="ollama_chat">Ollama Chat</option><option value="custom_http_json">Custom HTTP JSON</option></select></label>
            <label><span>API key <small>{apiKeyRequired ? copy.required : copy.optional}</small></span><input aria-label="API key" onChange={(event) => onFormChange(updateEndpointForm(form, "api_key", event.target.value))} placeholder={editingEndpointId ? "Leave blank to keep the encrypted key" : form.protocol_profile === "ollama_chat" ? "Optional for a local Ollama service" : "Stored encrypted"} required={apiKeyRequired} type="password" value={form.api_key} /></label>
            <details className="workspace-form-disclosure">
              <summary>{copy.advanced}</summary>
              <div className="workspace-form-disclosure__content">
            <div className="workspace-field-grid workspace-field-grid--three"><label>{endpointCopy.reasoningEffort}<select aria-label={endpointCopy.reasoningEffort} onChange={(event) => onFormChange(updateEndpointForm(form, "reasoning_effort", event.target.value as EndpointForm["reasoning_effort"]))} value={form.reasoning_effort}><option value="">{endpointCopy.providerDefault}</option><option value="low">{endpointCopy.low}</option><option value="medium">{endpointCopy.medium}</option><option value="high">{endpointCopy.high}</option></select></label><label>{endpointCopy.contextLength}<input aria-label={endpointCopy.contextLength} min="1" onChange={(event) => onFormChange(updateEndpointForm(form, "context_length", event.target.value))} placeholder={endpointCopy.notSet} type="number" value={form.context_length} /></label><label>{endpointCopy.maxOutputTokens}<input aria-label={endpointCopy.maxOutputTokens} min="1" onChange={(event) => onFormChange(updateEndpointForm(form, "max_output_tokens", event.target.value))} placeholder={endpointCopy.notSet} type="number" value={form.max_output_tokens} /></label></div>
            <label>Custom headers (JSON)<textarea onChange={(event) => onFormChange(updateEndpointForm(form, "custom_headers", event.target.value))} placeholder='{"X-Provider-Project":"project-id"}' spellCheck={false} value={form.custom_headers} /></label>
            <label>Default request body (JSON)<textarea onChange={(event) => onFormChange(updateEndpointForm(form, "default_request_body", event.target.value))} spellCheck={false} value={form.default_request_body} /></label>
            <div className="workspace-field-grid workspace-field-grid--five"><label>Timeout (seconds)<input max="600" min="1" onChange={(event) => onFormChange(updateEndpointForm(form, "timeout_seconds", event.target.value))} required type="number" value={form.timeout_seconds} /></label><label>Endpoint concurrency<input max="1000" min="1" onChange={(event) => onFormChange(updateEndpointForm(form, "max_concurrency", event.target.value))} required type="number" value={form.max_concurrency} /></label><label>Shared API-key concurrency<input max="1000" min="1" onChange={(event) => onFormChange(updateEndpointForm(form, "api_key_max_concurrency", event.target.value))} placeholder="Unlimited" type="number" value={form.api_key_max_concurrency} /></label><label>Requests / minute<input min="1" onChange={(event) => onFormChange(updateEndpointForm(form, "requests_per_minute", event.target.value))} placeholder="Unlimited" type="number" value={form.requests_per_minute} /></label><label>Tokens / minute<input min="1" onChange={(event) => onFormChange(updateEndpointForm(form, "tokens_per_minute", event.target.value))} placeholder="Unlimited" type="number" value={form.tokens_per_minute} /></label></div>
            <div className="workspace-field-grid workspace-field-grid--three"><label>Requests / second<input min="1" onChange={(event) => onFormChange(updateEndpointForm(form, "requests_per_second", event.target.value))} placeholder="Unlimited" type="number" value={form.requests_per_second} /></label><label>Input tokens / minute<input min="1" onChange={(event) => onFormChange(updateEndpointForm(form, "input_tokens_per_minute", event.target.value))} placeholder="Unlimited" type="number" value={form.input_tokens_per_minute} /></label><label>Output tokens / minute<input min="1" onChange={(event) => onFormChange(updateEndpointForm(form, "output_tokens_per_minute", event.target.value))} placeholder="Unlimited" type="number" value={form.output_tokens_per_minute} /></label></div>
            <div className="workspace-field-grid workspace-field-grid--three"><label>Input / 1M tokens<input min="0" onChange={(event) => onFormChange(updateEndpointForm(form, "input_cost_per_million", event.target.value))} step="any" type="number" value={form.input_cost_per_million} /></label><label>Output / 1M tokens<input min="0" onChange={(event) => onFormChange(updateEndpointForm(form, "output_cost_per_million", event.target.value))} step="any" type="number" value={form.output_cost_per_million} /></label><label>Currency<input maxLength={8} onChange={(event) => onFormChange(updateEndpointForm(form, "currency", event.target.value))} value={form.currency} /></label></div>
            <label>Tags (comma-separated)<input onChange={(event) => onFormChange(updateEndpointForm(form, "tags", event.target.value))} placeholder="production, vision" value={form.tags} /></label>
            <label>Notes<textarea onChange={(event) => onFormChange(updateEndpointForm(form, "notes", event.target.value))} value={form.notes} /></label>
              </div>
            </details>
            <div className="actions"><button disabled={busy === "endpoint"}>{busy === "endpoint" ? "Saving..." : editingEndpointId ? "Save model configuration" : "Save encrypted endpoint"}</button>{editingEndpointId && <button className="secondary" onClick={onCancelEdit} type="button">Cancel edit</button>}</div>
      </form>
    </WorkspacePanel>
  );
}

type ModelInventoryProps = Pick<ModelsPageProps, "busy" | "capabilities" | "endpoints" | "locale" | "onDeclare" | "onEdit" | "onOpenSandbox" | "onPreferredEndpointConsumed" | "onProbe" | "onTabChange" | "onTest" | "preferredEndpointId" | "testRequests">;

export function ModelInventory({ busy, capabilities, endpoints, locale = "en", onDeclare, onEdit, onOpenSandbox, onPreferredEndpointConsumed, onProbe, onTabChange, onTest, preferredEndpointId, testRequests }: ModelInventoryProps) {
  const onboarding = firstEvaluationCopy[locale];
  const copy = endpointWorkspaceCopy[locale];
  const [selectedEndpointId, setSelectedEndpointId] = useState<string | null>(() => preferredEndpointId ?? endpoints[0]?.id ?? null);
  const [operation, setOperation] = useState<"edit" | "test" | "probe" | "sandbox">("edit");
  const selectedEndpoint = endpoints.find((endpoint) => endpoint.id === selectedEndpointId) ?? endpoints[0] ?? null;

  useEffect(() => {
    if ((selectedEndpoint?.id ?? null) !== selectedEndpointId) setSelectedEndpointId(selectedEndpoint?.id ?? null);
  }, [selectedEndpoint?.id, selectedEndpointId]);

  useEffect(() => {
    if (preferredEndpointId && endpoints.some((endpoint) => endpoint.id === preferredEndpointId)) {
      setSelectedEndpointId(preferredEndpointId);
      onPreferredEndpointConsumed?.();
    }
  }, [endpoints, onPreferredEndpointConsumed, preferredEndpointId]);

  function runOperation() {
    if (!selectedEndpoint) return;
    if (operation === "edit") onEdit(selectedEndpoint);
    if (operation === "test") onTest(selectedEndpoint.id);
    if (operation === "probe") onProbe(selectedEndpoint.id);
    if (operation === "sandbox") onOpenSandbox?.(selectedEndpoint.id);
  }

  return (
    <div className="workspace-model-inventory-layout">
      <WorkspacePanel toolbar={<span className="workspace-count">{endpoints.length} configured</span>} title="Endpoint inventory">
        {endpoints.length === 0 ? <div className="workspace-empty-action"><p className="empty">{onboarding.modelEmpty}</p><button onClick={() => onTabChange("add-endpoint")} type="button">{onboarding.addEndpoint}</button></div> : (
          <div className="workspace-model-selector-list">
            {endpoints.map((endpoint) => (
              <button
                aria-label={`Select ${endpoint.display_name}`}
                aria-pressed={endpoint.id === selectedEndpoint?.id}
                className={endpoint.id === selectedEndpoint?.id ? "workspace-model-selector is-selected" : "workspace-model-selector"}
                key={endpoint.id}
                onClick={() => setSelectedEndpointId(endpoint.id)}
                type="button"
              >
                <span data-i18n-preserve><strong>{endpoint.display_name}</strong><small>{endpoint.model_name}</small></span>
                <span className={`badge ${endpoint.status}`}>{endpoint.status}</span>
              </button>
            ))}
          </div>
        )}
      </WorkspacePanel>

      <WorkspacePanel className="workspace-model-inspector" title="Selected model endpoint">
        {!selectedEndpoint ? <p className="empty">Select a configured endpoint to inspect it.</p> : (
          <article className="workspace-model-detail">
            <div className="workspace-inventory-item-heading" data-i18n-preserve>
              <div><h3>{selectedEndpoint.display_name}</h3><p>{selectedEndpoint.model_name} · {selectedEndpoint.api_key_mask}</p></div>
              <span className={`badge ${selectedEndpoint.status}`}>{selectedEndpoint.status}</span>
            </div>
            <p className="muted" data-i18n-preserve>{selectedEndpoint.base_url}</p>
            <dl className="workspace-model-metadata">
              <div><dt>Protocol</dt><dd data-i18n-preserve>{selectedEndpoint.protocol_profile}</dd></div>
              <div><dt>Endpoint concurrency</dt><dd>{selectedEndpoint.max_concurrency}</dd></div>
              <div><dt>Shared-key concurrency</dt><dd>{selectedEndpoint.api_key_max_concurrency ?? "Unlimited"}</dd></div>
              <div><dt>Requests / minute</dt><dd>{selectedEndpoint.requests_per_minute ?? "Unlimited"}</dd></div>
              <div><dt>Tokens / minute</dt><dd>{selectedEndpoint.tokens_per_minute ?? "Unlimited"}</dd></div>
              <div><dt>Input cost / 1M</dt><dd>{selectedEndpoint.input_cost_per_million ?? "--"} {selectedEndpoint.currency}</dd></div>
              <div><dt>Output cost / 1M</dt><dd>{selectedEndpoint.output_cost_per_million ?? "--"} {selectedEndpoint.currency}</dd></div>
              <div><dt>Timeout</dt><dd>{selectedEndpoint.timeout_seconds}s</dd></div>
              <div><dt>{copy.reasoningEffort}</dt><dd>{selectedEndpoint.reasoning_effort ?? copy.providerDefault}</dd></div>
              <div><dt>{copy.contextLength}</dt><dd>{selectedEndpoint.context_length ?? copy.notSet}</dd></div>
              <div><dt>{copy.maxOutputTokens}</dt><dd>{selectedEndpoint.max_output_tokens ?? copy.providerDefault}</dd></div>
            </dl>
            {selectedEndpoint.last_connection_error && <p className="error" role="alert" data-i18n-preserve>{selectedEndpoint.last_connection_error}</p>}
            <div className="workspace-inventory-operation"><label>{copy.operation}<select aria-label={copy.operation} onChange={(event) => setOperation(event.target.value as typeof operation)} value={operation}><option value="edit">{copy.editConfiguration}</option><option value="test">{copy.testConnection}</option><option value="probe">{copy.probeCapabilities}</option><option value="sandbox">{copy.openSandbox}</option></select></label><button className="secondary" disabled={busy === `test-${selectedEndpoint.id}` || busy === `capabilities-${selectedEndpoint.id}`} onClick={runOperation} type="button">{copy.runOperation}</button></div>
            {testRequests[selectedEndpoint.id] && <details><summary>Most recent model test request</summary><p className="muted">{testRequests[selectedEndpoint.id].method} {testRequests[selectedEndpoint.id].url}</p><pre>{JSON.stringify(testRequests[selectedEndpoint.id].body, null, 2)}</pre><p className="muted">Credentials and request headers are intentionally not shown.</p></details>}
            {capabilities[selectedEndpoint.id] && <CapabilityDeclarations capabilities={capabilities[selectedEndpoint.id]} busy={busy} endpointId={selectedEndpoint.id} onDeclare={onDeclare} />}
          </article>
        )}
      </WorkspacePanel>
    </div>
  );
}

export function ModelsPage({ activeTab, busy, capabilities, editingEndpointId, endpoints, form, locale = "en", onCancelEdit, onDeclare, onEdit, onFormChange, onOpenSandbox, onPreferredEndpointConsumed, onProbe, onSubmit, onTabChange, onTest, preferredEndpointId, sandbox = null, testRequests }: ModelsPageProps) {
  const copy = workspacePageTabCopy[locale].models;
  const tabs = [
    { id: "model-inventory", label: copy.modelInventory, description: copy.inventoryDescription },
    { id: "add-endpoint", label: copy.addEndpoint, description: copy.endpointDescription },
    { id: "sandbox", label: copy.sandbox, description: copy.sandboxDescription },
  ] as const;

  return (
    <div className="workspace-page models-page">
      <PageHeader
        description="Register endpoints, validate connectivity, and inspect the capabilities available to evaluations."
        eyebrow="Configure"
        status={<><strong>{endpoints.length}</strong> configured</>}
        title="Models"
      />
      <WorkspaceTabs ariaLabel="Models sections" idPrefix="models" onChange={onTabChange} tabs={tabs} value={activeTab} />
      <div aria-labelledby={workspaceTabId("models", activeTab)} id={workspaceTabPanelId("models", activeTab)} role="tabpanel" tabIndex={0}>
        {activeTab === "model-inventory" ? <ModelInventory busy={busy} capabilities={capabilities} endpoints={endpoints} locale={locale} onDeclare={onDeclare} onEdit={onEdit} onOpenSandbox={onOpenSandbox} onPreferredEndpointConsumed={onPreferredEndpointConsumed} onProbe={onProbe} onTabChange={onTabChange} onTest={onTest} preferredEndpointId={preferredEndpointId} testRequests={testRequests} /> : activeTab === "add-endpoint" ? <EndpointFormPanel busy={busy} editingEndpointId={editingEndpointId} form={form} locale={locale} onCancelEdit={onCancelEdit} onFormChange={onFormChange} onSubmit={onSubmit} /> : sandbox}
      </div>
    </div>
  );
}


export function CapabilityDeclarations({ busy, capabilities, endpointId, onDeclare }: { busy: string | null; capabilities: Capability[]; endpointId: string; onDeclare: (endpointId: string, capability: Capability, status: CapabilityStatus) => void }) {
  return <div className="workspace-capability-list">{capabilities.map((capability) => <div className="workspace-capability-row" key={capability.id}><div><strong data-i18n-preserve>{capability.capability_key}</strong><div className="workspace-capability-state" data-i18n-preserve><span>Detected: {capability.auto_detection_status}</span><span>Effective: {capability.effective_status}</span></div></div><label data-i18n-preserve>{capability.capability_key} declaration<select aria-label={`${capability.capability_key} declaration`} disabled={busy === `declare-${endpointId}-${capability.capability_key}`} onChange={(event) => onDeclare(endpointId, capability, event.target.value as CapabilityStatus)} value={capability.user_declared_status}><option value="unknown">User: unknown</option><option value="supported">User: supported</option><option value="unsupported">User: unsupported</option></select></label></div>)}</div>;
}
