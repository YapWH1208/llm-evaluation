import { type FormEvent, useEffect, useState } from "react";

import { endpointWorkspaceCopy, firstEvaluationCopy, workspacePageTabCopy, type Locale } from "../../i18n/catalog";
import { WorkspacePanel } from "../../components/workspace/WorkspacePanel";
import type { Endpoint, SandboxResult } from "./api";

export type SandboxSubmission = {
  endpointId: string;
  mode: "text" | "tool";
  userPrompt: string;
  systemPrompt: string;
};

type ModelSandboxProps = {
  busy: boolean;
  endpoints: Endpoint[];
  locale: Locale;
  onEndpointChange: (endpointId: string) => void;
  onSubmit: (submission: SandboxSubmission) => void;
  result: SandboxResult | null;
  selectedEndpointId: string | null;
};

export function ModelSandbox({ busy, endpoints, locale, onEndpointChange, onSubmit, result, selectedEndpointId }: ModelSandboxProps) {
  const copy = endpointWorkspaceCopy[locale];
  const [mode, setMode] = useState<"text" | "tool">("text");
  const [systemPrompt, setSystemPrompt] = useState("");
  const [userPrompt, setUserPrompt] = useState("");
  const selectedEndpoint = endpoints.find((endpoint) => endpoint.id === selectedEndpointId) ?? null;

  useEffect(() => {
    if (selectedEndpointId === null && endpoints[0]) onEndpointChange(endpoints[0].id);
  }, [endpoints, onEndpointChange, selectedEndpointId]);

  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!selectedEndpoint) return;
    onSubmit({ endpointId: selectedEndpoint.id, mode, userPrompt, systemPrompt });
  }

  return (
    <WorkspacePanel description={copy.sandboxIntro} title={workspacePageTabCopy[locale].models.sandbox}>
      {endpoints.length === 0 ? <p className="empty">{firstEvaluationCopy[locale].modelEmpty}</p> : (
        <form className="form workspace-sandbox-form" onSubmit={submit}>
          <label>
            {copy.sandboxEndpoint}
            <select aria-label={copy.sandboxEndpoint} onChange={(event) => onEndpointChange(event.target.value)} value={selectedEndpoint?.id ?? ""}>
              {endpoints.map((endpoint) => <option data-i18n-preserve key={endpoint.id} value={endpoint.id}>{endpoint.display_name} · {endpoint.model_name}</option>)}
            </select>
          </label>
          {selectedEndpoint && selectedEndpoint.status !== "available" && <p className="workspace-sandbox-warning" role="status">{copy.endpointStatusWarning}</p>}
          <fieldset className="workspace-sandbox-mode">
            <legend>{copy.sandboxMode}</legend>
            <label><input checked={mode === "text"} name="sandbox-mode" onChange={() => setMode("text")} type="radio" value="text" /> {copy.textMode}</label>
            <label><input checked={mode === "tool"} name="sandbox-mode" onChange={() => setMode("tool")} type="radio" value="tool" /> {copy.toolMode}</label>
          </fieldset>
          {mode === "text" ? <>
            <label>{copy.userPrompt}<textarea aria-label={copy.userPrompt} onChange={(event) => setUserPrompt(event.target.value)} required value={userPrompt} /></label>
            <label>{copy.systemPrompt}<textarea aria-label={copy.systemPrompt} onChange={(event) => setSystemPrompt(event.target.value)} value={systemPrompt} /></label>
          </> : <p className="muted">{copy.toolHelp}</p>}
          <button disabled={!selectedEndpoint || busy} type="submit">{busy ? copy.runningSandbox : copy.runSandbox}</button>
        </form>
      )}
      <SandboxEvidence copy={copy} result={result} />
    </WorkspacePanel>
  );
}

function SandboxEvidence({ copy, result }: { copy: (typeof endpointWorkspaceCopy)[Locale]; result: SandboxResult | null }) {
  if (!result) return <p className="empty">{copy.noSandboxEvidence}</p>;
  return (
    <section aria-live="polite" className="workspace-sandbox-evidence">
      {!result.success && <p className="error" role="alert"><strong>{copy.sandboxFailed}</strong>{result.error_message ? ` ${result.error_message}` : ""}</p>}
      <dl className="workspace-model-metadata">
        <div><dt>{copy.latency}</dt><dd>{result.latency_ms === null ? "--" : `${result.latency_ms} ms`}</dd></div>
        <div><dt>{copy.usage}</dt><dd>{result.usage.input_tokens ?? "--"} / {result.usage.output_tokens ?? "--"}</dd></div>
        <div><dt>{copy.providerStatus}</dt><dd>{result.provider_status_code ?? "--"}</dd></div>
      </dl>
      <details open><summary>{copy.request}</summary><pre>{JSON.stringify(result.request, null, 2)}</pre></details>
      {result.final_text !== null && <details open><summary>{copy.finalText}</summary><pre>{result.final_text}</pre></details>}
      {result.tool_calls.length > 0 && <details open><summary>{copy.toolCalls}</summary><pre>{JSON.stringify(result.tool_calls, null, 2)}</pre></details>}
    </section>
  );
}
