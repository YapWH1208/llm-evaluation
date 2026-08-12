import { type MouseEvent, ReactNode, useEffect, useRef, useState } from "react";

import { localeIds, localeNames, navigationCopy, shellCopy, type Locale } from "../i18n/catalog";
import { navigationGroupFor, navigationGroups, navigationItem, View } from "../dashboard/navigation";
import { workspacePath } from "../dashboard/routing";
import { useTranslation } from "../i18n/LocaleProvider";
import { SystemHealth } from "../api";
import { MenuIcon, NavigationIcon } from "./NavigationIcon";
import "../dashboard.css";

type Theme = "dark" | "light";

type AppShellProps = {
  accessRequired?: boolean;
  children: ReactNode;
  completedRunCount: number;
  locale: Locale;
  notice: string | null;
  systemHealth: SystemHealth | null;
  theme: Theme;
  view: View;
  onDismissNotice: () => void;
  onLocaleChange: (locale: Locale) => void;
  onOpenAccess?: () => void;
  onThemeToggle: () => void;
  onViewChange: (view: View) => void;
};

export function AppShell({
  accessRequired = false,
  children,
  completedRunCount,
  locale,
  notice,
  systemHealth,
  theme,
  view,
  onDismissNotice,
  onLocaleChange,
  onOpenAccess = () => undefined,
  onThemeToggle,
  onViewChange,
}: AppShellProps) {
  const [isNavigationOpen, setIsNavigationOpen] = useState(false);
  const dismissNoticeRef = useRef(onDismissNotice);
  const { t } = useTranslation();
  const currentItem = navigationItem(view);
  const currentGroup = navigationGroupFor(view);
  const copy = shellCopy[locale];
  const navigation = navigationCopy[locale];
  const healthLabel = systemHealth?.status === "ok" ? copy.systemHealthy : systemHealth?.status ? copy.systemStatus.replace("{{status}}", systemHealth.status) : copy.systemUnavailable;

  useEffect(() => {
    dismissNoticeRef.current = onDismissNotice;
  }, [onDismissNotice]);

  useEffect(() => {
    if (!notice) return;
    const timeoutId = window.setTimeout(() => dismissNoticeRef.current(), 5_000);
    return () => window.clearTimeout(timeoutId);
  }, [notice]);

  function navigate(event: MouseEvent<HTMLAnchorElement>, nextView: View) {
    if (event.button !== 0 || event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) return;
    event.preventDefault();
    onViewChange(nextView);
    setIsNavigationOpen(false);
  }

  return (
    <div className="app-shell">
      <button
        aria-label={copy.closeNavigation}
        className={isNavigationOpen ? "navigation-scrim is-visible" : "navigation-scrim"}
        onClick={() => setIsNavigationOpen(false)}
        tabIndex={isNavigationOpen ? 0 : -1}
        type="button"
      />
      <aside className={isNavigationOpen ? "sidebar is-open" : "sidebar is-closed"} data-testid="workspace-sidebar" id="workspace-navigation">
        <div className="sidebar-brand">
          <span aria-hidden="true" className="brand-mark">E</span>
          <div>
            <p>{copy.brand}</p>
            <strong>LLM / SLM</strong>
          </div>
        </div>
        <nav aria-label={copy.navigation} className="sidebar-navigation">
          {navigationGroups.map((group) => (
            <section className="navigation-group" key={group.id} aria-label={navigation.groups[group.id]}>
              <p className="navigation-group-label">{navigation.groups[group.id]}</p>
              {group.items.map((item) => (
                <a
                  aria-current={view === item.view ? "page" : undefined}
                  className={view === item.view ? "navigation-item is-active" : "navigation-item"}
                  href={workspacePath(item.view)}
                  key={item.view}
                  onClick={(event) => navigate(event, item.view)}
                  title={navigation.items[item.view].description}
                >
                  <NavigationIcon view={item.view} />
                  <span>{navigation.items[item.view].label}</span>
                </a>
              ))}
            </section>
          ))}
        </nav>
        <div className="sidebar-footer">
          <span className={systemHealth?.status === "ok" ? "health-dot is-healthy" : "health-dot"} />
          <span>{healthLabel}</span>
        </div>
      </aside>

      <div className="app-frame">
        <header className="topbar">
          <div className="topbar-leading">
            <button
              aria-controls="workspace-navigation"
              aria-expanded={isNavigationOpen}
              aria-label={copy.openNavigation}
              className="menu-toggle secondary"
              onClick={() => setIsNavigationOpen(true)}
              type="button"
            >
              <MenuIcon />
            </button>
            <div className="topbar-context">
              <p>{navigation.groups[currentGroup.id]}</p>
              <span>{navigation.items[currentItem.view].description}</span>
            </div>
          </div>
          <div className="topbar-actions">
            <span className="topbar-run-count"><strong>{completedRunCount}</strong> {copy.completed}</span>
            <label className="locale-control">
              <span className="sr-only">{t("locale.label")}</span>
              <select aria-label={t("locale.label")} onChange={(event) => onLocaleChange(event.target.value as Locale)} value={locale}>
                {localeIds.map((localeId) => <option key={localeId} value={localeId}>{localeNames[localeId]}</option>)}
              </select>
            </label>
            <button aria-label={theme === "dark" ? copy.switchToLight : copy.switchToDark} className="secondary theme-toggle" onClick={onThemeToggle} type="button">
              {theme === "dark" ? copy.lightMode : copy.darkMode}
            </button>
          </div>
        </header>

        <main className="workspace-main">
          {accessRequired && <section aria-labelledby="access-required-title" className="access-required" role="alert">
            <div>
              <h2 id="access-required-title">{t("accessRequired.title")}</h2>
              <p>{t("accessRequired.description")}</p>
            </div>
            <button onClick={onOpenAccess} type="button">{t("accessRequired.action")}</button>
          </section>}
          {notice && <button aria-live="polite" className="notice" onClick={onDismissNotice} type="button">{notice}<span>{t("common.dismiss")}</span></button>}
          <div className="workspace-page-content">{children}</div>
        </main>
      </div>
    </div>
  );
}
