import { dataLang, localeInfo, type Locale } from "@/i18n/config";

/** The localized field of an object with `<key>_ar` / `<key>_en` variants (see `dataLang`). */
export function pick(obj: object, key: string, locale: Locale): string {
  const fields = obj as Record<string, unknown>;
  const value = fields[`${key}_${locale}`] ?? fields[`${key}_${dataLang(locale)}`];
  return typeof value === "string" ? value : "";
}

export function formatNumber(n: number, locale: Locale): string {
  return new Intl.NumberFormat(localeInfo[locale].numbers).format(n);
}

export function formatDate(iso: string, locale: Locale): string {
  const tag =
    locale === "ar"
      ? "ar-SA-u-ca-gregory-nu-latn"
      : locale === "en"
        ? "en-GB"
        : localeInfo[locale].numbers;
  try {
    return new Intl.DateTimeFormat(tag, {
      year: "numeric",
      month: "long",
      day: "numeric",
    }).format(new Date(iso));
  } catch {
    return iso.slice(0, 10);
  }
}
