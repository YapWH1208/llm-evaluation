import { cleanup, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import { AppShell } from "./components/AppShell";
import { navigationGroups } from "./dashboard/navigation";

afterEach(cleanup);

function renderShell(overrides: Partial<React.ComponentProps<typeof AppShell>> = {}) {
  const props = {
    completedRunCount: 12,
    locale: "en" as const,
    notice: null,
    systemHealth: null,
    theme: "dark" as const,
    view: "dashboard" as const,
    onDismissNotice: vi.fn(),
    onLocaleChange: vi.fn(),
    onThemeToggle: vi.fn(),
    onViewChange: vi.fn(),
    ...overrides,
  };
  render(<AppShell {...props}><p>Workspace content</p></AppShell>);
  return props;
}

describe("AppShell", () => {
  it("groups every workspace destination and exposes the selected page", () => {
    const props = renderShell();

    for (const group of navigationGroups) {
      expect(screen.getByRole("region", { name: group.label.en })).toBeVisible();
      for (const item of group.items) {
        expect(screen.getByRole("button", { name: item.label.en })).toBeVisible();
      }
    }

    expect(screen.getByRole("button", { name: "Dashboard" })).toHaveAttribute("aria-current", "page");
    expect(screen.getByText("12", { selector: "strong" })).toBeVisible();
    expect(props.onViewChange).not.toHaveBeenCalled();
  });

  it("opens the responsive drawer and closes it after navigation", async () => {
    const user = userEvent.setup();
    const props = renderShell();
    const sidebar = screen.getByTestId("workspace-sidebar");

    expect(sidebar).not.toHaveClass("is-open");
    await user.click(screen.getByRole("button", { name: "Open navigation" }));
    expect(sidebar).toHaveClass("is-open");

    await user.click(screen.getByRole("button", { name: "Models" }));
    expect(props.onViewChange).toHaveBeenCalledWith("models");
    expect(sidebar).not.toHaveClass("is-open");
  });

  it("keeps the global theme, locale, and notice controls available", async () => {
    const user = userEvent.setup();
    const props = renderShell({ notice: "Endpoint connection failed." });

    await user.click(screen.getByRole("button", { name: "Switch to light mode" }));
    await user.selectOptions(screen.getByRole("combobox", { name: "Workspace language" }), "zh-CN");
    await user.click(screen.getByRole("button", { name: "Endpoint connection failed. Dismiss" }));

    expect(props.onThemeToggle).toHaveBeenCalledOnce();
    expect(props.onLocaleChange).toHaveBeenCalledWith("zh-CN");
    expect(props.onDismissNotice).toHaveBeenCalledOnce();
  });
});
