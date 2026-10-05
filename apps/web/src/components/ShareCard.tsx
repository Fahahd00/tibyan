"use client";

import type { AnswerResponse } from "@tibyan/contracts";
import { useEffect, useRef, useState } from "react";
import type { Locale } from "@/i18n/config";
import type { Dictionary } from "@/i18n/dictionaries";
import { pick } from "@/lib/text";
import { qrMatrix } from "./QrCode";

const W = 1080;
const H = 1350;
const PAD = 110;
const RTL_TEXT = /[؀-ۿ]/;

type Ctx = CanvasRenderingContext2D;

const cssVar = (name: string) =>
  getComputedStyle(document.documentElement).getPropertyValue(name).trim();

/** The lines of `text` that fit `width`; at most `max`, the last one marked … when cut. */
function wrap(ctx: Ctx, text: string, width: number, max: number): string[] {
  const lines: string[] = [];
  let line = "";
  for (const word of text.split(/\s+/).filter(Boolean)) {
    const next = line ? `${line} ${word}` : word;
    if (!line || ctx.measureText(next).width <= width) line = next;
    else {
      lines.push(line);
      line = word;
    }
  }
  if (line) lines.push(line);
  if (lines.length <= max) return lines;
  const kept = lines.slice(0, max);
  kept[max - 1] += " …";
  return kept;
}

/** Writes wrapped text from y (top of the first line) in its own direction, inside [left, left + width];
 * returns the y after it. */
function paragraph(
  ctx: Ctx,
  text: string,
  y: number,
  font: string,
  color: string,
  lineHeight: number,
  max: number,
  width = W - 2 * PAD,
  left = PAD,
): number {
  ctx.font = font;
  ctx.fillStyle = color;
  const rtl = RTL_TEXT.test(text);
  ctx.direction = rtl ? "rtl" : "ltr";
  ctx.textAlign = "start";
  ctx.textBaseline = "top";
  const x = rtl ? left + width : left;
  for (const line of wrap(ctx, text, width, max)) {
    ctx.fillText(line, x, y);
    y += lineHeight;
  }
  return y;
}

function centered(ctx: Ctx, text: string, y: number, font: string, color: string) {
  ctx.font = font;
  ctx.fillStyle = color;
  ctx.direction = RTL_TEXT.test(text) ? "rtl" : "ltr";
  ctx.textAlign = "center";
  ctx.textBaseline = "top";
  ctx.fillText(text, W / 2, y);
}

function star(ctx: Ctx, cx: number, cy: number, r: number) {
  for (const angle of [0, Math.PI / 4]) {
    ctx.save();
    ctx.translate(cx, cy);
    ctx.rotate(angle);
    ctx.strokeRect(-r, -r, 2 * r, 2 * r);
    ctx.restore();
  }
}

async function drawCard(answer: AnswerResponse, locale: Locale, dict: Dictionary, link: string) {
  const color = (n: string) => cssVar(`--color-${n}`);
  const fonts = {
    display: cssVar("--font-amiri") || "serif",
    naskh: cssVar("--font-naskh-ar") || "serif",
    sans: cssVar("--font-plex") || "sans-serif",
  };
  // Fonts the page has not used yet are fetched first; one that cannot load falls back to the next in its stack.
  await Promise.allSettled(
    [`700 72px ${fonts.display}`, `46px ${fonts.naskh}`, `600 30px ${fonts.sans}`].map((f) =>
      document.fonts.load(f, "تبيان Tibyan"),
    ),
  );

  const canvas = document.createElement("canvas");
  canvas.width = W;
  canvas.height = H;
  const ctx = canvas.getContext("2d") as Ctx;

  // Ground and the manuscript frame
  ctx.fillStyle = color("paper");
  ctx.fillRect(0, 0, W, H);
  ctx.strokeStyle = color("gold");
  ctx.lineWidth = 3;
  ctx.strokeRect(36, 36, W - 72, H - 72);
  ctx.lineWidth = 1.5;
  ctx.strokeRect(50, 50, W - 100, H - 100);
  for (const [x, y] of [
    [36, 36],
    [W - 36, 36],
    [36, H - 36],
    [W - 36, H - 36],
  ]) {
    ctx.fillStyle = color("paper");
    ctx.fillRect(x - 16, y - 16, 32, 32);
    star(ctx, x, y, 11);
  }

  // Name and tagline
  centered(ctx, "تِبْيان", 92, `700 76px ${fonts.display}`, color("ink"));
  centered(ctx, dict.hero.tagline, 205, `34px ${fonts.display}`, color("ink-2"));
  ctx.strokeStyle = color("gold");
  ctx.beginPath();
  ctx.moveTo(W / 2 - 170, 280);
  ctx.lineTo(W / 2 - 24, 280);
  ctx.moveTo(W / 2 + 24, 280);
  ctx.lineTo(W / 2 + 170, 280);
  ctx.stroke();
  star(ctx, W / 2, 280, 9);

  // The QR code (opening this answer with its trust chain) and the source take the bottom; the text above is
  // shortened to leave them room.
  const qrSize = 190;
  const qrY = H - 100 - qrSize;
  const bottom = qrY - 36;

  // Question, summary, the fatwa's own words
  const summaryClaim = answer.claims.find((c) => c.kept && c.role === "summary");
  const source = answer.evidence.find((e) => summaryClaim?.evidence_refs.includes(e.ref));
  let y = 320;
  y = paragraph(ctx, dict.answer.yourQuestion, y, `500 28px ${fonts.sans}`, color("muted"), 44, 1);
  y = paragraph(ctx, answer.question.text, y, `500 38px ${fonts.sans}`, color("ink"), 56, 2) + 22;
  y = paragraph(ctx, dict.answer.summary, y, `600 28px ${fonts.sans}`, color("accent"), 44, 1);
  y = paragraph(ctx, answer.summary ?? "", y + 4, `44px ${fonts.naskh}`, color("ink"), 76, 4) + 18;

  const quote = summaryClaim ? (summaryClaim.source_quote ?? summaryClaim.quote) : "";
  const quoteLines = Math.min(3, Math.floor((bottom - y - 66) / 60));
  if (quote && quoteLines >= 1) {
    const width = W - 2 * PAD - 60;
    ctx.font = `34px ${fonts.naskh}`;
    const boxH = 66 + Math.min(wrap(ctx, quote, width, quoteLines).length, quoteLines) * 60;
    ctx.fillStyle = color("gold-soft");
    ctx.fillRect(PAD, y, W - 2 * PAD, boxH);
    ctx.fillStyle = color("gold");
    ctx.fillRect(RTL_TEXT.test(quote) ? W - PAD - 6 : PAD, y, 6, boxH);
    paragraph(
      ctx,
      dict.share.quote,
      y + 16,
      `500 26px ${fonts.sans}`,
      color("muted"),
      40,
      1,
      width,
      PAD + 30,
    );
    paragraph(
      ctx,
      quote,
      y + 54,
      `34px ${fonts.naskh}`,
      color("ink-2"),
      60,
      quoteLines,
      width,
      PAD + 30,
    );
  }

  // Bottom row: the QR code on one side; the source and the invitation to scan on the other
  const rtlUi = RTL_TEXT.test(dict.share.scan);
  const qrX = rtlUi ? PAD : W - PAD - qrSize;
  const modules = qrMatrix(link);
  const cell = qrSize / modules.length;
  ctx.fillStyle = color("card");
  ctx.fillRect(qrX - 14, qrY - 14, qrSize + 28, qrSize + 28);
  ctx.fillStyle = color("ink");
  modules.forEach((row, r) =>
    row.forEach((dark, c) => {
      if (dark) ctx.fillRect(qrX + c * cell, qrY + r * cell, Math.ceil(cell), Math.ceil(cell));
    }),
  );
  const side = W - 2 * PAD - qrSize - 50;
  const sideLeft = rtlUi ? PAD + qrSize + 50 : PAD;
  if (source) {
    const name = pick(source.source, "publisher", locale) || pick(source.source, "name", locale);
    paragraph(ctx, name, qrY, `600 30px ${fonts.sans}`, color("ink"), 46, 1, side, sideLeft);
    paragraph(
      ctx,
      source.title,
      qrY + 48,
      `30px ${fonts.display}`,
      color("muted"),
      46,
      1,
      side,
      sideLeft,
    );
  }
  paragraph(
    ctx,
    dict.share.scan,
    qrY + 130,
    `600 30px ${fonts.sans}`,
    color("accent-2"),
    46,
    1,
    side,
    sideLeft,
  );

  return new Promise<Blob>((resolve, reject) =>
    canvas.toBlob((b) => (b ? resolve(b) : reject(new Error("canvas"))), "image/png"),
  );
}

/** «Share as image»: a card of the verified answer, its quote and source, with a QR code back to it. */
export function ShareCard({
  answer,
  locale,
  dict,
}: {
  answer: AnswerResponse;
  locale: Locale;
  dict: Dictionary;
}) {
  const dialog = useRef<HTMLDialogElement>(null);
  const [image, setImage] = useState<{ url: string; file: File } | null>(null);
  const [failed, setFailed] = useState(false);

  useEffect(
    () => () => {
      if (image) URL.revokeObjectURL(image.url);
    },
    [image],
  );

  async function open() {
    dialog.current?.showModal();
    if (image) return;
    setFailed(false);
    try {
      const link = `${window.location.origin}/${locale}/answers/${answer.answer_id}`;
      const blob = await drawCard(answer, locale, dict, link);
      setImage({
        url: URL.createObjectURL(blob),
        file: new File([blob], "tibyan.png", { type: "image/png" }),
      });
    } catch {
      setFailed(true);
    }
  }

  const canShare =
    typeof navigator !== "undefined" &&
    image !== null &&
    Boolean(navigator.canShare?.({ files: [image.file] }));

  return (
    <>
      <button
        type="button"
        onClick={() => void open()}
        className="inline-flex items-center gap-2 rounded-full border border-line bg-card px-3.5 py-1.5 text-sm text-ink-2 transition-colors hover:border-accent hover:text-accent"
      >
        <svg
          viewBox="0 0 24 24"
          className="h-4 w-4"
          fill="none"
          stroke="currentColor"
          strokeWidth="1.7"
          strokeLinecap="round"
          strokeLinejoin="round"
          aria-hidden="true"
        >
          <path d="M12 3v12M7 8l5-5 5 5M5 13v6a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2v-6" />
        </svg>
        {dict.share.button}
      </button>
      <dialog
        ref={dialog}
        aria-label={dict.share.title}
        className="m-auto w-[min(92vw,30rem)] rounded-[1.75rem] border border-line bg-card p-5 text-ink shadow-lift backdrop:bg-ink/40"
      >
        <p className="font-display text-2xl">{dict.share.title}</p>
        <div className="mt-4 grid min-h-60 place-items-center rounded-xl bg-paper-2">
          {image ? (
            // eslint-disable-next-line @next/next/no-img-element -- a local blob, not an optimizable asset
            <img
              src={image.url}
              alt={answer.summary ?? dict.share.title}
              className="max-h-[60vh] w-auto rounded-lg shadow-soft"
            />
          ) : (
            <p className="text-sm text-muted">{failed ? dict.ask.error : dict.share.preparing}</p>
          )}
        </div>
        <div className="mt-4 flex flex-wrap justify-end gap-2">
          {image && canShare && (
            <button
              type="button"
              onClick={() =>
                void navigator
                  .share({ files: [image.file], title: dict.share.title })
                  .catch(() => {})
              }
              className="rounded-full bg-accent px-4 py-2 text-sm font-medium text-white hover:bg-accent-2"
            >
              {dict.share.share}
            </button>
          )}
          {image && (
            <a
              href={image.url}
              download="tibyan.png"
              className="rounded-full border border-line px-4 py-2 text-sm text-ink-2 hover:border-accent hover:text-accent"
            >
              {dict.share.download}
            </a>
          )}
          <button
            type="button"
            onClick={() => dialog.current?.close()}
            className="rounded-full border border-line px-4 py-2 text-sm text-ink-2 hover:border-accent hover:text-accent"
          >
            {dict.share.close}
          </button>
        </div>
      </dialog>
    </>
  );
}
