import { cleanup, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import type { SystemHealth } from "./features/analytics/api";
import { SettingsPage } from "./components/pages/SystemPages";
import { LocaleProvider } from "./i18n/LocaleProvider";

afterEach(cleanup);

describe("settings workspace page", () => {
  const health = { status: "ok", database: "sqlite", schema_version: 3, database_connected: true, disk: { available_bytes: 30, total_bytes: 100 }, queue: { pending: 2, active: 1 } } as SystemHealth;

  function settingsProps(overrides: Partial<React.ComponentProps<typeof SettingsPage>> = {}) {
    const onToggleTheme = vi.fn();
    return { activeTab: "health" as const, locale: "en" as const, onLocaleChange: vi.fn(), onTabChange: vi.fn(), onToggleTheme, systemHealth: health, theme: "dark" as const, ...overrides };
  }

  it("shows deployment health on the default tab", async () => {
    const user = userEvent.setup();
    const props = settingsProps();
    render(<LocaleProvider><SettingsPage {...props} /></LocaleProvider>);

    expect(screen.getByRole("heading", { name: "System settings" })).toBeVisible();
    expect(screen.getByRole("tab", { name: "Health" })).toHaveAttribute("aria-selected", "true");
    expect(screen.getByRole("heading", { name: "Application and storage" })).toBeVisible();
    expect(screen.queryByLabelText("Workspace language")).not.toBeInTheDocument();

    await user.click(screen.getByRole("tab", { name: "Preferences" }));
    expect(props.onTabChange).toHaveBeenCalledWith("preferences");
  });

  it("keeps language, theme, and operating guidance on preferences", async () => {
    const user = userEvent.setup();
    const props = settingsProps({ activeTab: "preferences" });
    render(<LocaleProvider><SettingsPage {...props} /></LocaleProvider>);

    expect(screen.getByLabelText("Workspace language")).toBeVisible();
    await user.click(screen.getByRole("button", { name: "Switch to light mode" }));
    expect(props.onToggleTheme).toHaveBeenCalledOnce();
    expect(screen.getByRole("heading", { name: "Operating guidance" })).toBeVisible();
    expect(screen.queryByRole("heading", { name: "Application and storage" })).not.toBeInTheDocument();
  });
});
