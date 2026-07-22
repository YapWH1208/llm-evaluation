import { FormEvent, useCallback, useEffect, useState } from "react";
import { api, ApiError, Endpoint, EvaluationRun, SampleAttempt } from "./api";

const initialEndpoint = { base_url: "", api_key: "", model_name: "", display_name: "" };

function formatDate(value: string | null) {
  return value ? new Intl.DateTimeFormat(undefined, { dateStyle: "medium", timeStyle: "short" }).format(new Date(value)) : "—";
}

export default function App() {
  const [endpoints, setEndpoints] = useState<Endpoint[]>([]);
  const [runs, setRuns] = useState<EvaluationRun[]>([]);
  const [attempts, setAttempts] = useState<SampleAttempt[]>([]);
  const [selectedRun, setSelectedRun] = useState<string | null>(null);
  const [form, setForm] = useState(initialEndpoint);
  const [busy, setBusy] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    const [nextEndpoints, nextRuns] = await Promise.all([api.listEndpoints(), api.listRuns()]);
    setEndpoints(nextEndpoints);
    setRuns(nextRuns);
  }, []);

  useEffect(() => { void refresh().catch(showError); }, [refresh]);

  function showError(error: unknown) {
    setNotice(error instanceof ApiError ? error.message : "Unable to reach the evaluation service.");
  }

  async function createEndpoint(event: FormEvent) {
    event.preventDefault();
    setBusy("endpoint");
    try {
      await api.createEndpoint(form);
      setForm(initialEndpoint);
      setNotice("Endpoint saved. Test its connection before starting a run.");
      await refresh();
    } catch (error) { showError(error); } finally { setBusy(null); }
  }

  async function testEndpoint(id: string) {
    setBusy(id);
    try {
      const result = await api.testEndpoint(id);
      setNotice(result.message);
      await refresh();
    } catch (error) { showError(error); } finally { setBusy(null); }
  }

  async function createRun(endpointId: string) {
    setBusy(endpointId);
    try {
      const run = await api.createRun(endpointId);
      setSelectedRun(run.id);
      setNotice("Text Quick Check queued.");
      await refresh();
    } catch (error) { showError(error); } finally { setBusy(null); }
  }

  async function executeRun(runId: string) {
    setBusy(runId);
    try {
      await api.executeRun(runId);
      setNotice("Run completed. Inspect the saved sample evidence below.");
      await selectRun(runId);
      await refresh();
    } catch (error) { showError(error); } finally { setBusy(null); }
  }

  async function generateReport(runId: string) {
    setBusy(`report-${runId}`);
    try {
      const report = await api.createReport(runId, "html");
      setNotice("HTML report generated in the platform artifact store.");
      window.open(api.reportDownloadUrl(report.id), "_blank", "noopener,noreferrer");
    } catch (error) { showError(error); } finally { setBusy(null); }
  }

  async function selectRun(runId: string) {
    setSelectedRun(runId);
    try { setAttempts(await api.listAttempts(runId)); } catch (error) { showError(error); }
  }

  const completedRuns = runs.filter((run) => run.status.startsWith("completed"));

  return (
    <main>
      <header className="hero">
        <div><p className="eyebrow">SQLite-first workspace</p><h1>LLM/SLM Evaluation Platform</h1><p>Connect an API-hosted model, verify it, run a reproducible text benchmark, and inspect every saved attempt.</p></div>
        <div className="metric"><strong>{completedRuns.length}</strong><span>completed runs</span></div>
      </header>
      {notice && <button className="notice" onClick={() => setNotice(null)}>{notice}<span>×</span></button>}

      <section className="grid two">
        <article className="panel">
          <h2>Add model endpoint</h2>
          <form onSubmit={createEndpoint} className="form">
            <label>Display name<input value={form.display_name} onChange={(e) => setForm({ ...form, display_name: e.target.value })} placeholder="My local model" /></label>
            <label>Base URL<input required type="url" value={form.base_url} onChange={(e) => setForm({ ...form, base_url: e.target.value })} placeholder="https://provider.example/v1" /></label>
            <label>Model name<input required value={form.model_name} onChange={(e) => setForm({ ...form, model_name: e.target.value })} placeholder="model-id" /></label>
            <label>API key<input required type="password" value={form.api_key} onChange={(e) => setForm({ ...form, api_key: e.target.value })} placeholder="Stored encrypted" /></label>
            <button disabled={busy === "endpoint"}>{busy === "endpoint" ? "Saving…" : "Save encrypted endpoint"}</button>
          </form>
        </article>
        <article className="panel">
          <h2>Quick-start</h2>
          <ol><li>Add an OpenAI-compatible endpoint.</li><li>Run a bounded connection test.</li><li>Queue the built-in Text Quick Check.</li><li>Execute it and inspect per-sample evidence.</li></ol>
          <p className="muted">API keys are never returned to this UI; only a masked suffix is displayed.</p>
        </article>
      </section>

      <section className="panel"><div className="section-title"><h2>Models</h2><span>{endpoints.length} configured</span></div>
        {endpoints.length === 0 ? <p className="empty">No model endpoints yet.</p> : <div className="cards">{endpoints.map((endpoint) => <div className="card" key={endpoint.id}>
          <div><h3>{endpoint.display_name}</h3><p>{endpoint.model_name} · {endpoint.api_key_mask}</p><p className="muted">{endpoint.base_url}</p></div>
          <span className={`badge ${endpoint.status}`}>{endpoint.status}</span>
          <div className="actions"><button className="secondary" disabled={busy === endpoint.id} onClick={() => void testEndpoint(endpoint.id)}>Test connection</button><button disabled={endpoint.status !== "available" || busy === endpoint.id} onClick={() => void createRun(endpoint.id)}>Queue Quick Check</button></div>
        </div>)}</div>}
      </section>

      <section className="panel"><div className="section-title"><h2>Evaluation runs</h2><span>{runs.length} total</span></div>
        {runs.length === 0 ? <p className="empty">Verify a model endpoint to create the first run.</p> : <div className="run-list">{runs.map((run) => <div className={`run ${selectedRun === run.id ? "selected" : ""}`} key={run.id}>
          <button className="run-summary" onClick={() => void selectRun(run.id)}><strong>{run.benchmark_id}</strong><span>{run.status} · {run.completed_samples}/{run.total_samples} samples · {formatDate(run.created_at)}</span></button>
          <div className="actions"><button className="secondary" onClick={() => void selectRun(run.id)}>Evidence</button>{run.status === "queued" && <button disabled={busy === run.id} onClick={() => void executeRun(run.id)}>Execute</button>}{run.status.startsWith("completed") && <button disabled={busy === `report-${run.id}`} onClick={() => void generateReport(run.id)}>Download report</button>}</div>
        </div>)}</div>}
      </section>

      {selectedRun && <section className="panel"><div className="section-title"><h2>Sample evidence</h2><span>{attempts.length} attempts</span></div>
        {attempts.length === 0 ? <p className="empty">This run has no saved attempts yet.</p> : attempts.map((attempt) => <details className="attempt" key={attempt.id}><summary><span>{attempt.sample_id}</span><span className={`badge ${attempt.status}`}>{attempt.status}</span><span>score: {attempt.score ?? "—"}</span></summary><div className="evidence"><pre>{JSON.stringify({ input: attempt.input_snapshot, request: attempt.request_snapshot, reference: attempt.reference_snapshot }, null, 2)}</pre><pre>{attempt.raw_response ?? attempt.error_message ?? "No response captured."}</pre></div></details>)}
      </section>}
    </main>
  );
}
