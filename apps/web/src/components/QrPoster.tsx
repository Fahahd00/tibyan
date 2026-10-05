"use client";

import { useSyncExternalStore } from "react";
import { type Locale, localeInfo, locales } from "@/i18n/config";
import type { Dictionary } from "@/i18n/dictionaries";
import { QrCode } from "./QrCode";

const noSubscribe = () => () => {};

/** A printable QR code that opens this page (on the address it is served from). */
export function QrPoster({ locale, dict }: { locale: Locale; dict: Dictionary }) {
  const url = useSyncExternalStore(
    noSubscribe,
    () => `${window.location.origin}/${locale}/hajj`,
    () => null,
  );
  return (
    <section className="relative rounded-md border border-gold/40 bg-card/85 p-1.5 shadow-soft print:border-0 print:shadow-none">
      <div className="flex flex-col items-center gap-6 rounded-sm border border-gold/25 bg-gold-soft/40 px-6 py-8 text-center sm:flex-row sm:text-start">
        <div className="h-44 w-44 shrink-0 rounded-xl bg-card p-2 shadow-soft">
          {url && <QrCode value={url} label={dict.hajj.scanTitle} className="h-full w-full" />}
        </div>
        <div className="min-w-0">
          <h2 className="font-display text-2xl text-accent-2">{dict.hajj.scanTitle}</h2>
          <p className="mt-2 text-pretty leading-8 text-ink-2">{dict.hajj.scanBody}</p>
          <ul className="mt-3 flex flex-wrap justify-center gap-2 sm:justify-start">
            {locales.map((l) => (
              <li
                key={l}
                lang={l}
                className="rounded-full border border-gold/30 bg-card px-3 py-1 text-sm text-ink-2"
              >
                {localeInfo[l].name}
              </li>
            ))}
          </ul>
          <button
            type="button"
            onClick={() => window.print()}
            className="mt-4 rounded-full border border-line bg-card px-4 py-2 text-sm text-ink-2 transition-colors hover:border-accent hover:text-accent print:hidden"
          >
            {dict.hajj.print}
          </button>
        </div>
      </div>
    </section>
  );
}
