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

function runPageProps(overrides: Partial<React.ComponentProps<typeof RunsPage>> = {}) {
  return {
    activeTab: "run-inventory" as const,
    inspector: <p>Run inspector evidence</p>,
    launcher: <p>Launch controls</p>,
    onSelect: vi.fn(),
    onTabChange: vi.fn(),
    preflight: <p>Preflight controls</p>,
    quickStartLauncher: <p>Quick start controls</p>,
    renderActions: () => <button type="button">Run action</button>,
    runs: [firstRun, secondRun],
    selectedRunId: firstRun.id,
    ...overrides,
  };
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

  it("shows only run inventory on the default tab", async () => {
    const user = userEvent.setup();
    const props = runPageProps();
    renderOperationsPage(<RunsPage {...props} />);

    expect(screen.getByRole("tab", { name: "Run inventory" })).toHaveAttribute("aria-selected", "true");
    expect(screen.getByRole("button", { name: /math-check v1/i })).toBeVisible();
    expect(screen.queryByText("Launch controls")).not.toBeInTheDocument();
    expect(screen.queryByText("Run inspector evidence")).not.toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: /code-check v1/i }));
    expect(props.onSelect).toHaveBeenCalledWith(secondRun.id);
  });

  it("shows only preflight and launchers on the launch tab", () => {
    renderOperationsPage(<RunsPage {...runPageProps({ activeTab: "launch-evaluation" })} />);

    expect(screen.getByText("Launch controls")).toBeVisible();
    expect(screen.getByText("Quick start controls")).toBeVisible();
    expect(screen.getByText("Preflight controls")).toBeVisible();
    expect(screen.queryByRole("heading", { name: "Run inventory" })).not.toBeInTheDocument();
    expect(screen.queryByText("Run inspector evidence")).not.toBeInTheDocument();
  });

  it("shows only selected evidence or guidance on the run-details tab", () => {
    const { rerender } = renderOperationsPage(<RunsPage {...runPageProps({ activeTab: "run-details" })} />);

    expect(screen.getByText("Run inspector evidence")).toBeVisible();
    expect(screen.queryByText("Launch controls")).not.toBeInTheDocument();
    expect(screen.queryByRole("heading", { name: "Run inventory" })).not.toBeInTheDocument();

    rerender(<LocaleProvider><RunsPage {...runPageProps({ activeTab: "run-details", selectedRunId: null })} /></LocaleProvider>);
    expect(screen.getByRole("heading", { name: "Select a run" })).toBeVisible();
  });
});
