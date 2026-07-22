import { FormEvent, useCallback, useEffect, useState } from "react";
import { api, ApiError, Capability, Dashboard, Dataset, Endpoint, EvaluationRun, PromptPackage, SampleAttempt } from "./api";

const initialEndpoint = { base_url: "", api_key: "", model_name: "", display_name: "" };
const initialPrompt = { name: "", version: "1", system_message: "", user_template: "{{ question }}" };
const initialDataset = { dataset_id: "", version: "1", source_url: "", license_text: "" };

function formatDate(value: string | null) {
  return value ? new Intl.DateTimeFormat(undefined, { dateStyle: "medium", timeStyle: "short" }).format(new Date(value)) : "—";
}

export default function App() {
  const [endpoints, setEndpoints] = useState<Endpoint[]>([]);
  const [runs, setRuns] = useState<EvaluationRun[]>([]);
  const [dashboard, setDashboard] = useState<Dashboard | null>(null);
  const [prompts, setPrompts] = useState<PromptPackage[]>([]);
  const [datasets, setDatasets] = useState<Dataset[]>([]);
  const [capabilities, setCapabilities] = useState<Record<string, Capability[]>>({});
  const [attempts, setAttempts] = useState<SampleAttempt[]>([]);
  const [selectedRun, setSelectedRun] = useState<string | null>(null);
  const [form, setForm] = useState(initialEndpoint);
  const [promptForm, setPromptForm] = useState(initialPrompt);
  const [datasetForm, setDatasetForm] = useState(initialDataset);
  const [selectedPromptId, setSelectedPromptId] = useState("");
  const [busy, setBusy] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    const [nextEndpoints, nextRuns, nextDashboard, nextPrompts, nextDatasets] = await Promise.all([
      api.listEndpoints(),
      api.listRuns(),
      api.dashboard(),
      api.listPromptPackages(),
      api.listDatasets(),
    ]);
    setEndpoints(nextEndpoints);
    setRuns(nextRuns);
    setDashboard(nextDashboard);
    setPrompts(nextPrompts);
    setDatasets(nextDatasets);
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
      const run = await api.createRun(endpointId, selectedPromptId || undefined);
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

  async function createPrompt(event: FormEvent) {
    event.preventDefault();
    setBusy("prompt");
    try {
      await api.createPromptPackage({ ...promptForm, system_message: promptForm.system_message || null });
      setPromptForm(initialPrompt);
      setNotice("Versioned prompt package saved.");
      await refresh();
    } catch (error) { showError(error); } finally { setBusy(null); }
  }

  async function createDataset(event: FormEvent) {
    event.preventDefault();
    setBusy("dataset");
    try {
      await api.createDataset({
        ...datasetForm,
        source_url: datasetForm.source_url || null,
        license_text: datasetForm.license_text || null,
      });
      setDatasetForm(initialDataset);
      setNotice("Dataset version registered.");
      await refresh();
    } catch (error) { showError(error); } finally { setBusy(null); }
  }

  async function prepareDataset(dataset: Dataset) {
    setBusy(`dataset-${dataset.id}`);
    try {
      if (dataset.license_text && !dataset.license_accepted_at) {
        await api.acceptDatasetLicense(dataset.id);
        setNotice("License accepted. Download can now be started.");
      } else {
        await api.downloadDataset(dataset.id);
        setNotice("Dataset downloaded, verified, and cached.");
      }
      await refresh();
    } catch (error) { showError(error); } finally { setBusy(null); }
  }

  async function probeCapabilities(endpointId: string) {
    setBusy(`capabilities-${endpointId}`);
    try {
      const detected = await api.detectCapabilities(endpointId);
      setCapabilities((current) => ({ ...current, [endpointId]: detected }));
      setNotice("Low-cost capability probe finished; declarations remain unchanged.");
    } catch (error) { showError(error); } finally { setBusy(null); }
  }

  const completedRuns = runs.filter((run) => run.status.startsWith("completed"));
  const metrics = dashboard ?? {
    runs: { active: 0, completed: completedRuns.length },
    queue: { pending: 0, leased: 0 },
    endpoints: { available: 0, unavailable: 0, total: endpoints.length },
    datasets: { ready: 0, blocked: 0 },
    reports: 0,
  };

  return (
    <main>
      <header className="hero">
        <div><p className="eyebrow">SQLite-first workspace</p><h1>LLM/SLM Evaluation Platform</h1><p>Connect an API-hosted model, verify it, run a reproducible text benchmark, and inspect every saved attempt.</p></div>
        <div className="metric"><strong>{metrics.runs.completed}</strong><span>completed runs</span></div>
      </header>
      {notice && <button className="notice" onClick={() => setNotice(null)}>{notice}<span>×</span></button>}

      <section className="dashboard" aria-label="Operational status">
        <div><span>Active runs</span><strong>{metrics.runs.active}</strong><small>{metrics.queue.pending} waiting · {metrics.queue.leased} leased</small></div>
        <div><span>Endpoints</span><strong>{metrics.endpoints.available}/{metrics.endpoints.total}</strong><small>{metrics.endpoints.unavailable} unavailable</small></div>
        <div><span>Datasets</span><strong>{metrics.datasets.ready}</strong><small>{metrics.datasets.blocked} need attention</small></div>
        <div><span>Reports</span><strong>{metrics.reports}</strong><small>generated artifacts</small></div>
      </section>

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
          <label className="select-label">Prompt package for the next run
            <select value={selectedPromptId} onChange={(event) => setSelectedPromptId(event.target.value)}>
              <option value="">Built-in benchmark prompt</option>
              {prompts.map((prompt) => <option key={prompt.id} value={prompt.id}>{prompt.name} v{prompt.version}</option>)}
            </select>
          </label>
          <p className="muted">API keys are never returned to this UI; only a masked suffix is displayed.</p>
        </article>
      </section>

      <section className="grid two">
        <article className="panel">
          <h2>Create prompt package</h2>
          <form onSubmit={createPrompt} className="form">
            <label>Name<input required value={promptForm.name} onChange={(event) => setPromptForm({ ...promptForm, name: event.target.value })} placeholder="strict-answering" /></label>
            <label>Version<input required value={promptForm.version} onChange={(event) => setPromptForm({ ...promptForm, version: event.target.value })} /></label>
            <label>System message<textarea value={promptForm.system_message} onChange={(event) => setPromptForm({ ...promptForm, system_message: event.target.value })} placeholder="Optional system instruction" /></label>
            <label>User template<textarea required value={promptForm.user_template} onChange={(event) => setPromptForm({ ...promptForm, user_template: event.target.value })} /></label>
            <button disabled={busy === "prompt"}>{busy === "prompt" ? "Saving..." : "Save versioned prompt"}</button>
          </form>
          {prompts.length > 0 && <p className="muted">Available: {prompts.map((prompt) => `${prompt.name} v${prompt.version}`).join(", ")}</p>}
        </article>
        <article className="panel">
          <h2>Register dataset version</h2>
          <form onSubmit={createDataset} className="form">
            <label>Dataset ID<input required value={datasetForm.dataset_id} onChange={(event) => setDatasetForm({ ...datasetForm, dataset_id: event.target.value })} placeholder="benchmark-source" /></label>
            <label>Version<input required value={datasetForm.version} onChange={(event) => setDatasetForm({ ...datasetForm, version: event.target.value })} /></label>
            <label>Source URL<input type="url" value={datasetForm.source_url} onChange={(event) => setDatasetForm({ ...datasetForm, source_url: event.target.value })} placeholder="https://example.org/dataset.jsonl" /></label>
            <label>License text<textarea value={datasetForm.license_text} onChange={(event) => setDatasetForm({ ...datasetForm, license_text: event.target.value })} placeholder="Optional license acknowledgement" /></label>
            <button disabled={busy === "dataset"}>{busy === "dataset" ? "Saving..." : "Register dataset"}</button>
          </form>
        </article>
      </section>

      <section className="panel"><div className="section-title"><h2>Models</h2><span>{endpoints.length} configured</span></div>
        {endpoints.length === 0 ? <p className="empty">No model endpoints yet.</p> : <div className="cards">{endpoints.map((endpoint) => <div className="card" key={endpoint.id}>
          <div><h3>{endpoint.display_name}</h3><p>{endpoint.model_name} · {endpoint.api_key_mask}</p><p className="muted">{endpoint.base_url}</p></div>
          <span className={`badge ${endpoint.status}`}>{endpoint.status}</span>
          <div className="actions"><button className="secondary" disabled={busy === endpoint.id} onClick={() => void testEndpoint(endpoint.id)}>Test connection</button><button className="secondary" disabled={busy === `capabilities-${endpoint.id}`} onClick={() => void probeCapabilities(endpoint.id)}>Probe capabilities</button><button disabled={endpoint.status !== "available" || busy === endpoint.id} onClick={() => void createRun(endpoint.id)}>Queue Quick Check</button></div>
          {capabilities[endpoint.id] && <p className="muted">{capabilities[endpoint.id].map((item) => `${item.capability_key}: ${item.effective_status}`).join(" · ")}</p>}
        </div>)}</div>}
      </section>

      <section className="panel"><div className="section-title"><h2>Dataset cache</h2><span>{datasets.length} registered</span></div>
        {datasets.length === 0 ? <p className="empty">Register a version to make its download and license state visible here.</p> : <div className="cards">{datasets.map((dataset) => <div className="card" key={dataset.id}>
          <div><h3>{dataset.dataset_id} v{dataset.version}</h3><p className="muted">{dataset.source_url || "No source URL"}</p>{dataset.error_message && <p className="error">{dataset.error_message}</p>}</div>
          <span className={`badge ${dataset.status}`}>{dataset.status}</span>
          {dataset.status !== "ready" && <div className="actions"><button disabled={busy === `dataset-${dataset.id}` || (!dataset.source_url && (!dataset.license_text || Boolean(dataset.license_accepted_at)))} onClick={() => void prepareDataset(dataset)}>{dataset.license_text && !dataset.license_accepted_at ? "Accept license" : "Download and verify"}</button></div>}
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
