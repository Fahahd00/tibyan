"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { type Locale, localeInfo, locales } from "@/i18n/config";

export function LanguageSwitch({ locale, label }: { locale: Locale; label: string }) {
  const pathname = usePathname() || `/${locale}`;
  const prefix = new RegExp(`^/(${locales.join("|")})(?=/|$)`);
  return (
    // key: the menu closes once another language has been chosen
    <details key={locale} className="relative">
      <summary
        aria-label={label}
        className="flex cursor-pointer list-none items-center gap-1.5 rounded-full border border-line px-3 py-1.5 text-sm text-ink-2 transition-colors hover:border-accent hover:text-accent [&::-webkit-details-marker]:hidden"
      >
        <svg
          viewBox="0 0 24 24"
          className="h-4 w-4"
          fill="none"
          stroke="currentColor"
          strokeWidth="1.6"
          aria-hidden="true"
        >
          <circle cx="12" cy="12" r="9" />
          <path d="M3 12h18M12 3c2.5 2.6 3.8 5.6 3.8 9s-1.3 6.4-3.8 9c-2.5-2.6-3.8-5.6-3.8-9S9.5 5.6 12 3z" />
        </svg>
        <span className="hidden sm:inline">{localeInfo[locale].name}</span>
      </summary>
      <ul className="absolute end-0 z-40 mt-2 min-w-44 rounded-2xl border border-line bg-card p-1.5 shadow-lift">
        {locales.map((l) => (
          <li key={l}>
            <Link
              href={pathname.replace(prefix, `/${l}`)}
              hrefLang={l}
              lang={l}
              dir={localeInfo[l].dir}
              aria-current={l === locale ? "true" : undefined}
              className={`block rounded-xl px-3 py-2 text-sm transition-colors hover:bg-paper-2 ${
                l === locale ? "font-semibold text-accent" : "text-ink-2"
              }`}
            >
              {localeInfo[l].name}
            </Link>
          </li>
        ))}
      </ul>
    </details>
  );
}
