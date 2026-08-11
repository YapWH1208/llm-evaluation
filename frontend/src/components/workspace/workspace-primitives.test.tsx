import { cleanup, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import { PageHeader } from "./PageHeader";
import { WorkspacePanel } from "./WorkspacePanel";
import { WorkspaceTabs } from "./WorkspaceTabs";

afterEach(cleanup);

describe("workspace presentation primitives", () => {
  it("renders a page-owned heading with contextual actions", () => {
    render(
      <PageHeader
        actions={<button type="button">Add endpoint</button>}
        description="Register and validate model endpoints."
        eyebrow="Configure"
        title="Models"
      />,
    );

    expect(screen.getByRole("heading", { level: 1, name: "Models" })).toBeVisible();
    expect(screen.getByText("Register and validate model endpoints.")).toBeVisible();
    expect(screen.getByRole("button", { name: "Add endpoint" })).toBeVisible();
  });

  it("associates a workspace panel with its heading", () => {
    render(<WorkspacePanel description="Current endpoint health.">Endpoint inventory</WorkspacePanel>);

    expect(screen.getByRole("region", { name: "Endpoint inventory" })).toBeVisible();
    expect(screen.getByRole("heading", { level: 2, name: "Endpoint inventory" })).toBeVisible();
    expect(screen.getByText("Current endpoint health.")).toBeVisible();
  });

  it("marks the active workspace tab and reports changes", async () => {
    const user = userEvent.setup();
    const onChange = vi.fn();
    render(
      <WorkspaceTabs
        ariaLabel="Evidence sections"
        idPrefix="evidence"
        onChange={onChange}
        tabs={[
          { id: "inputs", label: "Inputs" },
          { id: "outputs", label: "Outputs", description: "Generated model evidence" },
        ]}
        value="inputs"
      />,
    );

    expect(screen.getByRole("tab", { name: "Inputs" })).toHaveAttribute("aria-selected", "true");
    expect(screen.getByRole("tab", { name: "Outputs" })).toHaveAttribute("aria-selected", "false");
    expect(screen.getByRole("tablist", { name: "Evidence sections" })).toBeVisible();
    expect(screen.getByRole("tab", { name: "Inputs" })).toHaveAttribute("id", "evidence-tab-inputs");
    expect(screen.getByRole("tab", { name: /Outputs/ })).toHaveAttribute("aria-controls", "evidence-tabpanel-outputs");
    expect(screen.getByText("Generated model evidence")).toBeVisible();

    await user.click(screen.getByRole("tab", { name: /Outputs/ }));

    expect(onChange).toHaveBeenCalledWith("outputs");
  });

  it("automatically activates adjacent, first, and last tabs from the keyboard", async () => {
    const user = userEvent.setup();
    const onChange = vi.fn();
    render(
      <WorkspaceTabs
        ariaLabel="Models sections"
        idPrefix="models"
        onChange={onChange}
        tabs={[
          { id: "inventory", label: "Inventory" },
          { id: "add", label: "Add" },
          { id: "limits", label: "Limits" },
        ]}
        value="inventory"
      />,
    );

    screen.getByRole("tab", { name: "Inventory" }).focus();
    await user.keyboard("{ArrowRight}");
    expect(onChange).toHaveBeenLastCalledWith("add");
    expect(screen.getByRole("tab", { name: "Add" })).toHaveFocus();

    await user.keyboard("{End}");
    expect(onChange).toHaveBeenLastCalledWith("limits");
    expect(screen.getByRole("tab", { name: "Limits" })).toHaveFocus();

    await user.keyboard("{Home}");
    expect(onChange).toHaveBeenLastCalledWith("inventory");
    expect(screen.getByRole("tab", { name: "Inventory" })).toHaveFocus();

    await user.keyboard("{ArrowLeft}");
    expect(onChange).toHaveBeenLastCalledWith("limits");
  });
});
