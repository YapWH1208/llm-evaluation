import { catalogs, type Locale } from "./catalog";

export function formatWorkspaceDate(locale: Locale, value: string | null | undefined) {
  return value
    ? new Intl.DateTimeFormat(locale, { dateStyle: "medium", timeStyle: "short" }).format(new Date(value))
    : catalogs[locale]["common.notRecorded"];
}

export function formatWorkspaceNumber(locale: Locale, value: number | null | undefined, digits = 2) {
  return value === null || value === undefined
    ? "--"
    : new Intl.NumberFormat(locale, { maximumFractionDigits: digits }).format(value);
}

export function formatWorkspacePercent(locale: Locale, value: number | null | undefined) {
  return value === null || value === undefined
    ? "--"
    : new Intl.NumberFormat(locale, { style: "percent", maximumFractionDigits: 1 }).format(value);
}

export function formatWorkspaceMoney(locale: Locale, value: number | null | undefined, currency: string | null | undefined, digits = 6) {
  return value === null || value === undefined
    ? catalogs[locale]["common.notConfigured"]
    : `${formatWorkspaceNumber(locale, value, digits)} ${currency ?? ""}`.trim();
}
