import { useEffect, useState } from "react";

import { OverviewDashboard } from "../../components/OverviewDashboard";
import type { FeatureRouteProps } from "../../app/types";
import { endpointsApi, type Endpoint } from "../endpoints/api";
import { runsApi, type EvaluationRun } from "../runs/api";
import { analyticsApi, type AnalyticsMatrix, type Dashboard, type SystemHealth, type Task } from "./api";

export function DashboardRoute({ activeTab, navigate, reportError }: FeatureRouteProps<"dashboard">) {
  const [analytics, setAnalytics] = useState<AnalyticsMatrix | null>(null);
  const [dashboard, setDashboard] = useState<Dashboard | null>(null);
  const [endpoints, setEndpoints] = useState<Endpoint[]>([]);
  const [runs, setRuns] = useState<EvaluationRun[]>([]);
  const [systemHealth, setSystemHealth] = useState<SystemHealth | null>(null);
  const [tasks, setTasks] = useState<Task[]>([]);

  useEffect(() => {
    void Promise.all([
      analyticsApi.matrix(),
      analyticsApi.dashboard(),
      endpointsApi.list(),
      runsApi.list(),
      analyticsApi.systemHealth().catch(() => null),
      analyticsApi.listTasks(),
    ]).then(([nextAnalytics, nextDashboard, nextEndpoints, nextRuns, nextHealth, nextTasks]) => {
      setAnalytics(nextAnalytics);
      setDashboard(nextDashboard);
      setEndpoints(nextEndpoints);
      setRuns(nextRuns);
      setSystemHealth(nextHealth);
      setTasks(nextTasks);
    }).catch(reportError);
  }, [reportError]);

  return <OverviewDashboard activeTab={activeTab} analytics={analytics} dashboard={dashboard} endpoints={endpoints} runs={runs} systemHealth={systemHealth} tasks={tasks} onInspectRun={(runId) => navigate("runs", { runId, tab: "run-details" })} onOpenSetup={() => navigate("runs", { tab: "quick-start" })} onOpenView={navigate} onTabChange={(tab) => navigate("dashboard", { tab })} />;
}
