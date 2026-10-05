import type { Metadata } from "next";
import {
  Amiri,
  IBM_Plex_Sans_Arabic,
  Noto_Naskh_Arabic,
  Noto_Sans,
  Noto_Sans_Bengali,
  Noto_Sans_Devanagari,
} from "next/font/google";
import { notFound } from "next/navigation";
import type { ReactNode } from "react";
import { ManuscriptBackdrop } from "@/components/Ornament";
import { SiteFooter } from "@/components/SiteFooter";
import { SiteHeader } from "@/components/SiteHeader";
import { dirOf, isLocale, locales } from "@/i18n/config";
import { getDictionary } from "@/i18n/dictionaries";
import { EASY_MODE_SCRIPT } from "@/lib/easyMode";
import "../globals.css";

const plex = IBM_Plex_Sans_Arabic({
  subsets: ["arabic", "latin", "latin-ext"],
  weight: ["300", "400", "500", "600", "700"],
  variable: "--font-plex",
  display: "swap",
});
const naskh = Noto_Naskh_Arabic({
  subsets: ["arabic"],
  weight: ["400", "500", "600"],
  variable: "--font-naskh-ar",
  display: "swap",
});
const amiri = Amiri({
  subsets: ["arabic", "latin", "latin-ext"],
  weight: ["400", "700"],
  variable: "--font-amiri",
  display: "swap",
});

// Hindi (Devanagari script)
const deva = Noto_Sans_Devanagari({
  subsets: ["devanagari"],
  weight: ["400", "500", "600", "700"],
  variable: "--font-deva",
  display: "swap",
});

// Bengali
const beng = Noto_Sans_Bengali({
  subsets: ["bengali"],
  weight: ["400", "500", "600", "700"],
  variable: "--font-beng",
  display: "swap",
});
// Kazakh (Cyrillic) and the extra Latin letters of Hausa and Uzbek, wherever the fonts above have no glyph
const world = Noto_Sans({
  subsets: ["cyrillic", "cyrillic-ext", "latin", "latin-ext"],
  weight: ["400", "500", "600", "700"],
  variable: "--font-world",
  display: "swap",
});

type Params = { params: Promise<{ locale: string }> };

export function generateStaticParams() {
  return locales.map((locale) => ({ locale }));
}

export async function generateMetadata({ params }: Params): Promise<Metadata> {
  const { locale } = await params;
  if (!isLocale(locale)) return {};
  const dict = getDictionary(locale);
  const siteName = dirOf(locale) === "rtl" ? "تِبْيان" : "تِبْيان | Tibyan";
  return {
    title: { default: dict.meta.title, template: `%s · ${siteName}` },
    description: dict.meta.description,
    applicationName: siteName,
    alternates: { languages: { ar: "/ar", en: "/en" } },
    openGraph: {
      title: dict.meta.title,
      description: dict.meta.description,
      siteName,
    },
  };
}

export default async function LocaleLayout({ children, params }: Params & { children: ReactNode }) {
  const { locale } = await params;
  if (!isLocale(locale)) notFound();
  const dict = getDictionary(locale);
  return (
    <html
      lang={locale}
      dir={dirOf(locale)}
      className={`${plex.variable} ${naskh.variable} ${amiri.variable} ${deva.variable} ${beng.variable} ${world.variable}`}
      suppressHydrationWarning // easy mode sets data-easy before React hydrates
    >
      <head>
        <script dangerouslySetInnerHTML={{ __html: EASY_MODE_SCRIPT }} />
      </head>
      <body className="min-h-dvh">
        <a
          href="#main"
          className="sr-only focus:not-sr-only focus:fixed focus:top-3 focus:z-50 focus:rounded-full focus:bg-ink focus:px-4 focus:py-2 focus:text-paper"
        >
          {dict.nav.skip}
        </a>
        <ManuscriptBackdrop />
        <SiteHeader locale={locale} dict={dict} />
        <main id="main">{children}</main>
        <SiteFooter locale={locale} dict={dict} />
      </body>
    </html>
  );
}
