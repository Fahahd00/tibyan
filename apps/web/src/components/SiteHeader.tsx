import Link from "next/link";
import type { Locale } from "@/i18n/config";
import type { Dictionary } from "@/i18n/dictionaries";
import { EasyModeToggle } from "./EasyModeToggle";
import { LanguageSwitch } from "./LanguageSwitch";
import { Logo } from "./Logo";
import { MobileMenu } from "./MobileMenu";

export function SiteHeader({ locale, dict }: { locale: Locale; dict: Dictionary }) {
  const links = [
    { href: `/${locale}`, label: dict.nav.home },
    { href: `/${locale}/hajj`, label: dict.nav.hajj },
    { href: `/${locale}/verify`, label: dict.nav.verify },
    { href: `/${locale}/sources`, label: dict.nav.sources },
    { href: `/${locale}/about`, label: dict.nav.about },
  ];
  return (
    <header className="sticky top-0 z-30 border-b border-line/70 bg-paper/80 backdrop-blur-md">
      <div className="mx-auto flex h-16 max-w-6xl items-center justify-between gap-4 px-4 sm:px-6">
        <Logo locale={locale} />
        <nav className="flex items-center gap-1 sm:gap-2" aria-label="primary">
          {/* Below lg every page sits in the menu; from lg the links show inline */}
          {links.map((l) => (
            <Link
              key={l.href}
              href={l.href}
              className="hidden whitespace-nowrap rounded-full px-3 py-1.5 text-sm text-ink-2 transition-colors hover:bg-paper-2 hover:text-ink lg:inline-block"
            >
              {l.label}
            </Link>
          ))}
          <EasyModeToggle label={dict.nav.easy} />
          <LanguageSwitch locale={locale} label={dict.nav.switchLanguage} />
          <MobileMenu links={links} label={dict.nav.menu} />
        </nav>
      </div>
    </header>
  );
}
