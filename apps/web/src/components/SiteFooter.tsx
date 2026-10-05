import Link from "next/link";
import type { Locale } from "@/i18n/config";
import type { Dictionary } from "@/i18n/dictionaries";
import { StarMark } from "./Ornament";

export function SiteFooter({ locale, dict }: { locale: Locale; dict: Dictionary }) {
  return (
    <footer className="mt-24 border-t border-line">
      <div className="mx-auto grid max-w-6xl gap-6 px-4 py-10 sm:grid-cols-[1fr_auto] sm:px-6">
        <div className="space-y-2">
          <p className="flex items-center gap-2 font-display text-xl text-ink">
            <StarMark className="h-5 w-5 text-gold" />
            {dict.footer.principle}
          </p>
          <p className="max-w-xl text-sm leading-7 text-muted">{dict.footer.disclaimer}</p>
        </div>
        <div className="flex flex-col items-start gap-2 text-sm text-muted sm:items-end">
          {/* The pages the header has no room for at this width */}
          <div className="flex flex-wrap gap-x-4 gap-y-2">
            <Link className="hover:text-accent sm:hidden" href={`/${locale}/hajj`}>
              {dict.nav.hajj}
            </Link>
            <Link className="hover:text-accent lg:hidden" href={`/${locale}/verify`}>
              {dict.nav.verify}
            </Link>
            <Link className="hover:text-accent lg:hidden" href={`/${locale}/sources`}>
              {dict.nav.sources}
            </Link>
            <Link className="hover:text-accent md:hidden" href={`/${locale}/about`}>
              {dict.nav.about}
            </Link>
            <Link className="hover:text-accent" href={`/${locale}/about#privacy`}>
              {dict.about.privacyTitle}
            </Link>
            <Link className="hover:text-accent" href={`/${locale}/admin`}>
              {dict.nav.admin}
            </Link>
          </div>
          <span>{dict.footer.team}</span>
        </div>
      </div>
    </footer>
  );
}
