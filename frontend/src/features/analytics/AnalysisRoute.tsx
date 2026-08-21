import { type FormEvent, useEffect, useMemo, useState } from "react";

import type { FeatureRouteProps } from "../../app/types";
import { AnalysisPage } from "../../components/pages/InsightsPages";
import { datasetsApi, type Dataset } from "../datasets/api";
import { endpointsApi, type Endpoint } from "../endpoints/api";
import { runsApi, type EvaluationRun } from "../runs/api";
import { analyticsApi, type Comparison } from "./api";

export function AnalysisRoute({ activeTab, navigate, reportError }: FeatureRouteProps<"analysis">) {
  const [busy, setBusy] = useState<string | null>(null);
  const [comparison, setComparison] = useState<Comparison | null>(null);
  const [datasets, setDatasets] = useState<Dataset[]>([]);
  const [endpoints, setEndpoints] = useState<Endpoint[]>([]);
  const [runA, setRunA] = useState("");
  const [runB, setRunB] = useState("");
  const [runs, setRuns] = useState<EvaluationRun[]>([]);
  const completedRuns = useMemo(() => runs.filter((run) => run.status.startsWith("completed")), [runs]);

  useEffect(() => {
    void Promise.all([datasetsApi.list(), endpointsApi.list(), runsApi.list()]).then(([nextDatasets, nextEndpoints, nextRuns]) => {
      setDatasets(nextDatasets);
      setEndpoints(nextEndpoints);
      setRuns(nextRuns);
    }).catch(reportError);
  }, [reportError]);

  async function compareRuns(event: FormEvent) {
    event.preventDefault();
    setBusy("comparison");
    try {
      setComparison(await analyticsApi.compare(runA, runB));
    } catch (error) {
      reportError(error);
    } finally {
      setBusy(null);
    }
  }

  return <AnalysisPage activeTab={activeTab} busy={busy} comparison={comparison} completedRuns={completedRuns} datasets={datasets} endpoints={endpoints} loadScatter={analyticsApi.scatter} onRunAChange={setRunA} onRunBChange={setRunB} onSubmitComparison={compareRuns} onTabChange={(tab) => navigate("analysis", { tab })} runA={runA} runB={runB} runs={runs} />;
}
