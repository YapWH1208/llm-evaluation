import { request } from "../../shared/api/client";
import type { Dataset } from "../../shared/api/types";

export const datasetsApi = {
  list: () => request<Dataset[]>("/datasets"),
  create: (body: Record<string, unknown>) => request<Dataset>("/datasets", { method: "POST", body: JSON.stringify(body) }),
  preview: (datasetId: string, limit = 5) => request<{ fields: string[]; rows: Array<Record<string, string>> }>(`/datasets/${datasetId}/preview?limit=${limit}`),
  update: (datasetId: string, body: Record<string, unknown>) => request<Dataset>(`/datasets/${datasetId}`, { method: "PUT", body: JSON.stringify(body) }),
  remove: (datasetId: string) => request<Dataset>(`/datasets/${datasetId}`, { method: "DELETE" }),
  acceptLicense: (datasetId: string) => request<Dataset>(`/datasets/${datasetId}/accept-license`, { method: "POST" }),
  download: (datasetId: string) => request<Dataset>(`/datasets/${datasetId}/download`, { method: "POST" }),
  retry: (datasetId: string) => request<Dataset>(`/datasets/${datasetId}/retry`, { method: "POST" }),
  pause: (datasetId: string) => request<Dataset>(`/datasets/${datasetId}/pause`, { method: "POST" }),
  validate: (datasetId: string) => request<Dataset>(`/datasets/${datasetId}/validate`, { method: "POST" }),
  clearCache: (datasetId: string) => request<Dataset>(`/datasets/${datasetId}/cache`, { method: "DELETE" }),
  diskUsage: () => request<{ root: string; cache_bytes: number; available_bytes: number; total_bytes: number }>("/datasets/disk-usage"),
  upload: (datasetId: string, body: { filename: string; base64_data: string }) => request<Dataset>(`/datasets/${datasetId}/upload`, { method: "POST", body: JSON.stringify(body) }),
};

export type { Dataset } from "../../shared/api/types";
