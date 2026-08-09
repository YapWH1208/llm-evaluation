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

  it("renders dataset and suite guidance as complete phrases", () => {
    const phrases = [
      "No dataset versions",
      "Register a dataset source from the Workspace catalog, then return here to prepare, validate, and inspect it.",
      "Dataset inventory",
      "Select a source version to inspect its cache, metadata, and lifecycle actions.",
      "Open suite builder",
      "Compose versioned benchmark sets and queue them on ready endpoints without losing the benchmark evidence behind each suite.",
      "No evaluation suites",
    ] as const;

    expect(translateStaticText("zh-CN", phrases[0])).toBe("没有数据集版本");
    expect(translateStaticText("fr", phrases[1])).toBe("Enregistrez une source de jeu de données depuis le catalogue de l’espace de travail, puis revenez ici pour la préparer, la valider et l’examiner.");
    expect(translateStaticText("de", phrases[2])).toBe("Datensatzübersicht");
    expect(translateStaticText("ru", phrases[3])).toBe("Выберите версию источника, чтобы изучить её кэш, метаданные и действия жизненного цикла.");
    expect(translateStaticText("ja", phrases[4])).toBe("スイートビルダーを開く");
    expect(translateStaticText("ko", phrases[5])).toBe("버전이 지정된 벤치마크 세트를 구성하고 각 스위트의 벤치마크 증거를 유지한 채 준비된 엔드포인트에서 대기열에 추가합니다.");
    expect(translateStaticText("ms", phrases[6])).toBe("Tiada set penilaian");
  });

  it("renders setup and run inventory guidance as complete phrases", () => {
    const phrases = [
      "Create a suite from the Workspace catalog to define versioned benchmark composition and default execution settings.",
      "Suite inventory",
      "Choose a versioned suite to inspect composition and queue it on an available endpoint.",
      "Build versioned inputs, attach validated media, compose suites, and inspect the catalog without leaving setup.",
      "4 workbench modes",
      "Run inventory",
      "Select a snapshot to inspect lifecycle evidence and exportable artifacts.",
    ] as const;

    expect(translateStaticText("zh-CN", phrases[0])).toBe("从工作区目录创建套件，以定义版本化基准测试组合和默认执行设置。");
    expect(translateStaticText("fr", phrases[1])).toBe("Inventaire des suites");
    expect(translateStaticText("de", phrases[2])).toBe("Wählen Sie eine versionierte Suite aus, um ihre Zusammensetzung zu prüfen und sie bei einem verfügbaren Endpunkt einzureihen.");
    expect(translateStaticText("ru", phrases[3])).toBe("Создавайте версионированные входные данные, прикрепляйте проверенные медиафайлы, составляйте наборы и изучайте каталог, не покидая настройку.");
    expect(translateStaticText("ja", phrases[4])).toBe("4 つのワークベンチモード");
    expect(translateStaticText("ko", phrases[5])).toBe("실행 인벤토리");
    expect(translateStaticText("ms", phrases[6])).toBe("Pilih petikan untuk memeriksa bukti kitar hayat dan artifak yang boleh dieksport.");
  });

  it("renders run launch and queue guidance as complete phrases", () => {
    const phrases = [
      "Launch immutable evaluation snapshots, then inspect their operational and evidence trail.",
      "Queue dataset evaluation",
      "Choose an available dataset, prompt version, and endpoint for a new evaluation.",
      "Selected run inspector",
      "Select a run from the persistent inventory to open its summary, evidence, and lifecycle history.",
      "Queue inventory",
      "Virtualised rows keep high-volume queues responsive while retaining task-level operational controls.",
    ] as const;

    expect(translateStaticText("zh-CN", phrases[0])).toBe("启动不可变的评测快照，然后检查其运行和证据轨迹。");
    expect(translateStaticText("fr", phrases[1])).toBe("Mettre l’évaluation du jeu de données en file");
    expect(translateStaticText("de", phrases[2])).toBe("Wählen Sie einen verfügbaren Datensatz, eine Prompt-Version und einen Endpunkt für eine neue Evaluierung aus.");
    expect(translateStaticText("ru", phrases[3])).toBe("Проверка выбранного запуска");
    expect(translateStaticText("ja", phrases[4])).toBe("永続的な一覧から実行を選択して、概要、証拠、ライフサイクル履歴を開きます。");
    expect(translateStaticText("ko", phrases[5])).toBe("대기열 인벤토리");
    expect(translateStaticText("ms", phrases[6])).toBe("Baris maya memastikan baris berjumlah tinggi responsif sambil mengekalkan kawalan operasi pada peringkat tugas.");
  });

  it("renders task and worker guidance as complete phrases", () => {
    const phrases = [
      "Find task",
      "Task status",
      "No tasks match the current filters.",
      "Track active task leases and the worker capacity currently consuming evaluation work.",
      "No active worker leases",
      "No worker has an active lease at the moment. Inspect the queue and system health before changing deployment capacity.",
      "Open task queue",
    ] as const;

    expect(translateStaticText("zh-CN", phrases[0])).toBe("查找任务");
    expect(translateStaticText("fr", phrases[1])).toBe("État de la tâche");
    expect(translateStaticText("de", phrases[2])).toBe("Keine Aufgaben entsprechen den aktuellen Filtern.");
    expect(translateStaticText("ru", phrases[3])).toBe("Отслеживайте активные аренды задач и ресурсы работников, которые сейчас выполняют оценочную работу.");
    expect(translateStaticText("ja", phrases[4])).toBe("アクティブなワーカーリースはありません");
    expect(translateStaticText("ko", phrases[5])).toBe("현재 활성 임대를 가진 작업자가 없습니다. 배포 용량을 변경하기 전에 대기열과 시스템 상태를 확인하세요.");
    expect(translateStaticText("ms", phrases[6])).toBe("Buka baris tugas");
  });

  it("renders worker summary and lease diagnostics as complete phrases", () => {
    const phrases = [
      "Active leases",
      "Connected workers",
      "Tasks currently leased or running",
      "Distinct workers with an active lease",
      "Pending tasks reported by system health",
      "Health signal unavailable",
      "Active worker leases",
    ] as const;

    expect(translateStaticText("zh-CN", phrases[0])).toBe("活动租约");
    expect(translateStaticText("fr", phrases[1])).toBe("Agents connectés");
    expect(translateStaticText("de", phrases[2])).toBe("Derzeit geleaste oder laufende Aufgaben");
    expect(translateStaticText("ru", phrases[3])).toBe("Отдельные работники с активной арендой");
    expect(translateStaticText("ja", phrases[4])).toBe("システムの健全性が報告した保留中のタスク");
    expect(translateStaticText("ko", phrases[5])).toBe("상태 신호를 사용할 수 없음");
    expect(translateStaticText("ms", phrases[6])).toBe("Pajakan pekerja aktif");
  });

  it("renders lease-detail and analysis guidance as complete phrases", () => {
    const phrases = [
      "Lease expiry is recorded with each task so stalled workers can be diagnosed without altering queue state.",
      "Investigate supplied quality, reliability, latency, and cost evidence across evaluation dimensions.",
      "Loading analysis",
      "Analysis matrix",
      "The analysis matrix is loading from the evaluation service.",
      "Analysis context",
      "The selected baseline applies to every evidence cell and delta shown below.",
    ] as const;

    expect(translateStaticText("zh-CN", phrases[0])).toBe("每项任务都会记录租约到期时间，因此可以诊断停滞的工作器而无需更改队列状态。");
    expect(translateStaticText("fr", phrases[1])).toBe("Examinez les preuves fournies de qualité, de fiabilité, de latence et de coût dans toutes les dimensions d’évaluation.");
    expect(translateStaticText("de", phrases[2])).toBe("Analyse wird geladen");
    expect(translateStaticText("ru", phrases[3])).toBe("Матрица анализа");
    expect(translateStaticText("ja", phrases[4])).toBe("分析マトリクスを評価サービスから読み込んでいます。");
    expect(translateStaticText("ko", phrases[5])).toBe("분석 컨텍스트");
    expect(translateStaticText("ms", phrases[6])).toBe("Garis asas yang dipilih digunakan pada setiap sel bukti dan delta yang dipaparkan di bawah.");
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

  it("renders report-source guidance as complete phrases", () => {
    const phrases = [
      "Choose two completed runs to begin an evidence-backed comparison.",
      "Generate portable evaluation artifacts, then manage their controlled, read-only share policies.",
      "Report context",
      "Select the run whose immutable evidence snapshot should anchor this report.",
      "Report source run",
      "Select a report source",
      "Choose an evaluation run above to generate and manage its artifacts without returning to a separate page.",
    ] as const;

    expect(translateStaticText("zh-CN", phrases[0])).toBe("选择两个已完成运行以开始有证据支持的比较。");
    expect(translateStaticText("fr", phrases[1])).toBe("Générez des artefacts d’évaluation portables, puis gérez leurs politiques de partage contrôlées en lecture seule.");
    expect(translateStaticText("de", phrases[2])).toBe("Berichtskontext");
    expect(translateStaticText("ru", phrases[3])).toBe("Выберите запуск, чей неизменяемый снимок доказательств должен служить основой для этого отчёта.");
    expect(translateStaticText("ja", phrases[4])).toBe("レポートのソース実行");
    expect(translateStaticText("ko", phrases[5])).toBe("보고서 소스 선택");
    expect(translateStaticText("ms", phrases[6])).toBe("Pilih larian penilaian di atas untuk menjana dan mengurus artifaknya tanpa kembali ke halaman berasingan.");
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

  it("renders report-generation and review-entry guidance as complete phrases", () => {
    const phrases = [
      "Select a run to generate a portable report or inspect saved artifacts.",
      "Generate report",
      "Select the report shape, then generate the download format needed by the next review or handoff.",
      "Download a generated artifact or create a scoped share link with explicit evidence and download controls.",
      "Keep human scoring and judge assessments tied to the precise run snapshot and sample under review.",
      "Select an evidence sample",
      "Review context",
    ] as const;

    expect(translateStaticText("zh-CN", phrases[0])).toBe("选择一个运行以生成可移植报告或检查已保存的工件。");
    expect(translateStaticText("fr", phrases[1])).toBe("Générer le rapport");
    expect(translateStaticText("de", phrases[2])).toBe("Wählen Sie die Berichtsform und erzeugen Sie anschließend das für die nächste Überprüfung oder Übergabe benötigte Downloadformat.");
    expect(translateStaticText("ru", phrases[3])).toBe("Скачайте созданный артефакт или создайте ограниченную ссылку общего доступа с явными элементами управления доказательствами и загрузкой.");
    expect(translateStaticText("ja", phrases[4])).toBe("人による採点と判定者の評価を、確認中の正確な実行スナップショットとサンプルに結び付けます。");
    expect(translateStaticText("ko", phrases[5])).toBe("증거 샘플 선택");
    expect(translateStaticText("ms", phrases[6])).toBe("Konteks semakan");
  });
});
