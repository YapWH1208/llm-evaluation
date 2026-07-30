import { createContext, ReactNode, useCallback, useContext, useEffect, useMemo, useState } from "react";

import { catalogs, Locale, resolveLocale, TranslationKey } from "./catalog";

type TranslationValues = Record<string, number | string | null | undefined>;

type LocaleContextValue = {
  locale: Locale;
  setLocale: (locale: Locale) => void;
  t: (key: TranslationKey, values?: TranslationValues) => string;
  formatDate: (value: string | null | undefined) => string;
  formatNumber: (value: number | null | undefined, digits?: number) => string;
  formatPercent: (value: number | null | undefined) => string;
  formatCurrency: (value: number | null | undefined, currency: string | null | undefined, digits?: number) => string;
};

const LocaleContext = createContext<LocaleContextValue | null>(null);

function interpolate(template: string, values: TranslationValues | undefined) {
  if (!values) return template;
  return template.replace(/\{\{(\w+)\}\}/g, (_match, key: string) => String(values[key] ?? ""));
}

export function LocaleProvider({ children }: { children: ReactNode }) {
  const [locale, setLocaleState] = useState<Locale>(() => resolveLocale(window.localStorage.getItem("lle-locale")));

  useEffect(() => {
    document.documentElement.lang = locale;
    window.localStorage.setItem("lle-locale", locale);
  }, [locale]);

  const setLocale = useCallback((nextLocale: Locale) => setLocaleState(resolveLocale(nextLocale)), []);
  const t = useCallback((key: TranslationKey, values?: TranslationValues) => interpolate(catalogs[locale][key] ?? catalogs.en[key], values), [locale]);
  const formatNumber = useCallback((value: number | null | undefined, digits = 2) => value === null || value === undefined ? "--" : new Intl.NumberFormat(locale, { maximumFractionDigits: digits }).format(value), [locale]);
  const formatPercent = useCallback((value: number | null | undefined) => value === null || value === undefined ? "--" : new Intl.NumberFormat(locale, { style: "percent", maximumFractionDigits: 1 }).format(value), [locale]);
  const formatDate = useCallback((value: string | null | undefined) => value ? new Intl.DateTimeFormat(locale, { dateStyle: "medium", timeStyle: "short" }).format(new Date(value)) : t("common.notRecorded"), [locale, t]);
  const formatCurrency = useCallback((value: number | null | undefined, currency: string | null | undefined, digits = 6) => value === null || value === undefined ? t("common.notConfigured") : new Intl.NumberFormat(locale, { style: "currency", currency: currency ?? "USD", maximumFractionDigits: digits }).format(value), [locale, t]);

  const value = useMemo<LocaleContextValue>(() => ({ locale, setLocale, t, formatDate, formatNumber, formatPercent, formatCurrency }), [formatCurrency, formatDate, formatNumber, formatPercent, locale, setLocale, t]);
  return <LocaleContext.Provider value={value}>{children}</LocaleContext.Provider>;
}

export function useTranslation() {
  const context = useContext(LocaleContext);
  if (!context) throw new Error(catalogs.en["provider.missing"]);
  return context;
}
