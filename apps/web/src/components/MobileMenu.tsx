"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

type NavLink = { href: string; label: string };

export function MobileMenu({ links, label }: { links: NavLink[]; label: string }) {
  const pathname = usePathname();
  return (
    // key: the menu closes once a page has been chosen
    <details key={pathname} className="relative lg:hidden">
      <summary
        aria-label={label}
        title={label}
        className="grid h-9 w-9 cursor-pointer list-none place-items-center rounded-full border border-line text-ink-2 transition-colors hover:border-accent hover:text-accent [&::-webkit-details-marker]:hidden"
      >
        <svg viewBox="0 0 24 24" className="h-4 w-4" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" aria-hidden="true">
          <path d="M4 7h16M4 12h16M4 17h16" />
        </svg>
      </summary>
      <ul className="absolute end-0 z-40 mt-2 min-w-52 rounded-2xl border border-line bg-card p-1.5 shadow-lift">
        {links.map((l) => (
          <li key={l.href}>
            <Link
              href={l.href}
              aria-current={l.href === pathname ? "page" : undefined}
              className={`block rounded-xl px-3 py-2.5 text-sm transition-colors hover:bg-paper-2 ${
                l.href === pathname ? "font-semibold text-accent" : "text-ink-2"
              }`}
            >
              {l.label}
            </Link>
          </li>
        ))}
      </ul>
    </details>
  );
}
