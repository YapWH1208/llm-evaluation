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
