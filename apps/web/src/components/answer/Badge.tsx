import type { ReactNode } from "react";

const tones = {
  accent: "bg-accent-soft text-accent-2 border-accent/15",
  gold: "bg-gold-soft text-gold border-gold/20",
  amber: "bg-amber-soft text-amber border-amber/15",
  rose: "bg-rose-soft text-rose border-rose/15",
  neutral: "bg-paper-2 text-ink-2 border-line",
} as const;

export function Badge({
  tone = "neutral",
  children,
}: {
  tone?: keyof typeof tones;
  children: ReactNode;
}) {
  return (
    <span
      className={`inline-flex items-center gap-1.5 rounded-full border px-2.5 py-0.5 text-xs font-medium ${tones[tone]}`}
    >
      {children}
    </span>
  );
}

export function Check({ className = "h-3.5 w-3.5" }: { className?: string }) {
  return (
    <svg
      viewBox="0 0 16 16"
      className={className}
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      aria-hidden="true"
    >
      <path d="M3.5 8.5l3 3 6-7" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}

export function SectionTitle({ children }: { children: ReactNode }) {
  return (
    <h3 className="mb-3 text-xs font-semibold uppercase tracking-[0.18em] text-faint">
      {children}
    </h3>
  );
}
