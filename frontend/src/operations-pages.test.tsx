import { cleanup, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import { EvaluationRun } from "./api";
import { RunInventory, RunsPage } from "./components/pages/OperationsPages";
import { LocaleProvider } from "./i18n/LocaleProvider";

afterEach(cleanup);

const firstRun = { id: "run-1", benchmark_id: "math-check", benchmark_version: "1", completed_samples: 4, total_samples: 10, status: "running", created_at: "2026-08-08T12:00:00Z" } as EvaluationRun;
const secondRun = { ...firstRun, id: "run-2", benchmark_id: "code-check", status: "completed" } as EvaluationRun;

function renderOperationsPage(page: React.ReactNode) {
  return render(<LocaleProvider>{page}</LocaleProvider>);
}

describe("runs workspace page", () => {
  it("renders the run inventory as a persistent selection surface", async () => {
    const user = userEvent.setup();
    const onSelect = vi.fn();
    renderOperationsPage(<RunInventory onSelect={onSelect} renderActions={() => null} runs={[firstRun, secondRun]} selectedRunId={secondRun.id} />);

    expect(screen.getByRole("button", { name: /code-check v1/i })).toHaveAttribute("aria-pressed", "true");
    await user.click(screen.getByRole("button", { name: /math-check v1/i }));
    expect(onSelect).toHaveBeenCalledWith(firstRun.id);
  });

  it("keeps launch, preflight, inventory, and selected evidence together", async () => {
    const user = userEvent.setup();
    const onSelect = vi.fn();
    renderOperationsPage(<RunsPage inspector={<p>Run inspector evidence</p>} launcher={<p>Launch controls</p>} onSelect={onSelect} preflight={<p>Preflight controls</p>} quickStartLauncher={<p>Quick start controls</p>} renderActions={() => <button type="button">Run action</button>} runs={[firstRun, secondRun]} selectedRunId={firstRun.id} />);

    expect(screen.getByText("Launch controls")).toBeVisible();
    expect(screen.getByText("Quick start controls")).toBeVisible();
    expect(screen.getByText("Preflight controls")).toBeVisible();
    expect(screen.getByText("Run inspector evidence")).toBeVisible();
    await user.click(screen.getByRole("button", { name: /code-check v1/i }));
    expect(onSelect).toHaveBeenCalledWith(secondRun.id);
  });
});
