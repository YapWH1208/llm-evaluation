import { ReactNode, useState } from "react";

import { Locale, navigationGroupFor, navigationGroups, navigationItem, View } from "../dashboard/navigation";
import { SystemHealth } from "../api";
import "../dashboard.css";

type Theme = "dark" | "light";

type AppShellProps = {
  children: ReactNode;
  completedRunCount: number;
  locale: Locale;
  notice: string | null;
  systemHealth: SystemHealth | null;
  theme: Theme;
  view: View;
  onDismissNotice: () => void;
  onLocaleChange: (locale: Locale) => void;
  onThemeToggle: () => void;
  onViewChange: (view: View) => void;
};

export function AppShell({
  children,
  completedRunCount,
  locale,
  notice,
  systemHealth,
  theme,
  view,
  onDismissNotice,
  onLocaleChange,
  onThemeToggle,
  onViewChange,
}: AppShellProps) {
  const [isNavigationOpen, setIsNavigationOpen] = useState(false);
  const currentItem = navigationItem(view);
  const currentGroup = navigationGroupFor(view);
  const healthLabel = systemHealth?.status === "healthy" ? "System healthy" : systemHealth?.status ? `System ${systemHealth.status}` : "System status unavailable";

  function navigate(nextView: View) {
    onViewChange(nextView);
    setIsNavigationOpen(false);
  }

  return (
    <div className="app-shell">
      <button
        aria-label="Close navigation"
        className={isNavigationOpen ? "navigation-scrim is-visible" : "navigation-scrim"}
        onClick={() => setIsNavigationOpen(false)}
        tabIndex={isNavigationOpen ? 0 : -1}
        type="button"
      />
      <aside className={isNavigationOpen ? "sidebar is-open" : "sidebar"} data-testid="workspace-sidebar" id="workspace-navigation">
        <div className="sidebar-brand">
          <span aria-hidden="true" className="brand-mark">LL</span>
          <div>
            <p>Evaluation workspace</p>
            <strong>LLM / SLM</strong>
          </div>
        </div>
        <nav aria-label="Workspace navigation" className="sidebar-navigation">
          {navigationGroups.map((group) => (
            <section className="navigation-group" key={group.id} aria-label={group.label[locale]}>
              <p className="navigation-group-label">{group.label[locale]}</p>
              {group.items.map((item) => (
                <button
                  aria-current={view === item.view ? "page" : undefined}
                  className={view === item.view ? "navigation-item is-active" : "navigation-item"}
                  key={item.view}
                  onClick={() => navigate(item.view)}
                  title={item.description[locale]}
                  type="button"
                >
                  <span aria-hidden="true" className="navigation-glyph">{item.glyph}</span>
                  <span>{item.label[locale]}</span>
                </button>
              ))}
            </section>
          ))}
        </nav>
        <div className="sidebar-footer">
          <span className={systemHealth?.status === "healthy" ? "health-dot is-healthy" : "health-dot"} />
          <span>{healthLabel}</span>
        </div>
      </aside>

      <div className="app-frame">
        <header className="topbar">
          <div className="topbar-leading">
            <button
              aria-controls="workspace-navigation"
              aria-expanded={isNavigationOpen}
              aria-label="Open navigation"
              className="menu-toggle secondary"
              onClick={() => setIsNavigationOpen(true)}
              type="button"
            >
              <span aria-hidden="true">☰</span>
            </button>
            <div className="topbar-context">
              <p>{currentGroup.label[locale]}</p>
              <span>{currentItem.description[locale]}</span>
            </div>
          </div>
          <div className="topbar-actions">
            <span className="topbar-run-count"><strong>{completedRunCount}</strong> completed</span>
            <label className="locale-control">
              <span className="sr-only">Workspace language</span>
              <select aria-label="Workspace language" onChange={(event) => onLocaleChange(event.target.value as Locale)} value={locale}>
                <option value="en">EN</option>
                <option value="zh-CN">简体中文</option>
              </select>
            </label>
            <button aria-label={`Switch to ${theme === "dark" ? "light" : "dark"} mode`} className="secondary theme-toggle" onClick={onThemeToggle} type="button">
              {theme === "dark" ? "Light mode" : "Dark mode"}
            </button>
          </div>
        </header>

        <main className="workspace-main">
          <section className="workspace-page-heading" aria-labelledby="workspace-page-title">
            <div>
              <p className="eyebrow">Evaluation control center</p>
              <h1 id="workspace-page-title">{currentItem.label[locale]}</h1>
              <p>{currentItem.description[locale]}</p>
            </div>
            <div className="page-health" aria-label={healthLabel}>
              <span className={systemHealth?.status === "healthy" ? "health-dot is-healthy" : "health-dot"} />
              <span>{healthLabel}</span>
            </div>
          </section>
          {notice && <button className="notice" onClick={onDismissNotice} type="button">{notice}<span>Dismiss</span></button>}
          <div className="workspace-page-content">{children}</div>
        </main>
      </div>
    </div>
  );
}
