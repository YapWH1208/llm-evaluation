import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { analyticsApi } from "./features/analytics/api";
import { datasetsApi } from "./features/datasets/api";
import { reportsApi } from "./features/reports/api";
import { runsApi } from "./features/runs/api";

describe("browser transport", () => {
  beforeEach(() => {
    vi.stubGlobal("fetch", vi.fn());
    vi.stubGlobal("URL", { createObjectURL: vi.fn(() => "blob:report"), revokeObjectURL: vi.fn() });
  });

  afterEach(() => vi.unstubAllGlobals());

  it("downloads a report artifact", async () => {
    vi.mocked(fetch).mockResolvedValue(new Response("report", { status: 200 }));

    await expect(reportsApi.download("report-id")).resolves.toBe("blob:report");
    expect(fetch).toHaveBeenCalledWith("http://127.0.0.1:8000/api/v1/reports/report-id/download");
  });

  it("opens the run event stream", async () => {
    const body = new ReadableStream<Uint8Array>({
      start(controller) {
        controller.enqueue(new TextEncoder().encode("event: run\ndata: {}\n\n"));
        controller.close();
      },
    });
    vi.mocked(fetch).mockResolvedValue({ ok: true, body } as Response);
    const close = runsApi.subscribe("run-id", vi.fn());

    await vi.waitFor(() => expect(fetch).toHaveBeenCalledOnce());
    expect(fetch).toHaveBeenCalledWith("http://127.0.0.1:8000/api/v1/evaluation-runs/run-id/events", expect.objectContaining({
      headers: expect.objectContaining({ Accept: "text/event-stream" }),
    }));
    close();
  });

  it("submits a public share password in a header rather than a URL", async () => {
    vi.mocked(fetch).mockResolvedValue(new Response("report", { status: 200 }));

    await reportsApi.openShared("share-token", "share-password");
    expect(fetch).toHaveBeenCalledWith("http://127.0.0.1:8000/shared-reports/share-token", {
      headers: { "X-Report-Password": "share-password" },
    });
  });

  it("creates a dataset evaluation run", async () => {
    vi.mocked(fetch).mockResolvedValue(new Response(JSON.stringify({ id: "run-1", benchmark_id: "dataset-evaluation", total_samples: 2, status: "queued" }), { status: 201, headers: { "Content-Type": "application/json" } }));
    const body = { model_endpoint_id: "ep-1", dataset_version_id: "ds-1", reference_field: "answer", sample_limit: 100 };
    const run = await runsApi.createDataset(body);
    expect(run.id).toBe("run-1");
    expect(fetch).toHaveBeenCalledWith("http://127.0.0.1:8000/api/v1/evaluation-runs/dataset", expect.objectContaining({ method: "POST", body: JSON.stringify(body) }));
  });

  it("previews, updates, and deletes dataset versions", async () => {
    vi.mocked(fetch)
      .mockResolvedValueOnce(new Response(JSON.stringify({ fields: ["q"], rows: [{ q: "?" }] }), { status: 200, headers: { "Content-Type": "application/json" } }))
      .mockResolvedValueOnce(new Response(JSON.stringify({ id: "ds-1", dataset_id: "x", version: "1", revision: "default", input_field: "q", reference_field: "a" }), { status: 200, headers: { "Content-Type": "application/json" } }))
      .mockResolvedValueOnce(new Response(JSON.stringify({ id: "ds-1" }), { status: 200, headers: { "Content-Type": "application/json" } }));
    const preview = await datasetsApi.preview("ds-1", 3);
    expect(preview.rows).toEqual([{ q: "?" }]);
    expect(fetch).toHaveBeenCalledWith("http://127.0.0.1:8000/api/v1/datasets/ds-1/preview?limit=3", expect.any(Object));

    const updated = await datasetsApi.update("ds-1", { dataset_id: "x", version: "1" });
    expect(updated.input_field).toBe("q");
    expect(fetch).toHaveBeenCalledWith("http://127.0.0.1:8000/api/v1/datasets/ds-1", expect.objectContaining({ method: "PUT", body: JSON.stringify({ dataset_id: "x", version: "1" }) }));

    await datasetsApi.remove("ds-1");
    expect(fetch).toHaveBeenCalledWith("http://127.0.0.1:8000/api/v1/datasets/ds-1", expect.objectContaining({ method: "DELETE" }));
  });

  it("encodes scatter axes and repeated run/status filters", async () => {
    vi.mocked(fetch).mockResolvedValue(new Response(JSON.stringify({
      x_axis: { metric_name: "score", label: "Primary score", unit: "ratio", profile: "all" },
      y_axis: { metric_name: "p95_latency_ms", label: "p95 latency", unit: "milliseconds", profile: "operational" },
      selected_run_ids: [], eligible_run_count: 0, plottable_count: 0, plotted_count: 0,
      unavailable_count: 0, unavailable_by_axis: { x: 0, y: 0, both: 0 }, unavailable_reasons: [],
      truncated_count: 0, max_points: 500, points: [],
    }), { status: 200, headers: { "Content-Type": "application/json" } }));

    await analyticsApi.scatter({
      x_axis: "score",
      y_axis: "p95_latency_ms",
      run_ids: ["run-a", "run-b"],
      statuses: ["completed", "failed"],
      min_score: 0.5,
      max_cost: 0.1,
    });

    expect(fetch).toHaveBeenCalledWith(
      "http://127.0.0.1:8000/api/v1/analytics/scatter?x_axis=score&y_axis=p95_latency_ms&run_ids=run-a&run_ids=run-b&status=completed&status=failed&min_score=0.5&max_cost=0.1",
      expect.any(Object),
    );
  });

  it("encodes leaderboard filters, ordering, and pagination", async () => {
    vi.mocked(fetch).mockResolvedValue(new Response(JSON.stringify({
      items: [], total: 0, page: 2, page_size: 25, total_pages: 0, sort: "score", direction: "desc",
    }), { status: 200, headers: { "Content-Type": "application/json" } }));

    await analyticsApi.leaderboard({
      dataset: "dataset-a",
      model_endpoint_id: "endpoint-a",
      statuses: ["completed", "completed_with_errors"],
      capability: "reasoning",
      language: "en",
      evaluation_type: "classification",
      available_metric: "f1_macro",
      sort: "score",
      direction: "desc",
      page: 2,
      page_size: 25,
    });

    expect(fetch).toHaveBeenCalledWith(
      "http://127.0.0.1:8000/api/v1/leaderboard?dataset=dataset-a&model_endpoint_id=endpoint-a&status=completed&status=completed_with_errors&capability=reasoning&language=en&evaluation_type=classification&available_metric=f1_macro&sort=score&direction=desc&page=2&page_size=25",
      expect.any(Object),
    );
  });

  it("loads named metrics for a selected run", async () => {
    vi.mocked(fetch).mockResolvedValue(new Response(JSON.stringify([]), { status: 200, headers: { "Content-Type": "application/json" } }));

    await runsApi.metrics("run/with spaces");

    expect(fetch).toHaveBeenCalledWith(
      "http://127.0.0.1:8000/api/v1/analytics/runs/run%2Fwith%20spaces/metrics",
      expect.any(Object),
    );
  });
});
