import { FormEvent, useState } from "react";

import { PromptPackage } from "../../api";
import { useTranslation } from "../../i18n/LocaleProvider";
import { PageHeader } from "../workspace/PageHeader";
import { WorkspacePanel } from "../workspace/WorkspacePanel";

type PromptPackageType = "official" | "platform_default" | "user_custom" | "benchmark_variant" | "language_specific";

export type PromptPackageCreatePayload = {
  name: string;
  version: string;
  prompt_type: PromptPackageType;
  system_message: string | null;
  user_template: string;
  few_shot_examples: unknown[];
  output_format: Record<string, unknown> | null;
  response_parser: Record<string, unknown> | null;
  scoring_rule: Record<string, unknown> | null;
  change_log: string | null;
};

type PromptPackageForm = {
  name: string;
  version: string;
  prompt_type: PromptPackageType;
  system_message: string;
  user_template: string;
  few_shot_examples: string;
  output_format: string;
  response_parser: string;
  scoring_rule: string;
  change_log: string;
};

const initialForm: PromptPackageForm = {
  name: "",
  version: "1",
  prompt_type: "user_custom",
  system_message: "",
  user_template: "",
  few_shot_examples: "[]",
  output_format: "",
  response_parser: "",
  scoring_rule: "",
  change_log: "",
};

class PromptPackageFormError extends Error {
  constructor(readonly messageKey: "promptPackage.invalidJson" | "promptPackage.examplesMustArray" | "promptPackage.configMustObject") {
    super(messageKey);
  }
}

function optionalObject(value: string): Record<string, unknown> | null {
  if (!value.trim()) return null;
  try {
    const parsed: unknown = JSON.parse(value);
    if (!parsed || Array.isArray(parsed) || typeof parsed !== "object") throw new PromptPackageFormError("promptPackage.configMustObject");
    return parsed as Record<string, unknown>;
  } catch (error) {
    if (error instanceof PromptPackageFormError) throw error;
    throw new PromptPackageFormError("promptPackage.invalidJson");
  }
}

function examples(value: string): unknown[] {
  try {
    const parsed: unknown = JSON.parse(value || "[]");
    if (!Array.isArray(parsed)) throw new PromptPackageFormError("promptPackage.examplesMustArray");
    return parsed;
  } catch (error) {
    if (error instanceof PromptPackageFormError) throw error;
    throw new PromptPackageFormError("promptPackage.invalidJson");
  }
}

export function promptPackagePayload(form: PromptPackageForm): PromptPackageCreatePayload {
  return {
    name: form.name.trim(),
    version: form.version.trim(),
    prompt_type: form.prompt_type,
    system_message: form.system_message.trim() || null,
    user_template: form.user_template,
    few_shot_examples: examples(form.few_shot_examples),
    output_format: optionalObject(form.output_format),
    response_parser: optionalObject(form.response_parser),
    scoring_rule: optionalObject(form.scoring_rule),
    change_log: form.change_log.trim() || null,
  };
}

type PromptPackagesPageProps = {
  busy: boolean;
  prompts: PromptPackage[];
  onCreate: (payload: PromptPackageCreatePayload) => Promise<void>;
};

export function PromptPackagesPage({ busy, prompts, onCreate }: PromptPackagesPageProps) {
  const { t } = useTranslation();
  const [form, setForm] = useState(initialForm);
  const [error, setError] = useState<string | null>(null);

  function updateForm(next: Partial<PromptPackageForm>) {
    setError(null);
    setForm((current) => ({ ...current, ...next }));
  }

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    try {
      await onCreate(promptPackagePayload(form));
      setForm(initialForm);
    } catch (caught) {
      setError(caught instanceof PromptPackageFormError ? t(caught.messageKey) : caught instanceof Error ? caught.message : t("promptPackage.invalidJson"));
    }
  }

  return (
    <div className="workspace-page prompt-packages-page">
      <PageHeader description={t("promptPackage.description")} status={<><strong>{prompts.length}</strong> {t("promptPackage.title").toLocaleLowerCase()}</>} title={t("promptPackage.title")} />
      <div className="workspace-settings-preferences">
        <WorkspacePanel title={t("promptPackage.inventory")} toolbar={<span className="workspace-count">{prompts.length}</span>}>
          {prompts.length === 0 ? <p className="empty">{t("promptPackage.empty")}</p> : <div className="workspace-model-selector-list">{prompts.map((prompt) => <article className="workspace-model-selector" key={prompt.id}><strong data-i18n-preserve>{prompt.name}</strong><small data-i18n-preserve>v{prompt.version} · {prompt.prompt_type}</small></article>)}</div>}
        </WorkspacePanel>
        <WorkspacePanel title={t("promptPackage.create")}>
          <form className="form" onSubmit={(event) => void submit(event)}>
            <div className="workspace-field-grid workspace-field-grid--two">
              <label>{t("promptPackage.name")}<input onChange={(event) => updateForm({ name: event.target.value })} required value={form.name} /></label>
              <label>{t("promptPackage.version")}<input onChange={(event) => updateForm({ version: event.target.value })} required value={form.version} /></label>
            </div>
            <label>{t("promptPackage.type")}<select onChange={(event) => updateForm({ prompt_type: event.target.value as PromptPackageType })} value={form.prompt_type}><option value="official">official</option><option value="platform_default">platform_default</option><option value="user_custom">user_custom</option><option value="benchmark_variant">benchmark_variant</option><option value="language_specific">language_specific</option></select></label>
            <label>{t("promptPackage.systemMessage")}<textarea onChange={(event) => updateForm({ system_message: event.target.value })} value={form.system_message} /></label>
            <label>{t("promptPackage.userTemplate")}<textarea onChange={(event) => updateForm({ user_template: event.target.value })} required value={form.user_template} /></label>
            <label>{t("promptPackage.fewShotExamples")}<textarea onChange={(event) => updateForm({ few_shot_examples: event.target.value })} spellCheck={false} value={form.few_shot_examples} /></label>
            <div className="workspace-field-grid workspace-field-grid--three">
              <label>{t("promptPackage.outputFormat")}<textarea onChange={(event) => updateForm({ output_format: event.target.value })} spellCheck={false} value={form.output_format} /></label>
              <label>{t("promptPackage.responseParser")}<textarea onChange={(event) => updateForm({ response_parser: event.target.value })} spellCheck={false} value={form.response_parser} /></label>
              <label>{t("promptPackage.scoringRule")}<textarea onChange={(event) => updateForm({ scoring_rule: event.target.value })} spellCheck={false} value={form.scoring_rule} /></label>
            </div>
            <label>{t("promptPackage.changeLog")}<textarea onChange={(event) => updateForm({ change_log: event.target.value })} value={form.change_log} /></label>
            {error && <p className="error" role="alert" data-i18n-preserve>{error}</p>}
            <div className="actions"><button disabled={busy}>{busy ? t("promptPackage.saving") : t("promptPackage.save")}</button></div>
          </form>
        </WorkspacePanel>
      </div>
    </div>
  );
}
