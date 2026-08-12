import { cleanup, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { useState } from "react";
import { afterEach, describe, expect, it, vi } from "vitest";

import App from "./App";
import { api, PromptPackage } from "./api";
import { PromptPackagesPage } from "./components/pages/PromptPackagesPage";
import type { WorkspaceTabFor } from "./dashboard/routing";
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
  few_shot_examples: [],
  output_format: null,
  response_parser: null,
  scoring_rule: { type: "exact_match" },
  change_log: "Initial version.",
  created_at: "2026-08-12T00:00:00Z",
};

const secondPrompt: PromptPackage = {
  ...prompt,
  id: "prompt-2",
  name: "Grounded answers",
  version: "2",
  system_message: "Use only the supplied context.",
  user_template: "{{context}}\n{{question}}",
  few_shot_examples: [{ role: "assistant", content: "Example" }],
  output_format: { type: "json" },
  response_parser: { path: "answer" },
  scoring_rule: null,
  change_log: null,
};

function renderPage(overrides: Partial<React.ComponentProps<typeof PromptPackagesPage>> = {}) {
  const props = {
    activeTab: "prompt-inventory" as WorkspaceTabFor<"prompts">,
    busy: null,
    prompts: [prompt, secondPrompt],
    onCreate: vi.fn().mockResolvedValue(prompt),
    onDelete: vi.fn().mockResolvedValue(undefined),
    onTabChange: vi.fn(),
    onUpdate: vi.fn().mockResolvedValue(prompt),
    ...overrides,
  };
  render(<LocaleProvider><PromptPackagesPage {...props} /></LocaleProvider>);
  return props;
}

function PromptPackagesHarness({ onCreate = vi.fn().mockResolvedValue(prompt), onDelete = vi.fn().mockResolvedValue(undefined), onUpdate = vi.fn().mockResolvedValue(prompt) }: {
  onCreate?: React.ComponentProps<typeof PromptPackagesPage>["onCreate"];
  onDelete?: React.ComponentProps<typeof PromptPackagesPage>["onDelete"];
  onUpdate?: React.ComponentProps<typeof PromptPackagesPage>["onUpdate"];
}) {
  const [activeTab, setActiveTab] = useState<WorkspaceTabFor<"prompts">>("prompt-inventory");
  return <PromptPackagesPage activeTab={activeTab} busy={null} onCreate={onCreate} onDelete={onDelete} onTabChange={setActiveTab} onUpdate={onUpdate} prompts={[prompt, secondPrompt]} />;
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
  it("uses tabs and a selected package inspector", async () => {
    const user = userEvent.setup();
    renderPage();

    expect(screen.getByRole("tab", { name: "Prompt inventory" })).toHaveAttribute("aria-selected", "true");
    expect(screen.getByRole("tab", { name: "New prompt package" })).toBeVisible();
    expect(screen.getByRole("button", { name: /Answer concisely v1/ })).toHaveAttribute("aria-pressed", "true");
    expect(screen.getByText("Answer concisely.")).toBeVisible();

    await user.click(screen.getByRole("button", { name: /Grounded answers v2/ }));
    expect(screen.getByRole("button", { name: /Grounded answers v2/ })).toHaveAttribute("aria-pressed", "true");
    expect(screen.getByText("Use only the supplied context.")).toBeVisible();
    expect(screen.getByText((_, element) => element?.tagName === "PRE" && element.textContent === "{{context}}\n{{question}}")).toBeVisible();
  });

  it("edits a package and displays protected deletion failures", async () => {
    const user = userEvent.setup();
    const onUpdate = vi.fn().mockResolvedValue({ ...prompt, system_message: "Follow the policy." });
    const onDelete = vi.fn().mockRejectedValue(new Error("Prompt package is referenced by an evaluation run"));
    vi.spyOn(window, "confirm").mockReturnValue(true);
    renderPage({ onDelete, onUpdate });

    await user.click(screen.getByRole("button", { name: "Edit prompt package" }));
    await user.clear(screen.getByLabelText("System message"));
    await user.type(screen.getByLabelText("System message"), "Follow the policy.");
    await user.click(screen.getByRole("button", { name: "Save changes" }));

    expect(onUpdate).toHaveBeenCalledWith(prompt.id, expect.objectContaining({ system_message: "Follow the policy." }));

    await user.click(screen.getByRole("button", { name: "Delete package" }));
    expect(onDelete).toHaveBeenCalledWith(prompt.id);
    expect(await screen.findByRole("alert")).toHaveTextContent("Prompt package is referenced by an evaluation run");
  });

  it("duplicates into the creation tab and creates a complete versioned payload", async () => {
    const user = userEvent.setup();
    const onCreate = vi.fn().mockResolvedValue({ ...prompt, id: "prompt-3", version: "3" });
    render(<LocaleProvider><PromptPackagesHarness onCreate={onCreate} /></LocaleProvider>);

    await user.click(screen.getByRole("button", { name: "Duplicate as new version" }));
    expect(screen.getByRole("tab", { name: "New prompt package" })).toHaveAttribute("aria-selected", "true");
    expect(screen.getByLabelText("Name")).toHaveValue(prompt.name);
    expect(screen.getByLabelText("Version")).toHaveValue("");

    await user.type(screen.getByLabelText("Version"), "3");
    await user.clear(screen.getByLabelText("System message"));
    await user.type(screen.getByLabelText("System message"), "Follow the policy.");
    await user.clear(screen.getByLabelText("Few-shot examples (JSON array)"));
    await user.click(screen.getByLabelText("Few-shot examples (JSON array)"));
    await user.paste("[]");
    await user.clear(screen.getByLabelText("Output format (JSON object)"));
    await user.click(screen.getByLabelText("Output format (JSON object)"));
    await user.paste('{"type":"json"}');
    await user.click(screen.getByRole("button", { name: "Save versioned prompt" }));

    expect(onCreate).toHaveBeenCalledWith({
      name: "Answer concisely",
      version: "3",
      prompt_type: "user_custom",
      system_message: "Follow the policy.",
      user_template: "{{question}}",
      few_shot_examples: [],
      output_format: { type: "json" },
      response_parser: null,
      scoring_rule: { type: "exact_match" },
      change_log: "Initial version.",
    });
  });

  it("blocks malformed optional JSON before calling the API", async () => {
    const user = userEvent.setup();
    const props = renderPage({ activeTab: "new-prompt-package", prompts: [] });

    await user.type(screen.getByLabelText("Name"), "Strict answers");
    await user.type(screen.getByLabelText("Version"), "1");
    await user.click(screen.getByLabelText("User template"));
    await user.paste("{{question}}");
    await user.click(screen.getByLabelText("Output format (JSON object)"));
    await user.paste("{");
    await user.click(screen.getByRole("button", { name: "Save versioned prompt" }));

    expect(await screen.findByRole("alert")).toHaveTextContent("Use valid JSON for optional configuration fields.");
    expect(props.onCreate).not.toHaveBeenCalled();
  });

  it("creates through the workspace API, returns to inventory, and refreshes it", async () => {
    const user = userEvent.setup();
    const createdPrompt = { ...prompt, id: "prompt-2", name: "New package", version: "2" };
    window.history.replaceState(null, "", "/prompts?tab=new-prompt-package");
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
    expect(await screen.findByRole("button", { name: /New package v2/ })).toBeVisible();
    expect(window.location.search).toBe("");
  });
});
