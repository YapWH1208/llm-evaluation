import { useEffect, useState } from "react";

import { api, SystemHealth } from "../../api";
import { localeIds, localeNames, reportCopy, type Locale } from "../../i18n/catalog";
import { useTranslation } from "../../i18n/LocaleProvider";
import { PageHeader } from "../workspace/PageHeader";
import { WorkspacePanel } from "../workspace/WorkspacePanel";


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
