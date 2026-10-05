import { encode } from "uqr";

/** A QR code drawn as one SVG path (crisp at any size, prints well). */
export function QrCode({
  value,
  label,
  className = "",
}: {
  value: string;
  label: string;
  className?: string;
}) {
  const { data, size } = encode(value, { border: 2 });
  let d = "";
  data.forEach((row, y) =>
    row.forEach((dark, x) => {
      if (dark) d += `M${x} ${y}h1v1h-1z`;
    }),
  );
  return (
    <svg
      viewBox={`0 0 ${size} ${size}`}
      role="img"
      aria-label={label}
      className={className}
      shapeRendering="crispEdges"
    >
      <rect width={size} height={size} fill="var(--color-card)" />
      <path d={d} fill="var(--color-ink)" />
    </svg>
  );
}

/** The dark modules of a QR code, for drawing it elsewhere (the share card's canvas). */
export function qrMatrix(value: string): boolean[][] {
  return encode(value, { border: 0 }).data;
}
