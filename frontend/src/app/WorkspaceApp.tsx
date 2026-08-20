import { useCallback, useEffect, useState } from "react";

import { AppShell } from "../components/AppShell";
import { Guide } from "../components/Guide";
import { SettingsPage } from "../components/pages/SystemPages";
import { workspacePath, workspaceRoute, type WorkspaceNavigate, type WorkspaceTabFor } from "../dashboard/routing";
import { analyticsApi, type SystemHealth } from "../features/analytics/api";
import { AnalysisRoute } from "../features/analytics/AnalysisRoute";
import { DashboardRoute } from "../features/analytics/DashboardRoute";
import { LeaderboardRoute } from "../features/analytics/LeaderboardRoute";
import { PromptsRoute } from "../features/benchmarks/PromptsRoute";
import { DatasetsRoute } from "../features/datasets/DatasetsRoute";
import { EndpointsRoute } from "../features/endpoints/EndpointsRoute";
import { RunsRoute } from "../features/runs/RunsRoute";
import { useTranslation } from "../i18n/LocaleProvider";
import { translateStaticTemplate } from "../i18n/operationalCopy";
import { StaticCopy } from "../i18n/StaticCopy";

type Theme = "dark" | "light";

export function WorkspaceApp() {
  const { locale, setLocale } = useTranslation();
  const [route, setRoute] = useState(() => workspaceRoute(window.location.pathname, window.location.search));
  const [theme, setTheme] = useState<Theme>(() => window.localStorage.getItem("lle-theme") === "light" ? "light" : "dark");
  const [notice, setNotice] = useState<string | null>(null);
  const [systemHealth, setSystemHealth] = useState<SystemHealth | null>(null);
  const [completedRunCount, setCompletedRunCount] = useState(0);

  const navigate = useCallback<WorkspaceNavigate>((nextView, options = {}) => {
    const href = workspacePath(nextView, options.tab, { datasetId: options.datasetId, runId: options.runId });
    if (`${window.location.pathname}${window.location.search}` !== href) {
      window.history[options.replace ? "replaceState" : "pushState"](null, "", href);
    }
    setRoute(workspaceRoute(window.location.pathname, window.location.search));
  }, []);

  const showNotice = useCallback((template: string, values?: Record<string, string | number>) => {
    setNotice(translateStaticTemplate(locale, template, values));
  }, [locale]);

  const reportError = useCallback((error: unknown) => {
    setNotice(error instanceof Error ? error.message : translateStaticTemplate(locale, "Unable to reach the evaluation service."));
  }, [locale]);

  useEffect(() => {
    const syncRoute = () => {
      const nextRoute = workspaceRoute(window.location.pathname, window.location.search);
      if (nextRoute.replace) window.history.replaceState(null, "", `${nextRoute.pathname}${nextRoute.search}${window.location.hash}`);
      setRoute(nextRoute);
    };
    syncRoute();
    window.addEventListener("popstate", syncRoute);
    return () => window.removeEventListener("popstate", syncRoute);
  }, []);

  useEffect(() => {
    document.documentElement.dataset.theme = theme;
    window.localStorage.setItem("lle-theme", theme);
  }, [theme]);

  useEffect(() => {
    void analyticsApi.systemHealth().then(setSystemHealth).catch(() => setSystemHealth(null));
    void analyticsApi.dashboard().then((dashboard) => setCompletedRunCount(dashboard.runs.completed)).catch(() => setCompletedRunCount(0));
  }, [route.view]);

  const featureProps = { navigate, reportError, showNotice };
  return <AppShell completedRunCount={completedRunCount} locale={locale} notice={notice} systemHealth={systemHealth} theme={theme} view={route.view} onDismissNotice={() => setNotice(null)} onLocaleChange={setLocale} onThemeToggle={() => setTheme(theme === "dark" ? "light" : "dark")} onViewChange={navigate}>
    <StaticCopy>
      {route.view === "dashboard" && <DashboardRoute {...featureProps} activeTab={route.tab as WorkspaceTabFor<"dashboard">} />}
      {route.view === "guide" && <Guide onOpenView={navigate} />}
      {route.view === "models" && <EndpointsRoute {...featureProps} activeTab={route.tab as WorkspaceTabFor<"models">} />}
      {route.view === "datasets" && <DatasetsRoute {...featureProps} activeTab={route.tab as WorkspaceTabFor<"datasets">} />}
      {route.view === "prompts" && <PromptsRoute {...featureProps} activeTab={route.tab as WorkspaceTabFor<"prompts">} />}
      {route.view === "runs" && <RunsRoute {...featureProps} activeTab={route.tab as WorkspaceTabFor<"runs">} routeSearch={route.search} />}
      {route.view === "analysis" && <AnalysisRoute {...featureProps} activeTab={route.tab as WorkspaceTabFor<"analysis">} />}
      {route.view === "leaderboard" && <LeaderboardRoute {...featureProps} activeTab={route.tab as WorkspaceTabFor<"leaderboard">} />}
      {route.view === "settings" && <SettingsPage activeTab={route.tab as WorkspaceTabFor<"settings">} locale={locale} onLocaleChange={setLocale} onTabChange={(tab) => navigate("settings", { tab })} onToggleTheme={() => setTheme(theme === "dark" ? "light" : "dark")} systemHealth={systemHealth} theme={theme} />}
    </StaticCopy>
  </AppShell>;
}
