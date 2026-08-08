import { cleanup, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it } from "vitest";

import { WorkspaceSetupPage } from "./components/pages/WorkspaceSetupPage";

afterEach(cleanup);

describe("workspace setup workbench", () => {
  it("switches setup modes without removing caller-owned form content", async () => {
    const user = userEvent.setup();
    render(
      <WorkspaceSetupPage
        assets={<label>Media asset<input /></label>}
        catalog={<p>Benchmark registry</p>}
        inputs={<label>Prompt name<input value="Baseline" readOnly /></label>}
        suites={<label>Suite name<input /></label>}
      />,
    );

    expect(screen.getByRole("heading", { level: 1, name: "Workspace" })).toBeVisible();
    expect(screen.getByRole("tab", { name: "Inputs" })).toHaveAttribute("aria-selected", "true");
    expect(screen.getByLabelText("Prompt name")).toHaveValue("Baseline");

    await user.click(screen.getByRole("tab", { name: "Assets" }));

    expect(screen.getByRole("tab", { name: "Assets" })).toHaveAttribute("aria-selected", "true");
    expect(screen.getByLabelText("Media asset")).toBeVisible();
    expect(screen.getByLabelText("Prompt name")).not.toBeVisible();
  });

  it("keeps existing setup sections mounted while switching the visible workbench mode", async () => {
    const user = userEvent.setup();
    render(<WorkspaceSetupPage><section>Prompt setup</section><section>Asset setup</section><section>Suite setup</section><section>Benchmark registry</section><section>Dataset cache</section></WorkspaceSetupPage>);

    expect(screen.getByText("Prompt setup")).toBeVisible();
    await user.click(screen.getByRole("tab", { name: "Catalog" }));

    expect(screen.getByText("Benchmark registry")).toBeVisible();
    expect(screen.getByText("Dataset cache")).toBeVisible();
    expect(screen.getByText("Prompt setup")).not.toBeVisible();
  });
});
