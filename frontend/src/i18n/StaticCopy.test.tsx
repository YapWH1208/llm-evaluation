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

  it("translates dataset catalog notices and the preview fallback copy", () => {
    window.localStorage.setItem("lle-locale", "fr");
    render(<LocaleProvider><StaticCopy>
      <p>Dataset version updated.</p>
      <p>Dataset version deleted.</p>
      <p>Preview unavailable.</p>
    </StaticCopy></LocaleProvider>);
    expect(screen.getByText("Version du jeu de données mise à jour.")).toBeTruthy();
    expect(screen.getByText("Version du jeu de données supprimée.")).toBeTruthy();
    expect(screen.getByText("Aperçu indisponible.")).toBeTruthy();
  });

  it("preserves dynamic values that collide with client copy and translates protocol labels", async () => {
    window.localStorage.setItem("lle-locale", "fr");
    const user = userEvent.setup();
    function SwitchLocale() {
      const { setLocale } = useTranslation();
      return <button onClick={() => setLocale("ja")}>Switch locale</button>;
    }

    render(<LocaleProvider><StaticCopy>
      <SwitchLocale />
      <h3 data-i18n-preserve data-testid="endpoint-name">Models</h3>
      <select aria-label="Protocol profile"><option value="openai_chat_completions">OpenAI-compatible Chat Completions</option><option value="endpoint-123" data-testid="endpoint-option">Models</option></select>
      <article className="card"><div className="section-title"><h3>Dataset catalog</h3></div><p className="muted" data-testid="dataset-revision">Revision <span data-i18n-preserve>Models</span></p></article>
      <button className="run-summary"><strong data-testid="benchmark-name">Models</strong></button>
    </StaticCopy></LocaleProvider>);

    expect(screen.getByTestId("endpoint-name")).toHaveTextContent("Models");
    expect(screen.getByTestId("endpoint-option")).toHaveTextContent("Models");
    expect(screen.getByTestId("dataset-revision")).toHaveTextContent("révision Models");
    expect(screen.getByTestId("benchmark-name")).toHaveTextContent("Models");
    expect(screen.getAllByRole("option")[0]).toHaveTextContent("Complétions de chat compatibles OpenAI");

    await user.click(screen.getByRole("button", { name: "Switch locale" }));
    expect(screen.getByTestId("endpoint-name")).toHaveTextContent("Models");
    expect(screen.getByTestId("endpoint-option")).toHaveTextContent("Models");
    expect(screen.getByTestId("dataset-revision")).toHaveTextContent("改訂 Models");
    expect(screen.getByTestId("benchmark-name")).toHaveTextContent("Models");
    expect(screen.getAllByRole("option")[0]).toHaveTextContent("OpenAI 互換チャット補完");
  });
});
