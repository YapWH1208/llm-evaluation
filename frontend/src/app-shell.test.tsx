import { act, cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import { AppShell } from "./components/AppShell";
import { navigationGroups } from "./dashboard/navigation";
import { navigationCopy } from "./i18n/catalog";
import { LocaleProvider } from "./i18n/LocaleProvider";

afterEach(() => {
  cleanup();
  vi.useRealTimers();
  vi.unstubAllGlobals();
  window.localStorage.clear();
});

function renderShell({ children = <p>Workspace content</p>, ...overrides }: Partial<React.ComponentProps<typeof AppShell>> = {}) {
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
  render(<LocaleProvider><AppShell {...props}>{children}</AppShell></LocaleProvider>);
  return props;
}

describe("AppShell", () => {
  it("groups every workspace destination and exposes the selected page", () => {
    const props = renderShell();

    for (const group of navigationGroups) {
      expect(screen.getByRole("region", { name: navigationCopy.en.groups[group.id] })).toBeVisible();
      for (const item of group.items) {
        const link = screen.getByRole("link", { name: navigationCopy.en.items[item.view].label });
        expect(link).toBeVisible();
        expect(link).toHaveAttribute("href", `/${item.view}`);
        expect(link.querySelector(`[data-navigation-icon="${item.view}"]`)).toHaveAttribute("aria-hidden", "true");
      }
    }

    expect(screen.getByRole("link", { name: "Dashboard" })).toHaveAttribute("aria-current", "page");
    expect(screen.getByText("12", { selector: "strong" })).toBeVisible();
    expect(props.onViewChange).not.toHaveBeenCalled();
  });

  it("leaves page headings to view content instead of rendering a duplicate shell heading", () => {
    const { rerender } = render(
      <LocaleProvider>
        <AppShell
          completedRunCount={12}
          locale="en"
          notice={null}
          systemHealth={null}
          theme="dark"
          view="dashboard"
          onDismissNotice={vi.fn()}
          onLocaleChange={vi.fn()}
          onThemeToggle={vi.fn()}
          onViewChange={vi.fn()}
        >
          <h1>Dashboard</h1>
        </AppShell>
      </LocaleProvider>,
    );

    expect(screen.getAllByRole("heading", { level: 1 })).toHaveLength(1);
    expect(document.querySelector(".workspace-page-heading")).not.toBeInTheDocument();

    rerender(
      <LocaleProvider>
        <AppShell
          completedRunCount={12}
          locale="en"
          notice={null}
          systemHealth={null}
          theme="dark"
          view="models"
          onDismissNotice={vi.fn()}
          onLocaleChange={vi.fn()}
          onThemeToggle={vi.fn()}
          onViewChange={vi.fn()}
        >
          <h1>Models</h1>
        </AppShell>
      </LocaleProvider>,
    );

    expect(document.querySelector(".workspace-page-heading")).not.toBeInTheDocument();
    expect(screen.getAllByRole("heading", { level: 1, name: "Models" })).toHaveLength(1);
  });

  it("opens the responsive drawer and closes it after navigation", async () => {
    const user = userEvent.setup();
    const props = renderShell();
    const sidebar = screen.getByTestId("workspace-sidebar");

    expect(sidebar).toHaveClass("is-closed");
    expect(sidebar).not.toHaveClass("is-open");
    await user.click(screen.getByRole("button", { name: "Open navigation" }));
    expect(sidebar).toHaveClass("is-open");
    expect(sidebar).not.toHaveClass("is-closed");

    await user.click(screen.getByRole("link", { name: "Models" }));
    expect(props.onViewChange).toHaveBeenCalledWith("models");
    expect(sidebar).toHaveClass("is-closed");
    expect(sidebar).not.toHaveClass("is-open");
  });

  it("makes the closed mobile drawer inert and contains focus while open", async () => {
    const mediaListeners = new Set<(event: MediaQueryListEvent) => void>();
    vi.stubGlobal("matchMedia", vi.fn().mockReturnValue({
      matches: true,
      media: "(max-width: 960px)",
      onchange: null,
      addEventListener: (_type: string, listener: (event: MediaQueryListEvent) => void) => mediaListeners.add(listener),
      removeEventListener: (_type: string, listener: (event: MediaQueryListEvent) => void) => mediaListeners.delete(listener),
      addListener: vi.fn(),
      removeListener: vi.fn(),
      dispatchEvent: vi.fn(),
    }));
    const user = userEvent.setup();
    renderShell();
    const sidebar = screen.getByTestId("workspace-sidebar");
    const opener = screen.getByRole("button", { name: "Open navigation" });

    await waitFor(() => expect(sidebar).toHaveAttribute("inert"));
    expect(sidebar).toHaveAttribute("aria-hidden", "true");

    await user.click(opener);
    const close = within(sidebar).getByRole("button", { name: "Close navigation" });
    expect(sidebar).not.toHaveAttribute("inert");
    expect(sidebar).not.toHaveAttribute("aria-hidden");
    expect(close).toHaveFocus();

    fireEvent.keyDown(sidebar, { key: "Tab", shiftKey: true });
    expect(within(sidebar).getByRole("link", { name: "Settings" })).toHaveFocus();
    fireEvent.keyDown(sidebar, { key: "Tab" });
    expect(close).toHaveFocus();

    fireEvent.keyDown(sidebar, { key: "Escape" });
    expect(sidebar).toHaveAttribute("inert");
    expect(opener).toHaveFocus();
  });

  it("leaves modified navigation clicks to the browser", () => {
    const props = renderShell();
    const link = screen.getByRole("link", { name: "Models" });
    link.addEventListener("click", (event) => event.preventDefault(), { once: true });

    fireEvent.click(link, { button: 0, metaKey: true });

    expect(props.onViewChange).not.toHaveBeenCalled();
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

  it("auto-dismisses a transient notice at exactly five seconds", () => {
    vi.useFakeTimers();
    const props = renderShell({ notice: "Evaluation queued." });

    act(() => vi.advanceTimersByTime(4_999));
    expect(props.onDismissNotice).not.toHaveBeenCalled();

    act(() => vi.advanceTimersByTime(1));
    expect(props.onDismissNotice).toHaveBeenCalledOnce();
  });

  it("restarts the dismissal timer when a notice is replaced", () => {
    vi.useFakeTimers();
    const onDismissNotice = vi.fn();
    const shell = (notice: string | null) => (
      <LocaleProvider>
        <AppShell
          completedRunCount={12}
          locale="en"
          notice={notice}
          systemHealth={null}
          theme="dark"
          view="dashboard"
          onDismissNotice={onDismissNotice}
          onLocaleChange={vi.fn()}
          onThemeToggle={vi.fn()}
          onViewChange={vi.fn()}
        >
          <p>Workspace content</p>
        </AppShell>
      </LocaleProvider>
    );
    const { rerender } = render(shell("First notice"));

    act(() => vi.advanceTimersByTime(3_000));
    rerender(shell("Replacement notice"));
    act(() => vi.advanceTimersByTime(4_999));
    expect(onDismissNotice).not.toHaveBeenCalled();

    act(() => vi.advanceTimersByTime(1));
    expect(onDismissNotice).toHaveBeenCalledOnce();
  });

  it("cancels the timer after manual dismissal", () => {
    vi.useFakeTimers();
    const onDismissNotice = vi.fn();
    const baseProps = {
      completedRunCount: 12,
      locale: "en" as const,
      systemHealth: null,
      theme: "dark" as const,
      view: "dashboard" as const,
      onDismissNotice,
      onLocaleChange: vi.fn(),
      onThemeToggle: vi.fn(),
      onViewChange: vi.fn(),
    };
    const { rerender } = render(
      <LocaleProvider><AppShell {...baseProps} notice="Dismiss me"><p>Content</p></AppShell></LocaleProvider>,
    );

    fireEvent.click(screen.getByRole("button", { name: "Dismiss me Dismiss" }));
    rerender(
      <LocaleProvider><AppShell {...baseProps} notice={null}><p>Content</p></AppShell></LocaleProvider>,
    );
    act(() => vi.advanceTimersByTime(5_000));

    expect(onDismissNotice).toHaveBeenCalledOnce();
  });

  it("cleans up a pending dismissal timer when the shell unmounts", () => {
    vi.useFakeTimers();
    const onDismissNotice = vi.fn();
    const { unmount } = render(
      <LocaleProvider>
        <AppShell
          completedRunCount={12}
          locale="en"
          notice="Pending notice"
          systemHealth={null}
          theme="dark"
          view="dashboard"
          onDismissNotice={onDismissNotice}
          onLocaleChange={vi.fn()}
          onThemeToggle={vi.fn()}
          onViewChange={vi.fn()}
        >
          <p>Content</p>
        </AppShell>
      </LocaleProvider>,
    );

    unmount();
    act(() => vi.advanceTimersByTime(5_000));

    expect(onDismissNotice).not.toHaveBeenCalled();
  });

  it("labels a healthy service from the deployed health response", () => {
    renderShell({ systemHealth: { status: "ok", database: "sqlite", schema_version: 1, database_connected: true, disk: { available_bytes: 1024, total_bytes: 2048 }, queue: { pending: 0, active: 0 } } });

    expect(screen.getByText("System healthy")).toBeVisible();
    expect(document.querySelector(".health-dot")).toHaveClass("is-healthy");
  });

  it("reports an unknown service state while health has not responded", () => {
    renderShell({ systemHealth: null });

    expect(screen.getByText("System status unavailable")).toBeVisible();
    expect(document.querySelector(".health-dot")).not.toHaveClass("is-healthy");
  });
});
