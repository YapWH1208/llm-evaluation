export type Benchmark = { id: string; benchmark_id: string; version: string; display_name: string; manifest: Record<string, unknown>; status: string; source: string; created_at: string };

export type PromptPackage = {
  id: string;
  name: string;
  version: string;
  prompt_type: string;
  system_message: string | null;
  user_template: string;
  few_shot_examples: unknown[];
  output_format: Record<string, unknown> | null;
  response_parser: Record<string, unknown> | null;
  scoring_rule: Record<string, unknown> | null;
  change_log: string | null;
  created_at: string;
};
