import { cleanup, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { useState } from "react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { DatasetRegistrationForm, type DatasetRegistrationFormValues } from "./components/datasets/DatasetRegistrationForm";
import { LocaleProvider } from "./i18n/LocaleProvider";

const initialValues: DatasetRegistrationFormValues = {
  capabilities: [],
  checksum: "",
  credential_binding_id: "",
  dataset_id: "",
  evaluation_type: "custom",
  input_field: "",
  languages: [],
  license_text: "",
  reference_field: "",
  revision: "main",
  source_url: "",
  version: "1",
};

afterEach(cleanup);

function StatefulForm() {
  const [values, setValues] = useState(initialValues);
  return <DatasetRegistrationForm busy={false} onChange={setValues} onSubmit={vi.fn((event) => event.preventDefault())} values={values} />;
}

describe("dataset registration form", () => {
  it("keeps essentials visible and preserves optional values through advanced disclosure", async () => {
    const user = userEvent.setup();
    render(<LocaleProvider><StatefulForm /></LocaleProvider>);

    expect(screen.getByLabelText("Dataset ID")).toBeVisible();
    expect(screen.getByText("Required fields are marked; everything else is optional.")).toBeVisible();
    expect(screen.getByLabelText("Expected SHA-256 checksum")).not.toBeVisible();

    await user.click(screen.getByText("Advanced settings (optional)"));
    await user.type(screen.getByLabelText("Expected SHA-256 checksum"), "abc123");
    await user.click(screen.getByText("Advanced settings (optional)"));
    await user.click(screen.getByText("Advanced settings (optional)"));

    expect(screen.getByLabelText("Expected SHA-256 checksum")).toHaveValue("abc123");
  });
});
