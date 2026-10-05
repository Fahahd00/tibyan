/** Renders source text with the verbatim quotes highlighted (only exact substrings are marked). */
export function Highlighted({ text, quotes }: { text: string; quotes: string[] }) {
  const ranges: [number, number][] = [];
  for (const q of quotes) {
    const i = q ? text.indexOf(q) : -1;
    if (i >= 0) ranges.push([i, i + q.length]);
  }
  ranges.sort((a, b) => a[0] - b[0]);
  const merged: [number, number][] = [];
  for (const r of ranges) {
    const last = merged[merged.length - 1];
    if (last && r[0] <= last[1]) last[1] = Math.max(last[1], r[1]);
    else merged.push([...r]);
  }
  const parts: { text: string; mark: boolean }[] = [];
  let pos = 0;
  for (const [s, e] of merged) {
    if (s > pos) parts.push({ text: text.slice(pos, s), mark: false });
    parts.push({ text: text.slice(s, e), mark: true });
    pos = e;
  }
  if (pos < text.length) parts.push({ text: text.slice(pos), mark: false });
  return (
    <>
      {parts.map((p, i) =>
        p.mark ? <mark key={i}>{p.text}</mark> : <span key={i}>{p.text}</span>,
      )}
    </>
  );
}
