import type { ReactNode } from "react";

/** Eight-pointed star (khatam) — the only ornament, drawn as hairlines. */
export function StarMark({ className = "" }: { className?: string }) {
  return (
    <svg
      viewBox="0 0 24 24"
      aria-hidden="true"
      className={className}
      fill="none"
      stroke="currentColor"
      strokeWidth="1.3"
    >
      <rect x="5" y="5" width="14" height="14" rx="0.6" />
      <rect x="5" y="5" width="14" height="14" rx="0.6" transform="rotate(45 12 12)" />
      <circle cx="12" cy="12" r="2.2" />
    </svg>
  );
}

/** A numeral (or short mark) set inside an eight-pointed star medallion. */
export function StarBadge({
  children,
  className = "",
}: {
  children: ReactNode;
  className?: string;
}) {
  return (
    <span className={`relative inline-grid shrink-0 place-items-center ${className}`}>
      <svg viewBox="0 0 48 48" aria-hidden="true" className="absolute inset-0 h-full w-full">
        <g fill="var(--color-card)" stroke="currentColor" strokeWidth="1.2">
          <rect x="10" y="10" width="28" height="28" rx="1" />
          <rect x="10" y="10" width="28" height="28" rx="1" transform="rotate(45 24 24)" />
        </g>
      </svg>
      <span className="relative font-display leading-none">{children}</span>
    </span>
  );
}

/** Hairline pointed (mihrab) arch that stretches to frame its container; strokes stay hairline. */
export function MihrabArch({ className = "" }: { className?: string }) {
  return (
    <svg
      viewBox="0 0 400 300"
      preserveAspectRatio="none"
      aria-hidden="true"
      className={className}
      fill="none"
      stroke="currentColor"
    >
      <path
        d="M8 300 V150 C8 74 104 34 200 4 C296 34 392 74 392 150 V300"
        strokeWidth="1.2"
        vectorEffect="non-scaling-stroke"
      />
      <path
        d="M20 300 V152 C20 84 110 46 200 18 C290 46 380 84 380 152 V300"
        strokeWidth="0.8"
        vectorEffect="non-scaling-stroke"
        opacity="0.6"
      />
    </svg>
  );
}

/** Gold hairline flourish: rule — star — rule. */
export function Flourish({ className = "" }: { className?: string }) {
  return (
    <span aria-hidden="true" className={`flex items-center justify-center gap-3 ${className}`}>
      <span className="h-px w-14 bg-linear-to-l from-gold/70 to-transparent sm:w-24" />
      <StarMark className="h-4 w-4 text-gold" />
      <span className="h-px w-14 bg-linear-to-r from-gold/70 to-transparent sm:w-24" />
    </span>
  );
}

// Words of the backdrop: the vocabulary of a fatwa and of Tibyan's idea (16 = one per slot of the 2×2 tile).
const BACKDROP_WORDS = [
  "فتوى",
  "دليل",
  "بيان",
  "يقين",
  "سؤال",
  "مصدر",
  "جواب",
  "علم",
  "تِبْيان",
  "فقه",
  "تحقّق",
  "حُكم",
  "اسأل أهل العلم",
  "العلم بالدليل",
  "من السؤال إلى المصدر",
  "الجواب بمصدره",
];

/**
 * Site backdrop: a khatam-star lattice whose open spaces carry Arabic words in classical naskh (Amiri).
 * Fixed behind every page; strongest at the edges and faded behind the reading column (see .manuscript-backdrop).
 */
export function ManuscriptBackdrop() {
  const T = 480; // one sub-tile; the pattern repeats a 2×2 super-tile so neighbouring words differ
  const slots = [
    [T / 2, 92],
    [T - 92, T / 2],
    [T / 2, T - 92],
    [92, T / 2],
  ];
  const tiles = [
    [0, 0],
    [T, 0],
    [0, T],
    [T, T],
  ];
  return (
    <div
      aria-hidden="true"
      className="manuscript-backdrop pointer-events-none fixed inset-0 -z-10 overflow-hidden"
    >
      <svg width="100%" height="100%">
        <defs>
          <pattern
            id="tibyan-manuscript"
            width={2 * T}
            height={2 * T}
            patternUnits="userSpaceOnUse"
          >
            {tiles.map(([ox, oy], t) => (
              <g key={t} transform={`translate(${ox} ${oy})`}>
                <g className="text-gold/20" fill="none" stroke="currentColor" strokeWidth="0.8">
                  <path d={`M0 0 L${T} ${T} M${T} 0 L0 ${T}`} />
                  {[
                    [0, 0],
                    [T, 0],
                    [0, T],
                    [T, T],
                    [T / 2, T / 2],
                  ].map(([x, y]) => (
                    <g key={`${x}-${y}`} transform={`translate(${x} ${y})`}>
                      <rect x="-26" y="-26" width="52" height="52" />
                      <rect x="-26" y="-26" width="52" height="52" transform="rotate(45)" />
                      <circle r="9" />
                    </g>
                  ))}
                  {[
                    [T / 2, 0],
                    [T, T / 2],
                    [T / 2, T],
                    [0, T / 2],
                  ].map(([x, y]) => (
                    <circle key={`m${x}-${y}`} cx={x} cy={y} r="3" />
                  ))}
                </g>
                <g
                  className="fill-current font-display text-ink/[0.07]"
                  textAnchor="middle"
                  dominantBaseline="middle"
                >
                  {slots.map(([x, y], s) => {
                    const word = BACKDROP_WORDS[t * 4 + s];
                    return (
                      <text key={s} x={x} y={y} fontSize={word.length > 8 ? 20 : 30}>
                        {word}
                      </text>
                    );
                  })}
                </g>
              </g>
            ))}
          </pattern>
        </defs>
        <rect width="100%" height="100%" fill="url(#tibyan-manuscript)" />
      </svg>
    </div>
  );
}

/** Very faint geometric lattice used behind the hero. */
export function Lattice({ className = "" }: { className?: string }) {
  return (
    <svg aria-hidden="true" className={className} width="100%" height="100%">
      <defs>
        <pattern id="tibyan-lattice" width="56" height="56" patternUnits="userSpaceOnUse">
          <g fill="none" stroke="currentColor" strokeWidth="0.6">
            <rect x="14" y="14" width="28" height="28" />
            <rect x="14" y="14" width="28" height="28" transform="rotate(45 28 28)" />
          </g>
        </pattern>
        <radialGradient id="tibyan-fade" cx="50%" cy="35%" r="65%">
          <stop offset="0%" stopColor="white" stopOpacity="1" />
          <stop offset="100%" stopColor="white" stopOpacity="0" />
        </radialGradient>
        <mask id="tibyan-mask">
          <rect width="100%" height="100%" fill="url(#tibyan-fade)" />
        </mask>
      </defs>
      <rect width="100%" height="100%" fill="url(#tibyan-lattice)" mask="url(#tibyan-mask)" />
    </svg>
  );
}
