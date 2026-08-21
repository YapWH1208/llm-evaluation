import { useEffect, useMemo, useState } from "react";

import { reportsApi } from "../reports/api";
import type { SampleAttempt } from "./api";

type EvidenceMedia = { assetId: string; kind: "image" | "audio" | "video" | "file"; mimeType: string };

function evidenceMedia(attempt: SampleAttempt): EvidenceMedia[] {
  const messages = attempt.input_snapshot.messages;
  if (!Array.isArray(messages)) return [];
  const previews: EvidenceMedia[] = [];
  for (const message of messages) {
    if (!message || typeof message !== "object" || !Array.isArray((message as Record<string, unknown>).content)) continue;
    for (const part of (message as { content: unknown[] }).content) {
      if (!part || typeof part !== "object") continue;
      const record = part as Record<string, unknown>;
      const source = record.source;
      const assetId = source && typeof source === "object" ? (source as Record<string, unknown>).asset_id : null;
      if (typeof assetId === "string" && ["image", "audio", "video", "file"].includes(String(record.type)) && typeof record.mime_type === "string") {
        previews.push({ assetId, kind: record.type as EvidenceMedia["kind"], mimeType: record.mime_type });
      }
    }
  }
  return previews;
}

function EvidenceMediaPreview({ attempt }: { attempt: SampleAttempt }) {
  const media = useMemo(() => evidenceMedia(attempt), [attempt]);
  const mediaKey = media.map((item) => item.assetId).join(",");
  const [urls, setUrls] = useState<Record<string, string>>({});

  useEffect(() => {
    let disposed = false;
    const objectUrls: string[] = [];
    void Promise.all(media.map(async (item) => {
      try {
        const url = await reportsApi.assetPreview(item.assetId);
        if (disposed) { URL.revokeObjectURL(url); return null; }
        objectUrls.push(url);
        return [item.assetId, url] as const;
      } catch { return null; }
    })).then((resolved) => {
      if (!disposed) setUrls(Object.fromEntries(resolved.filter((item): item is readonly [string, string] => item !== null)));
    });
    return () => { disposed = true; objectUrls.forEach((url) => URL.revokeObjectURL(url)); };
  }, [mediaKey]);

  if (media.length === 0) return null;
  return <section className="panel"><div className="section-title"><h2>Media preview</h2><span>Fetched only after this sample is selected.</span></div><div className="media-preview">{media.map((item) => {
    const url = urls[item.assetId];
    if (!url) return <p className="muted" key={item.assetId}>Loading {item.kind} evidence…</p>;
    if (item.kind === "image") return <img key={item.assetId} src={url} alt={`Evidence asset ${item.assetId}`} />;
    if (item.kind === "audio") return <audio key={item.assetId} controls src={url}>Audio preview unavailable.</audio>;
    if (item.kind === "video") return <video key={item.assetId} controls src={url}>Video preview unavailable.</video>;
    return <a key={item.assetId} href={url} download={`evidence.${item.mimeType.split("/")[1] ?? "file"}`}>Download attached file</a>;
  })}</div></section>;
}

export function EvidenceBrowser({ attempts, busy, selectedAttempt, onLoadMore, onReview }: { attempts: SampleAttempt[]; busy: string | null; selectedAttempt: SampleAttempt | null; onLoadMore: () => Promise<void>; onReview: (attempt: SampleAttempt) => void }) {
  const [query, setQuery] = useState("");
  const [status, setStatus] = useState("all");
  const [correctness, setCorrectness] = useState("all");
  const [capability, setCapability] = useState("all");
  const [modality, setModality] = useState("all");
  const [language, setLanguage] = useState("all");
  const [difficulty, setDifficulty] = useState("all");
  const [errorKind, setErrorKind] = useState("all");
  const [judgeState, setJudgeState] = useState("all");
  const [reviewState, setReviewState] = useState("all");
  const [anomaly, setAnomaly] = useState("all");
  const [visibleCount, setVisibleCount] = useState(100);
  const options = (field: "capability" | "language" | "difficulty") => Array.from(new Set(attempts.map((attempt) => attempt.sample_metadata[field]).filter(Boolean))).sort();
  const modalities = Array.from(new Set(attempts.map((attempt) => String(attempt.input_snapshot.modality ?? "unknown")))).sort();
  const averages = {
    latency: attempts.reduce((sum, attempt) => sum + (attempt.latency_ms ?? 0), 0) / Math.max(1, attempts.filter((attempt) => attempt.latency_ms !== null).length),
    tokens: attempts.reduce((sum, attempt) => sum + (attempt.input_tokens ?? 0) + (attempt.output_tokens ?? 0), 0) / Math.max(1, attempts.length),
    cost: attempts.reduce((sum, attempt) => sum + (attempt.estimated_cost ?? 0), 0) / Math.max(1, attempts.length),
  };
  const filtered = useMemo(() => attempts.filter((attempt) => {
    const searchable = `${attempt.sample_id} ${attempt.parsed_prediction ?? ""} ${attempt.error_type ?? ""} ${attempt.error_message ?? ""}`.toLowerCase();
    const apiError = (attempt.error_type ?? "").startsWith("http_") || ["timeout", "connection_error"].includes(attempt.error_type ?? "");
    const tokens = (attempt.input_tokens ?? 0) + (attempt.output_tokens ?? 0);
    const anomalous = anomaly === "all" || (anomaly === "latency" && (attempt.latency_ms ?? 0) > averages.latency * 2) || (anomaly === "tokens" && tokens > averages.tokens * 2) || (anomaly === "cost" && (attempt.estimated_cost ?? 0) > averages.cost * 2);
    return (status === "all" || attempt.status === status) && (correctness === "all" || (correctness === "correct" && attempt.score === 1) || (correctness === "incorrect" && attempt.score !== 1)) && (capability === "all" || attempt.sample_metadata.capability === capability) && (modality === "all" || String(attempt.input_snapshot.modality ?? "unknown") === modality) && (language === "all" || attempt.sample_metadata.language === language) && (difficulty === "all" || attempt.sample_metadata.difficulty === difficulty) && (errorKind === "all" || (errorKind === "api" && apiError) || (errorKind === "parser" && attempt.error_type === "response_parse_error") || (errorKind === "any" && Boolean(attempt.error_type))) && (judgeState === "all" || (judgeState === "disagreement" && attempt.judge_disagreement) || (judgeState === "agreement" && !attempt.judge_disagreement)) && (reviewState === "all" || attempt.human_review_status === reviewState) && anomalous && searchable.includes(query.trim().toLowerCase());
  }), [anomaly, attempts, averages.cost, averages.latency, averages.tokens, capability, correctness, difficulty, errorKind, judgeState, language, modality, query, reviewState, status]);
  const visible = filtered.slice(0, visibleCount);
  const resetPage = () => setVisibleCount(100);

  return <>
    <section className="panel"><div className="section-title"><h2>Sample evidence</h2><span>{filtered.length}/{attempts.length} attempts</span></div>{attempts.length === 0 ? <p className="empty">This run has no saved attempts yet.</p> : <>
      <div className="comparison-form" style={{ marginBottom: "1.5rem" }}>
        <label>Search samples<input value={query} onChange={(event) => { setQuery(event.target.value); resetPage(); }} placeholder="sample, prediction, error" /></label>
        <label>Status<select value={status} onChange={(event) => { setStatus(event.target.value); resetPage(); }}><option value="all">All states</option><option value="succeeded">Succeeded</option><option value="failed">Failed</option><option value="pending">Pending</option><option value="running">Running</option></select></label>
        <label>Correctness<select value={correctness} onChange={(event) => { setCorrectness(event.target.value); resetPage(); }}><option value="all">All</option><option value="correct">Correct</option><option value="incorrect">Incorrect</option></select></label>
        <label>Capability<select value={capability} onChange={(event) => { setCapability(event.target.value); resetPage(); }}><option value="all">All</option>{options("capability").map((item) => <option value={item} key={item}>{item}</option>)}</select></label>
        <label>Modality<select value={modality} onChange={(event) => { setModality(event.target.value); resetPage(); }}><option value="all">All</option>{modalities.map((item) => <option value={item} key={item}>{item}</option>)}</select></label>
        <label>Language<select value={language} onChange={(event) => { setLanguage(event.target.value); resetPage(); }}><option value="all">All</option>{options("language").map((item) => <option value={item} key={item}>{item}</option>)}</select></label>
        <label>Difficulty<select value={difficulty} onChange={(event) => { setDifficulty(event.target.value); resetPage(); }}><option value="all">All</option>{options("difficulty").map((item) => <option value={item} key={item}>{item}</option>)}</select></label>
        <label>Error type<select value={errorKind} onChange={(event) => { setErrorKind(event.target.value); resetPage(); }}><option value="all">All</option><option value="any">Any error</option><option value="api">API error</option><option value="parser">Parser error</option></select></label>
        <label>Judge<select value={judgeState} onChange={(event) => { setJudgeState(event.target.value); resetPage(); }}><option value="all">All</option><option value="disagreement">Disagreement</option><option value="agreement">No disagreement</option></select></label>
        <label>Human review<select value={reviewState} onChange={(event) => { setReviewState(event.target.value); resetPage(); }}><option value="all">All</option><option value="unreviewed">Unreviewed</option><option value="reviewed">Reviewed</option><option value="adjudicated">Adjudicated</option></select></label>
        <label>Anomaly<select value={anomaly} onChange={(event) => { setAnomaly(event.target.value); resetPage(); }}><option value="all">None</option><option value="latency">Latency &gt; 2× mean</option><option value="tokens">Tokens &gt; 2× mean</option><option value="cost">Cost &gt; 2× mean</option></select></label>
      </div>
      {visible.length === 0 ? <p className="empty">No samples match these filters.</p> : <div className="evidence-list">{visible.map((attempt) => <details className="attempt evidence-row" key={attempt.id}><summary><span className="evidence-sample"><strong>{attempt.sample_id} · attempt {attempt.attempt_number}</strong></span><span className="evidence-status"><span className={`badge ${attempt.status}`}>{attempt.status}</span></span><span className="evidence-context">{attempt.sample_metadata.capability ?? "unclassified"} · {attempt.sample_metadata.language ?? "unknown"}</span><span className="evidence-score">score {attempt.score ?? "--"}</span><span className="evidence-performance">{attempt.latency_ms ?? "--"} ms · {attempt.input_tokens ?? "--"}/{attempt.output_tokens ?? "--"} tokens</span><span className="evidence-cost">{attempt.estimated_cost ?? "--"}</span><span className="evidence-error">{attempt.error_type ?? ""}</span></summary><div className="evidence"><pre>{JSON.stringify({ input: attempt.input_snapshot, request: attempt.request_snapshot, reference: attempt.reference_snapshot, prediction: attempt.parsed_prediction, metadata: attempt.sample_metadata, judge_disagreement: attempt.judge_disagreement, human_review_status: attempt.human_review_status }, null, 2)}</pre><pre>{attempt.raw_response ?? attempt.error_message ?? "No response captured."}</pre></div><div className="actions"><button className="secondary" onClick={() => onReview(attempt)}>Human review</button></div></details>)}</div>}
      {visible.length < filtered.length && <div className="actions"><button className="secondary" onClick={() => setVisibleCount((value) => value + 100)}>Load next 100 samples</button></div>}
    </>}</section>
    <div className="actions"><button className="secondary" disabled={busy === "attempts-more"} onClick={() => void onLoadMore()}>{busy === "attempts-more" ? "Loading next page…" : "Load next evidence page"}</button></div>
    {selectedAttempt && <EvidenceMediaPreview attempt={selectedAttempt} />}
  </>;
}
