export type Report = { id: string; run_id: string; report_type: string; format: string; artifact_path: string; generator_version: string; generated_at: string };
export type ReportFormat = "html" | "json" | "csv" | "markdown";
export type ReportType = "single_model" | "multi_model_comparison" | "regression" | "prompt_comparison" | "benchmark" | "reliability" | "cost" | "human_review";
