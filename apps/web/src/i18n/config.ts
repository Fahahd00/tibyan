export const locales = ["ar", "en", "ur", "hi", "bn", "tr", "id", "ms", "uz", "kk", "ha"] as const;
export type Locale = (typeof locales)[number];
export const defaultLocale: Locale = "ar";

/** Native name, writing direction, speech-recognition tag and number formatting of each language. */
export const localeInfo: Record<
  Locale,
  { name: string; dir: "rtl" | "ltr"; speech: string; numbers: string }
> = {
  ar: { name: "العربية", dir: "rtl", speech: "ar-SA", numbers: "ar-u-nu-arab" },
  en: { name: "English", dir: "ltr", speech: "en-US", numbers: "en" },
  ur: { name: "اردو", dir: "rtl", speech: "ur-PK", numbers: "ur-u-nu-arabext" },
  hi: { name: "हिन्दी", dir: "ltr", speech: "hi-IN", numbers: "hi" },
  bn: { name: "বাংলা", dir: "ltr", speech: "bn-BD", numbers: "bn" },
  tr: { name: "Türkçe", dir: "ltr", speech: "tr-TR", numbers: "tr" },
  id: { name: "Bahasa Indonesia", dir: "ltr", speech: "id-ID", numbers: "id" },
  ms: { name: "Bahasa Melayu", dir: "ltr", speech: "ms-MY", numbers: "ms" },
  uz: { name: "O‘zbekcha", dir: "ltr", speech: "uz-UZ", numbers: "uz" },
  kk: { name: "Қазақша", dir: "ltr", speech: "kk-KZ", numbers: "kk" },
  ha: { name: "Hausa", dir: "ltr", speech: "ha-NG", numbers: "ha" },
};

export function isLocale(value: string): value is Locale {
  return (locales as readonly string[]).includes(value);
}

export function dirOf(locale: Locale): "rtl" | "ltr" {
  return localeInfo[locale].dir;
}

/** Data kept only in Arabic and English (source names, trace steps): Arabic-script languages show the Arabic. */
export function dataLang(locale: Locale): "ar" | "en" {
  return dirOf(locale) === "rtl" ? "ar" : "en";
}
