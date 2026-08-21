import { type FormEvent, useCallback, useEffect, useState } from "react";

import type { FeatureRouteProps } from "../../app/types";
import { ModelsPage, type EndpointForm } from "../../components/pages/EndpointPages";
import { translateStaticTemplate } from "../../i18n/operationalCopy";
import { useTranslation } from "../../i18n/LocaleProvider";
import { endpointsApi, type Capability, type Endpoint } from "./api";

const initialEndpoint: EndpointForm = {
  base_url: "", api_key: "", model_name: "", protocol_profile: "openai_chat_completions", custom_headers: "{}", display_name: "",
  input_cost_per_million: "", output_cost_per_million: "", currency: "USD", tags: "", notes: "", default_request_body: "{}",
  timeout_seconds: "60", max_concurrency: "1", api_key_max_concurrency: "", requests_per_second: "", requests_per_minute: "",
  tokens_per_minute: "", input_tokens_per_minute: "", output_tokens_per_minute: "",
};

function optionalNumber(value: string) {
  return value.trim() === "" ? null : Number(value);
}

export function EndpointsRoute({ activeTab, navigate, reportError, showNotice }: FeatureRouteProps<"models">) {
  const { locale } = useTranslation();
  const [busy, setBusy] = useState<string | null>(null);
  const [capabilities, setCapabilities] = useState<Record<string, Capability[]>>({});
  const [editingEndpointId, setEditingEndpointId] = useState<string | null>(null);
  const [endpoints, setEndpoints] = useState<Endpoint[]>([]);
  const [form, setForm] = useState(initialEndpoint);
  const [preferredEndpointId, setPreferredEndpointId] = useState<string | null>(null);
  const [testRequests, setTestRequests] = useState<Record<string, { method: "POST"; url: string; body: Record<string, unknown> }>>({});
  const consumePreferredEndpoint = useCallback(() => setPreferredEndpointId(null), []);

  const refresh = useCallback(async () => setEndpoints(await endpointsApi.list()), []);
  useEffect(() => { void refresh().catch(reportError); }, [refresh, reportError]);

  function editEndpoint(endpoint: Endpoint) {
    setEditingEndpointId(endpoint.id);
    setForm({
      display_name: endpoint.display_name, base_url: endpoint.base_url, model_name: endpoint.model_name, protocol_profile: endpoint.protocol_profile,
      api_key: "", custom_headers: JSON.stringify(endpoint.custom_headers, null, 2), default_request_body: JSON.stringify(endpoint.default_request_body, null, 2),
      timeout_seconds: String(endpoint.timeout_seconds), max_concurrency: String(endpoint.max_concurrency),
      api_key_max_concurrency: endpoint.api_key_max_concurrency === null ? "" : String(endpoint.api_key_max_concurrency),
      requests_per_second: endpoint.requests_per_second === null ? "" : String(endpoint.requests_per_second),
      requests_per_minute: endpoint.requests_per_minute === null ? "" : String(endpoint.requests_per_minute),
      tokens_per_minute: endpoint.tokens_per_minute === null ? "" : String(endpoint.tokens_per_minute),
      input_tokens_per_minute: endpoint.input_tokens_per_minute === null ? "" : String(endpoint.input_tokens_per_minute),
      output_tokens_per_minute: endpoint.output_tokens_per_minute === null ? "" : String(endpoint.output_tokens_per_minute),
      input_cost_per_million: endpoint.input_cost_per_million === null ? "" : String(endpoint.input_cost_per_million),
      output_cost_per_million: endpoint.output_cost_per_million === null ? "" : String(endpoint.output_cost_per_million),
      currency: endpoint.currency, tags: endpoint.tags.join(", "), notes: endpoint.notes ?? "",
    });
  }

  function cancelEndpointEdit() {
    setEditingEndpointId(null);
    setForm(initialEndpoint);
  }

  async function saveEndpoint(event: FormEvent) {
    event.preventDefault();
    setBusy("endpoint");
    try {
      const defaultRequestBody: unknown = JSON.parse(form.default_request_body);
      const customHeaders: unknown = JSON.parse(form.custom_headers);
      if (!defaultRequestBody || Array.isArray(defaultRequestBody) || typeof defaultRequestBody !== "object") throw new Error("Default request body must be a JSON object.");
      if (!customHeaders || Array.isArray(customHeaders) || typeof customHeaders !== "object") throw new Error("Custom headers must be a JSON object.");
      const payload: Record<string, unknown> = {
        ...form, default_request_body: defaultRequestBody, custom_headers: customHeaders,
        tags: form.tags.split(",").map((tag) => tag.trim()).filter(Boolean), notes: form.notes || null,
        timeout_seconds: Number(form.timeout_seconds), max_concurrency: Number(form.max_concurrency),
        input_cost_per_million: optionalNumber(form.input_cost_per_million), output_cost_per_million: optionalNumber(form.output_cost_per_million),
        api_key_max_concurrency: optionalNumber(form.api_key_max_concurrency), requests_per_second: optionalNumber(form.requests_per_second),
        requests_per_minute: optionalNumber(form.requests_per_minute), tokens_per_minute: optionalNumber(form.tokens_per_minute),
        input_tokens_per_minute: optionalNumber(form.input_tokens_per_minute), output_tokens_per_minute: optionalNumber(form.output_tokens_per_minute),
        currency: form.currency.toUpperCase(),
      };
      const wasCreating = !editingEndpointId;
      if (editingEndpointId) {
        if (!form.api_key.trim()) delete payload.api_key;
        await endpointsApi.update(editingEndpointId, payload);
        setTestRequests((current) => { const { [editingEndpointId]: _removed, ...remaining } = current; return remaining; });
        showNotice("Model configuration saved. Test its connection before starting a run.");
      } else {
        const created = await endpointsApi.create(payload);
        setPreferredEndpointId(created.id);
        showNotice("Endpoint saved. Test its connection before starting a run.");
      }
      cancelEndpointEdit();
      await refresh();
      if (wasCreating) navigate("models", { tab: "model-inventory" });
    } catch (error) {
      reportError(error);
    } finally {
      setBusy(null);
    }
  }

  async function testEndpoint(endpointId: string) {
    setBusy(`test-${endpointId}`);
    try {
      const result = await endpointsApi.test(endpointId);
      setTestRequests((current) => ({ ...current, [endpointId]: result.request }));
      showNotice(result.message);
      await refresh();
    } catch (error) { reportError(error); } finally { setBusy(null); }
  }

  async function probeCapabilities(endpointId: string) {
    if (!window.confirm(translateStaticTemplate(locale, "Capability probing sends small requests to this provider and may incur API charges. Continue?"))) return;
    setBusy(`capabilities-${endpointId}`);
    try {
      const detected = await endpointsApi.detectCapabilities(endpointId);
      setCapabilities((current) => ({ ...current, [endpointId]: detected }));
      showNotice("Capability probe completed. Declared capability settings were not changed.");
    } catch (error) { reportError(error); } finally { setBusy(null); }
  }

  async function declareCapability(endpointId: string, capability: Capability, status: "supported" | "unsupported" | "unknown") {
    setBusy(`declare-${endpointId}-${capability.capability_key}`);
    try {
      const updated = await endpointsApi.declareCapability(endpointId, capability.capability_key, status);
      setCapabilities((current) => ({ ...current, [endpointId]: (current[endpointId] ?? []).map((item) => item.capability_key === updated.capability_key ? updated : item) }));
      showNotice("User capability declaration saved alongside detection evidence.");
    } catch (error) { reportError(error); } finally { setBusy(null); }
  }

  return <ModelsPage activeTab={activeTab} busy={busy} capabilities={capabilities} editingEndpointId={editingEndpointId} endpoints={endpoints} form={form} locale={locale} onCancelEdit={cancelEndpointEdit} onDeclare={(endpointId, capability, status) => void declareCapability(endpointId, capability, status)} onEdit={(endpoint) => { editEndpoint(endpoint); navigate("models", { tab: "add-endpoint" }); }} onFormChange={setForm} onPreferredEndpointConsumed={consumePreferredEndpoint} onProbe={(endpointId) => void probeCapabilities(endpointId)} onSubmit={saveEndpoint} onTabChange={(tab) => navigate("models", { tab })} onTest={(endpointId) => void testEndpoint(endpointId)} preferredEndpointId={preferredEndpointId} testRequests={testRequests} />;
}
