import { cleanup, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import { SystemHealth } from "./api";
import { SettingsPage } from "./components/pages/SystemPages";
import { LocaleProvider } from "./i18n/LocaleProvider";

afterEach(cleanup);

describe("settings workspace page", () => {
  it("keeps health, masked token controls, locale, and theme actions together", async () => {
    const user = userEvent.setup();
    const health = { status: "ok", database: "sqlite", schema_version: 3, database_connected: true, disk: { available_bytes: 30, total_bytes: 100 }, queue: { pending: 2, active: 1 } } as SystemHealth;
    const onSaveToken = vi.fn();
    const onClearToken = vi.fn();
    const onToggleTheme = vi.fn();
    render(<LocaleProvider><SettingsPage apiToken="" locale="en" onApiTokenChange={vi.fn()} onClearToken={onClearToken} onLocaleChange={vi.fn()} onSaveToken={onSaveToken} onToggleTheme={onToggleTheme} systemHealth={health} theme="dark" /></LocaleProvider>);

    expect(screen.getByRole("heading", { name: "System settings" })).toBeVisible();
    expect(screen.getByLabelText("Administrator or user bearer token")).toHaveAttribute("type", "password");
    await user.click(screen.getByRole("button", { name: "Save token" }));
    await user.click(screen.getByRole("button", { name: "Clear token" }));
    await user.click(screen.getByRole("button", { name: "Switch to light mode" }));

    expect(onSaveToken).toHaveBeenCalledOnce();
    expect(onClearToken).toHaveBeenCalledOnce();
    expect(onToggleTheme).toHaveBeenCalledOnce();
  });
});
