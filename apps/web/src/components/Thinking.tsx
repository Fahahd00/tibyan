import { StarMark } from "./Ornament";

/** Tibyan at work: the eight-pointed star turning slowly, a short line, and three gold dots. */
export function Thinking({ label }: { label: string }) {
  return (
    <div role="status" className="flex items-center gap-3 text-ink-2">
      <StarMark className="h-6 w-6 shrink-0 text-gold animate-[spin_3.5s_linear_infinite] motion-reduce:animate-none" />
      <span>{label}</span>
      <span aria-hidden="true" className="flex items-center gap-1">
        {[0, 1, 2].map((i) => (
          <span
            key={i}
            className="h-1.5 w-1.5 rounded-full bg-gold animate-breathe motion-reduce:animate-none"
            style={{ animationDelay: `${i * 0.25}s` }}
          />
        ))}
      </span>
    </div>
  );
}
