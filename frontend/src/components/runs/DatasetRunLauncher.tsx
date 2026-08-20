import type { Dispatch, SetStateAction } from "react";

import type { Dataset, Endpoint, PromptPackage } from "../../shared/api";
import { datasetMetricIds, type DatasetMetricId } from "../../evaluations/scoringMetrics";
import type { TranslationKey } from "../../i18n/catalog";
import { useTranslation } from "../../i18n/LocaleProvider";

export type DatasetRunForm = {
  dataset_version_id: string;
  prompt_package_id: string;
  input_field: string;
  reference_field: string;
  sample_limit: string;
  model_endpoint_id: string;
  metric: DatasetMetricId;
  judge_endpoint_id: string;
  judge_system_message: string;
};

export const datasetMetricLabelKeys = {
  default: "datasetRun.metricDefault",
  exact_match: "datasetRun.metricExactMatch",
  normalized_exact_match: "datasetRun.metricNormalizedExactMatch",
  token_f1: "datasetRun.metricTokenF1",
  bleu: "datasetRun.metricBleu",
  rouge_l: "datasetRun.metricRougeL",
  llm_judge: "datasetRun.metricLlmJudge",
} as const satisfies Record<DatasetMetricId, TranslationKey>;

type DatasetRunLauncherProps = {
  busy: string | null;
  datasets: Dataset[];
  endpoints: Endpoint[];
  fields: string[];
  fieldsCollide: boolean;
  fieldsError: string | null;
  fieldsLoading: boolean;
  form: DatasetRunForm;
  handoffDatasetId: string | null;
  onFormChange: Dispatch<SetStateAction<DatasetRunForm>>;
  onPreflightReset: () => void;
  onQueue: () => void;
  onRetrySchema: () => void;
  prompts: PromptPackage[];
};

export function DatasetRunLauncher({
  busy,
  datasets,
  endpoints,
  fields,
  fieldsCollide,
  fieldsError,
  fieldsLoading,
  form,
  handoffDatasetId,
  onFormChange,
  onPreflightReset,
  onQueue,
  onRetrySchema,
  prompts,
}: DatasetRunLauncherProps) {
  const { t } = useTranslation();
  const isLlmJudge = form.metric === "llm_judge";
  const availableJudgeEndpoints = endpoints.filter(
    (endpoint) => endpoint.status === "available" && endpoint.id !== form.model_endpoint_id,
  );
  const judgeConfigurationMissing = isLlmJudge && (
    !form.judge_endpoint_id
    || form.judge_endpoint_id === form.model_endpoint_id
    || !availableJudgeEndpoints.some((endpoint) => endpoint.id === form.judge_endpoint_id)
    || !form.judge_system_message.trim()
  );
  const blocked = fieldsLoading
    || Boolean(fieldsError)
    || fieldsCollide
    || !form.model_endpoint_id
    || !form.dataset_version_id
    || (!form.input_field && !form.prompt_package_id)
    || !form.reference_field
    || judgeConfigurationMissing;

  function updateForm(next: Partial<DatasetRunForm>) {
    onPreflightReset();
    onFormChange((current) => ({ ...current, ...next }));
  }

  function changeMetric(metric: DatasetMetricId) {
    onPreflightReset();
    onFormChange((current) => ({
      ...current,
      metric,
      judge_endpoint_id: metric === "llm_judge" ? current.judge_endpoint_id : "",
      judge_system_message: metric === "llm_judge" ? current.judge_system_message : "",
    }));
  }

  return <form className="form workspace-run-launcher" onSubmit={(event) => { event.preventDefault(); onQueue(); }}>
    <label>{t("datasetRun.dataset")}<select required value={form.dataset_version_id} onChange={(event) => updateForm({ dataset_version_id: event.target.value, input_field: "", reference_field: "" })}><option value="">—</option>{datasets.filter((dataset) => dataset.status === "ready").map((dataset) => <option data-i18n-preserve key={dataset.id} value={dataset.id}>{dataset.dataset_id} v{dataset.version}</option>)}</select></label>
    {handoffDatasetId === form.dataset_version_id && <p className="workspace-launch-note">{t("runLauncher.datasetHandoff")}</p>}
    {datasets.some((dataset) => dataset.status !== "ready") && <p className="muted">{t("datasetRun.nonReadyHint")}</p>}
    {fieldsLoading && <p className="muted">{t("runLauncher.schemaLoading")}</p>}
    {fieldsError && <p className="error" role="alert" data-i18n-preserve>{fieldsError}</p>}
    {fieldsCollide && <p className="error" role="alert">{t("runLauncher.schemaDistinctFields")}</p>}
    {fieldsError && <div className="actions"><button type="button" onClick={onRetrySchema}>{t("runLauncher.schemaRetry")}</button></div>}
    <div className="workspace-field-grid workspace-field-grid--two">
      <label>{t("datasetRun.inputField")}<select disabled={fieldsLoading || fields.length === 0 || Boolean(form.prompt_package_id)} required value={form.input_field} onChange={(event) => updateForm({ input_field: event.target.value })}>{fields.length === 0 && <option value="">—</option>}{fields.map((field) => <option data-i18n-preserve key={field} value={field}>{field}</option>)}</select></label>
      <label>{t("datasetRun.referenceField")}<select disabled={fieldsLoading || fields.length === 0} required value={form.reference_field} onChange={(event) => updateForm({ reference_field: event.target.value })}>{fields.length === 0 && <option value="">—</option>}{fields.map((field) => <option data-i18n-preserve key={field} value={field}>{field}</option>)}</select></label>
    </div>
    <label>{t("datasetRun.promptPackage")}<select value={form.prompt_package_id} onChange={(event) => updateForm({ prompt_package_id: event.target.value })}><option value="">—</option>{prompts.map((prompt) => <option data-i18n-preserve key={prompt.id} value={prompt.id}>{prompt.name} v{prompt.version}</option>)}</select></label>
    <label>{t("datasetRun.metric")}<select value={form.metric} onChange={(event) => changeMetric(event.target.value as DatasetMetricId)}>{datasetMetricIds.map((metric) => <option key={metric} value={metric}>{t(datasetMetricLabelKeys[metric])}</option>)}</select></label>
    <p className="muted">{form.prompt_package_id && form.metric !== "default" ? t("datasetRun.metricOverrideHint") : t("datasetRun.metricDefaultHint")}</p>
    {isLlmJudge && <div className="workspace-run-judge-settings">
      <label>{t("datasetRun.judgeEndpoint")}<select required value={form.judge_endpoint_id} onChange={(event) => updateForm({ judge_endpoint_id: event.target.value })}><option value="">—</option>{availableJudgeEndpoints.map((endpoint) => <option data-i18n-preserve key={endpoint.id} value={endpoint.id}>{endpoint.display_name}</option>)}</select></label>
      <p className="muted">{t("datasetRun.judgeEndpointHint")}</p>
      <label>{t("datasetRun.judgeSystemMessage")}<textarea required value={form.judge_system_message} onChange={(event) => updateForm({ judge_system_message: event.target.value })} /></label>
      <p className="muted">{t("datasetRun.judgeSystemMessageHint")}</p>
      {judgeConfigurationMissing && <p className="error" role="alert">{t("datasetRun.judgeConfigurationRequired")}</p>}
    </div>}
    <label>{t("datasetRun.sampleLimit")}<input required type="number" min={1} max={10000} value={form.sample_limit} onChange={(event) => updateForm({ sample_limit: event.target.value })} /></label>
    <button className="primary" disabled={busy === "dataset-run" || blocked}>{t("datasetRun.queue")}</button>
  </form>;
}
