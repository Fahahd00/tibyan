import Link from "next/link";
import type { Locale } from "@/i18n/config";
import type { Dictionary } from "@/i18n/dictionaries";
import { EasyModeToggle } from "./EasyModeToggle";
import { LanguageSwitch } from "./LanguageSwitch";
import { Logo } from "./Logo";

export function SiteHeader({ locale, dict }: { locale: Locale; dict: Dictionary }) {
  const links = [
    { href: `/${locale}`, label: dict.nav.home, show: "inline-block" },
    { href: `/${locale}/hajj`, label: dict.nav.hajj, show: "hidden sm:inline-block" },
    { href: `/${locale}/verify`, label: dict.nav.verify, show: "hidden lg:inline-block" },
    { href: `/${locale}/sources`, label: dict.nav.sources, show: "hidden lg:inline-block" },
    { href: `/${locale}/about`, label: dict.nav.about, show: "hidden md:inline-block" },
  ];
  return (
    <header className="sticky top-0 z-30 border-b border-line/70 bg-paper/80 backdrop-blur-md">
      <div className="mx-auto flex h-16 max-w-6xl items-center justify-between gap-4 px-4 sm:px-6">
        <Logo locale={locale} />
        <nav className="flex items-center gap-1 sm:gap-2" aria-label="primary">
          {links.map((l) => (
            <Link
              key={l.href}
              href={l.href}
              className={`${l.show} whitespace-nowrap rounded-full px-3 py-1.5 text-sm text-ink-2 transition-colors hover:bg-paper-2 hover:text-ink`}
            >
              {l.label}
            </Link>
          ))}
          <EasyModeToggle label={dict.nav.easy} />
          <LanguageSwitch locale={locale} label={dict.nav.switchLanguage} />
        </nav>
      </div>
    </header>
  );
}
