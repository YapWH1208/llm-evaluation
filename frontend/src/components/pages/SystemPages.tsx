import { FormEvent, ReactNode, useEffect, useState } from "react";

import { api, AuditEvent, EvaluationRun, ReportType, SampleAttempt, SystemHealth, User } from "../../api";
import { localeIds, localeNames, reportCopy, type Locale } from "../../i18n/catalog";
import { useTranslation } from "../../i18n/LocaleProvider";
import { PageHeader } from "../workspace/PageHeader";
import { WorkspacePanel } from "../workspace/WorkspacePanel";

type ReportsPageProps = {
  completedRuns: EvaluationRun[];
  onGenerateReport: (runId: string, format: "html" | "json" | "csv" | "parquet" | "markdown" | "pdf") => void;
  onRelatedRunChange: (runId: string) => void;
  onReportTypeChange: (type: ReportType) => void;
  onSelectRun: (runId: string) => void;
  relatedRunId: string;
  reportArtifacts: ReactNode;
  reportType: ReportType;
  runs: EvaluationRun[];
  selectedRun: EvaluationRun | null;
};

const reportTypes: Array<{ value: ReportType; label: string }> = [
  { value: "single_model", label: "Single-model complete" },
  { value: "multi_model_comparison", label: "Multi-model comparison" },
  { value: "regression", label: "Regression" },
  { value: "prompt_comparison", label: "Prompt comparison" },
  { value: "benchmark", label: "Benchmark" },
  { value: "reliability", label: "Reliability" },
  { value: "cost", label: "Cost" },
  { value: "human_review", label: "Human review" },
];

export function ReportsPage({ completedRuns, onGenerateReport, onRelatedRunChange, onReportTypeChange, onSelectRun, relatedRunId, reportArtifacts, reportType, runs, selectedRun }: ReportsPageProps) {
  const comparisonType = ["multi_model_comparison", "regression", "prompt_comparison"].includes(reportType);

  return <div className="workspace-page reports-page">
    <PageHeader description="Generate portable evaluation artifacts, then manage their controlled, read-only share policies." eyebrow="Reporting" status={<>{runs.length} run snapshots</>} title="Reports" />
    <WorkspacePanel className="workspace-report-context" description="Select the run whose immutable evidence snapshot should anchor this report." title="Report context">
      <label className="workspace-filter-control">Report source run<select disabled={runs.length === 0} onChange={(event) => onSelectRun(event.target.value)} value={selectedRun?.id ?? ""}><option value="">Select run</option>{runs.map((run) => <option key={run.id} value={run.id}>{run.benchmark_id} · {run.id.slice(0, 8)} · {run.status.replaceAll("_", " ")}</option>)}</select></label>
      {selectedRun && <span className="workspace-count" data-i18n-preserve>{selectedRun.benchmark_id} v{selectedRun.benchmark_version} · {selectedRun.id.slice(0, 8)}</span>}
    </WorkspacePanel>
    {!selectedRun ? <WorkspacePanel description="Choose an evaluation run above to generate and manage its artifacts without returning to a separate page." title="Select a report source"><p className="empty">Select a run to generate a portable report or inspect saved artifacts.</p></WorkspacePanel> : <>
      <WorkspacePanel className="workspace-report-generator" description="Select the report shape, then generate the download format needed by the next review or handoff." title="Generate report">
        <div className="workspace-report-controls"><label>Report type<select onChange={(event) => onReportTypeChange(event.target.value as ReportType)} value={reportType}>{reportTypes.map((type) => <option key={type.value} value={type.value}>{type.label}</option>)}</select></label>{comparisonType && <label>Related completed run<select onChange={(event) => onRelatedRunChange(event.target.value)} value={relatedRunId}><option value="">Select run</option>{completedRuns.filter((run) => run.id !== selectedRun.id).map((run) => <option key={run.id} value={run.id}>{run.benchmark_id} · {run.id.slice(0, 8)}</option>)}</select></label>}</div>
        <div className="actions workspace-report-actions"><button onClick={() => onGenerateReport(selectedRun.id, "html")} type="button">Generate HTML</button><button className="secondary" onClick={() => onGenerateReport(selectedRun.id, "markdown")} type="button">Generate Markdown</button><button className="secondary" onClick={() => onGenerateReport(selectedRun.id, "pdf")} type="button">Generate PDF</button><button className="secondary" onClick={() => onGenerateReport(selectedRun.id, "json")} type="button">Generate JSON</button><button className="secondary" onClick={() => onGenerateReport(selectedRun.id, "csv")} type="button">Generate CSV</button><button className="secondary" onClick={() => onGenerateReport(selectedRun.id, "parquet")} type="button">Generate Parquet</button></div>
      </WorkspacePanel>
      <WorkspacePanel className="workspace-report-artifacts" description="Download a generated artifact or create a scoped share link with explicit evidence and download controls." title="Report artifacts">{reportArtifacts}</WorkspacePanel>
    </>}
  </div>;
}

type ReviewsPageProps = {
  attempts: SampleAttempt[];
  onSelectAttempt: (attempt: SampleAttempt) => void;
  onSelectRun: (runId: string) => void;
  reviewDetail: ReactNode;
  runs: EvaluationRun[];
  selectedAttempt: SampleAttempt | null;
  selectedRun: EvaluationRun | null;
};

export function ReviewsPage({ attempts, onSelectAttempt, onSelectRun, reviewDetail, runs, selectedAttempt, selectedRun }: ReviewsPageProps) {
  return <div className="workspace-page reviews-page">
    <PageHeader description="Keep human scoring and judge assessments tied to the precise run snapshot and sample under review." eyebrow="Quality review" status={<>{selectedAttempt ? `${selectedAttempt.sample_id} selected` : "Select an evidence sample"}</>} title="Human review" />
    <WorkspacePanel className="workspace-review-context" description="Choose the evaluation snapshot and sample before opening human or independent judge workflows." title="Review context">
      <label className="workspace-filter-control">Review run<select disabled={runs.length === 0} onChange={(event) => onSelectRun(event.target.value)} value={selectedRun?.id ?? ""}><option value="">Select run</option>{runs.map((run) => <option key={run.id} value={run.id}>{run.benchmark_id} · {run.id.slice(0, 8)} · {run.status.replaceAll("_", " ")}</option>)}</select></label>
      <label className="workspace-filter-control">Review sample<select disabled={!selectedRun || attempts.length === 0} onChange={(event) => { const next = attempts.find((attempt) => attempt.id === event.target.value); if (next) onSelectAttempt(next); }} value={selectedAttempt?.id ?? ""}><option value="">Select sample</option>{attempts.map((attempt) => <option key={attempt.id} value={attempt.id}>{attempt.sample_id} · attempt {attempt.attempt_number} · {attempt.status}</option>)}</select></label>
      <span className="workspace-count">{attempts.length} loaded samples</span>
    </WorkspacePanel>
    {!selectedRun ? <WorkspacePanel description="Choose a run above to load its sample evidence and review history in this workspace." title="Select a run"><p className="empty">Select a run to begin a human or judge review.</p></WorkspacePanel> : <section className="workspace-review-detail" aria-label="Human review workflow">{reviewDetail}</section>}
  </div>;
}

export type UserFormState = { email: string; display_name: string; role: string; max_concurrency: string };

type UsersPageProps = {
  auditEvents: AuditEvent[];
  busy: string | null;
  form: UserFormState;
  onFormChange: (value: UserFormState) => void;
  onSubmit: (event: FormEvent<HTMLFormElement>) => void;
  users: User[];
};

export function UsersPage({ auditEvents, busy, form, onFormChange, onSubmit, users }: UsersPageProps) {
  const { formatDate } = useTranslation();
  const activeUsers = users.filter((user) => user.status === "active").length;

  return <div className="workspace-page users-page">
    <PageHeader description="Provision constrained API users and keep recent administrative activity alongside the current inventory." eyebrow="Administration" status={<>{activeUsers}/{users.length} active users</>} title="Users" />
    <div className="workspace-system-grid">
      <WorkspacePanel description="Create a token-bearing account with the least-privileged role and an optional concurrency ceiling." title="Create user">
        <form className="form" onSubmit={onSubmit}><label>Email<input required type="email" value={form.email} onChange={(event) => onFormChange({ ...form, email: event.target.value })} /></label><label>Display name<input required value={form.display_name} onChange={(event) => onFormChange({ ...form, display_name: event.target.value })} /></label><label>Role<select value={form.role} onChange={(event) => onFormChange({ ...form, role: event.target.value })}><option value="viewer">Viewer</option><option value="reviewer">Reviewer</option><option value="evaluator">Evaluator</option><option value="admin">Admin</option></select></label><label>User concurrency cap<input type="number" min="1" max="1000" value={form.max_concurrency} onChange={(event) => onFormChange({ ...form, max_concurrency: event.target.value })} placeholder="Unlimited" /></label><button disabled={busy === "user"}>Create API-token user</button></form>
      </WorkspacePanel>
      <WorkspacePanel className="workspace-user-inventory" description="Roles, rate ceilings, and status remain visible before issuing additional credentials." title="User inventory" toolbar={<span className="workspace-count">{users.length} configured</span>}>
        {users.length === 0 ? <p className="empty">User administration needs an administrator bearer token when server authentication is enabled.</p> : <div className="table-wrap workspace-dense-table"><table><thead><tr><th>User</th><th>Role</th><th>Cap</th><th>Status</th><th>Created</th></tr></thead><tbody>{users.map((user) => <tr key={user.id}><td data-i18n-preserve>{user.display_name}<br /><small>{user.email}</small></td><td data-i18n-preserve>{user.role}</td><td data-i18n-preserve>{user.max_concurrency ?? "∞"}</td><td data-i18n-preserve>{user.status}</td><td>{formatDate(user.created_at)}</td></tr>)}</tbody></table></div>}
      </WorkspacePanel>
    </div>
    <WorkspacePanel className="workspace-audit-panel" description="The latest recorded administrative changes are retained as an audit trail, separate from user-authored values." title="Recent audit events" toolbar={<span className="workspace-count">{auditEvents.length} events</span>}>
      {auditEvents.length === 0 ? <p className="empty">No events available.</p> : <div className="table-wrap workspace-dense-table"><table><thead><tr><th>Action</th><th>Entity</th><th>When</th></tr></thead><tbody>{auditEvents.slice(0, 12).map((event) => <tr key={event.id}><td data-i18n-preserve>{event.action}</td><td data-i18n-preserve>{event.entity_type}</td><td>{formatDate(event.created_at)}</td></tr>)}</tbody></table></div>}
    </WorkspacePanel>
  </div>;
}

type SettingsPageProps = {
  apiToken: string;
  locale: Locale;
  onApiTokenChange: (value: string) => void;
  onClearToken: () => void;
  onLocaleChange: (locale: Locale) => void;
  onSaveToken: () => void;
  onToggleTheme: () => void;
  systemHealth: SystemHealth | null;
  theme: "dark" | "light";
};

export function SettingsPage({ apiToken, locale, onApiTokenChange, onClearToken, onLocaleChange, onSaveToken, onToggleTheme, systemHealth, theme }: SettingsPageProps) {
  const { formatNumber: display } = useTranslation();
  const status = systemHealth?.status ?? "Unavailable";

  return <div className="workspace-page settings-page">
    <PageHeader description="Inspect deployment-owned configuration, local workspace preferences, and the bearer token used for protected service calls." eyebrow="Administration" status={<>{status}</>} title="System settings" />
    <div className="workspace-system-grid">
      <WorkspacePanel className="workspace-settings-health" description="Runtime configuration is deployment-owned; sensitive values never return to the browser." title="Application and storage" toolbar={<span className="workspace-count">{systemHealth?.database ?? "Unavailable"}</span>}>
        <dl className="workspace-health-list"><dt>Database</dt><dd>{systemHealth?.database ?? "Unavailable"} · {systemHealth?.database_connected ? "connected" : "unavailable"}</dd><dt>Schema version</dt><dd>{systemHealth?.schema_version ?? "--"}</dd><dt>Health</dt><dd>{status}</dd><dt>Queue</dt><dd>{systemHealth ? `${systemHealth.queue.pending} pending · ${systemHealth.queue.active} active` : "--"}</dd><dt>Disk</dt><dd>{systemHealth ? `${display(systemHealth.disk.available_bytes)} free of ${display(systemHealth.disk.total_bytes)}` : "--"}</dd><dt>Theme</dt><dd>{theme}</dd></dl>
      </WorkspacePanel>
      <WorkspacePanel className="workspace-settings-access" description="The token remains only in this browser session. Clear it when you no longer need protected access." title="Access and preferences">
        <label>Workspace language<select value={locale} onChange={(event) => onLocaleChange(event.target.value as Locale)}>{localeIds.map((localeId) => <option key={localeId} value={localeId}>{localeNames[localeId]}</option>)}</select></label><label>Administrator or user bearer token<input type="password" value={apiToken} onChange={(event) => onApiTokenChange(event.target.value)} placeholder="Optional when server auth is enabled" /></label><div className="actions"><button onClick={onSaveToken} type="button">Save token</button><button className="secondary" onClick={onClearToken} type="button">Clear token</button></div>
      </WorkspacePanel>
    </div>
    <WorkspacePanel className="workspace-settings-guidance" description="Choose a storage deployment that matches the worker topology, then use the theme toggle for this workspace only." title="Operating guidance" toolbar={<button className="secondary" onClick={onToggleTheme} type="button">Switch to {theme === "dark" ? "light" : "dark"} mode</button>}>
      <p>SQLite is suitable for local or small-team use. Use PostgreSQL or MongoDB for multi-process, distributed worker deployments; configure global worker ceilings with deployment environment settings.</p>
    </WorkspacePanel>
  </div>;
}

export function openSharedReport(token: string, password: string) {
  return api.openSharedReport(token, password);
}

export function SharedReportPage({ token }: { token: string }) {
  const { locale } = useTranslation();
  const copy = reportCopy[locale];
  const [password, setPassword] = useState("");
  const [reportUrl, setReportUrl] = useState<string | null>(null);
  const [message, setMessage] = useState(copy.initialMessage);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    const root = document.documentElement;
    const previousTheme = root.dataset.theme;
    root.dataset.theme = window.localStorage.getItem("lle-theme") === "light" ? "light" : "dark";
    return () => {
      if (previousTheme) root.dataset.theme = previousTheme;
      else delete root.dataset.theme;
    };
  }, []);

  useEffect(() => () => { if (reportUrl) URL.revokeObjectURL(reportUrl); }, [reportUrl]);

  return <main className="shared-report"><section className="shared-report-panel"><p className="eyebrow">{copy.sharedReport}</p><h1>{copy.readOnlyAccess}</h1><p className="shared-report-intro">{copy.passwordSafety}</p><form className="form" onSubmit={(event) => { event.preventDefault(); setBusy(true); setMessage(""); void openSharedReport(token, password).then((nextUrl) => { setReportUrl((currentUrl) => { if (currentUrl) URL.revokeObjectURL(currentUrl); return nextUrl; }); setMessage(copy.readyMessage); }).catch(() => setMessage(copy.unavailableMessage)).finally(() => { setPassword(""); setBusy(false); }); }}><label>{copy.sharePassword}<input type="password" autoComplete="current-password" value={password} onChange={(event) => setPassword(event.target.value)} /></label><button disabled={busy}>{busy ? copy.opening : copy.openReport}</button></form><p className={reportUrl ? "notice" : "shared-report-status"} aria-live="polite">{message}</p>{reportUrl && <div className="actions shared-report-actions"><a href={reportUrl} target="_blank" rel="noreferrer">{copy.openNewTab}</a><a href={reportUrl} download="evaluation-report">{copy.download}</a></div>}</section></main>;
}
