import { type KeyboardEvent, useId, useState } from "react";

import type { Dataset } from "../../api";
import { useTranslation } from "../../i18n/LocaleProvider";


export type DatasetMetadataValues = {
  capabilities: string[];
  languages: string[];
  evaluation_type: Dataset["evaluation_type"];
};

type DatasetMetadataFieldsProps<T extends DatasetMetadataValues> = {
  onChange: (values: T) => void;
  values: T;
};

const capabilitySuggestions = ["reasoning", "classification", "coding", "text_input", "vision", "audio"];
const languageSuggestions = ["en", "ms", "zh-CN", "fr", "de", "ru", "ja", "ko"];

export function DatasetMetadataFields<T extends DatasetMetadataValues>({ onChange, values }: DatasetMetadataFieldsProps<T>) {
  const { t } = useTranslation();
  return (
    <fieldset className="dataset-metadata-fields">
      <legend>{t("datasetRegister.metadata")}</legend>
      <p className="muted">{t("datasetRegister.metadataHint")}</p>
      <div className="workspace-field-grid workspace-field-grid--two">
        <MultiValueInput
          hint={t("datasetRegister.multiValueHint")}
          label={t("datasetRegister.capabilities")}
          normalize={normalizeCapability}
          onChange={(capabilities) => onChange({ ...values, capabilities })}
          removeLabel={t("datasetRegister.removeCapability")}
          suggestions={capabilitySuggestions}
          values={values.capabilities}
        />
        <MultiValueInput
          hint={t("datasetRegister.multiValueHint")}
          label={t("datasetRegister.languages")}
          normalize={(value) => value.trim()}
          onChange={(languages) => onChange({ ...values, languages })}
          removeLabel={t("datasetRegister.removeLanguage")}
          suggestions={languageSuggestions}
          values={values.languages}
        />
      </div>
      <label>{t("datasetRegister.evaluationType")}
        <select value={values.evaluation_type} onChange={(event) => onChange({ ...values, evaluation_type: event.target.value as Dataset["evaluation_type"] })}>
          <option value="classification">{t("datasetRegister.typeClassification")}</option>
          <option value="generation">{t("datasetRegister.typeGeneration")}</option>
          <option value="code">{t("datasetRegister.typeCode")}</option>
          <option value="language_modeling">{t("datasetRegister.typeLanguageModeling")}</option>
          <option value="custom">{t("datasetRegister.typeCustom")}</option>
        </select>
      </label>
    </fieldset>
  );
}

type MultiValueInputProps = {
  hint: string;
  label: string;
  normalize: (value: string) => string;
  onChange: (values: string[]) => void;
  removeLabel: string;
  suggestions: string[];
  values: string[];
};

function MultiValueInput({ hint, label, normalize, onChange, removeLabel, suggestions, values }: MultiValueInputProps) {
  const [draft, setDraft] = useState("");
  const inputId = useId();
  const hintId = `${inputId}-hint`;
  const listId = `${inputId}-suggestions`;

  function addDraft() {
    const value = normalize(draft);
    if (!value) return setDraft("");
    if (!values.some((item) => item.toLocaleLowerCase() === value.toLocaleLowerCase())) {
      onChange([...values, value]);
    }
    setDraft("");
  }

  function handleKeyDown(event: KeyboardEvent<HTMLInputElement>) {
    if (event.key === "Enter" || event.key === ",") {
      event.preventDefault();
      addDraft();
    } else if (event.key === "Backspace" && !draft && values.length) {
      onChange(values.slice(0, -1));
    }
  }

  return <div className="dataset-multi-value">
    <label htmlFor={inputId}>{label}</label>
    <div className="dataset-multi-value-control">
      <div className="dataset-value-chips" aria-live="polite">
        {values.map((value) => <button aria-label={`${removeLabel} ${value}`} className="dataset-value-chip" key={value} onClick={() => onChange(values.filter((item) => item !== value))} type="button"><span data-i18n-preserve>{value}</span><span aria-hidden="true">×</span></button>)}
      </div>
      <input
        aria-describedby={hintId}
        autoComplete="off"
        id={inputId}
        list={listId}
        onBlur={addDraft}
        onChange={(event) => setDraft(event.target.value)}
        onKeyDown={handleKeyDown}
        value={draft}
      />
      <datalist id={listId}>{suggestions.filter((item) => !values.includes(item)).map((item) => <option key={item} value={item} />)}</datalist>
    </div>
    <small className="muted" id={hintId}>{hint}</small>
  </div>;
}

function normalizeCapability(value: string) {
  return value.trim().toLocaleLowerCase().replace(/[\s-]+/g, "_");
}
