import Link from "next/link";
import { dirOf, type Locale } from "@/i18n/config";
import { StarMark } from "./Ornament";

export function Logo({ locale }: { locale: Locale }) {
  return (
    <Link
      href={`/${locale}`}
      className="group inline-flex items-center gap-3"
      aria-label={dirOf(locale) === "rtl" ? "تِبْيان" : "تِبْيان — Tibyan"}
    >
      <StarMark className="h-7 w-7 text-accent transition-transform duration-700 group-hover:rotate-45" />
      <span className="flex items-baseline gap-2">
        <span lang="ar" className="font-display text-[1.7rem] font-bold leading-none text-ink">
          تِبْيان
        </span>
        {dirOf(locale) === "ltr" && (
          <span className="text-[0.7rem] font-medium uppercase tracking-[0.28em] text-muted">
            Tibyan
          </span>
        )}
      </span>
    </Link>
  );
}
