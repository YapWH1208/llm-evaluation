export type Endpoint = {
  id: string;
  display_name: string;
  base_url: string;
  model_name: string;
  protocol_profile: "openai_chat_completions" | "openai_responses" | "anthropic_messages" | "gemini_generate_content" | "azure_openai_chat_completions" | "ollama_chat" | "custom_http_json";
  api_key_mask: string;
  custom_headers: Record<string, string>;
  default_request_body: Record<string, unknown>;
  reasoning_effort: "low" | "medium" | "high" | null;
  context_length: number | null;
  max_output_tokens: number | null;
  timeout_seconds: number;
  status: "unverified" | "available" | "unavailable";
  max_concurrency: number;
  requests_per_second: number | null;
  requests_per_minute: number | null;
  tokens_per_minute: number | null;
  input_tokens_per_minute: number | null;
  output_tokens_per_minute: number | null;
  input_cost_per_million: number | null;
  output_cost_per_million: number | null;
  currency: string;
  tags: string[];
  notes: string | null;
  last_connection_error: string | null;
  api_key_max_concurrency: number | null;
};

export type ConnectionTest = {
  success: boolean;
  status: Endpoint["status"];
  message: string;
  provider_status_code: number | null;
  tested_at: string;
  request: { method: "POST"; url: string; body: Record<string, unknown> };
};

export type Capability = {
  id: string;
  capability_key: string;
  user_declared_status: string;
  auto_detection_status: string;
  effective_status: string;
};

export type SandboxToolCall = {
  name: string;
  arguments: Record<string, unknown>;
};

export type SandboxResult = {
  success: boolean;
  mode: "text" | "tool";
  protocol_profile: Endpoint["protocol_profile"];
  request: Record<string, unknown>;
  final_text: string | null;
  tool_calls: SandboxToolCall[];
  latency_ms: number | null;
  usage: { input_tokens: number | null; output_tokens: number | null };
  provider_status_code: number | null;
  error_type: string | null;
  error_message: string | null;
};
