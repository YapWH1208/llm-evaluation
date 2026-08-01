import { catalogs, resolveLocale } from "./catalog";

function currentLocale() {
  return resolveLocale(document.documentElement.lang);
}

export function formatWorkspaceDate(value: string | null) {
  const locale = currentLocale();
  return value
    ? new Intl.DateTimeFormat(locale, { dateStyle: "medium", timeStyle: "short" }).format(new Date(value))
    : catalogs[locale]["common.notRecorded"];
}

export function formatWorkspaceNumber(value: number | null | undefined, digits = 2) {
  return value === null || value === undefined
    ? "--"
    : new Intl.NumberFormat(currentLocale(), { maximumFractionDigits: digits }).format(value);
}

export function formatWorkspacePercent(value: number | null | undefined) {
  return value === null || value === undefined
    ? "--"
    : new Intl.NumberFormat(currentLocale(), { style: "percent", maximumFractionDigits: 1 }).format(value);
}

export function formatWorkspaceMoney(value: number | null | undefined, currency: string | null | undefined) {
  const locale = currentLocale();
  return value === null || value === undefined
    ? catalogs[locale]["common.notConfigured"]
    : `${formatWorkspaceNumber(value, 6)} ${currency ?? ""}`.trim();
}
