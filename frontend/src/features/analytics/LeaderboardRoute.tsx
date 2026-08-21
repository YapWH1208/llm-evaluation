import { useEffect, useState } from "react";

import type { FeatureRouteProps } from "../../app/types";
import { LeaderboardPage } from "../../components/pages/LeaderboardPage";
import { datasetsApi, type Dataset } from "../datasets/api";
import { endpointsApi, type Endpoint } from "../endpoints/api";
import { analyticsApi } from "./api";

export function LeaderboardRoute({ navigate, reportError }: FeatureRouteProps<"leaderboard">) {
  const [datasets, setDatasets] = useState<Dataset[]>([]);
  const [endpoints, setEndpoints] = useState<Endpoint[]>([]);

  useEffect(() => {
    void Promise.all([datasetsApi.list(), endpointsApi.list()]).then(([nextDatasets, nextEndpoints]) => {
      setDatasets(nextDatasets);
      setEndpoints(nextEndpoints);
    }).catch(reportError);
  }, [reportError]);

  return <LeaderboardPage datasets={datasets} endpoints={endpoints} loadLeaderboard={analyticsApi.leaderboard} onInspectRun={(runId) => navigate("runs", { runId, tab: "run-details" })} />;
}
