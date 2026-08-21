import { ApiError } from "./errors";

const apiBase = import.meta.env.VITE_API_BASE_URL ?? "http://127.0.0.1:8000/api/v1";
const publicApiBase = import.meta.env.VITE_PUBLIC_API_BASE_URL ?? apiBase.replace(/\/api\/v1$/, "");

export async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${apiBase}${path}`, {
    headers: { "Content-Type": "application/json", ...init?.headers },
    ...init,
  });
  if (!response.ok) {
    const payload = await response.json().catch(() => null);
    const detail = typeof payload?.detail === "string" ? payload.detail : "Request failed.";
    throw new ApiError(detail, response.status);
  }
  if (response.status === 204) return undefined as T;
  return response.json() as Promise<T>;
}

export async function requestObjectUrl(path: string): Promise<string> {
  const response = await fetch(`${apiBase}${path}`);
  if (!response.ok) throw new ApiError("Media preview is unavailable.", response.status);
  return URL.createObjectURL(await response.blob());
}

export async function downloadObjectUrl(path: string): Promise<string> {
  const response = await fetch(apiBase + path);
  if (!response.ok) throw new ApiError("Download is unavailable.", response.status);
  return URL.createObjectURL(await response.blob());
}

export async function openSharedReportObjectUrl(token: string, password = ""): Promise<string> {
  const response = await fetch(`${publicApiBase}/shared-reports/${encodeURIComponent(token)}`, {
    headers: password ? { "X-Report-Password": password } : undefined,
  });
  if (!response.ok) throw new ApiError("The shared report could not be opened.", response.status);
  return URL.createObjectURL(await response.blob());
}

export function subscribeToEvents(path: string, eventName: string, onEvent: () => void): () => void {
  const controller = new AbortController();
  void fetch(apiBase + path, { headers: { Accept: "text/event-stream" }, signal: controller.signal }).then(async (response) => {
    if (!response.ok || !response.body) throw new ApiError("Event stream is unavailable.", response.status);
    const reader = response.body.getReader();
    const decoder = new TextDecoder();
    let buffer = "";
    while (!controller.signal.aborted) {
      const next = await reader.read();
      if (next.done) break;
      buffer += decoder.decode(next.value, { stream: true });
      const messages = buffer.split("\n\n");
      buffer = messages.pop() ?? "";
      for (const message of messages) if (message.split("\n").some((line) => line === "event: " + eventName)) onEvent();
    }
  }).catch(() => undefined);
  return () => controller.abort();
}

export async function systemRequest<T>(path: string): Promise<T> {
  const response = await fetch(`${apiBase.replace(/\/api\/v1$/, "")}${path}`);
  if (!response.ok) throw new ApiError("System request failed.", response.status);
  return response.json() as Promise<T>;
}
