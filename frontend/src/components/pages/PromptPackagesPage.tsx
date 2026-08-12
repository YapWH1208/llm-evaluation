import { type FormEvent, useEffect, useState } from "react";

import { PromptPackage } from "../../api";
import type { WorkspaceTabFor } from "../../dashboard/routing";
import { useTranslation } from "../../i18n/LocaleProvider";
import { PageHeader } from "../workspace/PageHeader";
import { WorkspacePanel } from "../workspace/WorkspacePanel";
import { WorkspaceTabs, workspaceTabId, workspaceTabPanelId } from "../workspace/WorkspaceTabs";

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

const supportedTemplateVariables = ["question", "choices", "context", "image", "audio", "video", "language", "output_schema"];
const templateVariable = /{{\s*([a-zA-Z_][a-zA-Z0-9_]*)\s*}}/g;

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

function jsonValue(value: Record<string, unknown> | unknown[] | null): string {
  return value === null ? "" : JSON.stringify(value, null, 2);
}

function promptPackageForm(prompt: PromptPackage): PromptPackageForm {
  return {
    name: prompt.name,
    version: prompt.version,
    prompt_type: prompt.prompt_type as PromptPackageType,
    system_message: prompt.system_message ?? "",
    user_template: prompt.user_template,
    few_shot_examples: jsonValue(prompt.few_shot_examples),
    output_format: jsonValue(prompt.output_format),
    response_parser: jsonValue(prompt.response_parser),
    scoring_rule: jsonValue(prompt.scoring_rule),
    change_log: prompt.change_log ?? "",
  };
}

function templateVariables(template: string): string[] {
  return [...new Set([...template.matchAll(templateVariable)].map((match) => match[1]))];
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
  activeTab: WorkspaceTabFor<"prompts">;
  busy: string | null;
  prompts: PromptPackage[];
  onCreate: (payload: PromptPackageCreatePayload) => Promise<PromptPackage>;
  onDelete: (promptPackageId: string) => Promise<void>;
  onTabChange: (tab: WorkspaceTabFor<"prompts">) => void;
  onUpdate: (promptPackageId: string, payload: PromptPackageCreatePayload) => Promise<PromptPackage>;
};

type PromptPackageFormProps = {
  busy: boolean;
  form: PromptPackageForm;
  onCancel?: () => void;
  onChange: (next: Partial<PromptPackageForm>) => void;
  onSubmit: (event: FormEvent<HTMLFormElement>) => void;
  submitLabel: string;
};

function PromptPackageFormFields({ busy, form, onCancel, onChange, onSubmit, submitLabel }: PromptPackageFormProps) {
  const { t } = useTranslation();
  return <form className="form workspace-prompt-form" onSubmit={onSubmit}>
    <section className="workspace-prompt-form-section">
      <h3>{t("promptPackage.identity")}</h3>
      <div className="workspace-field-grid workspace-field-grid--two">
        <label>{t("promptPackage.name")}<input onChange={(event) => onChange({ name: event.target.value })} required value={form.name} /></label>
        <label>{t("promptPackage.version")}<input onChange={(event) => onChange({ version: event.target.value })} required value={form.version} /></label>
      </div>
      <label>{t("promptPackage.type")}<select onChange={(event) => onChange({ prompt_type: event.target.value as PromptPackageType })} value={form.prompt_type}><option value="official">official</option><option value="platform_default">platform_default</option><option value="user_custom">user_custom</option><option value="benchmark_variant">benchmark_variant</option><option value="language_specific">language_specific</option></select></label>
    </section>
    <section className="workspace-prompt-form-section">
      <h3>{t("promptPackage.instructions")}</h3>
      <label>{t("promptPackage.systemMessage")}<textarea onChange={(event) => onChange({ system_message: event.target.value })} value={form.system_message} /></label>
      <label>{t("promptPackage.userTemplate")}<textarea onChange={(event) => onChange({ user_template: event.target.value })} required value={form.user_template} /></label>
      <p className="workspace-prompt-template-hint">{t("promptPackage.templateHint")} {supportedTemplateVariables.map((variable) => <code key={variable}>{`{{${variable}}}`}</code>)}</p>
    </section>
    <section className="workspace-prompt-form-section">
      <h3>{t("promptPackage.advanced")}</h3>
      <label>{t("promptPackage.fewShotExamples")}<textarea onChange={(event) => onChange({ few_shot_examples: event.target.value })} spellCheck={false} value={form.few_shot_examples} /></label>
      <div className="workspace-field-grid workspace-field-grid--three">
        <label>{t("promptPackage.outputFormat")}<textarea onChange={(event) => onChange({ output_format: event.target.value })} spellCheck={false} value={form.output_format} /></label>
        <label>{t("promptPackage.responseParser")}<textarea onChange={(event) => onChange({ response_parser: event.target.value })} spellCheck={false} value={form.response_parser} /></label>
        <label>{t("promptPackage.scoringRule")}<textarea onChange={(event) => onChange({ scoring_rule: event.target.value })} spellCheck={false} value={form.scoring_rule} /></label>
      </div>
      <label>{t("promptPackage.changeLog")}<textarea onChange={(event) => onChange({ change_log: event.target.value })} value={form.change_log} /></label>
    </section>
    <div className="actions"><button disabled={busy}>{submitLabel}</button>{onCancel && <button className="secondary" disabled={busy} onClick={onCancel} type="button">{t("promptPackage.cancel")}</button>}</div>
  </form>;
}

function PromptConfiguration({ label, value }: { label: string; value: Record<string, unknown> | unknown[] | null }) {
  const { t } = useTranslation();
  return <section className="workspace-prompt-configuration"><h3>{label}</h3>{value === null || (Array.isArray(value) && value.length === 0) ? <p className="empty">{t("promptPackage.notConfigured")}</p> : <pre>{JSON.stringify(value, null, 2)}</pre>}</section>;
}

function PromptPackageInspector({ busy, prompt, onDelete, onDuplicate, onStartEdit }: {
  busy: string | null;
  prompt: PromptPackage;
  onDelete: () => void;
  onDuplicate: () => void;
  onStartEdit: () => void;
}) {
  const { t } = useTranslation();
  const variables = templateVariables(prompt.user_template);
  return <WorkspacePanel className="workspace-prompt-inspector" title={<span data-i18n-preserve>{prompt.name} v{prompt.version}</span>} toolbar={<span className="badge" data-i18n-preserve>{prompt.prompt_type}</span>}>
    <div className="workspace-inspector-summary">
      <p><span className="workspace-item-meta">{t("promptPackage.variables")}</span> <span data-i18n-preserve>{variables.length ? variables.map((variable) => `{{${variable}}}`).join(", ") : t("common.notConfigured")}</span></p>
      <p><span className="workspace-item-meta">{t("promptPackage.fewShotExamples")}</span> {prompt.few_shot_examples.length}</p>
    </div>
    <section className="workspace-prompt-instructions"><div><h3>{t("promptPackage.systemMessage")}</h3><pre>{prompt.system_message ?? t("promptPackage.noSystemMessage")}</pre></div><div><h3>{t("promptPackage.userTemplate")}</h3><pre data-i18n-preserve>{prompt.user_template}</pre></div></section>
    <div className="workspace-prompt-configuration-grid">
      <PromptConfiguration label={t("promptPackage.fewShotExamples")} value={prompt.few_shot_examples} />
      <PromptConfiguration label={t("promptPackage.outputFormat")} value={prompt.output_format} />
      <PromptConfiguration label={t("promptPackage.responseParser")} value={prompt.response_parser} />
      <PromptConfiguration label={t("promptPackage.scoringRule")} value={prompt.scoring_rule} />
    </div>
    <section className="workspace-prompt-configuration"><h3>{t("promptPackage.changeLog")}</h3><p>{prompt.change_log || t("promptPackage.noChangeLog")}</p></section>
    <div className="actions workspace-prompt-actions"><button className="secondary" disabled={busy !== null} onClick={onStartEdit} type="button">{t("promptPackage.edit")}</button><button className="secondary" disabled={busy !== null} onClick={onDuplicate} type="button">{t("promptPackage.duplicate")}</button><button className="danger" disabled={busy !== null} onClick={onDelete} type="button">{busy === `prompt-package-delete-${prompt.id}` ? t("promptPackage.deleting") : t("promptPackage.delete")}</button></div>
  </WorkspacePanel>;
}

export function PromptPackagesPage({ activeTab, busy, prompts, onCreate, onDelete, onTabChange, onUpdate }: PromptPackagesPageProps) {
  const { t } = useTranslation();
  const [createForm, setCreateForm] = useState(initialForm);
  const [editForm, setEditForm] = useState(initialForm);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [selectedId, setSelectedId] = useState<string | null>(() => prompts[0]?.id ?? null);
  const selectedPrompt = prompts.find((prompt) => prompt.id === selectedId) ?? prompts[0] ?? null;
  const tabs = [{ id: "prompt-inventory", label: t("promptPackage.inventoryTab"), description: t("promptPackage.inventoryDescription") }, { id: "new-prompt-package", label: t("promptPackage.createTab"), description: t("promptPackage.createDescription") }] as const;

  useEffect(() => {
    if (selectedPrompt?.id !== selectedId) setSelectedId(selectedPrompt?.id ?? null);
  }, [selectedId, selectedPrompt?.id]);

  function updateCreateForm(next: Partial<PromptPackageForm>) {
    setError(null);
    setCreateForm((current) => ({ ...current, ...next }));
  }

  function updateEditForm(next: Partial<PromptPackageForm>) {
    setError(null);
    setEditForm((current) => ({ ...current, ...next }));
  }

  function reportError(caught: unknown) {
    setError(caught instanceof PromptPackageFormError ? t(caught.messageKey) : caught instanceof Error ? caught.message : t("promptPackage.invalidJson"));
  }

  async function submitCreate(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    try {
      const created = await onCreate(promptPackagePayload(createForm));
      setCreateForm(initialForm);
      setSelectedId(created.id);
      onTabChange("prompt-inventory");
    } catch (caught) {
      reportError(caught);
    }
  }

  async function submitEdit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!selectedPrompt) return;
    try {
      const updated = await onUpdate(selectedPrompt.id, promptPackagePayload(editForm));
      setSelectedId(updated.id);
      setEditingId(null);
    } catch (caught) {
      reportError(caught);
    }
  }

  async function requestDelete() {
    if (!selectedPrompt || !window.confirm(t("promptPackage.deleteConfirmation", { name: selectedPrompt.name, version: selectedPrompt.version }))) return;
    try {
      await onDelete(selectedPrompt.id);
      setSelectedId(null);
      setEditingId(null);
    } catch (caught) {
      reportError(caught);
    }
  }

  function duplicatePrompt() {
    if (!selectedPrompt) return;
    setError(null);
    setCreateForm({ ...promptPackageForm(selectedPrompt), version: "" });
    onTabChange("new-prompt-package");
  }

  return <div className="workspace-page prompt-packages-page">
    <PageHeader description={t("promptPackage.description")} eyebrow="Configure" status={<><strong>{prompts.length}</strong> {t("promptPackage.title").toLocaleLowerCase()}</>} title={t("promptPackage.title")} />
    <WorkspaceTabs ariaLabel={t("promptPackage.title")} idPrefix="prompts" onChange={onTabChange} tabs={tabs} value={activeTab} />
    <div aria-labelledby={workspaceTabId("prompts", activeTab)} id={workspaceTabPanelId("prompts", activeTab)} role="tabpanel" tabIndex={0}>
      {error && <p className="error" role="alert">{error}</p>}
      {activeTab === "new-prompt-package" ? <WorkspacePanel description={t("promptPackage.createDescription")} title={t("promptPackage.create")}><PromptPackageFormFields busy={busy === "prompt-package-create"} form={createForm} onChange={updateCreateForm} onSubmit={(event) => void submitCreate(event)} submitLabel={busy === "prompt-package-create" ? t("promptPackage.saving") : t("promptPackage.save")} /></WorkspacePanel> : (
        prompts.length === 0 ? <WorkspacePanel description={t("promptPackage.inventoryDescription")} title={t("promptPackage.inventory")}><p className="empty">{t("promptPackage.empty")}</p><div className="actions"><button onClick={() => onTabChange("new-prompt-package")} type="button">{t("promptPackage.createTab")}</button></div></WorkspacePanel> : <div className="workspace-split workspace-split--catalog workspace-prompt-inventory-layout">
          <WorkspacePanel description={t("promptPackage.inventoryDescription")} title={t("promptPackage.inventory")} toolbar={<span className="workspace-count">{prompts.length}</span>}>
            <div className="workspace-inventory-list workspace-catalog-inventory">{prompts.map((prompt) => <button aria-label={`${prompt.name} v${prompt.version}`} aria-pressed={selectedPrompt?.id === prompt.id} className={selectedPrompt?.id === prompt.id ? "workspace-select-row is-selected" : "workspace-select-row"} key={prompt.id} onClick={() => { setError(null); setEditingId(null); setSelectedId(prompt.id); }} type="button"><span data-i18n-preserve><strong>{prompt.name} v{prompt.version}</strong></span><span className="badge" data-i18n-preserve>{prompt.prompt_type}</span><small data-i18n-preserve>{templateVariables(prompt.user_template).length} {t("promptPackage.variables").toLocaleLowerCase()} · {prompt.few_shot_examples.length} {t("promptPackage.fewShotExamples").toLocaleLowerCase()}</small></button>)}</div>
          </WorkspacePanel>
          {selectedPrompt && (editingId === selectedPrompt.id ? <WorkspacePanel className="workspace-prompt-inspector" title={t("promptPackage.edit")}><PromptPackageFormFields busy={busy === `prompt-package-update-${selectedPrompt.id}`} form={editForm} onCancel={() => { setError(null); setEditingId(null); }} onChange={updateEditForm} onSubmit={(event) => void submitEdit(event)} submitLabel={busy === `prompt-package-update-${selectedPrompt.id}` ? t("promptPackage.saving") : t("promptPackage.saveChanges")} /></WorkspacePanel> : <PromptPackageInspector busy={busy} onDelete={() => void requestDelete()} onDuplicate={duplicatePrompt} onStartEdit={() => { setError(null); setEditForm(promptPackageForm(selectedPrompt)); setEditingId(selectedPrompt.id); }} prompt={selectedPrompt} />)}
        </div>
      )}
    </div>
  </div>;
}
