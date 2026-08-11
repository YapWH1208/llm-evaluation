import { FormEvent, useEffect, useState } from "react";

import { Capability, Endpoint } from "../../api";
import type { WorkspaceTabFor } from "../../dashboard/routing";
import { workspacePageTabCopy, type Locale } from "../../i18n/catalog";
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
  max_concurrency: string;
  model_name: string;
  notes: string;
  output_cost_per_million: string;
  output_tokens_per_minute: string;
  protocol_profile: Endpoint["protocol_profile"];
  requests_per_minute: string;
  requests_per_second: string;
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
  onFormChange: (form: EndpointForm) => void;
  onProbe: (endpointId: string) => void;
  onSubmit: (event: FormEvent<HTMLFormElement>) => void;
  onTabChange: (tab: WorkspaceTabFor<"models">) => void;
  onTest: (endpointId: string) => void;
  testRequests: Record<string, { method: "POST"; url: string; body: Record<string, unknown> }>;
};

type EndpointFormPanelProps = Pick<ModelsPageProps, "busy" | "editingEndpointId" | "form" | "onCancelEdit" | "onFormChange" | "onSubmit">;

export function EndpointFormPanel({ busy, editingEndpointId, form, onCancelEdit, onFormChange, onSubmit }: EndpointFormPanelProps) {
  return (
    <WorkspacePanel description="Connection, rate-limit, and cost settings remain editable without exposing stored credentials." title={editingEndpointId ? "Edit model endpoint" : "Add model endpoint"}>
      <form className="form" onSubmit={onSubmit}>
            <label>Display name<input onChange={(event) => onFormChange(updateEndpointForm(form, "display_name", event.target.value))} placeholder="My local model" value={form.display_name} /></label>
            <label>Base URL<input onChange={(event) => onFormChange(updateEndpointForm(form, "base_url", event.target.value))} placeholder="https://provider.example/v1" required type="url" value={form.base_url} /></label>
            <label>Model name<input onChange={(event) => onFormChange(updateEndpointForm(form, "model_name", event.target.value))} placeholder="model-id" required value={form.model_name} /></label>
            <label>Protocol profile<select onChange={(event) => onFormChange(updateEndpointForm(form, "protocol_profile", event.target.value as Endpoint["protocol_profile"]))} value={form.protocol_profile}><option value="openai_chat_completions">OpenAI-compatible Chat Completions</option><option value="openai_responses">OpenAI-compatible Responses API</option><option value="anthropic_messages">Anthropic Messages</option><option value="gemini_generate_content">Gemini GenerateContent</option><option value="azure_openai_chat_completions">Azure OpenAI Chat Completions</option><option value="ollama_chat">Ollama Chat</option><option value="custom_http_json">Custom HTTP JSON</option></select></label>
            <label>API key<input onChange={(event) => onFormChange(updateEndpointForm(form, "api_key", event.target.value))} placeholder={editingEndpointId ? "Leave blank to keep the encrypted key" : form.protocol_profile === "ollama_chat" ? "Optional for a local Ollama service" : "Stored encrypted"} required={!editingEndpointId && form.protocol_profile !== "ollama_chat"} type="password" value={form.api_key} /></label>
            <label>Custom headers (JSON)<textarea onChange={(event) => onFormChange(updateEndpointForm(form, "custom_headers", event.target.value))} placeholder='{"X-Provider-Project":"project-id"}' spellCheck={false} value={form.custom_headers} /></label>
            <label>Default request body (JSON)<textarea onChange={(event) => onFormChange(updateEndpointForm(form, "default_request_body", event.target.value))} spellCheck={false} value={form.default_request_body} /></label>
            <div className="workspace-field-grid workspace-field-grid--five"><label>Timeout (seconds)<input max="600" min="1" onChange={(event) => onFormChange(updateEndpointForm(form, "timeout_seconds", event.target.value))} required type="number" value={form.timeout_seconds} /></label><label>Endpoint concurrency<input max="1000" min="1" onChange={(event) => onFormChange(updateEndpointForm(form, "max_concurrency", event.target.value))} required type="number" value={form.max_concurrency} /></label><label>Shared API-key concurrency<input max="1000" min="1" onChange={(event) => onFormChange(updateEndpointForm(form, "api_key_max_concurrency", event.target.value))} placeholder="Unlimited" type="number" value={form.api_key_max_concurrency} /></label><label>Requests / minute<input min="1" onChange={(event) => onFormChange(updateEndpointForm(form, "requests_per_minute", event.target.value))} placeholder="Unlimited" type="number" value={form.requests_per_minute} /></label><label>Tokens / minute<input min="1" onChange={(event) => onFormChange(updateEndpointForm(form, "tokens_per_minute", event.target.value))} placeholder="Unlimited" type="number" value={form.tokens_per_minute} /></label></div>
            <div className="workspace-field-grid workspace-field-grid--three"><label>Requests / second<input min="1" onChange={(event) => onFormChange(updateEndpointForm(form, "requests_per_second", event.target.value))} placeholder="Unlimited" type="number" value={form.requests_per_second} /></label><label>Input tokens / minute<input min="1" onChange={(event) => onFormChange(updateEndpointForm(form, "input_tokens_per_minute", event.target.value))} placeholder="Unlimited" type="number" value={form.input_tokens_per_minute} /></label><label>Output tokens / minute<input min="1" onChange={(event) => onFormChange(updateEndpointForm(form, "output_tokens_per_minute", event.target.value))} placeholder="Unlimited" type="number" value={form.output_tokens_per_minute} /></label></div>
            <div className="workspace-field-grid workspace-field-grid--three"><label>Input / 1M tokens<input min="0" onChange={(event) => onFormChange(updateEndpointForm(form, "input_cost_per_million", event.target.value))} step="any" type="number" value={form.input_cost_per_million} /></label><label>Output / 1M tokens<input min="0" onChange={(event) => onFormChange(updateEndpointForm(form, "output_cost_per_million", event.target.value))} step="any" type="number" value={form.output_cost_per_million} /></label><label>Currency<input maxLength={8} onChange={(event) => onFormChange(updateEndpointForm(form, "currency", event.target.value))} value={form.currency} /></label></div>
            <label>Tags (comma-separated)<input onChange={(event) => onFormChange(updateEndpointForm(form, "tags", event.target.value))} placeholder="production, vision" value={form.tags} /></label>
            <label>Notes<textarea onChange={(event) => onFormChange(updateEndpointForm(form, "notes", event.target.value))} value={form.notes} /></label>
            <div className="actions"><button disabled={busy === "endpoint"}>{busy === "endpoint" ? "Saving..." : editingEndpointId ? "Save model configuration" : "Save encrypted endpoint"}</button>{editingEndpointId && <button className="secondary" onClick={onCancelEdit} type="button">Cancel edit</button>}</div>
      </form>
    </WorkspacePanel>
  );
}

type ModelInventoryProps = Pick<ModelsPageProps, "busy" | "capabilities" | "endpoints" | "onDeclare" | "onEdit" | "onProbe" | "onTest" | "testRequests">;

export function ModelInventory({ busy, capabilities, endpoints, onDeclare, onEdit, onProbe, onTest, testRequests }: ModelInventoryProps) {
  const [selectedEndpointId, setSelectedEndpointId] = useState<string | null>(() => endpoints[0]?.id ?? null);
  const selectedEndpoint = endpoints.find((endpoint) => endpoint.id === selectedEndpointId) ?? endpoints[0] ?? null;

  useEffect(() => {
    if ((selectedEndpoint?.id ?? null) !== selectedEndpointId) setSelectedEndpointId(selectedEndpoint?.id ?? null);
  }, [selectedEndpoint?.id, selectedEndpointId]);

  return (
    <div className="workspace-model-inventory-layout">
      <WorkspacePanel toolbar={<span className="workspace-count">{endpoints.length} configured</span>} title="Endpoint inventory">
        {endpoints.length === 0 ? <p className="empty">No model endpoints yet.</p> : (
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
            </dl>
            {selectedEndpoint.last_connection_error && <p className="error" role="alert" data-i18n-preserve>{selectedEndpoint.last_connection_error}</p>}
            <div className="actions"><button className="secondary" onClick={() => onEdit(selectedEndpoint)} type="button">Edit configuration</button><button className="secondary" disabled={busy === `test-${selectedEndpoint.id}`} onClick={() => onTest(selectedEndpoint.id)} type="button">Test connection</button><button className="secondary" disabled={busy === `capabilities-${selectedEndpoint.id}`} onClick={() => onProbe(selectedEndpoint.id)} type="button">Probe capabilities</button></div>
            {testRequests[selectedEndpoint.id] && <details><summary>Most recent model test request</summary><p className="muted">{testRequests[selectedEndpoint.id].method} {testRequests[selectedEndpoint.id].url}</p><pre>{JSON.stringify(testRequests[selectedEndpoint.id].body, null, 2)}</pre><p className="muted">Credentials and request headers are intentionally not shown.</p></details>}
            {capabilities[selectedEndpoint.id] && <CapabilityDeclarations capabilities={capabilities[selectedEndpoint.id]} busy={busy} endpointId={selectedEndpoint.id} onDeclare={onDeclare} />}
          </article>
        )}
      </WorkspacePanel>
    </div>
  );
}

export function ModelsPage({ activeTab, busy, capabilities, editingEndpointId, endpoints, form, locale = "en", onCancelEdit, onDeclare, onEdit, onFormChange, onProbe, onSubmit, onTabChange, onTest, testRequests }: ModelsPageProps) {
  const copy = workspacePageTabCopy[locale].models;
  const tabs = [
    { id: "model-inventory", label: copy.modelInventory, description: copy.inventoryDescription },
    { id: "add-endpoint", label: copy.addEndpoint, description: copy.endpointDescription },
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
        {activeTab === "model-inventory" ? (
          <ModelInventory busy={busy} capabilities={capabilities} endpoints={endpoints} onDeclare={onDeclare} onEdit={onEdit} onProbe={onProbe} onTest={onTest} testRequests={testRequests} />
        ) : (
          <EndpointFormPanel busy={busy} editingEndpointId={editingEndpointId} form={form} onCancelEdit={onCancelEdit} onFormChange={onFormChange} onSubmit={onSubmit} />
        )}
      </div>
    </div>
  );
}


export function CapabilityDeclarations({ busy, capabilities, endpointId, onDeclare }: { busy: string | null; capabilities: Capability[]; endpointId: string; onDeclare: (endpointId: string, capability: Capability, status: CapabilityStatus) => void }) {
  return <div className="workspace-capability-list">{capabilities.map((capability) => <div className="workspace-capability-row" key={capability.id}><div><strong data-i18n-preserve>{capability.capability_key}</strong><div className="workspace-capability-state" data-i18n-preserve><span>Detected: {capability.auto_detection_status}</span><span>Effective: {capability.effective_status}</span></div></div><label data-i18n-preserve>{capability.capability_key} declaration<select aria-label={`${capability.capability_key} declaration`} disabled={busy === `declare-${endpointId}-${capability.capability_key}`} onChange={(event) => onDeclare(endpointId, capability, event.target.value as CapabilityStatus)} value={capability.user_declared_status}><option value="unknown">User: unknown</option><option value="supported">User: supported</option><option value="unsupported">User: unsupported</option></select></label></div>)}</div>;
}
