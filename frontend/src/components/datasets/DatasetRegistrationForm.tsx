import type { FormEvent } from "react";

import { formCopy } from "../../i18n/catalog";
import { useTranslation } from "../../i18n/LocaleProvider";
import { WorkspacePanel } from "../workspace/WorkspacePanel";
import { DatasetMetadataFields, type DatasetMetadataValues } from "./DatasetMetadataFields";

export type DatasetRegistrationFormValues = DatasetMetadataValues & {
  checksum: string;
  credential_binding_id: string;
  dataset_id: string;
  input_field: string;
  license_text: string;
  reference_field: string;
  revision: string;
  source_url: string;
  version: string;
};

type DatasetRegistrationFormProps = {
  busy: boolean;
  onChange: (values: DatasetRegistrationFormValues) => void;
  onSubmit: (event: FormEvent<HTMLFormElement>) => void;
  values: DatasetRegistrationFormValues;
};

export function DatasetRegistrationForm({ busy, onChange, onSubmit, values }: DatasetRegistrationFormProps) {
  const { locale, t } = useTranslation();
  const copy = formCopy[locale];

  return (
    <WorkspacePanel title="Register dataset version">
      <form className="form" onSubmit={onSubmit}>
        <p className="workspace-form-requirements">{copy.requirements}</p>
        <label><span>Dataset ID <small>{copy.required}</small></span><input aria-label="Dataset ID" required value={values.dataset_id} onChange={(event) => onChange({ ...values, dataset_id: event.target.value })} /></label>
        <div className="field-row"><label><span>Version <small>{copy.required}</small></span><input aria-label="Version" required value={values.version} onChange={(event) => onChange({ ...values, version: event.target.value })} /></label><label><span>Revision <small>{copy.required}</small></span><input aria-label="Revision" required value={values.revision} onChange={(event) => onChange({ ...values, revision: event.target.value })} /></label></div>
        <label><span>Source HTTPS URL <small>{copy.optional}</small></span><input aria-label="Source HTTPS URL" value={values.source_url} onChange={(event) => onChange({ ...values, source_url: event.target.value })} placeholder="https://… or hf://owner/repository/path" /></label>
        <p className="muted">Use the dataset upload action for local files.</p>
        <details className="workspace-form-disclosure">
          <summary>{copy.advanced}</summary>
          <div className="workspace-form-disclosure__content">
            <label>Expected SHA-256 checksum<input value={values.checksum} onChange={(event) => onChange({ ...values, checksum: event.target.value })} placeholder="Optional; calculated after first verified download" /></label>
            <label>Credential binding ID<input value={values.credential_binding_id} onChange={(event) => onChange({ ...values, credential_binding_id: event.target.value })} placeholder="Optional administrator-configured binding" /></label>
            <label>License text<textarea value={values.license_text} onChange={(event) => onChange({ ...values, license_text: event.target.value })} /></label>
            <label>{t("datasetRegister.inputField")}<input value={values.input_field} onChange={(event) => onChange({ ...values, input_field: event.target.value })} placeholder={t("datasetRegister.inputFieldHint")} /></label>
            <label>{t("datasetRegister.referenceField")}<input value={values.reference_field} onChange={(event) => onChange({ ...values, reference_field: event.target.value })} placeholder={t("datasetRegister.referenceFieldHint")} /></label>
            <DatasetMetadataFields onChange={onChange} values={values} />
          </div>
        </details>
        <button disabled={busy}>Register dataset</button>
      </form>
    </WorkspacePanel>
  );
}
