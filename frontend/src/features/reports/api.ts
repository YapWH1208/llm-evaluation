import { downloadObjectUrl, openSharedReportObjectUrl, request, requestObjectUrl } from "../../shared/api/client";
import type { Report, ReportFormat, ReportType } from "./types";

export const reportsApi = {
  create: (runId: string, format: ReportFormat, reportType: ReportType = "single_model", relatedRunIds: string[] = []) => request<Report>("/reports", { method: "POST", body: JSON.stringify({ run_id: runId, format, report_type: reportType, related_run_ids: relatedRunIds }) }),
  remove: (reportId: string) => request<void>(`/reports/${reportId}`, { method: "DELETE" }),
  list: (runId: string) => request<Report[]>(`/reports/run/${runId}`),
  download: (reportId: string) => downloadObjectUrl(`/reports/${reportId}/download`),
  openShared: (token: string, password = "") => openSharedReportObjectUrl(token, password),
  assetPreview: (assetId: string) => requestObjectUrl(`/assets/${assetId}/download`),
};

export type { Report, ReportFormat, ReportType } from "./types";
