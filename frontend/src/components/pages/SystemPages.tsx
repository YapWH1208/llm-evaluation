import { useEffect, useState } from "react";

import { api, SystemHealth } from "../../shared/api";
import type { WorkspaceTabFor } from "../../dashboard/routing";
import { localeIds, localeNames, reportCopy, workspacePageTabCopy, type Locale } from "../../i18n/catalog";
import { useTranslation } from "../../i18n/LocaleProvider";
import { PageHeader } from "../workspace/PageHeader";
import { WorkspacePanel } from "../workspace/WorkspacePanel";
import { WorkspaceTabs, workspaceTabId, workspaceTabPanelId } from "../workspace/WorkspaceTabs";


type SettingsPageProps = {
  activeTab: WorkspaceTabFor<"settings">;
  locale: Locale;
  onLocaleChange: (locale: Locale) => void;
  onTabChange: (tab: WorkspaceTabFor<"settings">) => void;
  onToggleTheme: () => void;
  systemHealth: SystemHealth | null;
  theme: "dark" | "light";
};

export function SettingsPage({ activeTab, locale, onLocaleChange, onTabChange, onToggleTheme, systemHealth, theme }: SettingsPageProps) {
  const { formatNumber: display, locale: displayLocale } = useTranslation();
  const copy = workspacePageTabCopy[displayLocale].settings;
  const status = systemHealth?.status ?? "Unavailable";

  return <div className="workspace-page settings-page">
    <PageHeader description="Inspect deployment-owned configuration and local workspace preferences." eyebrow="Administration" status={<>{status}</>} title="System settings" />
    <WorkspaceTabs ariaLabel="Settings sections" idPrefix="settings" onChange={onTabChange} tabs={[{ id: "health", label: copy.health }, { id: "preferences", label: copy.preferences }]} value={activeTab} />
    <div aria-labelledby={workspaceTabId("settings", activeTab)} id={workspaceTabPanelId("settings", activeTab)} role="tabpanel" tabIndex={0}>
      {activeTab === "health" && <WorkspacePanel className="workspace-settings-health" description="Runtime configuration is deployment-owned; sensitive values never return to the browser." title="Application and storage" toolbar={<span className="workspace-count">{systemHealth?.database ?? "Unavailable"}</span>}>
        <dl className="workspace-health-list"><dt>Database</dt><dd>{systemHealth?.database ?? "Unavailable"} · {systemHealth?.database_connected ? "connected" : "unavailable"}</dd><dt>Schema version</dt><dd>{systemHealth?.schema_version ?? "--"}</dd><dt>Health</dt><dd>{status}</dd><dt>Queue</dt><dd>{systemHealth ? `${systemHealth.queue.pending} pending · ${systemHealth.queue.active} active` : "--"}</dd><dt>Disk</dt><dd>{systemHealth ? `${display(systemHealth.disk.available_bytes)} free of ${display(systemHealth.disk.total_bytes)}` : "--"}</dd></dl>
      </WorkspacePanel>}
      {activeTab === "preferences" && <div className="workspace-settings-preferences">
        <WorkspacePanel className="workspace-settings-access" description="Language and theme apply only to this browser workspace." title="Workspace preferences">
          <label>Workspace language<select value={locale} onChange={(event) => onLocaleChange(event.target.value as Locale)}>{localeIds.map((localeId) => <option key={localeId} value={localeId}>{localeNames[localeId]}</option>)}</select></label><div className="actions"><button className="secondary" onClick={onToggleTheme} type="button">Switch to {theme === "dark" ? "light" : "dark"} mode</button></div>
        </WorkspacePanel>
        <WorkspacePanel className="workspace-settings-guidance" description="Choose a storage deployment that matches the worker topology." title="Operating guidance">
          <p>SQLite is suitable for local or small-team use. Use MongoDB for multi-process, distributed worker deployments; configure global worker ceilings with deployment environment settings.</p>
        </WorkspacePanel>
      </div>}
    </div>
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
