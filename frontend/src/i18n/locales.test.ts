import { describe, expect, it } from "vitest";

import * as catalogModule from "./catalog";
import { catalogs, isLocale, localeIds, navigationCopy, overviewCopy, resolveLocale } from "./catalog";
import { hasExplicitStaticTranslation, staticSourceTexts, translateStaticTemplate, translateStaticText } from "./operationalCopy";

const analyticsOverviewKeys = [
  "dashboardTitle",
  "dashboardDescription",
  "performanceSummary",
  "successRate",
  "evaluationTrend",
  "limitedHistory",
  "noHistory",
  "modelBenchmarkComparison",
  "model",
  "benchmark",
  "sampleCount",
  "latencyCostErrors",
  "latency",
  "cost",
  "errorRate",
  "recentEvaluations",
  "progress",
  "started",
  "systemReadiness",
  "operational",
  "attentionNeeded",
  "unknownValue",
] as const;

const datasetMetricKeys = [
  "datasetRun.metric",
  "datasetRun.metricDefault",
  "datasetRun.metricExactMatch",
  "datasetRun.metricNormalizedExactMatch",
  "datasetRun.metricTokenF1",
  "datasetRun.metricBleu",
  "datasetRun.metricRougeL",
  "datasetRun.metricDefaultHint",
  "datasetRun.metricOverrideHint",
  "datasetRun.effectiveMetric",
] as const;

describe("workspace locale catalog", () => {
  it("provides the approved page-tab structure in every shipped locale", () => {
    const tabCopy = (catalogModule as typeof catalogModule & {
      workspacePageTabCopy?: Record<string, Record<string, Record<string, string>>>;
    }).workspacePageTabCopy;
    const expectedKeys = {
      dashboard: ["summary", "evaluations", "readiness"],
      guide: ["gettingStarted", "prepareData", "runAndAnalyze"],
      models: ["modelInventory", "addEndpoint", "inventoryDescription", "endpointDescription"],
      datasets: ["datasetInventory", "registerDataset"],
      runs: ["runInventory", "launchEvaluation", "runDetails"],
      analysis: ["evidenceMatrix", "compareRuns"],
      settings: ["health", "access", "preferences"],
    };

    expect(tabCopy?.en).toEqual(expect.objectContaining({
      dashboard: { summary: "Summary", evaluations: "Evaluations", readiness: "Readiness" },
      models: expect.objectContaining({ modelInventory: "Model inventory", addEndpoint: "Add endpoint" }),
      runs: { runInventory: "Run inventory", launchEvaluation: "Launch evaluation", runDetails: "Run details" },
    }));
    for (const locale of localeIds) {
      const localizedCopy = tabCopy?.[locale] as Record<string, Record<string, string>> | undefined;
      expect(Object.keys(localizedCopy ?? {})).toEqual(Object.keys(expectedKeys));
      for (const [page, keys] of Object.entries(expectedKeys)) {
        expect(Object.keys(localizedCopy?.[page] ?? {})).toEqual(keys);
        expect(Object.values(localizedCopy?.[page] ?? {}).every((value) => value.trim().length > 0)).toBe(true);
      }
    }
  });

  it("ships the requested locales with the complete English key set", () => {
    expect(localeIds).toEqual(["en", "zh-CN", "fr", "de", "ru", "ja", "ko", "ms"]);
    const englishKeys = Object.keys(catalogs.en).sort();

    for (const locale of localeIds) {
      expect(Object.keys(catalogs[locale]).sort()).toEqual(englishKeys);
      expect(Object.values(catalogs[locale]).every(Boolean)).toBe(true);
    }
  });

  it("accepts only shipped locale identifiers and falls back to English", () => {
    expect(isLocale("fr")).toBe(true);
    expect(isLocale("es")).toBe(false);
    expect(resolveLocale("zh-CN")).toBe("zh-CN");
    expect(resolveLocale("unsupported")).toBe("en");
    expect(resolveLocale(null)).toBe("en");
  });

  it("keeps corrected French operational language and localized templates intact", () => {
    expect(navigationCopy.fr.items.runs).toEqual({ label: "Exécutions", description: "Exécution, résultats et preuves" });
    expect(overviewCopy.fr.workers).toBe("Agents");
    expect(translateStaticTemplate("fr", "configured")).toBe("configuré");
    expect(translateStaticTemplate("ja", "{{benchmark}} queued with an immutable configuration snapshot.", { benchmark: "benchmark-a" })).toContain("benchmark-a");
    expect(translateStaticTemplate("ja", "{{benchmark}} queued with an immutable configuration snapshot.", { benchmark: "benchmark-a" })).not.toContain("queued");
  });

  it("provides non-empty analytics dashboard terminology in every shipped locale", () => {
    for (const locale of localeIds) {
      for (const key of analyticsOverviewKeys) {
        expect(overviewCopy[locale][key].trim(), `${locale}.${key}`).not.toBe("");
      }
    }
  });

  it("provides every dataset scoring metric label in each shipped locale", () => {
    for (const locale of localeIds) {
      for (const key of datasetMetricKeys) {
        expect(catalogs[locale][key].trim(), `${locale}.${key}`).not.toBe("");
      }
    }
  });

  it("keeps redesigned workspace labels eligible for the static-copy bridge", () => {
    const workspaceLabels = [
      "Operating guidance",
      "Find run", "Benchmark, status, or ID", "Run status", "No runs match the current filters.",
      "Pause download", "Validate cache", "Clear cache", "Retry download", "Upload local revision",
      "Loading disk usage…", "Comparing…", "total runs",
    ];

    for (const locale of localeIds.filter((locale) => locale !== "en")) {
      for (const label of workspaceLabels) {
        expect(translateStaticText(locale, label), `${locale}: ${label}`).not.toBe(label);
      }
    }
  });

  it("renders redesigned workspace descriptions as complete locale phrases", () => {
    const description = "Register endpoints, validate connectivity, and keep new-run defaults close to the models they govern.";

    expect(translateStaticText("zh-CN", description)).toBe("注册端点、验证连接，并让新运行的默认设置贴近其所管理的模型。");
    expect(translateStaticText("fr", description)).toBe("Enregistrez les points de terminaison, validez la connectivité et conservez les paramètres par défaut des nouvelles exécutions près des modèles qu’ils régissent.");
    expect(translateStaticText("de", description)).toBe("Registrieren Sie Endpunkte, prüfen Sie die Verbindung und halten Sie die Standardwerte für neue Ausführungen bei den Modellen, für die sie gelten.");
    expect(translateStaticText("ru", description)).toBe("Зарегистрируйте конечные точки, проверьте подключение и храните параметры по умолчанию для новых запусков рядом с моделями, которыми они управляют.");
    expect(translateStaticText("ja", description)).toBe("エンドポイントを登録して接続を検証し、新しい実行の既定値を対象モデルの近くに保ちます。");
    expect(translateStaticText("ko", description)).toBe("엔드포인트를 등록하고 연결을 검증하며 새 실행의 기본값을 해당 모델 가까이에 유지합니다.");
    expect(translateStaticText("ms", description)).toBe("Daftarkan titik akhir, sahkan sambungan dan kekalkan lalai larian baharu berdekatan model yang ditadbirnya.");
  });

  it("renders redesigned workspace guidance without falling back to isolated words", () => {
    const guidance = "Each stage opens an essential evaluation destination, so the guide remains an actionable path rather than a static checklist." as const;

    expect(translateStaticText("zh-CN", guidance)).toBe("每个阶段都会打开一个必要的评测目标，因此指南仍是一条可执行的路径，而非静态清单。");
    expect(translateStaticText("fr", guidance)).toBe("Chaque étape ouvre une destination d’évaluation essentielle, si bien que le guide reste un parcours actionnable plutôt qu’une liste statique.");
    expect(translateStaticText("de", guidance)).toBe("Jede Stufe öffnet ein wesentliches Bewertungsziel, sodass der Leitfaden ein ausführbarer Pfad und keine statische Checkliste bleibt.");
    expect(translateStaticText("ru", guidance)).toBe("Каждый этап открывает важный целевой раздел оценки, поэтому руководство остаётся действующим планом, а не статичным списком.");
    expect(translateStaticText("ja", guidance)).toBe("各段階で不可欠な評価先が開くため、このガイドは静的なチェックリストではなく実行可能な手順として機能します。");
    expect(translateStaticText("ko", guidance)).toBe("각 단계는 필수 평가 목적지를 열므로 가이드는 정적 체크리스트가 아닌 실행 가능한 경로로 유지됩니다.");
    expect(translateStaticText("ms", guidance)).toBe("Setiap peringkat membuka destinasi penilaian penting, jadi panduan kekal sebagai laluan boleh laksana dan bukan senarai semak statik.");
  });

  it("renders redesigned guide steps and action labels as complete phrases", () => {
    const guideSteps = [
      "6 steps",
      "4. Queue a dataset run",
      "5. Inspect evidence",
      "6. Analyze results",
      "Runs · pick the dataset, evaluation metric, reference field, and endpoint, then queue the run.",
      "Runs · open the run to review samples, scores, latency, cost, and errors.",
      "Analysis · inspect evaluation dimensions or compare two completed runs.",
      "Open Models",
      "Open Datasets",
      "Review Datasets",
      "Open Runs",
      "Inspect Runs",
      "Open Analysis",
    ] as const;

    expect(translateStaticText("zh-CN", guideSteps[0])).toBe("6 个步骤");
    expect(translateStaticText("fr", guideSteps[4])).toBe("Exécutions · choisissez le jeu de données, la métrique d’évaluation, le champ de référence et le point de terminaison, puis mettez l’exécution en file.");
    expect(translateStaticText("de", guideSteps[5])).toBe("Ausführungen · Öffnen Sie den Lauf, um Stichproben, Punktzahlen, Latenz, Kosten und Fehler zu prüfen.");
    expect(translateStaticText("ru", guideSteps[6])).toBe("Анализ · изучите измерения оценки или сравните два завершённых запуска.");
    expect(translateStaticText("ja", guideSteps[11])).toBe("実行を確認");
    expect(translateStaticText("ko", guideSteps[12])).toBe("분석 열기");
    expect(translateStaticText("ms", guideSteps[7])).toBe("Buka model");
  });

  it("renders endpoint and catalog guidance as complete phrases", () => {
    const phrases = [
      "Connection, rate-limit, and cost settings remain editable without exposing stored credentials.",
      "These defaults are merged into a newly queued benchmark run without changing a saved endpoint.",
      "Inspect detected capability evidence separately from the declarations used by run compatibility checks.",
      "No endpoints available",
      "Select a configured endpoint to inspect it.",
      "Inspect versioned benchmark packs, their supported modalities, and the availability state used by new runs.",
      "Manage source versions, cached data, licenses, and field mapping while keeping the selected dataset’s evidence in view.",
      "Selected model endpoint",
    ] as const;

    expect(translateStaticText("zh-CN", phrases[0])).toBe("连接、速率限制和成本设置仍可编辑，同时不会暴露已存储的凭据。");
    expect(translateStaticText("fr", phrases[1])).toBe("Ces valeurs par défaut sont fusionnées dans une nouvelle exécution de benchmark mise en file sans modifier un point de terminaison enregistré.");
    expect(translateStaticText("de", phrases[2])).toBe("Prüfen Sie erkannte Fähigkeitsnachweise getrennt von den Deklarationen, die von Kompatibilitätsprüfungen für Ausführungen verwendet werden.");
    expect(translateStaticText("ru", phrases[3])).toBe("Нет доступных конечных точек");
    expect(translateStaticText("ja", phrases[4])).toBe("設定済みのエンドポイントを選択して確認します。");
    expect(translateStaticText("ko", phrases[5])).toBe("버전이 지정된 벤치마크 팩, 지원되는 모달리티 및 새 실행에 사용되는 가용성 상태를 검토합니다.");
    expect(translateStaticText("ms", phrases[6])).toBe("Urus versi sumber, data cache, lesen dan pemetaan medan sambil mengekalkan bukti set data yang dipilih dalam paparan.");
    expect(translateStaticText("zh-CN", phrases[7])).toBe("所选模型端点");
  });

  it("renders dataset inventory guidance as complete phrases", () => {
    const phrases = [
      "No dataset versions",
      "Register a source, then prepare, validate, and inspect it here.",
      "Dataset inventory",
      "Select a source version to inspect its cache, metadata, and lifecycle actions.",
    ] as const;

    expect(translateStaticText("zh-CN", phrases[0])).toBe("没有数据集版本");
    expect(translateStaticText("fr", phrases[1])).toBe("Enregistrez une source, puis préparez-la, validez-la et examinez-la ici.");
    expect(translateStaticText("de", phrases[2])).toBe("Datensatzübersicht");
    expect(translateStaticText("ru", phrases[3])).toBe("Выберите версию источника, чтобы изучить её кэш, метаданные и действия жизненного цикла.");
  });

  it("renders run inventory guidance as complete phrases", () => {
    const phrases = [
      "Run inventory",
      "Select a snapshot to inspect lifecycle evidence and exportable artifacts.",
    ] as const;

    expect(translateStaticText("zh-CN", phrases[0])).toBe("运行清单");
    expect(translateStaticText("fr", phrases[1])).toBe("Sélectionnez un instantané pour examiner les preuves de cycle de vie et les artefacts exportables.");
  });

  it("renders run launch and inventory guidance as complete phrases", () => {
    const phrases = [
      "Launch immutable evaluation snapshots, then inspect their operational and evidence trail.",
      "Selected run inspector",
      "Select a run from Run inventory to open its summary, evidence, and lifecycle history.",
    ] as const;

    expect(translateStaticText("zh-CN", phrases[0])).toBe("启动不可变的评测快照，然后检查其运行和证据轨迹。");
    expect(translateStaticText("fr", phrases[1])).toBe("Inspecteur de l’exécution sélectionnée");
    expect(translateStaticText("ja", phrases[2])).toBe("実行一覧から実行を選択して、概要、証拠、ライフサイクル履歴を開きます。");
  });

  it("renders analysis guidance and page titles as complete phrases", () => {
    const phrases = [
      "Investigate supplied quality, reliability, latency, cost, and run-to-run evidence.",
      "Runs",
      "Datasets",
      "Analysis",
    ] as const;

    expect(translateStaticText("zh-CN", phrases[0])).toBe("检查所提供的质量、可靠性、延迟、成本和运行间证据。");
    expect(translateStaticText("fr", phrases[1])).toBe("Exécutions");
    expect(translateStaticText("ja", phrases[2])).toBe("データセット");
    expect(translateStaticText("ko", phrases[3])).toBe("분석");
  });

  it("renders comparison workspace guidance as complete phrases", () => {
    const phrases = [
      "Click or use Enter on a bar to inspect the supplied model-capability result.",
      "Compare runs",
      "Compare two completed runs from the same benchmark version and retain the complete evidence trail.",
      "Comparison sources",
      "Choose two distinct completed snapshots. Differences are always calculated as Run A minus Run B.",
      "Comparison evidence",
      "Select two source runs and compare them to expose shared-sample outcomes and metric deltas.",
    ] as const;

    expect(translateStaticText("zh-CN", phrases[0])).toBe("单击条形图或按 Enter 键以检查提供的模型能力结果。");
    expect(translateStaticText("fr", phrases[1])).toBe("Comparer les exécutions");
    expect(translateStaticText("de", phrases[2])).toBe("Vergleichen Sie zwei abgeschlossene Ausführungen derselben Benchmark-Version und bewahren Sie die vollständige Nachweisspur auf.");
    expect(translateStaticText("ru", phrases[3])).toBe("Источники сравнения");
    expect(translateStaticText("ja", phrases[4])).toBe("異なる完了済みスナップショットを 2 つ選択します。差分は常に実行 A から実行 B を引いて計算されます。");
    expect(translateStaticText("ko", phrases[5])).toBe("비교 증거");
    expect(translateStaticText("ms", phrases[6])).toBe("Pilih dua larian sumber dan bandingkannya untuk mendedahkan hasil sampel dikongsi serta delta metrik.");
  });

  it("renders redesigned workspace navigation headers as complete phrases", () => {
    expect(translateStaticText("zh-CN", "Overview")).toBe("概览");
    expect(translateStaticText("fr", "Configure")).toBe("Configurer");
    expect(translateStaticText("de", "Catalog")).toBe("Katalog");
    expect(translateStaticText("ru", "Operations")).toBe("Операции");
    expect(translateStaticText("ja", "Insights")).toBe("インサイト");
    expect(translateStaticText("ko", "Reporting")).toBe("보고");
    expect(translateStaticText("ms", "Quality review")).toBe("Semakan kualiti");
  });

  it("requires direct translations for every bridged static phrase", () => {
    for (const locale of localeIds.filter((locale) => locale !== "en")) {
      for (const phrase of staticSourceTexts) {
        expect(hasExplicitStaticTranslation(locale, phrase), `${locale}: ${phrase}`).toBe(true);
      }
    }
  });
});
