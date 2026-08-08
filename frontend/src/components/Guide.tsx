import { useTranslation } from "../i18n/LocaleProvider";

const steps = [
  ["1. Add a model endpoint", "Models · configure the provider, run a connection test, and confirm it is available."],
  ["2. Register a dataset", "Datasets · declare the source and, optionally, the input and reference fields."],
  ["3. Download and verify", "Download the dataset and wait until its status is ready."],
  ["4. Create a prompt package", "Workspace · write the user template; record fields render through {{ placeholders }}."],
  ["5. Queue a dataset run", "Runs · pick the dataset, reference field, and endpoint, then queue the run."],
  ["6. Inspect evidence", "Open the run to review samples, scores, latency, cost, and errors."],
  ["7. Judge, review, and report", "Run blind pairwise judging, save human reviews, and generate reports."],
] as const;

export function Guide() {
  const { formatNumber } = useTranslation();
  void formatNumber;
  return (
    <section className="panel">
      <div className="section-title"><h2>How to use this workspace</h2><span>7 steps</span></div>
      <p className="muted">Register a model endpoint and a dataset, then queue evaluation runs and inspect the evidence.</p>
      <div className="cards">
        {steps.map(([title, description]) => (
          <article className="card" key={title}>
            <h3>{title}</h3>
            <p className="muted">{description}</p>
          </article>
        ))}
      </div>
    </section>
  );
}
