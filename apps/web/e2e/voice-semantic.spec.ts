import { expect, test } from "@playwright/test";

/**
 * Voice semantic test: a natural colloquial spoken question must take the same pipeline as text and reach the
 * same fatwa. Only the browser speech engine is stubbed (real microphones cannot be automated).
 */
const SPOKEN = "أنا بسافر وبجلس هناك كم يوم، هل أقصر الصلاة؟";

async function citedSources(page: import("@playwright/test").Page): Promise<string[]> {
  const links = page
    .locator("article")
    .first()
    .getByRole("link", { name: /فتح المصدر|Open source/ });
  return (
    await links.evaluateAll((els) =>
      els.map((e) => (e as HTMLAnchorElement).href.match(/fatwas\/(\d+)/)?.[1] ?? ""),
    )
  ).sort();
}

test("spoken colloquial question reaches the same verified source as the typed one, and is read aloud", async ({
  page,
}) => {
  await page.addInitScript((spoken: string) => {
    const w = window as unknown as Record<string, unknown>;
    const said: string[] = [];
    w.__spoken = said;
    class FakeRecognition {
      lang = "";
      interimResults = false;
      continuous = false;
      onresult: ((e: unknown) => void) | null = null;
      onerror: ((e: unknown) => void) | null = null;
      onend: (() => void) | null = null;
      start() {
        setTimeout(() => {
          this.onresult?.({
            results: [Object.assign([{ transcript: spoken }], { isFinal: true })],
          });
          this.onend?.();
        }, 200);
      }
      stop() {}
    }
    w.SpeechRecognition = FakeRecognition;
    w.webkitSpeechRecognition = FakeRecognition;
    window.speechSynthesis.speak = (u: SpeechSynthesisUtterance) => void said.push(u.text);
    // Server voice (TTS_PROVIDER=openai) plays a stored answer through new Audio(url): record the url, never load it.
    class FakeAudio {
      onended: ((e: Event) => void) | null = null;
      onerror: ((e: Event) => void) | null = null;
      constructor(public src = "") {}
      play() {
        said.push(this.src);
        setTimeout(() => this.onended?.(new Event("ended")), 300);
        return Promise.resolve();
      }
      pause() {}
    }
    (window as unknown as { Audio: unknown }).Audio = FakeAudio;
  }, SPOKEN);

  await page.goto("/ar");
  await page.getByRole("button", { name: /اسأل صوتيًا/ }).click();
  const card = page.locator("article").first();
  await expect(card.getByText("الخلاصة", { exact: true }).first()).toBeVisible();
  await expect(card.getByText("🎙")).toBeVisible();
  const voiceSources = await citedSources(page);
  expect(voiceSources.length).toBeGreaterThan(0);
  await expect
    .poll(() =>
      page.evaluate(() => ((window as unknown as { __spoken: string[] }).__spoken ?? []).length),
    )
    .toBeGreaterThan(0);

  // Same question typed: same pipeline, same verified source(s).
  await page.goto("/ar");
  await page.getByRole("textbox").first().fill(SPOKEN);
  await page.getByRole("button", { name: /^إرسال/ }).click();
  await expect(
    page.locator("article").first().getByText("الخلاصة", { exact: true }).first(),
  ).toBeVisible();
  const textSources = await citedSources(page);
  expect(textSources.filter((s) => voiceSources.includes(s)).length).toBeGreaterThan(0);
});
