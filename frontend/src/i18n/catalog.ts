export const localeIds = ["en", "zh-CN", "fr", "de", "ru", "ja", "ko", "ms"] as const;

export type Locale = typeof localeIds[number];

export const localeNames: Record<Locale, string> = {
  en: "English",
  "zh-CN": "简体中文",
  fr: "Français",
  de: "Deutsch",
  ru: "Русский",
  ja: "日本語",
  ko: "한국어",
  ms: "Bahasa Melayu",
};

const en = {
  "common.dismiss": "Dismiss",
  "common.loading": "Loading…",
  "common.notConfigured": "Not configured",
  "common.notRecorded": "Not recorded",
  "common.unavailable": "Unavailable",
  "common.unknown": "Unknown",
  "locale.label": "Workspace language",
  "locale.unsupported": "Unsupported locale",
  "provider.missing": "Translation provider is unavailable.",
  "runLauncher.contextTitle": "Launch context",
  "runLauncher.contextDescription": "Choose one available endpoint and check either launch path before queueing.",
  "runLauncher.quickStartTitle": "Quick start",
  "runLauncher.quickStartDescription": "Run a small built-in evaluation without preparing a dataset first.",
  "runLauncher.datasetDescription": "Choose a ready dataset and map its prepared fields into an evaluation snapshot.",
  "runLauncher.quickStartBenchmark": "Quick-start benchmark",
  "runLauncher.offlineHint": "Built-in fixtures are small, deterministic, and available offline for text and modality checks.",
  "runLauncher.queueQuickStart": "Queue quick start",
  "runLauncher.preflightQuickStart": "Preflight quick start",
  "runLauncher.preflightDataset": "Preflight dataset",
  "runLauncher.notChecked": "Not checked",
  "runLauncher.checking": "Checking…",
  "runLauncher.ready": "Ready to queue",
  "runLauncher.blocked": "Blocked",
  "runLauncher.datasetHandoff": "Selected from the dataset catalog. Review the detected field mapping before queueing.",
  "runLauncher.schemaLoading": "Reading prepared dataset fields…",
  "runLauncher.schemaEmpty": "This dataset has no selectable fields.",
  "runLauncher.schemaReferenceRequired": "This dataset exposes only one field; a distinct reference field is required.",
  "runLauncher.schemaDistinctFields": "Input and reference fields must be different.",
  "runLauncher.schemaRetry": "Retry",
  "datasetRun.title": "Dataset evaluation",
  "datasetRun.dataset": "Dataset",
  "datasetRun.promptPackage": "Prompt package (optional)",
  "datasetRun.referenceField": "Reference field",
  "datasetRun.referenceFieldHint": "Record field holding the expected answer",
  "datasetRun.sampleLimit": "Sample limit",
  "datasetRun.endpoint": "Endpoint",
  "datasetRun.nonReadyHint": "Only ready datasets are listed. Download and verify other versions first.",
  "datasetRun.queue": "Queue dataset run",
  "datasetRun.queued": "Dataset evaluation run queued.",
  "datasetRun.inputField": "Input field",
  "datasetRun.startEvaluation": "Start evaluation",
  "datasetRegister.title": "Register dataset version",
  "datasetRegister.inputField": "Input field",
  "datasetRegister.referenceField": "Reference (output) field",
  "datasetRegister.inputFieldHint": "Optional record field used as the prompt input",
  "datasetRegister.referenceFieldHint": "Optional record field holding the expected answer",
} as const;

export type TranslationKey = keyof typeof en;
export type TranslationCatalog = Record<TranslationKey, string>;

const zhCN: TranslationCatalog = {
  "common.dismiss": "关闭",
  "common.loading": "正在加载…",
  "common.notConfigured": "未配置",
  "common.notRecorded": "未记录",
  "common.unavailable": "不可用",
  "common.unknown": "未知",
  "locale.label": "工作区语言",
  "locale.unsupported": "不支持的语言区域",
  "provider.missing": "翻译提供程序不可用。",
  "runLauncher.contextTitle": "启动上下文",
  "runLauncher.contextDescription": "选择一个可用端点，并在加入队列前检查任一启动方式。",
  "runLauncher.quickStartTitle": "快速开始",
  "runLauncher.quickStartDescription": "无需先准备数据集即可运行小型内置评测。",
  "runLauncher.datasetDescription": "选择已就绪的数据集，并将准备好的字段映射到评测快照。",
  "runLauncher.quickStartBenchmark": "快速开始基准",
  "runLauncher.offlineHint": "内置样本小巧、确定且可离线用于文本和模态检查。",
  "runLauncher.queueQuickStart": "将快速开始加入队列",
  "runLauncher.preflightQuickStart": "预检快速开始",
  "runLauncher.preflightDataset": "预检数据集",
  "runLauncher.notChecked": "尚未检查",
  "runLauncher.checking": "正在检查…",
  "runLauncher.ready": "可以加入队列",
  "runLauncher.blocked": "已阻止",
  "runLauncher.datasetHandoff": "已从数据集目录选择。加入队列前请检查检测到的字段映射。",
  "runLauncher.schemaLoading": "正在读取准备好的数据集字段…",
  "runLauncher.schemaEmpty": "此数据集没有可选择的字段。",
  "runLauncher.schemaReferenceRequired": "此数据集仅公开一个字段；需要一个不同的参考字段。",
  "runLauncher.schemaDistinctFields": "输入字段和参考字段必须不同。",
  "runLauncher.schemaRetry": "重试",
  "datasetRun.title": "数据集评测",
  "datasetRun.dataset": "数据集",
  "datasetRun.promptPackage": "提示词包（可选）",
  "datasetRun.referenceField": "参考答案字段",
  "datasetRun.referenceFieldHint": "保存预期答案的记录字段",
  "datasetRun.sampleLimit": "样本数量上限",
  "datasetRun.endpoint": "端点",
  "datasetRun.nonReadyHint": "仅列出已就绪的数据集。请先下载并验证其他版本。",
  "datasetRun.queue": "将数据集评测加入队列",
  "datasetRun.queued": "数据集评测已加入队列。",
  "datasetRun.inputField": "输入字段",
  "datasetRun.startEvaluation": "开始评测",
  "datasetRegister.title": "注册数据集版本",
  "datasetRegister.inputField": "输入字段",
  "datasetRegister.referenceField": "参考答案（输出）字段",
  "datasetRegister.inputFieldHint": "可选：用作提示词输入的记录字段",
  "datasetRegister.referenceFieldHint": "可选：保存预期答案的记录字段",
};

const fr: TranslationCatalog = {
  "common.dismiss": "Fermer",
  "common.loading": "Chargement…",
  "common.notConfigured": "Non configuré",
  "common.notRecorded": "Non enregistré",
  "common.unavailable": "Indisponible",
  "common.unknown": "Inconnu",
  "locale.label": "Langue de l’espace de travail",
  "locale.unsupported": "Langue non prise en charge",
  "provider.missing": "Le fournisseur de traductions est indisponible.",
  "runLauncher.contextTitle": "Contexte de lancement",
  "runLauncher.contextDescription": "Choisissez un point de terminaison disponible et vérifiez le parcours avant la mise en file.",
  "runLauncher.quickStartTitle": "Démarrage rapide",
  "runLauncher.quickStartDescription": "Lancez une petite évaluation intégrée sans préparer de jeu de données.",
  "runLauncher.datasetDescription": "Choisissez un jeu de données prêt et mappez ses champs préparés dans un instantané d’évaluation.",
  "runLauncher.quickStartBenchmark": "Référentiel de démarrage rapide",
  "runLauncher.offlineHint": "Les exemples intégrés sont petits, déterministes et disponibles hors ligne pour les tests texte et multimodaux.",
  "runLauncher.queueQuickStart": "Mettre le démarrage rapide en file",
  "runLauncher.preflightQuickStart": "Vérifier le démarrage rapide",
  "runLauncher.preflightDataset": "Vérifier le jeu de données",
  "runLauncher.notChecked": "Non vérifié",
  "runLauncher.checking": "Vérification…",
  "runLauncher.ready": "Prêt à mettre en file",
  "runLauncher.blocked": "Bloqué",
  "runLauncher.datasetHandoff": "Sélectionné depuis le catalogue. Vérifiez le mappage détecté avant la mise en file.",
  "runLauncher.schemaLoading": "Lecture des champs préparés…",
  "runLauncher.schemaEmpty": "Ce jeu de données ne contient aucun champ sélectionnable.",
  "runLauncher.schemaReferenceRequired": "Ce jeu de données n’expose qu’un seul champ ; un champ de référence distinct est requis.",
  "runLauncher.schemaDistinctFields": "Les champs d’entrée et de référence doivent être différents.",
  "runLauncher.schemaRetry": "Réessayer",
  "datasetRun.title": "Évaluation du jeu de données",
  "datasetRun.dataset": "Jeu de données",
  "datasetRun.promptPackage": "Pack de prompts (facultatif)",
  "datasetRun.referenceField": "Champ de référence",
  "datasetRun.referenceFieldHint": "Champ de l’enregistrement contenant la réponse attendue",
  "datasetRun.sampleLimit": "Limite d’échantillons",
  "datasetRun.endpoint": "Point de terminaison",
  "datasetRun.nonReadyHint": "Seuls les jeux de données prêts sont répertoriés. Téléchargez et vérifiez d’abord les autres versions.",
  "datasetRun.queue": "Mettre l’évaluation du jeu de données en file",
  "datasetRun.queued": "Évaluation du jeu de données mise en file.",
  "datasetRun.inputField": "Champ d’entrée",
  "datasetRun.startEvaluation": "Démarrer l’évaluation",
  "datasetRegister.title": "Enregistrer une version de jeu de données",
  "datasetRegister.inputField": "Champ d’entrée",
  "datasetRegister.referenceField": "Champ de référence (sortie)",
  "datasetRegister.inputFieldHint": "Champ d’enregistrement facultatif utilisé comme entrée du prompt",
  "datasetRegister.referenceFieldHint": "Champ d’enregistrement facultatif contenant la réponse attendue",
};

const de: TranslationCatalog = {
  "common.dismiss": "Schließen",
  "common.loading": "Wird geladen…",
  "common.notConfigured": "Nicht konfiguriert",
  "common.notRecorded": "Nicht erfasst",
  "common.unavailable": "Nicht verfügbar",
  "common.unknown": "Unbekannt",
  "locale.label": "Arbeitsbereichssprache",
  "locale.unsupported": "Nicht unterstützte Sprache",
  "provider.missing": "Der Übersetzungsanbieter ist nicht verfügbar.",
  "runLauncher.contextTitle": "Startkontext",
  "runLauncher.contextDescription": "Wählen Sie einen verfügbaren Endpunkt und prüfen Sie den Startweg vor dem Einreihen.",
  "runLauncher.quickStartTitle": "Schnellstart",
  "runLauncher.quickStartDescription": "Führen Sie eine kleine integrierte Evaluierung ohne vorbereiteten Datensatz aus.",
  "runLauncher.datasetDescription": "Wählen Sie einen bereiten Datensatz und ordnen Sie seine Felder dem Evaluierungssnapshot zu.",
  "runLauncher.quickStartBenchmark": "Schnellstart-Benchmark",
  "runLauncher.offlineHint": "Integrierte Beispiele sind klein, deterministisch und offline für Text- und Modalitätsprüfungen verfügbar.",
  "runLauncher.queueQuickStart": "Schnellstart einreihen",
  "runLauncher.preflightQuickStart": "Schnellstart prüfen",
  "runLauncher.preflightDataset": "Datensatz prüfen",
  "runLauncher.notChecked": "Nicht geprüft",
  "runLauncher.checking": "Wird geprüft…",
  "runLauncher.ready": "Bereit zum Einreihen",
  "runLauncher.blocked": "Blockiert",
  "runLauncher.datasetHandoff": "Aus dem Datensatzkatalog ausgewählt. Prüfen Sie vor dem Einreihen die erkannte Feldzuordnung.",
  "runLauncher.schemaLoading": "Vorbereitete Datensatzfelder werden gelesen…",
  "runLauncher.schemaEmpty": "Dieser Datensatz hat keine auswählbaren Felder.",
  "runLauncher.schemaReferenceRequired": "Dieser Datensatz enthält nur ein Feld; ein separates Referenzfeld ist erforderlich.",
  "runLauncher.schemaDistinctFields": "Eingabe- und Referenzfeld müssen sich unterscheiden.",
  "runLauncher.schemaRetry": "Erneut versuchen",
  "datasetRun.title": "Datensatz-Evaluierung",
  "datasetRun.dataset": "Datensatz",
  "datasetRun.promptPackage": "Prompt-Paket (optional)",
  "datasetRun.referenceField": "Referenzfeld",
  "datasetRun.referenceFieldHint": "Datensatzfeld mit der erwarteten Antwort",
  "datasetRun.sampleLimit": "Stichprobenlimit",
  "datasetRun.endpoint": "Endpunkt",
  "datasetRun.nonReadyHint": "Nur bereite Datensätze werden aufgelistet. Laden Sie andere Versionen zuerst herunter und prüfen Sie sie.",
  "datasetRun.queue": "Datensatz-Evaluierung einreihen",
  "datasetRun.queued": "Datensatz-Evaluierung in die Warteschlange eingereiht.",
  "datasetRun.inputField": "Eingabefeld",
  "datasetRun.startEvaluation": "Evaluierung starten",
  "datasetRegister.title": "Datensatzversion registrieren",
  "datasetRegister.inputField": "Eingabefeld",
  "datasetRegister.referenceField": "Referenzfeld (Ausgabe)",
  "datasetRegister.inputFieldHint": "Optionaler Datensatzfeld als Prompt-Eingabe",
  "datasetRegister.referenceFieldHint": "Optionaler Datensatzfeld mit der erwarteten Antwort",
};

const ru: TranslationCatalog = {
  "common.dismiss": "Закрыть",
  "common.loading": "Загрузка…",
  "common.notConfigured": "Не настроено",
  "common.notRecorded": "Не записано",
  "common.unavailable": "Недоступно",
  "common.unknown": "Неизвестно",
  "locale.label": "Язык рабочего пространства",
  "locale.unsupported": "Неподдерживаемая локаль",
  "provider.missing": "Поставщик переводов недоступен.",
  "runLauncher.contextTitle": "Контекст запуска",
  "runLauncher.contextDescription": "Выберите доступную конечную точку и проверьте способ запуска перед постановкой в очередь.",
  "runLauncher.quickStartTitle": "Быстрый старт",
  "runLauncher.quickStartDescription": "Запустите небольшую встроенную оценку без предварительной подготовки набора данных.",
  "runLauncher.datasetDescription": "Выберите готовый набор данных и сопоставьте его поля со снимком оценки.",
  "runLauncher.quickStartBenchmark": "Бенчмарк быстрого старта",
  "runLauncher.offlineHint": "Встроенные примеры малы, детерминированы и доступны офлайн для проверки текста и модальностей.",
  "runLauncher.queueQuickStart": "Поставить быстрый старт в очередь",
  "runLauncher.preflightQuickStart": "Проверить быстрый старт",
  "runLauncher.preflightDataset": "Проверить набор данных",
  "runLauncher.notChecked": "Не проверено",
  "runLauncher.checking": "Проверка…",
  "runLauncher.ready": "Готово к постановке в очередь",
  "runLauncher.blocked": "Заблокировано",
  "runLauncher.datasetHandoff": "Выбрано из каталога. Проверьте сопоставление полей перед постановкой в очередь.",
  "runLauncher.schemaLoading": "Чтение подготовленных полей набора данных…",
  "runLauncher.schemaEmpty": "В этом наборе данных нет доступных для выбора полей.",
  "runLauncher.schemaReferenceRequired": "В этом наборе данных доступно только одно поле; требуется отдельное поле эталона.",
  "runLauncher.schemaDistinctFields": "Поля ввода и эталона должны различаться.",
  "runLauncher.schemaRetry": "Повторить",
  "datasetRun.title": "Оценка набора данных",
  "datasetRun.dataset": "Набор данных",
  "datasetRun.promptPackage": "Пакет промптов (необязательно)",
  "datasetRun.referenceField": "Поле эталонного ответа",
  "datasetRun.referenceFieldHint": "Поле записи с ожидаемым ответом",
  "datasetRun.sampleLimit": "Лимит выборки",
  "datasetRun.endpoint": "Конечная точка",
  "datasetRun.nonReadyHint": "Перечислены только готовые наборы данных. Сначала загрузите и проверьте другие версии.",
  "datasetRun.queue": "Поставить оценку набора данных в очередь",
  "datasetRun.queued": "Оценка набора данных поставлена в очередь.",
  "datasetRun.inputField": "Поле ввода",
  "datasetRun.startEvaluation": "Начать оценку",
  "datasetRegister.title": "Регистрация версии набора данных",
  "datasetRegister.inputField": "Поле ввода",
  "datasetRegister.referenceField": "Поле эталонного ответа (вывод)",
  "datasetRegister.inputFieldHint": "Необязательное поле записи, используемое как вход промпта",
  "datasetRegister.referenceFieldHint": "Необязательное поле записи с ожидаемым ответом",
};

const ja: TranslationCatalog = {
  "common.dismiss": "閉じる",
  "common.loading": "読み込み中…",
  "common.notConfigured": "未設定",
  "common.notRecorded": "記録なし",
  "common.unavailable": "利用不可",
  "common.unknown": "不明",
  "locale.label": "ワークスペースの言語",
  "locale.unsupported": "サポートされていないロケール",
  "provider.missing": "翻訳プロバイダーを利用できません。",
  "runLauncher.contextTitle": "起動コンテキスト",
  "runLauncher.contextDescription": "利用可能なエンドポイントを選択し、キュー投入前に起動方法を確認します。",
  "runLauncher.quickStartTitle": "クイックスタート",
  "runLauncher.quickStartDescription": "データセットを準備せずに小さな組み込み評価を実行します。",
  "runLauncher.datasetDescription": "準備済みデータセットを選択し、そのフィールドを評価スナップショットに割り当てます。",
  "runLauncher.quickStartBenchmark": "クイックスタート ベンチマーク",
  "runLauncher.offlineHint": "組み込みサンプルは小さく決定的で、テキストとモダリティの確認にオフラインで使用できます。",
  "runLauncher.queueQuickStart": "クイックスタートをキューに入れる",
  "runLauncher.preflightQuickStart": "クイックスタートを事前確認",
  "runLauncher.preflightDataset": "データセットを事前確認",
  "runLauncher.notChecked": "未確認",
  "runLauncher.checking": "確認中…",
  "runLauncher.ready": "キュー投入可能",
  "runLauncher.blocked": "ブロック済み",
  "runLauncher.datasetHandoff": "データセット カタログから選択されました。キュー投入前にフィールド割り当てを確認してください。",
  "runLauncher.schemaLoading": "準備済みデータセットのフィールドを読み込み中…",
  "runLauncher.schemaEmpty": "このデータセットには選択可能なフィールドがありません。",
  "runLauncher.schemaReferenceRequired": "このデータセットにはフィールドが 1 つしかないため、別の参照フィールドが必要です。",
  "runLauncher.schemaDistinctFields": "入力フィールドと参照フィールドは異なる必要があります。",
  "runLauncher.schemaRetry": "再試行",
  "datasetRun.title": "データセット評価",
  "datasetRun.dataset": "データセット",
  "datasetRun.promptPackage": "プロンプト パッケージ（省略可能）",
  "datasetRun.referenceField": "参照フィールド",
  "datasetRun.referenceFieldHint": "期待される回答を保持するレコード フィールド",
  "datasetRun.sampleLimit": "サンプル上限",
  "datasetRun.endpoint": "エンドポイント",
  "datasetRun.nonReadyHint": "準備ができたデータセットのみが表示されます。他のバージョンを先にダウンロードして検証してください。",
  "datasetRun.queue": "データセット評価をキューに入れる",
  "datasetRun.queued": "データセット評価がキューに入りました。",
  "datasetRun.inputField": "入力フィールド",
  "datasetRun.startEvaluation": "評価を開始",
  "datasetRegister.title": "データセット バージョンの登録",
  "datasetRegister.inputField": "入力フィールド",
  "datasetRegister.referenceField": "参照フィールド（出力）",
  "datasetRegister.inputFieldHint": "プロンプト入力として使用するレコード フィールド（省略可能）",
  "datasetRegister.referenceFieldHint": "期待される回答を保持するレコード フィールド（省略可能）",
};

const ko: TranslationCatalog = {
  "common.dismiss": "닫기",
  "common.loading": "불러오는 중…",
  "common.notConfigured": "구성되지 않음",
  "common.notRecorded": "기록되지 않음",
  "common.unavailable": "사용할 수 없음",
  "common.unknown": "알 수 없음",
  "locale.label": "작업 공간 언어",
  "locale.unsupported": "지원하지 않는 로캘",
  "provider.missing": "번역 공급자를 사용할 수 없습니다.",
  "runLauncher.contextTitle": "실행 컨텍스트",
  "runLauncher.contextDescription": "사용 가능한 엔드포인트를 선택하고 대기열에 추가하기 전에 실행 경로를 확인하세요.",
  "runLauncher.quickStartTitle": "빠른 시작",
  "runLauncher.quickStartDescription": "데이터 세트를 준비하지 않고 작은 내장 평가를 실행합니다.",
  "runLauncher.datasetDescription": "준비된 데이터 세트를 선택하고 필드를 평가 스냅샷에 매핑합니다.",
  "runLauncher.quickStartBenchmark": "빠른 시작 벤치마크",
  "runLauncher.offlineHint": "내장 샘플은 작고 결정적이며 텍스트 및 모달리티 확인에 오프라인으로 사용할 수 있습니다.",
  "runLauncher.queueQuickStart": "빠른 시작 대기열에 추가",
  "runLauncher.preflightQuickStart": "빠른 시작 사전 확인",
  "runLauncher.preflightDataset": "데이터 세트 사전 확인",
  "runLauncher.notChecked": "확인하지 않음",
  "runLauncher.checking": "확인 중…",
  "runLauncher.ready": "대기열 추가 준비됨",
  "runLauncher.blocked": "차단됨",
  "runLauncher.datasetHandoff": "데이터 세트 카탈로그에서 선택했습니다. 대기열에 추가하기 전에 필드 매핑을 확인하세요.",
  "runLauncher.schemaLoading": "준비된 데이터 세트 필드를 읽는 중…",
  "runLauncher.schemaEmpty": "이 데이터 세트에는 선택 가능한 필드가 없습니다.",
  "runLauncher.schemaReferenceRequired": "이 데이터 세트에는 필드가 하나만 있으므로 별도의 참조 필드가 필요합니다.",
  "runLauncher.schemaDistinctFields": "입력 필드와 참조 필드는 달라야 합니다.",
  "runLauncher.schemaRetry": "다시 시도",
  "datasetRun.title": "데이터 세트 평가",
  "datasetRun.dataset": "데이터 세트",
  "datasetRun.promptPackage": "프롬프트 패키지(선택 사항)",
  "datasetRun.referenceField": "참조 필드",
  "datasetRun.referenceFieldHint": "예상 답변이 포함된 레코드 필드",
  "datasetRun.sampleLimit": "샘플 제한",
  "datasetRun.endpoint": "엔드포인트",
  "datasetRun.nonReadyHint": "준비된 데이터 세트만 나열됩니다. 다른 버전을 먼저 다운로드하여 확인하세요.",
  "datasetRun.queue": "데이터 세트 평가 대기열에 추가",
  "datasetRun.queued": "데이터 세트 평가가 대기열에 추가되었습니다.",
  "datasetRun.inputField": "입력 필드",
  "datasetRun.startEvaluation": "평가 시작",
  "datasetRegister.title": "데이터 세트 버전 등록",
  "datasetRegister.inputField": "입력 필드",
  "datasetRegister.referenceField": "참조 필드(출력)",
  "datasetRegister.inputFieldHint": "프롬프트 입력으로 사용되는 레코드 필드(선택 사항)",
  "datasetRegister.referenceFieldHint": "예상 답변이 포함된 레코드 필드(선택 사항)",
};

const ms: TranslationCatalog = {
  "common.dismiss": "Tutup",
  "common.loading": "Memuatkan…",
  "common.notConfigured": "Belum dikonfigurasikan",
  "common.notRecorded": "Tidak direkodkan",
  "common.unavailable": "Tidak tersedia",
  "common.unknown": "Tidak diketahui",
  "locale.label": "Bahasa ruang kerja",
  "locale.unsupported": "Bahasa tidak disokong",
  "provider.missing": "Penyedia terjemahan tidak tersedia.",
  "runLauncher.contextTitle": "Konteks pelancaran",
  "runLauncher.contextDescription": "Pilih satu titik akhir yang tersedia dan semak laluan pelancaran sebelum dimasukkan ke dalam baris.",
  "runLauncher.quickStartTitle": "Mula pantas",
  "runLauncher.quickStartDescription": "Jalankan penilaian terbina dalam yang kecil tanpa menyediakan set data dahulu.",
  "runLauncher.datasetDescription": "Pilih set data yang sedia dan petakan medannya ke dalam petikan penilaian.",
  "runLauncher.quickStartBenchmark": "Penanda aras mula pantas",
  "runLauncher.offlineHint": "Sampel terbina dalam kecil, deterministik dan tersedia di luar talian untuk semakan teks dan modaliti.",
  "runLauncher.queueQuickStart": "Masukkan mula pantas ke dalam baris",
  "runLauncher.preflightQuickStart": "Prasemak mula pantas",
  "runLauncher.preflightDataset": "Prasemak set data",
  "runLauncher.notChecked": "Belum disemak",
  "runLauncher.checking": "Sedang menyemak…",
  "runLauncher.ready": "Sedia dimasukkan ke dalam baris",
  "runLauncher.blocked": "Disekat",
  "runLauncher.datasetHandoff": "Dipilih daripada katalog set data. Semak pemetaan medan sebelum dimasukkan ke dalam baris.",
  "runLauncher.schemaLoading": "Membaca medan set data yang disediakan…",
  "runLauncher.schemaEmpty": "Set data ini tiada medan yang boleh dipilih.",
  "runLauncher.schemaReferenceRequired": "Set data ini hanya mendedahkan satu medan; medan rujukan yang berbeza diperlukan.",
  "runLauncher.schemaDistinctFields": "Medan input dan medan rujukan mestilah berbeza.",
  "runLauncher.schemaRetry": "Cuba semula",
  "datasetRun.title": "Penilaian set data",
  "datasetRun.dataset": "Set data",
  "datasetRun.promptPackage": "Pakej prom (pilihan)",
  "datasetRun.referenceField": "Medan rujukan",
  "datasetRun.referenceFieldHint": "Medan rekod yang mengandungi jawapan yang dijangkakan",
  "datasetRun.sampleLimit": "Had sampel",
  "datasetRun.endpoint": "Titik akhir",
  "datasetRun.nonReadyHint": "Hanya set data yang sedia disenaraikan. Muat turun dan sahkan versi lain dahulu.",
  "datasetRun.queue": "Letakkan penilaian set data dalam baris",
  "datasetRun.queued": "Penilaian set data telah dimasukkan ke dalam baris.",
  "datasetRun.inputField": "Medan input",
  "datasetRun.startEvaluation": "Mulakan penilaian",
  "datasetRegister.title": "Daftar versi set data",
  "datasetRegister.inputField": "Medan input",
  "datasetRegister.referenceField": "Medan rujukan (output)",
  "datasetRegister.inputFieldHint": "Medan rekod pilihan yang digunakan sebagai input prom",
  "datasetRegister.referenceFieldHint": "Medan rekod pilihan yang mengandungi jawapan yang dijangkakan",
};

export const catalogs: Record<Locale, TranslationCatalog> = { en, "zh-CN": zhCN, fr, de, ru, ja, ko, ms };

export function isLocale(value: string | null | undefined): value is Locale {
  return typeof value === "string" && localeIds.includes(value as Locale);
}

export function resolveLocale(value: string | null | undefined): Locale {
  return isLocale(value) ? value : "en";
}

export const workspaceViews = ["dashboard", "guide", "models", "capabilities", "workspace", "benchmarks", "datasets", "suites", "runs", "queue", "workers", "analysis", "compare", "reports", "reviews", "users", "settings"] as const;
export type WorkspaceView = typeof workspaceViews[number];
export type NavigationGroupId = "overview" | "configure" | "operations" | "insights" | "system";

type NavigationCopy = {
  groups: Record<NavigationGroupId, string>;
  items: Record<WorkspaceView, { label: string; description: string }>;
};

function navigation(groups: [string, string, string, string, string], items: Array<[string, string]>): NavigationCopy {
  return {
    groups: { overview: groups[0], configure: groups[1], operations: groups[2], insights: groups[3], system: groups[4] },
    items: Object.fromEntries(workspaceViews.map((view, index) => [view, { label: items[index][0], description: items[index][1] }])) as NavigationCopy["items"],
  };
}

export const navigationCopy: Record<Locale, NavigationCopy> = {
  en: navigation(["Overview", "Configure", "Operations", "Insights", "System"], [
    ["Dashboard", "Operational status and recent work"], ["Guide", "Step-by-step usage walkthrough"], ["Models", "Endpoints and run defaults"], ["Capabilities", "Detection and declarations"], ["Workspace", "Prompts, assets, and setup"], ["Benchmarks", "Benchmark registry"], ["Datasets", "Versioned data sources"], ["Suites", "Reusable evaluation suites"], ["Runs", "Execution, results, and evidence"], ["Task queue", "Priorities and pending work"], ["Workers", "Leases and active workers"], ["Analysis", "Capability and trend evidence"], ["Compare", "Run-to-run comparisons"], ["Reports", "Exports and shared artifacts"], ["Human review", "Review and adjudication"], ["Users", "Users and audit activity"], ["Settings", "Health, access, and preferences"],
  ]),
  "zh-CN": navigation(["概览", "配置", "运营", "洞察", "系统"], [
    ["仪表盘", "运行状态和近期工作"], ["指南", "分步使用说明"], ["模型", "端点和运行默认值"], ["能力", "检测与声明"], ["工作区", "提示词、资产与设置"], ["基准", "评测基准注册表"], ["数据集", "版本化数据源"], ["套件", "可复用的评测套件"], ["运行", "执行、结果与证据"], ["任务队列", "优先级与待处理工作"], ["工作节点", "租约和活动工作节点"], ["分析", "能力与趋势证据"], ["对比", "运行之间的对比"], ["报告", "导出和共享工件"], ["人工审核", "审核与裁决"], ["用户", "用户和审计活动"], ["设置", "运行状况、访问和偏好设置"],
  ]),
  fr: navigation(["Aperçu", "Configuration", "Opérations", "Analyses", "Système"], [
    ["Tableau de bord", "État opérationnel et travaux récents"], ["Guide", "Parcours d’utilisation pas à pas"], ["Modèles", "Points de terminaison et paramètres d’exécution"], ["Capacités", "Détection et déclarations"], ["Espace de travail", "Prompts, ressources et configuration"], ["Référentiels", "Registre des référentiels"], ["Jeux de données", "Sources de données versionnées"], ["Suites", "Suites d’évaluation réutilisables"], ["Exécutions", "Exécution, résultats et preuves"], ["File d’attente", "Priorités et travail en attente"], ["Agents", "Baux et agents actifs"], ["Analyse", "Preuves de capacités et tendances"], ["Comparer", "Comparaisons entre exécutions"], ["Rapports", "Exports et artefacts partagés"], ["Révision humaine", "Révision et arbitrage"], ["Utilisateurs", "Utilisateurs et activité d’audit"], ["Paramètres", "État, accès et préférences"],
  ]),
  de: navigation(["Übersicht", "Konfiguration", "Betrieb", "Einblicke", "System"], [
    ["Dashboard", "Betriebsstatus und aktuelle Arbeit"], ["Leitfaden", "Schritt-für-Schritt-Anleitung"], ["Modelle", "Endpunkte und Ausführungsstandards"], ["Fähigkeiten", "Erkennung und Deklarationen"], ["Arbeitsbereich", "Prompts, Assets und Einrichtung"], ["Benchmarks", "Benchmark-Register"], ["Datensätze", "Versionierte Datenquellen"], ["Suiten", "Wiederverwendbare Evaluierungssuiten"], ["Ausführungen", "Ausführung, Ergebnisse und Nachweise"], ["Aufgabenwarteschlange", "Prioritäten und ausstehende Arbeit"], ["Worker", "Leases und aktive Worker"], ["Analyse", "Fähigkeits- und Trendnachweise"], ["Vergleichen", "Vergleiche zwischen Ausführungen"], ["Berichte", "Exporte und geteilte Artefakte"], ["Menschliche Prüfung", "Prüfung und Entscheidung"], ["Benutzer", "Benutzer und Auditaktivität"], ["Einstellungen", "Status, Zugriff und Präferenzen"],
  ]),
  ru: navigation(["Обзор", "Настройка", "Операции", "Аналитика", "Система"], [
    ["Панель", "Рабочее состояние и недавние задачи"], ["Руководство", "Пошаговое руководство по использованию"], ["Модели", "Конечные точки и настройки запуска"], ["Возможности", "Обнаружение и объявления"], ["Рабочая область", "Промпты, ресурсы и настройка"], ["Бенчмарки", "Реестр бенчмарков"], ["Наборы данных", "Версионируемые источники данных"], ["Наборы", "Повторно используемые наборы оценки"], ["Запуски", "Выполнение, результаты и доказательства"], ["Очередь задач", "Приоритеты и ожидающая работа"], ["Рабочие узлы", "Аренды и активные рабочие узлы"], ["Анализ", "Доказательства возможностей и трендов"], ["Сравнение", "Сравнения запусков"], ["Отчёты", "Экспорт и общие артефакты"], ["Проверка человеком", "Проверка и арбитраж"], ["Пользователи", "Пользователи и аудит"], ["Настройки", "Состояние, доступ и предпочтения"],
  ]),
  ja: navigation(["概要", "設定", "運用", "分析情報", "システム"], [
    ["ダッシュボード", "運用状況と最近の作業"], ["ガイド", "ステップバイステップの使い方"], ["モデル", "エンドポイントと実行の既定値"], ["機能", "検出と宣言"], ["ワークスペース", "プロンプト、アセット、設定"], ["ベンチマーク", "ベンチマーク レジストリ"], ["データセット", "バージョン管理されたデータソース"], ["スイート", "再利用可能な評価スイート"], ["実行", "実行、結果、証拠"], ["タスク キュー", "優先順位と保留中の作業"], ["ワーカー", "リースとアクティブなワーカー"], ["分析", "機能と傾向の証拠"], ["比較", "実行間の比較"], ["レポート", "エクスポートと共有アーティファクト"], ["人によるレビュー", "レビューと裁定"], ["ユーザー", "ユーザーと監査アクティビティ"], ["設定", "状態、アクセス、設定"],
  ]),
  ko: navigation(["개요", "구성", "운영", "인사이트", "시스템"], [
    ["대시보드", "운영 상태 및 최근 작업"], ["가이드", "단계별 사용 안내"], ["모델", "엔드포인트 및 실행 기본값"], ["기능", "감지 및 선언"], ["작업 공간", "프롬프트, 자산 및 설정"], ["벤치마크", "벤치마크 레지스트리"], ["데이터 세트", "버전 관리 데이터 원본"], ["스위트", "재사용 가능한 평가 스위트"], ["실행", "실행, 결과 및 증거"], ["작업 대기열", "우선순위 및 대기 중인 작업"], ["워커", "리스 및 활성 워커"], ["분석", "기능 및 추세 증거"], ["비교", "실행 간 비교"], ["보고서", "내보내기 및 공유 아티팩트"], ["사람 검토", "검토 및 조정"], ["사용자", "사용자 및 감사 활동"], ["설정", "상태, 액세스 및 기본 설정"],
  ]),
  ms: navigation(["Gambaran keseluruhan", "Konfigurasi", "Operasi", "Wawasan", "Sistem"], [
    ["Papan pemuka", "Status operasi dan kerja terkini"], ["Panduan", "Panduan penggunaan langkah demi langkah"], ["Model", "Titik akhir dan lalai pelaksanaan"], ["Keupayaan", "Pengesanan dan pengisytiharan"], ["Ruang kerja", "Prom, aset dan persediaan"], ["Penanda aras", "Daftar penanda aras"], ["Set data", "Sumber data berversi"], ["Suite", "Suite penilaian boleh guna semula"], ["Larian", "Pelaksanaan, hasil dan bukti"], ["Baris tugas", "Keutamaan dan kerja menunggu"], ["Pekerja", "Pajakan dan pekerja aktif"], ["Analisis", "Bukti keupayaan dan aliran"], ["Bandingkan", "Perbandingan antara larian"], ["Laporan", "Eksport dan artifak dikongsi"], ["Semakan manusia", "Semakan dan pengadilan"], ["Pengguna", "Pengguna dan aktiviti audit"], ["Tetapan", "Kesihatan, akses dan keutamaan"],
  ]),
};

export type ShellCopy = {
  brand: string;
  navigation: string;
  closeNavigation: string;
  openNavigation: string;
  systemHealthy: string;
  systemStatus: string;
  systemUnavailable: string;
  completed: string;
  switchToLight: string;
  switchToDark: string;
  lightMode: string;
  darkMode: string;
  controlCenter: string;
};

export const shellCopy: Record<Locale, ShellCopy> = {
  en: { brand: "Evaluation workspace", navigation: "Workspace navigation", closeNavigation: "Close navigation", openNavigation: "Open navigation", systemHealthy: "System healthy", systemStatus: "System {{status}}", systemUnavailable: "System status unavailable", completed: "completed", switchToLight: "Switch to light mode", switchToDark: "Switch to dark mode", lightMode: "Light mode", darkMode: "Dark mode", controlCenter: "Evaluation control center" },
  "zh-CN": { brand: "评测工作区", navigation: "工作区导航", closeNavigation: "关闭导航", openNavigation: "打开导航", systemHealthy: "系统正常", systemStatus: "系统 {{status}}", systemUnavailable: "系统状态不可用", completed: "已完成", switchToLight: "切换到浅色模式", switchToDark: "切换到深色模式", lightMode: "浅色模式", darkMode: "深色模式", controlCenter: "评测控制中心" },
  fr: { brand: "Espace de travail d’évaluation", navigation: "Navigation de l’espace de travail", closeNavigation: "Fermer la navigation", openNavigation: "Ouvrir la navigation", systemHealthy: "Système opérationnel", systemStatus: "Système {{status}}", systemUnavailable: "État du système indisponible", completed: "terminées", switchToLight: "Passer au mode clair", switchToDark: "Passer au mode sombre", lightMode: "Mode clair", darkMode: "Mode sombre", controlCenter: "Centre de contrôle des évaluations" },
  de: { brand: "Evaluierungsarbeitsbereich", navigation: "Arbeitsbereichsnavigation", closeNavigation: "Navigation schließen", openNavigation: "Navigation öffnen", systemHealthy: "System fehlerfrei", systemStatus: "System {{status}}", systemUnavailable: "Systemstatus nicht verfügbar", completed: "abgeschlossen", switchToLight: "Zum hellen Modus wechseln", switchToDark: "Zum dunklen Modus wechseln", lightMode: "Heller Modus", darkMode: "Dunkler Modus", controlCenter: "Evaluierungszentrale" },
  ru: { brand: "Рабочая область оценки", navigation: "Навигация рабочей области", closeNavigation: "Закрыть навигацию", openNavigation: "Открыть навигацию", systemHealthy: "Система исправна", systemStatus: "Система: {{status}}", systemUnavailable: "Статус системы недоступен", completed: "завершено", switchToLight: "Перейти к светлой теме", switchToDark: "Перейти к тёмной теме", lightMode: "Светлая тема", darkMode: "Тёмная тема", controlCenter: "Центр управления оценками" },
  ja: { brand: "評価ワークスペース", navigation: "ワークスペース ナビゲーション", closeNavigation: "ナビゲーションを閉じる", openNavigation: "ナビゲーションを開く", systemHealthy: "システムは正常です", systemStatus: "システム {{status}}", systemUnavailable: "システム状態を利用できません", completed: "完了", switchToLight: "ライトモードに切り替える", switchToDark: "ダークモードに切り替える", lightMode: "ライトモード", darkMode: "ダークモード", controlCenter: "評価コントロール センター" },
  ko: { brand: "평가 작업 공간", navigation: "작업 공간 탐색", closeNavigation: "탐색 닫기", openNavigation: "탐색 열기", systemHealthy: "시스템 정상", systemStatus: "시스템 {{status}}", systemUnavailable: "시스템 상태를 사용할 수 없음", completed: "완료", switchToLight: "라이트 모드로 전환", switchToDark: "다크 모드로 전환", lightMode: "라이트 모드", darkMode: "다크 모드", controlCenter: "평가 제어 센터" },
  ms: { brand: "Ruang kerja penilaian", navigation: "Navigasi ruang kerja", closeNavigation: "Tutup navigasi", openNavigation: "Buka navigasi", systemHealthy: "Sistem sihat", systemStatus: "Sistem {{status}}", systemUnavailable: "Status sistem tidak tersedia", completed: "selesai", switchToLight: "Tukar kepada mod cerah", switchToDark: "Tukar kepada mod gelap", lightMode: "Mod cerah", darkMode: "Mod gelap", controlCenter: "Pusat kawalan penilaian" },
};

export type OverviewCopy = {
  unavailableRegion: string; unavailableTitle: string; unavailableDescription: string; configureModel: string; openRuns: string;
  operations: string; heroTitle: string; heroDescription: string; viewAllRuns: string; prepareWorkspace: string; operationalStatus: string;
  activeRuns: string; endpoints: string; workers: string; estimatedCost: string; pendingLeased: string; unavailable: string; activeQueueTasks: string; completedEvidence: string;
  currentWork: string; runsInProgress: string; noActiveRuns: string; noActiveDescription: string; setupEvaluation: string; samples: string; inspect: string;
  readiness: string; workspaceReady: string; verified: string; modelEndpoints: string; availableForEvaluation: string; verifyModel: string; manage: string; configure: string;
  evaluationData: string; readyDataset: string; readyDatasets: string; registerDataset: string; review: string; addData: string;
  queuePressure: string; noWorkWaiting: string; taskNeedsCapacity: string; tasksNeedCapacity: string; inspectQueue: string;
  evaluationHealth: string; qualityAtGlance: string; openAnalysis: string; accuracy: string; successful: string; apiErrors: string; requests: string; p95Latency: string; measured: string; tokens: string; inputOutput: string;
  completedWork: string; recentRuns: string; complete: string; noCompleted: string; noCompletedDescription: string; runHistory: string;
  dashboardTitle: string; dashboardDescription: string; performanceSummary: string; successRate: string; evaluationTrend: string; limitedHistory: string; noHistory: string;
  modelBenchmarkComparison: string; model: string; benchmark: string; sampleCount: string; latencyCostErrors: string; latency: string; cost: string; errorRate: string;
  recentEvaluations: string; progress: string; started: string; systemReadiness: string; operational: string; attentionNeeded: string; unknownValue: string;
};

type AnalyticsOverviewCopy = Pick<OverviewCopy,
  | "dashboardTitle"
  | "dashboardDescription"
  | "performanceSummary"
  | "successRate"
  | "evaluationTrend"
  | "limitedHistory"
  | "noHistory"
  | "modelBenchmarkComparison"
  | "model"
  | "benchmark"
  | "sampleCount"
  | "latencyCostErrors"
  | "latency"
  | "cost"
  | "errorRate"
  | "recentEvaluations"
  | "progress"
  | "started"
  | "systemReadiness"
  | "operational"
  | "attentionNeeded"
  | "unknownValue"
>;

type OverviewCopyBase = Omit<OverviewCopy, keyof AnalyticsOverviewCopy> & Partial<AnalyticsOverviewCopy>;

const overviewCopyBase: Record<Locale, OverviewCopyBase> = {
  en: { unavailableRegion: "Operational overview unavailable", unavailableTitle: "Operational signals are loading", unavailableDescription: "The workspace is still reachable. Configure a model or inspect your evaluation runs while live status becomes available.", configureModel: "Configure a model", openRuns: "Open runs", operations: "Evaluation operations", heroTitle: "Keep every evaluation moving", heroDescription: "Monitor current work, verify capacity, and act on the next setup step from one place.", viewAllRuns: "View all runs", prepareWorkspace: "Prepare workspace", operationalStatus: "Operational status", activeRuns: "Active runs", endpoints: "Endpoints", workers: "Workers", estimatedCost: "Estimated cost", pendingLeased: "{{pending}} pending · {{leased}} leased", unavailable: "{{count}} unavailable", activeQueueTasks: "{{count}} active queue tasks", completedEvidence: "completed run evidence", currentWork: "Current work", runsInProgress: "Runs in progress", noActiveRuns: "No active runs", noActiveDescription: "Start from a verified endpoint, benchmark, and dataset.", setupEvaluation: "Set up an evaluation", samples: "samples", inspect: "Inspect", readiness: "Readiness", workspaceReady: "Keep the workspace ready", verified: "{{count}} verified", modelEndpoints: "Model endpoints", availableForEvaluation: "{{count}} available for evaluation", verifyModel: "Verify a model before queueing work", manage: "Manage", configure: "Configure", evaluationData: "Evaluation data", readyDataset: "{{count}} ready dataset", readyDatasets: "{{count}} ready datasets", registerDataset: "Register a dataset to start a benchmark", review: "Review", addData: "Add data", queuePressure: "Queue pressure", noWorkWaiting: "No work is waiting", taskNeedsCapacity: "{{count}} task needs capacity", tasksNeedCapacity: "{{count}} tasks need capacity", inspectQueue: "Inspect queue", evaluationHealth: "Evaluation health", qualityAtGlance: "Quality at a glance", openAnalysis: "Open analysis", accuracy: "Accuracy", successful: "{{successful}}/{{total}} successful", apiErrors: "API errors", requests: "{{count}} requests", p95Latency: "P95 latency", measured: "{{count}} measured", tokens: "Tokens", inputOutput: "{{input}} in / {{output}} out", completedWork: "Completed work", recentRuns: "Recent runs", complete: "{{count}} complete", noCompleted: "No completed runs yet", noCompletedDescription: "Results will appear here after the first evaluation finishes.", runHistory: "See run history", dashboardTitle: "Dashboard", dashboardDescription: "Track evaluation quality, model behavior, and operational readiness from live evidence.", performanceSummary: "Performance summary", successRate: "Success rate", evaluationTrend: "Evaluation trend", limitedHistory: "More completed runs are needed to show a trend.", noHistory: "Evaluation history is not available yet.", modelBenchmarkComparison: "Model / benchmark comparison", model: "Model", benchmark: "Benchmark", sampleCount: "Samples", latencyCostErrors: "Latency, cost & errors", latency: "Latency", cost: "Cost", errorRate: "Error rate", recentEvaluations: "Recent evaluations", progress: "Progress", started: "Started", systemReadiness: "System readiness", operational: "Operational", attentionNeeded: "Attention needed", unknownValue: "Not available" },
  "zh-CN": { unavailableRegion: "运营概览不可用", unavailableTitle: "正在加载运营信号", unavailableDescription: "工作区仍可访问。实时状态可用前，您可以配置模型或查看评测运行。", configureModel: "配置模型", openRuns: "打开运行", operations: "评测运营", heroTitle: "让每次评测持续推进", heroDescription: "在一处监控当前工作、确认容量并执行下一步设置。", viewAllRuns: "查看所有运行", prepareWorkspace: "准备工作区", operationalStatus: "运营状态", activeRuns: "活动运行", endpoints: "端点", workers: "工作节点", estimatedCost: "预估成本", pendingLeased: "{{pending}} 个待处理 · {{leased}} 个已租用", unavailable: "{{count}} 个不可用", activeQueueTasks: "{{count}} 个活动队列任务", completedEvidence: "已完成运行证据", currentWork: "当前工作", runsInProgress: "正在运行", noActiveRuns: "没有活动运行", noActiveDescription: "从已验证的端点、基准和数据集开始。", setupEvaluation: "设置评测", samples: "个样本", inspect: "查看", readiness: "就绪情况", workspaceReady: "保持工作区就绪", verified: "已验证 {{count}} 个", modelEndpoints: "模型端点", availableForEvaluation: "{{count}} 个可用于评测", verifyModel: "在排队工作前验证模型", manage: "管理", configure: "配置", evaluationData: "评测数据", readyDataset: "{{count}} 个就绪数据集", readyDatasets: "{{count}} 个就绪数据集", registerDataset: "注册数据集以开始基准评测", review: "查看", addData: "添加数据", queuePressure: "队列压力", noWorkWaiting: "没有等待中的工作", taskNeedsCapacity: "{{count}} 个任务需要容量", tasksNeedCapacity: "{{count}} 个任务需要容量", inspectQueue: "查看队列", evaluationHealth: "评测健康度", qualityAtGlance: "质量概览", openAnalysis: "打开分析", accuracy: "准确率", successful: "成功 {{successful}}/{{total}}", apiErrors: "API 错误", requests: "{{count}} 次请求", p95Latency: "P95 延迟", measured: "测量 {{count}} 次", tokens: "令牌", inputOutput: "输入 {{input}} / 输出 {{output}}", completedWork: "已完成工作", recentRuns: "近期运行", complete: "已完成 {{count}} 个", noCompleted: "尚无已完成运行", noCompletedDescription: "首次评测完成后，结果将显示在这里。", runHistory: "查看运行历史" },
  fr: { unavailableRegion: "Aperçu opérationnel indisponible", unavailableTitle: "Chargement des signaux opérationnels", unavailableDescription: "L’espace de travail reste accessible. Configurez un modèle ou inspectez vos évaluations pendant le chargement de l’état en direct.", configureModel: "Configurer un modèle", openRuns: "Ouvrir les exécutions", operations: "Opérations d’évaluation", heroTitle: "Faites avancer chaque évaluation", heroDescription: "Suivez le travail en cours, vérifiez la capacité et lancez la prochaine étape depuis un seul endroit.", viewAllRuns: "Voir toutes les exécutions", prepareWorkspace: "Préparer l’espace de travail", operationalStatus: "État opérationnel", activeRuns: "Exécutions actives", endpoints: "Points de terminaison", workers: "Agents", estimatedCost: "Coût estimé", pendingLeased: "{{pending}} en attente · {{leased}} louées", unavailable: "{{count}} indisponibles", activeQueueTasks: "{{count}} tâches actives", completedEvidence: "preuves d’exécutions terminées", currentWork: "Travail en cours", runsInProgress: "Exécutions en cours", noActiveRuns: "Aucune exécution active", noActiveDescription: "Commencez avec un point de terminaison, un référentiel et un jeu de données vérifiés.", setupEvaluation: "Configurer une évaluation", samples: "échantillons", inspect: "Inspecter", readiness: "Préparation", workspaceReady: "Préparez l’espace de travail", verified: "{{count}} vérifiés", modelEndpoints: "Points de terminaison de modèle", availableForEvaluation: "{{count}} disponibles pour l’évaluation", verifyModel: "Vérifiez un modèle avant de mettre du travail en file", manage: "Gérer", configure: "Configurer", evaluationData: "Données d’évaluation", readyDataset: "{{count}} jeu de données prêt", readyDatasets: "{{count}} jeux de données prêts", registerDataset: "Enregistrez un jeu de données pour lancer un référentiel", review: "Examiner", addData: "Ajouter des données", queuePressure: "Pression de la file", noWorkWaiting: "Aucun travail n’attend", taskNeedsCapacity: "{{count}} tâche nécessite de la capacité", tasksNeedCapacity: "{{count}} tâches nécessitent de la capacité", inspectQueue: "Inspecter la file", evaluationHealth: "Santé de l’évaluation", qualityAtGlance: "Qualité en un coup d’œil", openAnalysis: "Ouvrir l’analyse", accuracy: "Précision", successful: "{{successful}}/{{total}} réussies", apiErrors: "Erreurs API", requests: "{{count}} requêtes", p95Latency: "Latence P95", measured: "{{count}} mesurées", tokens: "Jetons", inputOutput: "{{input}} entrée / {{output}} sortie", completedWork: "Travail terminé", recentRuns: "Exécutions récentes", complete: "{{count}} terminées", noCompleted: "Aucune exécution terminée", noCompletedDescription: "Les résultats apparaîtront ici après la première évaluation.", runHistory: "Voir l’historique" },
  de: { unavailableRegion: "Betriebsübersicht nicht verfügbar", unavailableTitle: "Betriebssignale werden geladen", unavailableDescription: "Der Arbeitsbereich ist weiterhin erreichbar. Konfigurieren Sie ein Modell oder prüfen Sie Ausführungen, während der Live-Status geladen wird.", configureModel: "Modell konfigurieren", openRuns: "Ausführungen öffnen", operations: "Evaluierungsbetrieb", heroTitle: "Jede Evaluierung voranbringen", heroDescription: "Überwachen Sie aktuelle Arbeit, prüfen Sie Kapazität und führen Sie den nächsten Einrichtungsschritt an einem Ort aus.", viewAllRuns: "Alle Ausführungen anzeigen", prepareWorkspace: "Arbeitsbereich vorbereiten", operationalStatus: "Betriebsstatus", activeRuns: "Aktive Ausführungen", endpoints: "Endpunkte", workers: "Worker", estimatedCost: "Geschätzte Kosten", pendingLeased: "{{pending}} ausstehend · {{leased}} geleast", unavailable: "{{count}} nicht verfügbar", activeQueueTasks: "{{count}} aktive Warteschlangenaufgaben", completedEvidence: "Nachweise abgeschlossener Ausführungen", currentWork: "Aktuelle Arbeit", runsInProgress: "Laufende Ausführungen", noActiveRuns: "Keine aktiven Ausführungen", noActiveDescription: "Beginnen Sie mit einem verifizierten Endpunkt, Benchmark und Datensatz.", setupEvaluation: "Evaluierung einrichten", samples: "Beispiele", inspect: "Prüfen", readiness: "Bereitschaft", workspaceReady: "Arbeitsbereich bereithalten", verified: "{{count}} verifiziert", modelEndpoints: "Modellendpunkte", availableForEvaluation: "{{count}} für Evaluierung verfügbar", verifyModel: "Verifizieren Sie ein Modell vor dem Einreihen", manage: "Verwalten", configure: "Konfigurieren", evaluationData: "Evaluierungsdaten", readyDataset: "{{count}} bereiter Datensatz", readyDatasets: "{{count}} bereite Datensätze", registerDataset: "Registrieren Sie einen Datensatz für einen Benchmark", review: "Prüfen", addData: "Daten hinzufügen", queuePressure: "Warteschlangendruck", noWorkWaiting: "Keine Arbeit wartet", taskNeedsCapacity: "{{count}} Aufgabe benötigt Kapazität", tasksNeedCapacity: "{{count}} Aufgaben benötigen Kapazität", inspectQueue: "Warteschlange prüfen", evaluationHealth: "Evaluierungszustand", qualityAtGlance: "Qualität auf einen Blick", openAnalysis: "Analyse öffnen", accuracy: "Genauigkeit", successful: "{{successful}}/{{total}} erfolgreich", apiErrors: "API-Fehler", requests: "{{count}} Anfragen", p95Latency: "P95-Latenz", measured: "{{count}} gemessen", tokens: "Token", inputOutput: "{{input}} ein / {{output}} aus", completedWork: "Abgeschlossene Arbeit", recentRuns: "Letzte Ausführungen", complete: "{{count}} abgeschlossen", noCompleted: "Noch keine abgeschlossenen Ausführungen", noCompletedDescription: "Ergebnisse erscheinen hier nach der ersten abgeschlossenen Evaluierung.", runHistory: "Ausführungsverlauf anzeigen" },
  ru: { unavailableRegion: "Оперативный обзор недоступен", unavailableTitle: "Загрузка рабочих сигналов", unavailableDescription: "Рабочая область доступна. Настройте модель или проверьте запуски, пока загружается состояние в реальном времени.", configureModel: "Настроить модель", openRuns: "Открыть запуски", operations: "Операции оценки", heroTitle: "Поддерживайте движение каждой оценки", heroDescription: "Отслеживайте текущую работу, проверяйте доступную мощность и выполняйте следующий шаг настройки в одном месте.", viewAllRuns: "Все запуски", prepareWorkspace: "Подготовить рабочую область", operationalStatus: "Рабочее состояние", activeRuns: "Активные запуски", endpoints: "Конечные точки", workers: "Рабочие узлы", estimatedCost: "Расчётная стоимость", pendingLeased: "{{pending}} в ожидании · {{leased}} арендовано", unavailable: "{{count}} недоступно", activeQueueTasks: "{{count}} активных задач", completedEvidence: "доказательства завершённых запусков", currentWork: "Текущая работа", runsInProgress: "Выполняемые запуски", noActiveRuns: "Нет активных запусков", noActiveDescription: "Начните с проверенной конечной точки, бенчмарка и набора данных.", setupEvaluation: "Настроить оценку", samples: "образцов", inspect: "Открыть", readiness: "Готовность", workspaceReady: "Поддерживайте готовность рабочей области", verified: "{{count}} проверено", modelEndpoints: "Конечные точки модели", availableForEvaluation: "{{count}} доступны для оценки", verifyModel: "Проверьте модель перед постановкой задач в очередь", manage: "Управлять", configure: "Настроить", evaluationData: "Данные оценки", readyDataset: "{{count}} готовый набор данных", readyDatasets: "{{count}} готовых наборов данных", registerDataset: "Зарегистрируйте набор данных для запуска бенчмарка", review: "Проверить", addData: "Добавить данные", queuePressure: "Нагрузка очереди", noWorkWaiting: "Нет ожидающей работы", taskNeedsCapacity: "{{count}} задаче нужна мощность", tasksNeedCapacity: "{{count}} задачам нужна мощность", inspectQueue: "Проверить очередь", evaluationHealth: "Состояние оценки", qualityAtGlance: "Качество с первого взгляда", openAnalysis: "Открыть анализ", accuracy: "Точность", successful: "{{successful}}/{{total}} успешно", apiErrors: "Ошибки API", requests: "{{count}} запросов", p95Latency: "Задержка P95", measured: "{{count}} измерено", tokens: "Токены", inputOutput: "{{input}} вход / {{output}} выход", completedWork: "Завершённая работа", recentRuns: "Недавние запуски", complete: "{{count}} завершено", noCompleted: "Пока нет завершённых запусков", noCompletedDescription: "Результаты появятся здесь после завершения первой оценки.", runHistory: "История запусков" },
  ja: { unavailableRegion: "運用概要を利用できません", unavailableTitle: "運用シグナルを読み込んでいます", unavailableDescription: "ワークスペースには引き続きアクセスできます。ライブ状態が利用可能になるまで、モデルの設定または評価実行の確認を行えます。", configureModel: "モデルを設定", openRuns: "実行を開く", operations: "評価運用", heroTitle: "すべての評価を前進させる", heroDescription: "現在の作業を監視し、容量を確認して、次の設定操作を一か所から実行します。", viewAllRuns: "すべての実行を表示", prepareWorkspace: "ワークスペースを準備", operationalStatus: "運用状況", activeRuns: "アクティブな実行", endpoints: "エンドポイント", workers: "ワーカー", estimatedCost: "推定コスト", pendingLeased: "保留 {{pending}} · リース {{leased}}", unavailable: "{{count}} 利用不可", activeQueueTasks: "アクティブなキュー タスク {{count}}", completedEvidence: "完了した実行の証拠", currentWork: "現在の作業", runsInProgress: "進行中の実行", noActiveRuns: "アクティブな実行はありません", noActiveDescription: "検証済みのエンドポイント、ベンチマーク、データセットから開始します。", setupEvaluation: "評価を設定", samples: "サンプル", inspect: "確認", readiness: "準備状況", workspaceReady: "ワークスペースを準備済みに保つ", verified: "{{count}} 検証済み", modelEndpoints: "モデル エンドポイント", availableForEvaluation: "{{count}} 件を評価に使用可能", verifyModel: "作業をキューに入れる前にモデルを検証します", manage: "管理", configure: "設定", evaluationData: "評価データ", readyDataset: "準備済みデータセット {{count}} 件", readyDatasets: "準備済みデータセット {{count}} 件", registerDataset: "ベンチマークを開始するにはデータセットを登録します", review: "確認", addData: "データを追加", queuePressure: "キューの負荷", noWorkWaiting: "待機中の作業はありません", taskNeedsCapacity: "{{count}} 件のタスクに容量が必要", tasksNeedCapacity: "{{count}} 件のタスクに容量が必要", inspectQueue: "キューを確認", evaluationHealth: "評価の健全性", qualityAtGlance: "品質の概要", openAnalysis: "分析を開く", accuracy: "正確性", successful: "{{successful}}/{{total}} 成功", apiErrors: "API エラー", requests: "{{count}} リクエスト", p95Latency: "P95 レイテンシ", measured: "{{count}} 件を測定", tokens: "トークン", inputOutput: "入力 {{input}} / 出力 {{output}}", completedWork: "完了した作業", recentRuns: "最近の実行", complete: "{{count}} 件完了", noCompleted: "完了した実行はまだありません", noCompletedDescription: "最初の評価が完了すると、結果がここに表示されます。", runHistory: "実行履歴を表示" },
  ko: { unavailableRegion: "운영 개요를 사용할 수 없음", unavailableTitle: "운영 신호를 불러오는 중", unavailableDescription: "작업 공간에는 계속 접근할 수 있습니다. 실시간 상태를 사용할 수 있을 때까지 모델을 구성하거나 평가 실행을 확인하세요.", configureModel: "모델 구성", openRuns: "실행 열기", operations: "평가 운영", heroTitle: "모든 평가를 계속 진행하세요", heroDescription: "현재 작업을 모니터링하고 용량을 확인한 후 다음 설정 단계를 한 곳에서 수행합니다.", viewAllRuns: "모든 실행 보기", prepareWorkspace: "작업 공간 준비", operationalStatus: "운영 상태", activeRuns: "활성 실행", endpoints: "엔드포인트", workers: "워커", estimatedCost: "예상 비용", pendingLeased: "대기 {{pending}} · 임대 {{leased}}", unavailable: "{{count}}개 사용 불가", activeQueueTasks: "활성 대기열 작업 {{count}}개", completedEvidence: "완료된 실행 증거", currentWork: "현재 작업", runsInProgress: "진행 중인 실행", noActiveRuns: "활성 실행이 없습니다", noActiveDescription: "확인된 엔드포인트, 벤치마크 및 데이터 세트에서 시작하세요.", setupEvaluation: "평가 설정", samples: "샘플", inspect: "검사", readiness: "준비 상태", workspaceReady: "작업 공간을 준비 상태로 유지", verified: "{{count}}개 확인됨", modelEndpoints: "모델 엔드포인트", availableForEvaluation: "{{count}}개를 평가에 사용할 수 있음", verifyModel: "작업을 대기열에 넣기 전에 모델을 확인하세요", manage: "관리", configure: "구성", evaluationData: "평가 데이터", readyDataset: "준비된 데이터 세트 {{count}}개", readyDatasets: "준비된 데이터 세트 {{count}}개", registerDataset: "벤치마크를 시작하려면 데이터 세트를 등록하세요", review: "검토", addData: "데이터 추가", queuePressure: "대기열 압력", noWorkWaiting: "대기 중인 작업이 없습니다", taskNeedsCapacity: "작업 {{count}}개에 용량이 필요함", tasksNeedCapacity: "작업 {{count}}개에 용량이 필요함", inspectQueue: "대기열 검사", evaluationHealth: "평가 상태", qualityAtGlance: "한눈에 보는 품질", openAnalysis: "분석 열기", accuracy: "정확도", successful: "{{successful}}/{{total}}개 성공", apiErrors: "API 오류", requests: "요청 {{count}}개", p95Latency: "P95 지연 시간", measured: "{{count}}개 측정", tokens: "토큰", inputOutput: "입력 {{input}} / 출력 {{output}}", completedWork: "완료된 작업", recentRuns: "최근 실행", complete: "{{count}}개 완료", noCompleted: "완료된 실행이 아직 없습니다", noCompletedDescription: "첫 번째 평가가 끝나면 결과가 여기에 표시됩니다.", runHistory: "실행 기록 보기" },
  ms: { unavailableRegion: "Gambaran operasi tidak tersedia", unavailableTitle: "Memuatkan isyarat operasi", unavailableDescription: "Ruang kerja masih boleh dicapai. Konfigurasikan model atau periksa larian penilaian sementara status langsung tersedia.", configureModel: "Konfigurasi model", openRuns: "Buka larian", operations: "Operasi penilaian", heroTitle: "Pastikan setiap penilaian bergerak", heroDescription: "Pantau kerja semasa, sahkan kapasiti dan lakukan langkah persediaan seterusnya dari satu tempat.", viewAllRuns: "Lihat semua larian", prepareWorkspace: "Sediakan ruang kerja", operationalStatus: "Status operasi", activeRuns: "Larian aktif", endpoints: "Titik akhir", workers: "Pekerja", estimatedCost: "Kos anggaran", pendingLeased: "{{pending}} menunggu · {{leased}} dipajak", unavailable: "{{count}} tidak tersedia", activeQueueTasks: "{{count}} tugas baris aktif", completedEvidence: "bukti larian selesai", currentWork: "Kerja semasa", runsInProgress: "Larian sedang berjalan", noActiveRuns: "Tiada larian aktif", noActiveDescription: "Mulakan dengan titik akhir, penanda aras dan set data yang disahkan.", setupEvaluation: "Sediakan penilaian", samples: "sampel", inspect: "Periksa", readiness: "Kesediaan", workspaceReady: "Pastikan ruang kerja sedia", verified: "{{count}} disahkan", modelEndpoints: "Titik akhir model", availableForEvaluation: "{{count}} tersedia untuk penilaian", verifyModel: "Sahkan model sebelum memasukkan kerja ke baris", manage: "Urus", configure: "Konfigurasi", evaluationData: "Data penilaian", readyDataset: "{{count}} set data sedia", readyDatasets: "{{count}} set data sedia", registerDataset: "Daftarkan set data untuk memulakan penanda aras", review: "Semak", addData: "Tambah data", queuePressure: "Tekanan baris", noWorkWaiting: "Tiada kerja menunggu", taskNeedsCapacity: "{{count}} tugas memerlukan kapasiti", tasksNeedCapacity: "{{count}} tugas memerlukan kapasiti", inspectQueue: "Periksa baris", evaluationHealth: "Kesihatan penilaian", qualityAtGlance: "Kualiti sepintas lalu", openAnalysis: "Buka analisis", accuracy: "Ketepatan", successful: "{{successful}}/{{total}} berjaya", apiErrors: "Ralat API", requests: "{{count}} permintaan", p95Latency: "Kependaman P95", measured: "{{count}} diukur", tokens: "Token", inputOutput: "{{input}} masuk / {{output}} keluar", completedWork: "Kerja selesai", recentRuns: "Larian terkini", complete: "{{count}} selesai", noCompleted: "Belum ada larian selesai", noCompletedDescription: "Hasil akan muncul di sini selepas penilaian pertama selesai.", runHistory: "Lihat sejarah larian" },
};

const analyticsOverviewCopy: Record<Locale, AnalyticsOverviewCopy> = {
  en: {
    dashboardTitle: "Dashboard",
    dashboardDescription: "Track evaluation quality, model behavior, and operational readiness from live evidence.",
    performanceSummary: "Performance summary",
    successRate: "Success rate",
    evaluationTrend: "Evaluation trend",
    limitedHistory: "More completed runs are needed to show a trend.",
    noHistory: "Evaluation history is not available yet.",
    modelBenchmarkComparison: "Model / benchmark comparison",
    model: "Model",
    benchmark: "Benchmark",
    sampleCount: "Samples",
    latencyCostErrors: "Latency, cost & errors",
    latency: "Latency",
    cost: "Cost",
    errorRate: "Error rate",
    recentEvaluations: "Recent evaluations",
    progress: "Progress",
    started: "Started",
    systemReadiness: "System readiness",
    operational: "Operational",
    attentionNeeded: "Attention needed",
    unknownValue: "Not available",
  },
  "zh-CN": {
    dashboardTitle: "仪表板",
    dashboardDescription: "基于实时评测证据跟踪质量、模型表现和运营就绪情况。",
    performanceSummary: "性能摘要",
    successRate: "成功率",
    evaluationTrend: "评测趋势",
    limitedHistory: "需要更多已完成运行才能显示趋势。",
    noHistory: "暂无评测历史。",
    modelBenchmarkComparison: "模型 / 基准比较",
    model: "模型",
    benchmark: "基准",
    sampleCount: "样本数",
    latencyCostErrors: "延迟、成本和错误",
    latency: "延迟",
    cost: "成本",
    errorRate: "错误率",
    recentEvaluations: "近期评测",
    progress: "进度",
    started: "开始时间",
    systemReadiness: "系统就绪情况",
    operational: "运行正常",
    attentionNeeded: "需要关注",
    unknownValue: "不可用",
  },
  fr: {
    dashboardTitle: "Tableau de bord",
    dashboardDescription: "Suivez la qualité des évaluations, le comportement des modèles et la préparation opérationnelle à partir de preuves en direct.",
    performanceSummary: "Synthèse des performances",
    successRate: "Taux de réussite",
    evaluationTrend: "Tendance des évaluations",
    limitedHistory: "D’autres exécutions terminées sont nécessaires pour afficher une tendance.",
    noHistory: "L’historique des évaluations n’est pas encore disponible.",
    modelBenchmarkComparison: "Comparaison modèle / référentiel",
    model: "Modèle",
    benchmark: "Référentiel",
    sampleCount: "Échantillons",
    latencyCostErrors: "Latence, coût et erreurs",
    latency: "Latence",
    cost: "Coût",
    errorRate: "Taux d’erreur",
    recentEvaluations: "Évaluations récentes",
    progress: "Progression",
    started: "Démarrée",
    systemReadiness: "Préparation du système",
    operational: "Opérationnel",
    attentionNeeded: "Attention requise",
    unknownValue: "Indisponible",
  },
  de: {
    dashboardTitle: "Dashboard",
    dashboardDescription: "Verfolgen Sie Evaluierungsqualität, Modellverhalten und Betriebsbereitschaft anhand aktueller Evidenz.",
    performanceSummary: "Leistungsübersicht",
    successRate: "Erfolgsrate",
    evaluationTrend: "Evaluierungstrend",
    limitedHistory: "Für einen Trend sind weitere abgeschlossene Ausführungen erforderlich.",
    noHistory: "Der Evaluierungsverlauf ist noch nicht verfügbar.",
    modelBenchmarkComparison: "Modell-/Benchmark-Vergleich",
    model: "Modell",
    benchmark: "Benchmark",
    sampleCount: "Stichproben",
    latencyCostErrors: "Latenz, Kosten und Fehler",
    latency: "Latenz",
    cost: "Kosten",
    errorRate: "Fehlerrate",
    recentEvaluations: "Letzte Evaluierungen",
    progress: "Fortschritt",
    started: "Gestartet",
    systemReadiness: "Systembereitschaft",
    operational: "Betriebsbereit",
    attentionNeeded: "Handlungsbedarf",
    unknownValue: "Nicht verfügbar",
  },
  ru: {
    dashboardTitle: "Панель",
    dashboardDescription: "Отслеживайте качество оценок, поведение моделей и операционную готовность по текущим данным.",
    performanceSummary: "Сводка показателей",
    successRate: "Доля успешных",
    evaluationTrend: "Динамика оценок",
    limitedHistory: "Для графика нужны дополнительные завершённые запуски.",
    noHistory: "История оценок пока недоступна.",
    modelBenchmarkComparison: "Сравнение модели и бенчмарка",
    model: "Модель",
    benchmark: "Бенчмарк",
    sampleCount: "Образцы",
    latencyCostErrors: "Задержка, стоимость и ошибки",
    latency: "Задержка",
    cost: "Стоимость",
    errorRate: "Доля ошибок",
    recentEvaluations: "Недавние оценки",
    progress: "Ход выполнения",
    started: "Запущено",
    systemReadiness: "Готовность системы",
    operational: "Работает",
    attentionNeeded: "Требует внимания",
    unknownValue: "Недоступно",
  },
  ja: {
    dashboardTitle: "ダッシュボード",
    dashboardDescription: "最新の証拠から評価品質、モデルの挙動、運用準備状況を追跡します。",
    performanceSummary: "パフォーマンス概要",
    successRate: "成功率",
    evaluationTrend: "評価トレンド",
    limitedHistory: "トレンド表示には、さらに完了した実行が必要です。",
    noHistory: "評価履歴はまだありません。",
    modelBenchmarkComparison: "モデル / ベンチマーク比較",
    model: "モデル",
    benchmark: "ベンチマーク",
    sampleCount: "サンプル数",
    latencyCostErrors: "レイテンシ、コスト、エラー",
    latency: "レイテンシ",
    cost: "コスト",
    errorRate: "エラー率",
    recentEvaluations: "最近の評価",
    progress: "進行状況",
    started: "開始",
    systemReadiness: "システム準備状況",
    operational: "稼働中",
    attentionNeeded: "要確認",
    unknownValue: "利用不可",
  },
  ko: {
    dashboardTitle: "대시보드",
    dashboardDescription: "실시간 증거로 평가 품질, 모델 동작 및 운영 준비 상태를 추적합니다.",
    performanceSummary: "성능 요약",
    successRate: "성공률",
    evaluationTrend: "평가 추이",
    limitedHistory: "추이를 표시하려면 완료된 실행이 더 필요합니다.",
    noHistory: "아직 평가 기록이 없습니다.",
    modelBenchmarkComparison: "모델 / 벤치마크 비교",
    model: "모델",
    benchmark: "벤치마크",
    sampleCount: "샘플 수",
    latencyCostErrors: "지연 시간, 비용 및 오류",
    latency: "지연 시간",
    cost: "비용",
    errorRate: "오류율",
    recentEvaluations: "최근 평가",
    progress: "진행률",
    started: "시작됨",
    systemReadiness: "시스템 준비 상태",
    operational: "정상",
    attentionNeeded: "확인 필요",
    unknownValue: "사용할 수 없음",
  },
  ms: {
    dashboardTitle: "Papan pemuka",
    dashboardDescription: "Jejaki kualiti penilaian, tingkah laku model dan kesediaan operasi daripada bukti langsung.",
    performanceSummary: "Ringkasan prestasi",
    successRate: "Kadar kejayaan",
    evaluationTrend: "Trend penilaian",
    limitedHistory: "Lebih banyak larian selesai diperlukan untuk memaparkan trend.",
    noHistory: "Sejarah penilaian belum tersedia.",
    modelBenchmarkComparison: "Perbandingan model / penanda aras",
    model: "Model",
    benchmark: "Penanda aras",
    sampleCount: "Sampel",
    latencyCostErrors: "Kependaman, kos dan ralat",
    latency: "Kependaman",
    cost: "Kos",
    errorRate: "Kadar ralat",
    recentEvaluations: "Penilaian terkini",
    progress: "Kemajuan",
    started: "Dimulakan",
    systemReadiness: "Kesediaan sistem",
    operational: "Beroperasi",
    attentionNeeded: "Perlu perhatian",
    unknownValue: "Tidak tersedia",
  },
};

export const overviewCopy: Record<Locale, OverviewCopy> = {
  en: { ...overviewCopyBase.en, ...analyticsOverviewCopy.en },
  "zh-CN": { ...overviewCopyBase["zh-CN"], ...analyticsOverviewCopy["zh-CN"] },
  fr: { ...overviewCopyBase.fr, ...analyticsOverviewCopy.fr },
  de: { ...overviewCopyBase.de, ...analyticsOverviewCopy.de },
  ru: { ...overviewCopyBase.ru, ...analyticsOverviewCopy.ru },
  ja: { ...overviewCopyBase.ja, ...analyticsOverviewCopy.ja },
  ko: { ...overviewCopyBase.ko, ...analyticsOverviewCopy.ko },
  ms: { ...overviewCopyBase.ms, ...analyticsOverviewCopy.ms },
};

export type ReportCopy = {
  noArtifacts: string; artifacts: string; readOnlyPolicy: string; expiresInDays: string; optionalPassword: string; passwordPlaceholder: string;
  allowDownload: string; shareRawEvidence: string; policyDescription: string; openShare: string; format: string; generated: string; version: string;
  download: string; share: string; shareCreateFailed: string; downloadFailed: string; sharedReport: string; readOnlyAccess: string; passwordSafety: string;
  sharePassword: string; opening: string; openReport: string; initialMessage: string; readyMessage: string; unavailableMessage: string; openNewTab: string;
};

export const reportCopy: Record<Locale, ReportCopy> = {
  en: { noArtifacts: "No report artifacts for this run yet.", artifacts: "Report artifacts", readOnlyPolicy: "Read-only sharing policy", expiresInDays: "Expires in days", optionalPassword: "Optional password", passwordPlaceholder: "Required to open when set", allowDownload: "Allow download", shareRawEvidence: "Share raw evidence", policyDescription: "Raw JSON, CSV, and Parquet reports require both controls. Share links can be revoked through the report API.", openShare: "Open the newly created share link", format: "Format", generated: "Generated", version: "Version", download: "Download", share: "Share", shareCreateFailed: "The report share could not be created.", downloadFailed: "The report download failed.", sharedReport: "Shared evaluation report", readOnlyAccess: "Read-only report access", passwordSafety: "The password is sent only with this request and is never added to the URL or browser storage.", sharePassword: "Share password (if required)", opening: "Opening report…", openReport: "Open report", initialMessage: "Enter the optional share password to open this read-only report.", readyMessage: "The shared report is ready to view.", unavailableMessage: "The shared report could not be opened. Check the password, expiry, or link.", openNewTab: "Open report in a new tab" },
  "zh-CN": { noArtifacts: "此运行尚无报告工件。", artifacts: "报告工件", readOnlyPolicy: "只读共享策略", expiresInDays: "有效期（天）", optionalPassword: "可选密码", passwordPlaceholder: "设置后打开时需要", allowDownload: "允许下载", shareRawEvidence: "共享原始证据", policyDescription: "原始 JSON、CSV 和 Parquet 报告需要同时启用两个控件。可通过报告 API 撤销共享链接。", openShare: "打开新创建的共享链接", format: "格式", generated: "生成时间", version: "版本", download: "下载", share: "共享", shareCreateFailed: "无法创建报告共享。", downloadFailed: "报告下载失败。", sharedReport: "共享评测报告", readOnlyAccess: "只读报告访问", passwordSafety: "密码仅随此请求发送，绝不会添加到 URL 或浏览器存储中。", sharePassword: "共享密码（如需要）", opening: "正在打开报告…", openReport: "打开报告", initialMessage: "请输入可选的共享密码以打开此只读报告。", readyMessage: "共享报告已可查看。", unavailableMessage: "无法打开共享报告。请检查密码、有效期或链接。", openNewTab: "在新标签页中打开报告" },
  fr: { noArtifacts: "Aucun artefact de rapport pour cette exécution.", artifacts: "Artefacts de rapport", readOnlyPolicy: "Politique de partage en lecture seule", expiresInDays: "Expire dans", optionalPassword: "Mot de passe facultatif", passwordPlaceholder: "Requis pour ouvrir lorsqu’il est défini", allowDownload: "Autoriser le téléchargement", shareRawEvidence: "Partager les preuves brutes", policyDescription: "Les rapports JSON, CSV et Parquet bruts nécessitent les deux contrôles. Les liens peuvent être révoqués par l’API.", openShare: "Ouvrir le nouveau lien partagé", format: "Format", generated: "Généré", version: "Version", download: "Télécharger", share: "Partager", shareCreateFailed: "Le partage du rapport n’a pas pu être créé.", downloadFailed: "Le téléchargement du rapport a échoué.", sharedReport: "Rapport d’évaluation partagé", readOnlyAccess: "Accès au rapport en lecture seule", passwordSafety: "Le mot de passe est envoyé uniquement avec cette requête et n’est jamais ajouté à l’URL ou au stockage du navigateur.", sharePassword: "Mot de passe de partage (si nécessaire)", opening: "Ouverture du rapport…", openReport: "Ouvrir le rapport", initialMessage: "Saisissez le mot de passe facultatif pour ouvrir ce rapport en lecture seule.", readyMessage: "Le rapport partagé est prêt à être consulté.", unavailableMessage: "Le rapport partagé n’a pas pu être ouvert. Vérifiez le mot de passe, l’expiration ou le lien.", openNewTab: "Ouvrir le rapport dans un nouvel onglet" },
  de: { noArtifacts: "Für diese Ausführung gibt es noch keine Berichtsartefakte.", artifacts: "Berichtsartefakte", readOnlyPolicy: "Freigaberichtlinie nur lesen", expiresInDays: "Läuft ab in Tagen", optionalPassword: "Optionales Passwort", passwordPlaceholder: "Beim Öffnen erforderlich, wenn gesetzt", allowDownload: "Download erlauben", shareRawEvidence: "Rohdaten teilen", policyDescription: "Rohe JSON-, CSV- und Parquet-Berichte benötigen beide Optionen. Freigabelinks können über die Bericht-API widerrufen werden.", openShare: "Neuen Freigabelink öffnen", format: "Format", generated: "Erstellt", version: "Version", download: "Herunterladen", share: "Teilen", shareCreateFailed: "Die Berichtsfreigabe konnte nicht erstellt werden.", downloadFailed: "Der Berichtsdownload ist fehlgeschlagen.", sharedReport: "Geteilter Evaluierungsbericht", readOnlyAccess: "Schreibgeschützter Berichtszugriff", passwordSafety: "Das Passwort wird nur mit dieser Anfrage gesendet und nie der URL oder dem Browserspeicher hinzugefügt.", sharePassword: "Freigabepasswort (falls erforderlich)", opening: "Bericht wird geöffnet…", openReport: "Bericht öffnen", initialMessage: "Geben Sie das optionale Freigabepasswort ein, um diesen schreibgeschützten Bericht zu öffnen.", readyMessage: "Der geteilte Bericht kann angezeigt werden.", unavailableMessage: "Der geteilte Bericht konnte nicht geöffnet werden. Prüfen Sie Passwort, Ablauf oder Link.", openNewTab: "Bericht in neuem Tab öffnen" },
  ru: { noArtifacts: "Для этого запуска пока нет артефактов отчёта.", artifacts: "Артефакты отчёта", readOnlyPolicy: "Политика общего доступа только для чтения", expiresInDays: "Срок действия в днях", optionalPassword: "Необязательный пароль", passwordPlaceholder: "Требуется для открытия, если задан", allowDownload: "Разрешить скачивание", shareRawEvidence: "Поделиться исходными доказательствами", policyDescription: "Для исходных отчётов JSON, CSV и Parquet нужны оба параметра. Ссылки можно отозвать через API отчётов.", openShare: "Открыть новую общую ссылку", format: "Формат", generated: "Создан", version: "Версия", download: "Скачать", share: "Поделиться", shareCreateFailed: "Не удалось создать общий доступ к отчёту.", downloadFailed: "Не удалось скачать отчёт.", sharedReport: "Общий отчёт об оценке", readOnlyAccess: "Доступ к отчёту только для чтения", passwordSafety: "Пароль отправляется только с этим запросом и не добавляется в URL или хранилище браузера.", sharePassword: "Пароль общего доступа (если нужен)", opening: "Открытие отчёта…", openReport: "Открыть отчёт", initialMessage: "Введите необязательный пароль общего доступа, чтобы открыть этот отчёт только для чтения.", readyMessage: "Общий отчёт готов к просмотру.", unavailableMessage: "Не удалось открыть общий отчёт. Проверьте пароль, срок действия или ссылку.", openNewTab: "Открыть отчёт в новой вкладке" },
  ja: { noArtifacts: "この実行にはまだレポート アーティファクトがありません。", artifacts: "レポート アーティファクト", readOnlyPolicy: "読み取り専用の共有ポリシー", expiresInDays: "有効期限（日数）", optionalPassword: "任意のパスワード", passwordPlaceholder: "設定時は開くために必要", allowDownload: "ダウンロードを許可", shareRawEvidence: "生の証拠を共有", policyDescription: "生の JSON、CSV、Parquet レポートには両方の設定が必要です。共有リンクはレポート API で取り消せます。", openShare: "新しい共有リンクを開く", format: "形式", generated: "生成", version: "バージョン", download: "ダウンロード", share: "共有", shareCreateFailed: "レポート共有を作成できませんでした。", downloadFailed: "レポートをダウンロードできませんでした。", sharedReport: "共有評価レポート", readOnlyAccess: "読み取り専用レポート アクセス", passwordSafety: "パスワードはこのリクエストでのみ送信され、URL やブラウザー ストレージには追加されません。", sharePassword: "共有パスワード（必要な場合）", opening: "レポートを開いています…", openReport: "レポートを開く", initialMessage: "この読み取り専用レポートを開くには、任意の共有パスワードを入力します。", readyMessage: "共有レポートを表示できます。", unavailableMessage: "共有レポートを開けませんでした。パスワード、有効期限、リンクを確認してください。", openNewTab: "新しいタブでレポートを開く" },
  ko: { noArtifacts: "이 실행에는 아직 보고서 아티팩트가 없습니다.", artifacts: "보고서 아티팩트", readOnlyPolicy: "읽기 전용 공유 정책", expiresInDays: "만료 일수", optionalPassword: "선택적 비밀번호", passwordPlaceholder: "설정된 경우 열 때 필요", allowDownload: "다운로드 허용", shareRawEvidence: "원시 증거 공유", policyDescription: "원시 JSON, CSV 및 Parquet 보고서에는 두 설정이 모두 필요합니다. 공유 링크는 보고서 API에서 해제할 수 있습니다.", openShare: "새 공유 링크 열기", format: "형식", generated: "생성됨", version: "버전", download: "다운로드", share: "공유", shareCreateFailed: "보고서 공유를 만들 수 없습니다.", downloadFailed: "보고서 다운로드에 실패했습니다.", sharedReport: "공유 평가 보고서", readOnlyAccess: "읽기 전용 보고서 액세스", passwordSafety: "비밀번호는 이 요청과 함께만 전송되며 URL이나 브라우저 저장소에 추가되지 않습니다.", sharePassword: "공유 비밀번호(필요한 경우)", opening: "보고서를 여는 중…", openReport: "보고서 열기", initialMessage: "이 읽기 전용 보고서를 열려면 선택적 공유 비밀번호를 입력하세요.", readyMessage: "공유 보고서를 볼 수 있습니다.", unavailableMessage: "공유 보고서를 열 수 없습니다. 비밀번호, 만료 또는 링크를 확인하세요.", openNewTab: "새 탭에서 보고서 열기" },
  ms: { noArtifacts: "Tiada artifak laporan untuk larian ini lagi.", artifacts: "Artifak laporan", readOnlyPolicy: "Dasar perkongsian baca sahaja", expiresInDays: "Tamat dalam hari", optionalPassword: "Kata laluan pilihan", passwordPlaceholder: "Diperlukan untuk dibuka apabila ditetapkan", allowDownload: "Benarkan muat turun", shareRawEvidence: "Kongsi bukti mentah", policyDescription: "Laporan JSON, CSV dan Parquet mentah memerlukan kedua-dua kawalan. Pautan kongsi boleh dibatalkan melalui API laporan.", openShare: "Buka pautan kongsi baharu", format: "Format", generated: "Dijana", version: "Versi", download: "Muat turun", share: "Kongsi", shareCreateFailed: "Perkongsian laporan tidak dapat dibuat.", downloadFailed: "Muat turun laporan gagal.", sharedReport: "Laporan penilaian dikongsi", readOnlyAccess: "Akses laporan baca sahaja", passwordSafety: "Kata laluan dihantar hanya dengan permintaan ini dan tidak pernah ditambah pada URL atau storan pelayar.", sharePassword: "Kata laluan perkongsian (jika perlu)", opening: "Membuka laporan…", openReport: "Buka laporan", initialMessage: "Masukkan kata laluan perkongsian pilihan untuk membuka laporan baca sahaja ini.", readyMessage: "Laporan dikongsi sedia untuk dilihat.", unavailableMessage: "Laporan dikongsi tidak dapat dibuka. Semak kata laluan, tempoh tamat atau pautan.", openNewTab: "Buka laporan dalam tab baharu" },
};
