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
};

export const catalogs: Record<Locale, TranslationCatalog> = { en, "zh-CN": zhCN, fr, de, ru, ja, ko, ms };

export function isLocale(value: string | null | undefined): value is Locale {
  return typeof value === "string" && localeIds.includes(value as Locale);
}

export function resolveLocale(value: string | null | undefined): Locale {
  return isLocale(value) ? value : "en";
}

export const workspaceViews = ["dashboard", "models", "capabilities", "workspace", "benchmarks", "datasets", "suites", "runs", "queue", "workers", "analysis", "compare", "reports", "reviews", "users", "settings"] as const;
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
    ["Dashboard", "Operational status and recent work"], ["Models", "Endpoints and run defaults"], ["Capabilities", "Detection and declarations"], ["Workspace", "Prompts, assets, and setup"], ["Benchmarks", "Benchmark registry"], ["Datasets", "Versioned data sources"], ["Suites", "Reusable evaluation suites"], ["Runs", "Execution, results, and evidence"], ["Task queue", "Priorities and pending work"], ["Workers", "Leases and active workers"], ["Analysis", "Capability and trend evidence"], ["Compare", "Run-to-run comparisons"], ["Reports", "Exports and shared artifacts"], ["Human review", "Review and adjudication"], ["Users", "Users and audit activity"], ["Settings", "Health, access, and preferences"],
  ]),
  "zh-CN": navigation(["概览", "配置", "运营", "洞察", "系统"], [
    ["仪表盘", "运行状态和近期工作"], ["模型", "端点和运行默认值"], ["能力", "检测与声明"], ["工作区", "提示词、资产与设置"], ["基准", "评测基准注册表"], ["数据集", "版本化数据源"], ["套件", "可复用的评测套件"], ["运行", "执行、结果与证据"], ["任务队列", "优先级与待处理工作"], ["工作节点", "租约和活动工作节点"], ["分析", "能力与趋势证据"], ["对比", "运行之间的对比"], ["报告", "导出和共享工件"], ["人工审核", "审核与裁决"], ["用户", "用户和审计活动"], ["设置", "运行状况、访问和偏好设置"],
  ]),
  fr: navigation(["Aperçu", "Configuration", "Opérations", "Analyses", "Système"], [
    ["Tableau de bord", "État opérationnel et travaux récents"], ["Modèles", "Points de terminaison et paramètres d’exécution"], ["Capacités", "Détection et déclarations"], ["Espace de travail", "Prompts, ressources et configuration"], ["Référentiels", "Registre des référentiels"], ["Jeux de données", "Sources de données versionnées"], ["Suites", "Suites d’évaluation réutilisables"], ["Exécutions", "Exécution, résultats et preuves"], ["File d’attente", "Priorités et travail en attente"], ["Workers", "Baux et workers actifs"], ["Analyse", "Preuves de capacités et tendances"], ["Comparer", "Comparaisons entre exécutions"], ["Rapports", "Exports et artefacts partagés"], ["Révision humaine", "Révision et arbitrage"], ["Utilisateurs", "Utilisateurs et activité d’audit"], ["Paramètres", "État, accès et préférences"],
  ]),
  de: navigation(["Übersicht", "Konfiguration", "Betrieb", "Einblicke", "System"], [
    ["Dashboard", "Betriebsstatus und aktuelle Arbeit"], ["Modelle", "Endpunkte und Ausführungsstandards"], ["Fähigkeiten", "Erkennung und Deklarationen"], ["Arbeitsbereich", "Prompts, Assets und Einrichtung"], ["Benchmarks", "Benchmark-Register"], ["Datensätze", "Versionierte Datenquellen"], ["Suiten", "Wiederverwendbare Evaluierungssuiten"], ["Ausführungen", "Ausführung, Ergebnisse und Nachweise"], ["Aufgabenwarteschlange", "Prioritäten und ausstehende Arbeit"], ["Worker", "Leases und aktive Worker"], ["Analyse", "Fähigkeits- und Trendnachweise"], ["Vergleichen", "Vergleiche zwischen Ausführungen"], ["Berichte", "Exporte und geteilte Artefakte"], ["Menschliche Prüfung", "Prüfung und Entscheidung"], ["Benutzer", "Benutzer und Auditaktivität"], ["Einstellungen", "Status, Zugriff und Präferenzen"],
  ]),
  ru: navigation(["Обзор", "Настройка", "Операции", "Аналитика", "Система"], [
    ["Панель", "Рабочее состояние и недавние задачи"], ["Модели", "Конечные точки и настройки запуска"], ["Возможности", "Обнаружение и объявления"], ["Рабочая область", "Промпты, ресурсы и настройка"], ["Бенчмарки", "Реестр бенчмарков"], ["Наборы данных", "Версионируемые источники данных"], ["Наборы", "Повторно используемые наборы оценки"], ["Запуски", "Выполнение, результаты и доказательства"], ["Очередь задач", "Приоритеты и ожидающая работа"], ["Рабочие узлы", "Аренды и активные рабочие узлы"], ["Анализ", "Доказательства возможностей и трендов"], ["Сравнение", "Сравнения запусков"], ["Отчёты", "Экспорт и общие артефакты"], ["Проверка человеком", "Проверка и арбитраж"], ["Пользователи", "Пользователи и аудит"], ["Настройки", "Состояние, доступ и предпочтения"],
  ]),
  ja: navigation(["概要", "設定", "運用", "分析情報", "システム"], [
    ["ダッシュボード", "運用状況と最近の作業"], ["モデル", "エンドポイントと実行の既定値"], ["機能", "検出と宣言"], ["ワークスペース", "プロンプト、アセット、設定"], ["ベンチマーク", "ベンチマーク レジストリ"], ["データセット", "バージョン管理されたデータソース"], ["スイート", "再利用可能な評価スイート"], ["実行", "実行、結果、証拠"], ["タスク キュー", "優先順位と保留中の作業"], ["ワーカー", "リースとアクティブなワーカー"], ["分析", "機能と傾向の証拠"], ["比較", "実行間の比較"], ["レポート", "エクスポートと共有アーティファクト"], ["人によるレビュー", "レビューと裁定"], ["ユーザー", "ユーザーと監査アクティビティ"], ["設定", "状態、アクセス、設定"],
  ]),
  ko: navigation(["개요", "구성", "운영", "인사이트", "시스템"], [
    ["대시보드", "운영 상태 및 최근 작업"], ["모델", "엔드포인트 및 실행 기본값"], ["기능", "감지 및 선언"], ["작업 공간", "프롬프트, 자산 및 설정"], ["벤치마크", "벤치마크 레지스트리"], ["데이터 세트", "버전 관리 데이터 원본"], ["스위트", "재사용 가능한 평가 스위트"], ["실행", "실행, 결과 및 증거"], ["작업 대기열", "우선순위 및 대기 중인 작업"], ["워커", "리스 및 활성 워커"], ["분석", "기능 및 추세 증거"], ["비교", "실행 간 비교"], ["보고서", "내보내기 및 공유 아티팩트"], ["사람 검토", "검토 및 조정"], ["사용자", "사용자 및 감사 활동"], ["설정", "상태, 액세스 및 기본 설정"],
  ]),
  ms: navigation(["Gambaran keseluruhan", "Konfigurasi", "Operasi", "Wawasan", "Sistem"], [
    ["Papan pemuka", "Status operasi dan kerja terkini"], ["Model", "Titik akhir dan lalai pelaksanaan"], ["Keupayaan", "Pengesanan dan pengisytiharan"], ["Ruang kerja", "Prom, aset dan persediaan"], ["Penanda aras", "Daftar penanda aras"], ["Set data", "Sumber data berversi"], ["Suite", "Suite penilaian boleh guna semula"], ["Larian", "Pelaksanaan, hasil dan bukti"], ["Baris tugas", "Keutamaan dan kerja menunggu"], ["Pekerja", "Pajakan dan pekerja aktif"], ["Analisis", "Bukti keupayaan dan aliran"], ["Bandingkan", "Perbandingan antara larian"], ["Laporan", "Eksport dan artifak dikongsi"], ["Semakan manusia", "Semakan dan pengadilan"], ["Pengguna", "Pengguna dan aktiviti audit"], ["Tetapan", "Kesihatan, akses dan keutamaan"],
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
