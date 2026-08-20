import { cleanup, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import App from "./App";
import { api, SampleAttempt } from "./shared/api";
import { LocaleProvider } from "./i18n/LocaleProvider";

afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
  window.history.replaceState(null, "", "/dashboard");
});

function deferred<T>() {
  let resolve!: (value: T) => void;
  const promise = new Promise<T>((resolvePromise) => {
    resolve = resolvePromise;
  });
  return { promise, resolve };
}

const firstAttempt = {
  id: "attempt-a",
  sample_id: "sample-7",
  attempt_number: 1,
  status: "succeeded",
  input_snapshot: { modality: "text" },
  reference_snapshot: {},
  request_snapshot: null,
  raw_response: null,
  parsed_prediction: "42",
  score: 1,
  latency_ms: 120,
  input_tokens: 30,
  output_tokens: 20,
  estimated_cost: 0.001,
  error_type: null,
  error_message: null,
  created_at: "2026-08-08T12:00:00Z",
  completed_at: "2026-08-08T12:00:01Z",
  sample_metadata: {},
  judge_disagreement: false,
  human_review_status: "unreviewed",
} as SampleAttempt;
const secondAttempt = { ...firstAttempt, id: "attempt-b", sample_id: "sample-9" } as SampleAttempt;

describe("review run switching", () => {
  it("clears the previous run's samples while the next run's attempts load", async () => {
    const user = userEvent.setup();
    const secondAttempts = deferred<SampleAttempt[]>();
    vi.spyOn(api, "listEndpoints").mockResolvedValue([]);
    vi.spyOn(api, "listRuns").mockResolvedValue([
      { id: "run-a", benchmark_id: "math-check", benchmark_version: "1", status: "completed", created_at: "2026-08-08T12:00:00Z", completed_at: "2026-08-08T12:05:00Z" },
      { id: "run-b", benchmark_id: "code-check", benchmark_version: "1", status: "completed", created_at: "2026-08-08T13:00:00Z", completed_at: "2026-08-08T13:05:00Z" },
    ] as never);
    vi.spyOn(api, "dashboard").mockResolvedValue(null as never);
    vi.spyOn(api, "listPromptPackages").mockResolvedValue([]);
    vi.spyOn(api, "listDatasets").mockResolvedValue([]);
    vi.spyOn(api, "listBenchmarks").mockResolvedValue([]);
    vi.spyOn(api, "listTasks").mockResolvedValue([]);
    vi.spyOn(api, "analyticsMatrix").mockResolvedValue(null as never);
    vi.spyOn(api, "systemHealth").mockResolvedValue(null as never);
    vi.spyOn(api, "listAttempts")
      .mockResolvedValueOnce([firstAttempt] as never)
      .mockReturnValue(secondAttempts.promise as never);
    vi.spyOn(api, "getRunSummary").mockResolvedValue(null as never);
    vi.spyOn(api, "listReports").mockResolvedValue([]);
    vi.spyOn(api, "listRunLogs").mockResolvedValue([]);
    vi.spyOn(api, "listRunMetrics").mockResolvedValue([]);

    render(<LocaleProvider><App /></LocaleProvider>);
    await user.click(screen.getByRole("link", { name: "Runs" }));
    await user.click(screen.getByRole("button", { name: /math-check v1/ }));
    await user.click(screen.getByRole("tab", { name: "Evidence" }));
    await waitFor(() => expect(screen.getByText(/sample-7 · attempt 1/)).toBeInTheDocument());

    await user.click(screen.getByRole("tab", { name: "Run inventory" }));
    await user.click(screen.getByRole("button", { name: /code-check v1/ }));
    await user.click(screen.getByRole("tab", { name: "Evidence" }));

    expect(screen.queryByText(/sample-7 · attempt 1/)).not.toBeInTheDocument();

    secondAttempts.resolve([secondAttempt]);
    await waitFor(() => expect(screen.getByText(/sample-9 · attempt 1/)).toBeInTheDocument());
  }, 10_000);
});
