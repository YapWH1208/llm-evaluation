import { cleanup, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import App from "./App";
import { api, PromptPackage } from "./api";
import { PromptPackagesPage } from "./components/pages/PromptPackagesPage";
import { LocaleProvider } from "./i18n/LocaleProvider";

afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
  window.history.replaceState(null, "", "/dashboard");
});

const prompt: PromptPackage = {
  id: "prompt-1",
  name: "Answer concisely",
  version: "1",
  prompt_type: "user_custom",
  system_message: "Answer concisely.",
  user_template: "{{question}}",
  created_at: "2026-08-12T00:00:00Z",
};

function renderPage(overrides: Partial<React.ComponentProps<typeof PromptPackagesPage>> = {}) {
  const props = {
    busy: false,
    prompts: [prompt],
    onCreate: vi.fn().mockResolvedValue(undefined),
    ...overrides,
  };
  render(<LocaleProvider><PromptPackagesPage {...props} /></LocaleProvider>);
  return props;
}

function mockWorkspace(promptPackages: PromptPackage[] = []) {
  vi.spyOn(api, "listEndpoints").mockResolvedValue([]);
  vi.spyOn(api, "listRuns").mockResolvedValue([]);
  vi.spyOn(api, "dashboard").mockResolvedValue(null as never);
  vi.spyOn(api, "listPromptPackages").mockResolvedValue(promptPackages);
  vi.spyOn(api, "listDatasets").mockResolvedValue([]);
  vi.spyOn(api, "listBenchmarks").mockResolvedValue([]);
  vi.spyOn(api, "listTasks").mockResolvedValue([]);
  vi.spyOn(api, "analyticsMatrix").mockResolvedValue(null as never);
  vi.spyOn(api, "systemHealth").mockResolvedValue(null as never);
}

describe("PromptPackagesPage", () => {
  it("lists prompt packages and creates a complete versioned package payload", async () => {
    const user = userEvent.setup();
    const props = renderPage();

    expect(screen.getByRole("heading", { level: 1, name: "Prompt packages" })).toBeVisible();
    expect(screen.getByText("Answer concisely")).toBeVisible();
    expect(screen.getByText("v1 · user_custom")).toBeVisible();

    await user.type(screen.getByLabelText("Name"), "Strict answers");
    await user.clear(screen.getByLabelText("Version"));
    await user.type(screen.getByLabelText("Version"), "2");
    await user.type(screen.getByLabelText("System message"), "Follow the policy.");
    await user.click(screen.getByLabelText("User template"));
    await user.paste("{{question}}");
    await user.clear(screen.getByLabelText("Few-shot examples (JSON array)"));
    await user.click(screen.getByLabelText("Few-shot examples (JSON array)"));
    await user.paste("[]");
    await user.click(screen.getByLabelText("Output format (JSON object)"));
    await user.paste('{"type":"json"}');
    await user.click(screen.getByRole("button", { name: "Save versioned prompt" }));

    expect(props.onCreate).toHaveBeenCalledWith({
      name: "Strict answers",
      version: "2",
      prompt_type: "user_custom",
      system_message: "Follow the policy.",
      user_template: "{{question}}",
      few_shot_examples: [],
      output_format: { type: "json" },
      response_parser: null,
      scoring_rule: null,
      change_log: null,
    });
  });

  it("blocks malformed optional JSON before calling the API", async () => {
    const user = userEvent.setup();
    const props = renderPage({ prompts: [] });

    await user.type(screen.getByLabelText("Name"), "Strict answers");
    await user.click(screen.getByLabelText("User template"));
    await user.paste("{{question}}");
    await user.click(screen.getByLabelText("Output format (JSON object)"));
    await user.paste("{");
    await user.click(screen.getByRole("button", { name: "Save versioned prompt" }));

    expect(await screen.findByRole("alert")).toHaveTextContent("Use valid JSON for optional configuration fields.");
    expect(props.onCreate).not.toHaveBeenCalled();
  });

  it("creates through the workspace API and refreshes the inventory", async () => {
    const user = userEvent.setup();
    const createdPrompt = { ...prompt, id: "prompt-2", name: "New package", version: "2" };
    window.history.replaceState(null, "", "/prompts");
    mockWorkspace([]);
    const createPromptPackage = vi.spyOn(api, "createPromptPackage").mockResolvedValue(createdPrompt);
    vi.mocked(api.listPromptPackages).mockResolvedValueOnce([]).mockResolvedValue([createdPrompt]);

    render(<LocaleProvider><App /></LocaleProvider>);
    await screen.findByRole("heading", { level: 1, name: "Prompt packages" });
    await user.type(screen.getByLabelText("Name"), "New package");
    await user.clear(screen.getByLabelText("Version"));
    await user.type(screen.getByLabelText("Version"), "2");
    await user.click(screen.getByLabelText("User template"));
    await user.paste("{{question}}");
    await user.click(screen.getByRole("button", { name: "Save versioned prompt" }));

    await waitFor(() => expect(createPromptPackage).toHaveBeenCalledOnce());
    expect(createPromptPackage).toHaveBeenCalledWith(expect.objectContaining({ name: "New package", version: "2", user_template: "{{question}}" }));
    expect(await screen.findByText("New package")).toBeVisible();
  });
});
