import { request } from "../../shared/api/client";
import type { Benchmark, PromptPackage } from "./types";

export const benchmarksApi = {
  list: () => request<Benchmark[]>("/benchmarks"),
  listPrompts: () => request<PromptPackage[]>("/prompt-packages"),
  createPrompt: (body: Record<string, unknown>) => request<PromptPackage>("/prompt-packages", { method: "POST", body: JSON.stringify(body) }),
  updatePrompt: (promptPackageId: string, body: Record<string, unknown>) => request<PromptPackage>(`/prompt-packages/${promptPackageId}`, { method: "PUT", body: JSON.stringify(body) }),
  removePrompt: (promptPackageId: string) => request<PromptPackage>(`/prompt-packages/${promptPackageId}`, { method: "DELETE" }),
};

export type { Benchmark, PromptPackage } from "./types";
