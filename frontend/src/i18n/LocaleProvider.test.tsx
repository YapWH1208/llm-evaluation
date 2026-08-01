import { cleanup, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it } from "vitest";

import { LocaleProvider, useTranslation } from "./LocaleProvider";

afterEach(() => {
  cleanup();
  window.localStorage.clear();
});

function LocaleProbe() {
  const { formatDate, formatNumber, locale, setLocale, t } = useTranslation();
  return <>
    <span data-testid="locale">{locale}</span>
    <span data-testid="copy">{t("common.dismiss")}</span>
    <span data-testid="number">{formatNumber(1234.5, 1)}</span>
    <span data-testid="date">{formatDate("2026-07-30T09:00:00Z")}</span>
    <button onClick={() => setLocale("ja")}>Japanese</button>
  </>;
}

describe("LocaleProvider", () => {
  it("hydrates a supported preference, persists a switch, and formats in the active locale", async () => {
    window.localStorage.setItem("lle-locale", "fr");
    const user = userEvent.setup();
    render(<LocaleProvider><LocaleProbe /></LocaleProvider>);

    expect(screen.getByTestId("locale")).toHaveTextContent("fr");
    expect(screen.getByTestId("copy")).toHaveTextContent("Fermer");
    expect(screen.getByTestId("number")).toHaveTextContent("1 234,5");
    expect(screen.getByTestId("date")).toHaveTextContent("juil.");

    await user.click(screen.getByRole("button", { name: "Japanese" }));
    expect(screen.getByTestId("locale")).toHaveTextContent("ja");
    expect(screen.getByTestId("number")).toHaveTextContent("1,234.5");
    expect(screen.getByTestId("copy")).toHaveTextContent("閉じる");
    expect(window.localStorage.getItem("lle-locale")).toBe("ja");
    expect(document.documentElement.lang).toBe("ja");
  });

  it("uses English when the stored locale is unsupported", () => {
    window.localStorage.setItem("lle-locale", "es");
    render(<LocaleProvider><LocaleProbe /></LocaleProvider>);

    expect(screen.getByTestId("locale")).toHaveTextContent("en");
    expect(screen.getByTestId("copy")).toHaveTextContent("Dismiss");
  });
});
