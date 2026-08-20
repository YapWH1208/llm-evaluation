import { request } from "../../shared/api/client";
import type { Capability, ConnectionTest, Endpoint } from "./types";

export const endpointsApi = {
  list: () => request<Endpoint[]>("/model-endpoints"),
  create: (body: Record<string, unknown>) => request<Endpoint>("/model-endpoints", { method: "POST", body: JSON.stringify(body) }),
  update: (endpointId: string, body: Record<string, unknown>) => request<Endpoint>(`/model-endpoints/${endpointId}`, { method: "PATCH", body: JSON.stringify(body) }),
  test: (endpointId: string) => request<ConnectionTest>(`/model-endpoints/${endpointId}/connection-test`, { method: "POST" }),
  listCapabilities: (endpointId: string) => request<Capability[]>(`/model-endpoints/${endpointId}/capabilities`),
  detectCapabilities: (endpointId: string) => request<Capability[]>(`/model-endpoints/${endpointId}/capabilities/detect`, { method: "POST" }),
  declareCapability: (endpointId: string, capabilityKey: string, userDeclaredStatus: "supported" | "unsupported" | "unknown") => request<Capability>(`/model-endpoints/${endpointId}/capabilities`, { method: "PUT", body: JSON.stringify({ capability_key: capabilityKey, user_declared_status: userDeclaredStatus }) }),
};

export type { Capability, ConnectionTest, Endpoint } from "./types";
