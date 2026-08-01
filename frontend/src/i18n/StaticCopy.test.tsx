import { cleanup, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it } from "vitest";

import { LocaleProvider, useTranslation } from "./LocaleProvider";
import { StaticCopy } from "./StaticCopy";

afterEach(() => {
  cleanup();
  window.localStorage.clear();
});

describe("StaticCopy", () => {
  it("translates client-owned operational copy without rewriting raw or server-owned values", async () => {
    window.localStorage.setItem("lle-locale", "fr");
    const user = userEvent.setup();
    function SwitchLocale() {
      const { setLocale } = useTranslation();
      return <button data-testid="switch-locale" onClick={() => setLocale("ja")}>Switch locale</button>;
    }
    render(<LocaleProvider><StaticCopy>
      <SwitchLocale />
      <h2>Add model endpoint</h2>
      <label>Display name<input placeholder="My local model" /></label>
      <span className="badge">available</span>
      <span>queued</span>
      <pre>available</pre>
    </StaticCopy></LocaleProvider>);

    expect(screen.getByRole("heading")).toHaveTextContent("Ajouter un point de terminaison de modèle");
    expect(screen.getByLabelText("affichage nom")).toHaveAttribute("placeholder", "My local modèle");
    expect(screen.getAllByText("available")).toHaveLength(2);
    expect(screen.getByText("queued")).toBeInTheDocument();

    await user.click(screen.getByTestId("switch-locale"));
    expect(screen.getByRole("heading")).toHaveTextContent("モデルエンドポイントを追加");
    expect(screen.getByLabelText("表示 名前")).toHaveAttribute("placeholder", "My ローカル モデル");
    expect(screen.getAllByText("available")).toHaveLength(2);
  });
});
