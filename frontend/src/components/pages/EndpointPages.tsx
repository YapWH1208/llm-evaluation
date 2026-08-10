import { FormEvent, useState } from "react";

import { Capability, Endpoint } from "../../api";
import { PageHeader } from "../workspace/PageHeader";
import { WorkspacePanel } from "../workspace/WorkspacePanel";

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
  busy: string | null;
  capabilities: Record<string, Capability[]>;
  editingEndpointId: string | null;
  endpoints: Endpoint[];
  form: EndpointForm;
  onCancelEdit: () => void;
  onDeclare: (endpointId: string, capability: Capability, status: CapabilityStatus) => void;
  onEdit: (endpoint: Endpoint) => void;
  onFormChange: (form: EndpointForm) => void;
  onProbe: (endpointId: string) => void;
  onSubmit: (event: FormEvent<HTMLFormElement>) => void;
  onTest: (endpointId: string) => void;
  testRequests: Record<string, { method: "POST"; url: string; body: Record<string, unknown> }>;
};

export function ModelsPage({ busy, capabilities, editingEndpointId, endpoints, form, onCancelEdit, onDeclare, onEdit, onFormChange, onProbe, onSubmit, onTest, testRequests }: ModelsPageProps) {
  return (
    <div className="workspace-page models-page">
      <PageHeader
        description="Register endpoints, validate connectivity, and inspect the capabilities available to evaluations."
        eyebrow="Configure"
        status={<><strong>{endpoints.length}</strong> configured</>}
        title="Models"
      />
      <div className="workspace-split workspace-split--models">
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
        <div className="workspace-stack">
          <WorkspacePanel toolbar={<span className="workspace-count">{endpoints.length} configured</span>} title="Endpoint inventory">
            {endpoints.length === 0 ? <p className="empty">No model endpoints yet.</p> : <div className="workspace-inventory-list">{endpoints.map((endpoint) => <article className="workspace-inventory-item" key={endpoint.id}>
              <div className="workspace-inventory-item-heading" data-i18n-preserve><div><h3>{endpoint.display_name}</h3><p>{endpoint.model_name} · {endpoint.api_key_mask}</p></div><span className={`badge ${endpoint.status}`}>{endpoint.status}</span></div>
              <p className="muted" data-i18n-preserve>{endpoint.base_url}</p>
              <p className="workspace-item-meta">{endpoint.max_concurrency} endpoint / {endpoint.api_key_max_concurrency ?? "∞"} shared-key concurrent · {endpoint.input_cost_per_million ?? "--"} {endpoint.currency} input / 1M</p>
              <div className="actions"><button className="secondary" onClick={() => onEdit(endpoint)} type="button">Edit configuration</button><button className="secondary" disabled={busy === `test-${endpoint.id}`} onClick={() => onTest(endpoint.id)} type="button">Test connection</button><button className="secondary" disabled={busy === `capabilities-${endpoint.id}`} onClick={() => onProbe(endpoint.id)} type="button">Probe capabilities</button></div>
              {testRequests[endpoint.id] && <details><summary>Most recent model test request</summary><p className="muted">{testRequests[endpoint.id].method} {testRequests[endpoint.id].url}</p><pre>{JSON.stringify(testRequests[endpoint.id].body, null, 2)}</pre><p className="muted">Credentials and request headers are intentionally not shown.</p></details>}
              {capabilities[endpoint.id] && <CapabilityDeclarations capabilities={capabilities[endpoint.id]} busy={busy} endpointId={endpoint.id} onDeclare={onDeclare} />}
            </article>)}</div>}
          </WorkspacePanel>
        </div>
      </div>
    </div>
  );
}


export function CapabilityDeclarations({ busy, capabilities, endpointId, onDeclare }: { busy: string | null; capabilities: Capability[]; endpointId: string; onDeclare: (endpointId: string, capability: Capability, status: CapabilityStatus) => void }) {
  return <div className="workspace-capability-list">{capabilities.map((capability) => <div className="workspace-capability-row" key={capability.id}><div><strong data-i18n-preserve>{capability.capability_key}</strong><div className="workspace-capability-state" data-i18n-preserve><span>Detected: {capability.auto_detection_status}</span><span>Effective: {capability.effective_status}</span></div></div><label data-i18n-preserve>{capability.capability_key} declaration<select aria-label={`${capability.capability_key} declaration`} disabled={busy === `declare-${endpointId}-${capability.capability_key}`} onChange={(event) => onDeclare(endpointId, capability, event.target.value as CapabilityStatus)} value={capability.user_declared_status}><option value="unknown">User: unknown</option><option value="supported">User: supported</option><option value="unsupported">User: unsupported</option></select></label></div>)}</div>;
}
