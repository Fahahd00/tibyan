import { expect, test } from "@playwright/test";

/**
 * Voice conversation mode: hands-free loop through the real pipeline. Only the browser speech engine is stubbed:
 * each recognition "hears" the next queued utterance (none left = silence), and speech synthesis records what
 * would be read aloud.
 */
test("voice conversation asks, clarifies by voice, reads the verified answer and keeps listening @mobile", async ({
  page,
}, info) => {
  await page.addInitScript(() => {
    const w = window as unknown as Record<string, unknown>;
    const queue = ["هل يجوز لي قصر الصلاة؟", "أنا مسافر"];
    const spoken: string[] = [];
    w.__spoken = spoken;
    class FakeRecognition {
      lang = "";
      interimResults = false;
      continuous = false;
      onresult: ((e: unknown) => void) | null = null;
      onerror: ((e: unknown) => void) | null = null;
      onend: (() => void) | null = null;
      start() {
        const said = queue.shift();
        setTimeout(() => {
          if (said)
            this.onresult?.({
              results: [Object.assign([{ transcript: said }], { isFinal: true })],
            });
          this.onend?.();
        }, 3000);
      }
      stop() {}
    }
    w.SpeechRecognition = FakeRecognition;
    w.webkitSpeechRecognition = FakeRecognition;
    window.speechSynthesis.speak = (u: SpeechSynthesisUtterance) => {
      spoken.push(u.text);
      setTimeout(() => u.onend?.(new Event("end") as SpeechSynthesisEvent), 4000);
    };
    // Server voice (TTS_PROVIDER=openai) plays a stored answer through new Audio(url): record the url, never load it.
    class FakeAudio {
      onended: ((e: Event) => void) | null = null;
      onerror: ((e: Event) => void) | null = null;
      constructor(public src = "") {}
      play() {
        spoken.push(this.src);
        setTimeout(() => this.onended?.(new Event("ended")), 4000);
        return Promise.resolve();
      }
      pause() {}
    }
    (window as unknown as { Audio: unknown }).Audio = FakeAudio;
  });
  const shot = (name: string) =>
    page.screenshot({ path: `test-results/voice-mode-${info.project.name}-${name}.png` });

  await page.goto("/ar");
  await shot("0-entry");
  await page.getByRole("button", { name: "محادثة صوتية" }).click();
  const dialog = page.getByRole("dialog", { name: "محادثة صوتية" });
  await expect(dialog.getByText("أستمع إليك…")).toBeVisible();

  // Clarification is asked aloud with its options, then answered by voice. (Assert first, screenshot after:
  // each phase lasts only as long as the stubbed speech.)
  await expect(dialog.getByText("مسافر", { exact: true })).toBeVisible();
  await expect(dialog.getByText("تِبْيان يجيب")).toBeVisible();
  await shot("2-clarification");
  await expect(dialog.getByText("أبحث في المصادر الموثوقة…")).toBeVisible();
  await shot("3-thinking");

  // The verified answer is read aloud with its source, then the loop listens again (silence pauses it).
  await expect(dialog.getByRole("link", { name: /^المصدر:/ })).toBeVisible();
  await shot("4-answer");
  await expect(dialog.getByText("اضغط على النجمة لتتحدث")).toBeVisible();
  await shot("5-paused");

  const spoken = await page.evaluate(() => (window as unknown as { __spoken: string[] }).__spoken);
  expect(spoken).toHaveLength(2);
  // Browser voice reads the choices aloud; the server voice reads the stored clarification (choices included).
  expect(spoken[0].includes("مسافر أو مقيم") || spoken[0].includes("/api/voice/synthesize/")).toBe(
    true,
  );

  // Ending the conversation leaves the full verified answer, with its source, on the page.
  await dialog.getByRole("button", { name: "إنهاء المحادثة" }).click();
  await expect(dialog).toBeHidden();
  await expect(page.getByRole("link", { name: "فتح المصدر" }).first()).toBeVisible();
});
