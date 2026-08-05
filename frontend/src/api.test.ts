import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { api } from "./api";

describe("authenticated browser transport", () => {
  beforeEach(() => {
    api.setBearerToken("browser-token");
    vi.stubGlobal("fetch", vi.fn());
    vi.stubGlobal("URL", { createObjectURL: vi.fn(() => "blob:report"), revokeObjectURL: vi.fn() });
  });

  afterEach(() => vi.unstubAllGlobals());

  it("sends the bearer token when downloading a protected report", async () => {
    vi.mocked(fetch).mockResolvedValue(new Response("report", { status: 200 }));

    await expect(api.downloadReport("report-id")).resolves.toBe("blob:report");
    expect(fetch).toHaveBeenCalledWith("http://127.0.0.1:8000/api/v1/reports/report-id/download", {
      headers: { Authorization: "Bearer browser-token" },
    });
  });

  it("opens the run event stream with the bearer token", async () => {
    const body = new ReadableStream<Uint8Array>({
      start(controller) {
        controller.enqueue(new TextEncoder().encode("event: run\\ndata: {}\\n\\n"));
        controller.close();
      },
    });
    vi.mocked(fetch).mockResolvedValue({ ok: true, body } as Response);
    const close = api.subscribeToRunEvents("run-id", vi.fn());

    await vi.waitFor(() => expect(fetch).toHaveBeenCalledOnce());
    expect(fetch).toHaveBeenCalledWith("http://127.0.0.1:8000/api/v1/evaluation-runs/run-id/events", expect.objectContaining({
      headers: expect.objectContaining({ Authorization: "Bearer browser-token", Accept: "text/event-stream" }),
    }));
    close();
  });

  it("submits a public share password in a header rather than a URL", async () => {
    api.setBearerToken("");
    vi.mocked(fetch).mockResolvedValue(new Response("report", { status: 200 }));

    await api.openSharedReport("share-token", "share-password");
    expect(fetch).toHaveBeenCalledWith("http://127.0.0.1:8000/shared-reports/share-token", {
      headers: { "X-Report-Password": "share-password" },
    });
  });

  it("creates a dataset evaluation run", async () => {
    api.setBearerToken("");
    vi.mocked(fetch).mockResolvedValue(new Response(JSON.stringify({ id: "run-1", benchmark_id: "dataset-evaluation", total_samples: 2, status: "queued" }), { status: 201, headers: { "Content-Type": "application/json" } }));
    const body = { model_endpoint_id: "ep-1", dataset_version_id: "ds-1", reference_field: "answer", sample_limit: 100 };
    const run = await api.createDatasetRun(body);
    expect(run.id).toBe("run-1");
    expect(fetch).toHaveBeenCalledWith("http://127.0.0.1:8000/api/v1/evaluation-runs/dataset", expect.objectContaining({ method: "POST", body: JSON.stringify(body) }));
  });
});
