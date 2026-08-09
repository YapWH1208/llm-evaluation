import { cleanup, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import App from "./App";
import { api, SampleAttempt } from "./api";
import { LocaleProvider } from "./i18n/LocaleProvider";

afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
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
    vi.spyOn(api, "listSuites").mockResolvedValue([]);
    vi.spyOn(api, "listBenchmarks").mockResolvedValue([]);
    vi.spyOn(api, "listTasks").mockResolvedValue([]);
    vi.spyOn(api, "analyticsMatrix").mockResolvedValue(null as never);
    vi.spyOn(api, "listUsers").mockResolvedValue([]);
    vi.spyOn(api, "listAuditEvents").mockResolvedValue([]);
    vi.spyOn(api, "systemHealth").mockResolvedValue(null as never);
    vi.spyOn(api, "listAttempts")
      .mockResolvedValueOnce([firstAttempt] as never)
      .mockReturnValue(secondAttempts.promise as never);
    vi.spyOn(api, "getRunSummary").mockResolvedValue(null as never);
    vi.spyOn(api, "listReports").mockResolvedValue([]);
    vi.spyOn(api, "listRunLogs").mockResolvedValue([]);

    render(<LocaleProvider><App /></LocaleProvider>);
    await user.click(screen.getByRole("button", { name: "Human review" }));
    await waitFor(() => expect(screen.getByLabelText("Review run")).toBeEnabled());

    await user.selectOptions(screen.getByLabelText("Review run"), "run-a");
    await waitFor(() => expect(screen.getByRole("option", { name: /sample-7/ })).toBeInTheDocument());

    await user.selectOptions(screen.getByLabelText("Review run"), "run-b");

    expect(screen.getByLabelText("Review sample")).toBeDisabled();
    expect(screen.queryByRole("option", { name: /sample-7/ })).not.toBeInTheDocument();

    secondAttempts.resolve([secondAttempt]);
    await waitFor(() => expect(screen.getByRole("option", { name: /sample-9/ })).toBeInTheDocument());
    expect(screen.getByLabelText("Review sample")).toBeEnabled();
  }, 10_000);
});
