import { cleanup, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import { SystemHealth } from "./api";
import { SettingsPage } from "./components/pages/SystemPages";
import { LocaleProvider } from "./i18n/LocaleProvider";

afterEach(cleanup);

describe("settings workspace page", () => {
  const health = { status: "ok", database: "sqlite", schema_version: 3, database_connected: true, disk: { available_bytes: 30, total_bytes: 100 }, queue: { pending: 2, active: 1 } } as SystemHealth;

  function settingsProps(overrides: Partial<React.ComponentProps<typeof SettingsPage>> = {}) {
    const onSaveToken = vi.fn();
    const onClearToken = vi.fn();
    const onToggleTheme = vi.fn();
    return { activeTab: "health" as const, apiToken: "", locale: "en" as const, onApiTokenChange: vi.fn(), onClearToken, onLocaleChange: vi.fn(), onSaveToken, onTabChange: vi.fn(), onToggleTheme, systemHealth: health, theme: "dark" as const, ...overrides };
  }

  it("shows deployment health only on the default tab", async () => {
    const user = userEvent.setup();
    const props = settingsProps();
    render(<LocaleProvider><SettingsPage {...props} /></LocaleProvider>);

    expect(screen.getByRole("heading", { name: "System settings" })).toBeVisible();
    expect(screen.getByRole("tab", { name: "Health" })).toHaveAttribute("aria-selected", "true");
    expect(screen.getByRole("heading", { name: "Application and storage" })).toBeVisible();
    expect(screen.queryByLabelText("Administrator or user bearer token")).not.toBeInTheDocument();
    expect(screen.queryByLabelText("Workspace language")).not.toBeInTheDocument();

    await user.click(screen.getByRole("tab", { name: "Access" }));
    expect(props.onTabChange).toHaveBeenCalledWith("access");
  });

  it("keeps bearer token actions only on the access tab", async () => {
    const user = userEvent.setup();
    const props = settingsProps({ activeTab: "access" });
    render(<LocaleProvider><SettingsPage {...props} /></LocaleProvider>);

    expect(screen.getByLabelText("Administrator or user bearer token")).toHaveAttribute("type", "password");
    await user.click(screen.getByRole("button", { name: "Save token" }));
    await user.click(screen.getByRole("button", { name: "Clear token" }));

    expect(props.onSaveToken).toHaveBeenCalledOnce();
    expect(props.onClearToken).toHaveBeenCalledOnce();
    expect(screen.queryByRole("heading", { name: "Application and storage" })).not.toBeInTheDocument();
    expect(screen.queryByLabelText("Workspace language")).not.toBeInTheDocument();
  });

  it("keeps language, theme, and operating guidance on preferences", async () => {
    const user = userEvent.setup();
    const props = settingsProps({ activeTab: "preferences" });
    render(<LocaleProvider><SettingsPage {...props} /></LocaleProvider>);

    expect(screen.getByLabelText("Workspace language")).toBeVisible();
    await user.click(screen.getByRole("button", { name: "Switch to light mode" }));
    expect(props.onToggleTheme).toHaveBeenCalledOnce();
    expect(screen.getByRole("heading", { name: "Operating guidance" })).toBeVisible();
    expect(screen.queryByLabelText("Administrator or user bearer token")).not.toBeInTheDocument();
    expect(screen.queryByRole("heading", { name: "Application and storage" })).not.toBeInTheDocument();
  });
});
