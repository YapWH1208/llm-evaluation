import { describe, expect, it } from "vitest";

import { catalogs, isLocale, localeIds, navigationCopy, overviewCopy, resolveLocale } from "./catalog";
import { translateStaticTemplate, translateStaticText } from "./operationalCopy";

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

describe("workspace locale catalog", () => {
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

  it("keeps corrected French worker language and localized templates intact", () => {
    expect(navigationCopy.fr.items.workers).toEqual({ label: "Agents", description: "Baux et agents actifs" });
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

  it("keeps redesigned workspace labels eligible for the static-copy bridge", () => {
    const workspaceLabels = [
      "Report context", "Review context", "User inventory", "Application and storage", "Operating guidance",
      "Filter benchmarks", "Name, source, status…", "Find run", "Benchmark, status, or ID", "Run status", "No runs match the current filters.",
      "Pause download", "Validate cache", "Clear cache", "Retry download", "Upload local revision",
      "Benchmark composition", "Queue suite", "Uses each selected endpoint’s saved connection and capacity configuration.", "No available endpoints are ready to receive this suite.",
      "Loading disk usage…", "No events available.", "Comparing…", "registered versions", "total runs", "tasks visible",
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
    const guidance = [
      "Each stage opens the existing workspace destination, so the guide remains an actionable path rather than a static checklist.",
      "Filters affect this inventory only; registry records and their operational controls remain available in the loaded catalog.",
      "Monitor queued work, prioritise eligible tasks, and trace each task back to its immutable run.",
      "Generate portable evaluation artifacts, then manage their controlled, read-only share policies.",
    ] as const;

    expect(translateStaticText("zh-CN", guidance[0])).toBe("每个阶段都会打开现有的工作区目标，因此指南仍是一条可执行的路径，而非静态清单。");
    expect(translateStaticText("fr", guidance[1])).toBe("Les filtres n’affectent que cet inventaire ; les entrées du registre et leurs contrôles opérationnels restent disponibles dans le catalogue chargé.");
    expect(translateStaticText("de", guidance[2])).toBe("Überwachen Sie die wartende Arbeit, priorisieren Sie berechtigte Aufgaben und verfolgen Sie jede Aufgabe zu ihrem unveränderlichen Lauf zurück.");
    expect(translateStaticText("ru", guidance[3])).toBe("Создавайте переносимые артефакты оценки, а затем управляйте их контролируемыми политиками общего доступа только для чтения.");
    expect(translateStaticText("ja", guidance[0])).toBe("各段階で既存のワークスペース画面を開くため、このガイドは静的なチェックリストではなく実行可能な手順として機能します。");
    expect(translateStaticText("ko", guidance[1])).toBe("필터는 이 인벤토리에만 적용되며 레지스트리 레코드와 운영 제어 기능은 로드된 카탈로그에서 계속 사용할 수 있습니다.");
    expect(translateStaticText("ms", guidance[2])).toBe("Pantau kerja beratur, utamakan tugas yang layak dan jejak setiap tugas kembali kepada larian tidak berubahnya.");
  });

  it("renders endpoint and catalog guidance as complete phrases", () => {
    const phrases = [
      "Connection, rate-limit, and cost settings remain editable without exposing stored credentials.",
      "These defaults are merged into a newly queued benchmark run without changing a saved endpoint.",
      "Inspect detected capability evidence separately from the declarations used by run compatibility checks.",
      "No endpoints available",
      "Choose an endpoint to inspect its detection and declaration evidence.",
      "Inspect versioned benchmark packs, their supported modalities, and the availability state used by new runs.",
      "Manage source versions, cached data, licenses, and field mapping while keeping the selected dataset’s evidence in view.",
    ] as const;

    expect(translateStaticText("zh-CN", phrases[0])).toBe("连接、速率限制和成本设置仍可编辑，同时不会暴露已存储的凭据。");
    expect(translateStaticText("fr", phrases[1])).toBe("Ces valeurs par défaut sont fusionnées dans une nouvelle exécution de benchmark mise en file sans modifier un point de terminaison enregistré.");
    expect(translateStaticText("de", phrases[2])).toBe("Prüfen Sie erkannte Fähigkeitsnachweise getrennt von den Deklarationen, die von Kompatibilitätsprüfungen für Ausführungen verwendet werden.");
    expect(translateStaticText("ru", phrases[3])).toBe("Нет доступных конечных точек");
    expect(translateStaticText("ja", phrases[4])).toBe("エンドポイントを選択して、その検出および宣言の証拠を確認します。");
    expect(translateStaticText("ko", phrases[5])).toBe("버전이 지정된 벤치마크 팩, 지원되는 모달리티 및 새 실행에 사용되는 가용성 상태를 검토합니다.");
    expect(translateStaticText("ms", phrases[6])).toBe("Urus versi sumber, data cache, lesen dan pemetaan medan sambil mengekalkan bukti set data yang dipilih dalam paparan.");
  });
});
