import { cleanup, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import type { Dataset, Endpoint, LeaderboardQuery, LeaderboardResponse, LeaderboardRow } from "./api";
import { LeaderboardPage } from "./components/pages/LeaderboardPage";
import { LocaleProvider } from "./i18n/LocaleProvider";

afterEach(cleanup);

const completedRow: LeaderboardRow = {
  run_id: "run-1",
  display_name: "model-a_math-check_20260808T120000Z",
  model_endpoint_id: "endpoint-1",
  model_name: "model-a",
  dataset: "math-check",
  benchmark_id: "math-check",
  benchmark_version: "1",
  status: "completed",
  created_at: "2026-08-08T12:00:00Z",
  completed_at: "2026-08-08T12:05:00Z",
  capabilities: ["reasoning"],
  languages: ["en"],
  evaluation_type: "classification",
  score: .92,
  primary_metric: "score",
  average_latency_ms: 210,
  p95_latency_ms: 340,
  estimated_cost: .04,
  sample_count: 100,
  completed_samples: 100,
  successful_samples: 98,
  failed_samples: 2,
  available_metrics: ["score", "f1_macro"],
  named_metrics: {
    f1_macro: { metric_name: "f1_macro", label: "Macro F1", unit: "ratio", value: .9, sample_count: 100, availability_reason: null },
  },
};

const queuedRow: LeaderboardRow = {
  ...completedRow,
  run_id: "run-2",
  display_name: "model-b_math-check_20260809T120000Z",
  model_endpoint_id: "endpoint-2",
  model_name: "model-b",
  status: "queued",
  completed_at: null,
  score: null,
  average_latency_ms: null,
  p95_latency_ms: null,
  estimated_cost: null,
  completed_samples: 0,
  successful_samples: 0,
  failed_samples: 0,
  available_metrics: [],
  named_metrics: {},
};

const endpoints = [
  { id: "endpoint-1", display_name: "Model A", model_name: "model-a" },
  { id: "endpoint-2", display_name: "Model B", model_name: "model-b" },
] as Endpoint[];

const datasets = [{ dataset_id: "math-check", capabilities: ["reasoning"], languages: ["en"], evaluation_type: "classification" }] as Dataset[];

function response(query: LeaderboardQuery = {}): LeaderboardResponse {
  return {
    items: [completedRow, queuedRow],
    total: 52,
    page: query.page ?? 1,
    page_size: query.page_size ?? 50,
    total_pages: 2,
    sort: query.sort ?? "default",
    direction: query.direction ?? "desc",
  };
}

function renderLeaderboard(loadLeaderboard = vi.fn((query: LeaderboardQuery) => Promise.resolve(response(query)))) {
  const onInspectRun = vi.fn();
  render(<LocaleProvider><LeaderboardPage datasets={datasets} endpoints={endpoints} loadLeaderboard={loadLeaderboard} onInspectRun={onInspectRun} /></LocaleProvider>);
  return { loadLeaderboard, onInspectRun };
}

describe("leaderboard workspace", () => {
  it("loads a bounded ranked page and keeps incomplete runs explicitly unscored", async () => {
    const { loadLeaderboard } = renderLeaderboard();

    await waitFor(() => expect(loadLeaderboard).toHaveBeenCalledWith({ page: 1, page_size: 50 }));
    expect(screen.getByRole("heading", { level: 1, name: "Leaderboard" })).toBeVisible();
    expect(screen.getByText(/completed and scored runs rank first/i)).toBeVisible();
    expect(screen.getByRole("row", { name: /model-a_math-check.*92%.*340 ms/i })).toBeVisible();
    expect(screen.getByRole("row", { name: /model-b_math-check.*queued.*N\/A/i })).toBeVisible();
    expect(screen.getAllByText("52 runs")).toHaveLength(2);
  });

  it("combines every filter, exposes removable chips, and resets to the bounded default", async () => {
    const user = userEvent.setup();
    const { loadLeaderboard } = renderLeaderboard();
    await screen.findByRole("row", { name: /model-a_math-check/i });

    await user.selectOptions(screen.getByLabelText("Dataset"), "math-check");
    await user.selectOptions(screen.getByLabelText("Model"), "endpoint-1");
    await user.click(screen.getByRole("checkbox", { name: "completed" }));
    await user.type(screen.getByLabelText("From date"), "2026-08-01");
    await user.type(screen.getByLabelText("To date"), "2026-08-31");
    await user.selectOptions(screen.getByLabelText("Capability"), "reasoning");
    await user.selectOptions(screen.getByLabelText("Language"), "en");
    await user.selectOptions(screen.getByLabelText("Evaluation type"), "classification");
    await user.selectOptions(screen.getByLabelText("Available metric"), "f1_macro");
    await user.click(screen.getByRole("button", { name: "Apply filters" }));

    await waitFor(() => expect(loadLeaderboard).toHaveBeenLastCalledWith({
      dataset: "math-check",
      model_endpoint_id: "endpoint-1",
      statuses: ["completed"],
      created_from: "2026-08-01T00:00:00Z",
      created_to: "2026-08-31T23:59:59.999Z",
      capability: "reasoning",
      language: "en",
      evaluation_type: "classification",
      available_metric: "f1_macro",
      page: 1,
      page_size: 50,
    }));
    expect(screen.getByRole("button", { name: "Remove Dataset: math-check" })).toBeVisible();

    await user.click(screen.getByRole("button", { name: "Reset filters" }));
    await waitFor(() => expect(loadLeaderboard).toHaveBeenLastCalledWith({ page: 1, page_size: 50 }));
  });

  it("sorts in both directions, paginates on the server, and opens immutable run detail links", async () => {
    const user = userEvent.setup();
    const { loadLeaderboard, onInspectRun } = renderLeaderboard();
    await screen.findByRole("row", { name: /model-a_math-check/i });

    await user.click(screen.getByRole("button", { name: "Sort by Score descending" }));
    await waitFor(() => expect(loadLeaderboard).toHaveBeenLastCalledWith({ sort: "score", direction: "desc", page: 1, page_size: 50 }));
    expect(screen.getByRole("columnheader", { name: /Score/ })).toHaveAttribute("aria-sort", "descending");

    await user.click(screen.getByRole("button", { name: "Sort by Score ascending" }));
    await waitFor(() => expect(loadLeaderboard).toHaveBeenLastCalledWith({ sort: "score", direction: "asc", page: 1, page_size: 50 }));

    await user.click(screen.getByRole("button", { name: "Next page" }));
    await waitFor(() => expect(loadLeaderboard).toHaveBeenLastCalledWith({ sort: "score", direction: "asc", page: 2, page_size: 50 }));

    const detailLink = screen.getByRole("link", { name: "Inspect model-a_math-check_20260808T120000Z" });
    expect(detailLink).toHaveAttribute("href", "/runs?tab=run-details&run=run-1");
    await user.click(detailLink);
    expect(onInspectRun).toHaveBeenCalledWith("run-1");
  });

  it("keeps loading, errors, retry, and empty results explicit", async () => {
    const loadLeaderboard = vi.fn().mockRejectedValueOnce(new Error("Leaderboard unavailable")).mockResolvedValueOnce({ ...response(), items: [], total: 0, total_pages: 0 });
    const user = userEvent.setup();
    renderLeaderboard(loadLeaderboard);

    expect(await screen.findByRole("alert")).toHaveTextContent("Leaderboard unavailable");
    await user.click(screen.getByRole("button", { name: "Retry" }));
    expect(await screen.findByText("No runs match the current filters.")).toBeVisible();
  });
});
