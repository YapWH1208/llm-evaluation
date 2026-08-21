import { request, systemRequest } from "../../shared/api/client";
import type { AnalyticsMatrix, Comparison, Dashboard, LeaderboardQuery, LeaderboardResponse, ScatterQuery, ScatterResponse, SystemHealth, Task } from "./types";

export const analyticsApi = {
  dashboard: () => request<Dashboard>("/dashboard"),
  compare: (runA: string, runB: string) => request<Comparison>(`/comparisons?run_a=${encodeURIComponent(runA)}&run_b=${encodeURIComponent(runB)}`),
  listTasks: () => request<Task[]>("/tasks"),
  matrix: (baselineRunId?: string) => request<AnalyticsMatrix>(`/analytics/matrix${baselineRunId ? `?baseline_run_id=${encodeURIComponent(baselineRunId)}` : ""}`),
  scatter: (query: ScatterQuery = {}) => {
    const params = new URLSearchParams();
    if (query.x_axis) params.set("x_axis", query.x_axis); if (query.y_axis) params.set("y_axis", query.y_axis);
    query.run_ids?.forEach((value) => params.append("run_ids", value)); if (query.date_from) params.set("date_from", query.date_from); if (query.date_to) params.set("date_to", query.date_to);
    if (query.model_endpoint_id) params.set("model_endpoint_id", query.model_endpoint_id); if (query.dataset) params.set("dataset", query.dataset); query.statuses?.forEach((value) => params.append("status", value));
    if (query.capability) params.set("capability", query.capability); if (query.language) params.set("language", query.language); if (query.evaluation_type) params.set("evaluation_type", query.evaluation_type);
    for (const [key, value] of Object.entries(query)) if (typeof value === "number") params.set(key, String(value));
    return request<ScatterResponse>(`/analytics/scatter${params.size ? `?${params.toString()}` : ""}`);
  },
  leaderboard: (query: LeaderboardQuery = {}) => {
    const params = new URLSearchParams();
    for (const [key, value] of Object.entries(query)) if (Array.isArray(value)) value.forEach((item) => params.append(key === "statuses" ? "status" : key, String(item))); else if (value !== undefined) params.set(key, String(value));
    return request<LeaderboardResponse>(`/leaderboard${params.size ? `?${params.toString()}` : ""}`);
  },
  systemHealth: () => systemRequest<SystemHealth>("/health"),
};

export type { AnalyticsCell, AnalyticsMatrix, Comparison, Dashboard, LeaderboardQuery, LeaderboardResponse, LeaderboardRow, ScatterPoint, ScatterQuery, ScatterResponse, SystemHealth, Task } from "./types";
