"use client";

import { useEasyMode } from "@/hooks/useEasyMode";

export function EasyModeToggle({ label }: { label: string }) {
  const { on, toggle } = useEasyMode();
  return (
    <button
      type="button"
      onClick={toggle}
      aria-pressed={on}
      aria-label={label}
      title={label}
      className={`grid h-9 w-9 shrink-0 place-items-center rounded-full border text-sm font-semibold transition-colors ${
        on
          ? "border-accent bg-accent-soft text-accent-2"
          : "border-line text-ink-2 hover:border-accent hover:text-accent"
      }`}
    >
      <span aria-hidden="true" className="flex items-baseline leading-none">
        <span className="text-[0.7rem]">A</span>
        <span className="text-base">A</span>
      </span>
    </button>
  );
}
