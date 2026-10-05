import { expect, test } from "@playwright/test";

async function ask(page: import("@playwright/test").Page, question: string) {
  await page.getByRole("textbox").first().fill(question);
  await page.getByRole("button", { name: /^(إرسال|Send)/ }).click();
}

test.describe("Scenario A — verified answer (Arabic)", () => {
  test("answers from an approved source with quote, source link and trust chain @mobile", async ({
    page,
  }) => {
    await page.goto("/ar");
    await expect(page.locator("html")).toHaveAttribute("dir", "rtl");
    await expect(page.getByRole("heading", { level: 1 })).toContainText("تِبْيان");
    await ask(page, "ما المدة التي يقصر فيها المسافر الصلاة؟");

    const card = page.locator("article").first();
    await expect(card.getByText("الخلاصة", { exact: true }).first()).toBeVisible();
    await expect(card.getByText("النص المستند إليه").first()).toBeVisible();
    await expect(card.locator("mark").first()).toBeVisible(); // the verbatim quote is highlighted in the source text
    const open = card.getByRole("link", { name: "فتح المصدر" }).first();
    await expect(open).toHaveAttribute("href", /^https:\/\/binbaz\.org\.sa\/fatwas\//);

    await card.getByRole("button", { name: /كيف وصلنا لهذه الإجابة/ }).click();
    await expect(card.getByText("المصادر التي تم البحث فيها")).toBeVisible();
    await expect(card.getByText(/مستبعد/).first()).toBeVisible(); // pending / not-indexed sources are listed as excluded
    await expect(card.getByText("التحقق", { exact: true })).toBeVisible();
  });
});

test("Scenario B — incomplete question asks for clarification, then answers", async ({ page }) => {
  await page.goto("/ar");
  await ask(page, "هل يجوز لي قصر الصلاة؟");
  await expect(page.getByText("هل أنت مسافر أم مقيم؟")).toBeVisible();
  await page.getByRole("button", { name: "مسافر", exact: true }).click();
  await expect(page.getByText("الخلاصة", { exact: true }).first()).toBeVisible();
  await expect(page.getByText(/وأنا مسافر/).first()).toBeVisible();
});

test("Scenario C — personal case is escalated to verified official bodies", async ({ page }) => {
  await page.goto("/ar");
  await ask(page, "طلقت زوجتي وأنا غضبان فهل يقع الطلاق؟");
  await expect(page.getByText("هذه المسألة تحتاج إلى جهة مختصة")).toBeVisible();
  await expect(page.getByRole("link", { name: /^وزارة العدل/ })).toHaveAttribute(
    "href",
    "https://www.moj.gov.sa",
  );
  await expect(page.getByText("الخلاصة", { exact: true }).first()).toHaveCount(0);
});

test("Abstention — no sufficient reference is stated plainly", async ({ page }) => {
  await page.goto("/ar");
  // Live search answers from the approved websites when the index cannot; a made-up term has no fatwa anywhere.
  await ask(page, "ما حكم صيام يوم الزرقلة؟");
  await expect(page.getByText("لم نجد مرجعًا كافيًا للإجابة.")).toBeVisible();
});

test("English locale renders LTR and answers @mobile", async ({ page }) => {
  await page.goto("/en");
  await expect(page.locator("html")).toHaveAttribute("dir", "ltr");
  await ask(page, "How long may a traveller shorten the prayer?");
  await expect(page.getByText("Summary", { exact: true })).toBeVisible();
  await expect(page.getByRole("link", { name: "Open source" }).first()).toBeVisible();
});

test("Voice — spoken question goes through the same pipeline and the verified answer is read aloud", async ({
  page,
}) => {
  // Stand-in for the browser speech engine only; transcription result → real pipeline → real answer.
  await page.addInitScript(() => {
    const spoken: string[] = [];
    (window as unknown as { __spoken: string[] }).__spoken = spoken;
    class FakeRecognition {
      lang = "";
      interimResults = false;
      continuous = false;
      onresult: ((e: unknown) => void) | null = null;
      onerror: ((e: unknown) => void) | null = null;
      onend: (() => void) | null = null;
      start() {
        setTimeout(() => {
          const result = Object.assign(
            [{ transcript: "ما المدة التي يقصر فيها المسافر الصلاة؟" }],
            { isFinal: true },
          );
          this.onresult?.({ results: [result] });
          this.onend?.();
        }, 200);
      }
      stop() {}
    }
    const w = window as unknown as { webkitSpeechRecognition: unknown; SpeechRecognition: unknown };
    w.SpeechRecognition = FakeRecognition;
    w.webkitSpeechRecognition = FakeRecognition;
    window.speechSynthesis.speak = (u: SpeechSynthesisUtterance) => {
      spoken.push(u.text);
    };
    // Server voice (TTS_PROVIDER=openai) plays a stored answer through new Audio(url): record the url, never load it.
    class FakeAudio {
      onended: ((e: Event) => void) | null = null;
      onerror: ((e: Event) => void) | null = null;
      constructor(public src = "") {}
      play() {
        spoken.push(this.src);
        setTimeout(() => this.onended?.(new Event("ended")), 300);
        return Promise.resolve();
      }
      pause() {}
    }
    (window as unknown as { Audio: unknown }).Audio = FakeAudio;
  });
  await page.goto("/ar");
  await page.getByRole("button", { name: /اسأل صوتيًا/ }).click();
  await expect(page.getByText("الخلاصة", { exact: true }).first()).toBeVisible();
  await expect(page.getByText("🎙")).toBeVisible();
  await expect
    .poll(async () =>
      page.evaluate(() => (window as unknown as { __spoken: string[] }).__spoken.length),
    )
    .toBeGreaterThan(0);
  const spokenText = await page.evaluate(
    () => (window as unknown as { __spoken: string[] }).__spoken[0],
  );
  if (spokenText.includes("/api/voice/synthesize/")) return; // server voice: the stored answer, by id
  const summary = await page.locator("article p.font-naskh").first().innerText();
  expect(spokenText.startsWith(summary.trim().slice(0, 20))).toBe(true);
});

test("Sources page shows governance status", async ({ page }) => {
  await page.goto("/ar/sources");
  await expect(page.getByText("معتمد").first()).toBeVisible();
  await expect(page.getByText("قيد المراجعة").first()).toBeVisible();
});

test("Small talk — a greeting gets a courteous reply and an invitation to ask @mobile", async ({
  page,
}) => {
  await page.goto("/ar");
  await ask(page, "السلام عليكم، كيف حالك؟");
  await expect(page.getByText(/^وعليكم السلام ورحمة الله وبركاته/)).toBeVisible();
  await expect(page.getByText("لم نجد مرجعًا كافيًا للإجابة.")).toHaveCount(0);
});

test("Focus mode — typing dims the page and the exchange builds up as one conversation @mobile", async ({
  page,
}) => {
  await page.goto("/ar");
  const exit = page.getByRole("button", { name: "إغلاق وضع التركيز" });
  await expect(exit).toHaveCount(0);
  await page.getByRole("textbox").first().focus();
  await expect(exit).toBeVisible();
  await ask(page, "السلام عليكم");
  await expect(page.locator("article")).toHaveCount(1);
  await ask(page, "جزاك الله خيرًا");
  await expect(page.locator("article")).toHaveCount(2); // the earlier exchange stays above the new one
  await page.keyboard.press("Escape");
  await expect(exit).toHaveCount(0);
  await expect(page.locator("article")).toHaveCount(2);
});

test("General message — a short reply first, then the invitation to ask a religious question", async ({
  page,
}) => {
  await page.goto("/ar");
  await ask(page, "ما عاصمة فرنسا؟");
  await expect(page.getByText(/ما المسألة الشرعية التي تودّ السؤال عنها؟$/)).toBeVisible();
  await expect(page.getByText("لم نجد مرجعًا كافيًا للإجابة.")).toHaveCount(0);
});

test("Language menu — eleven languages; Urdu is right-to-left @mobile", async ({ page }) => {
  await page.goto("/ur");
  await expect(page.locator("html")).toHaveAttribute("dir", "rtl");
  await page.getByLabel("زبان").click();
  for (const name of [
    "العربية",
    "English",
    "اردو",
    "हिन्दी",
    "বাংলা",
    "Türkçe",
    "Bahasa Indonesia",
    "Bahasa Melayu",
    "O‘zbekcha",
    "Қазақша",
    "Hausa",
  ])
    await expect(page.getByRole("link", { name, exact: true })).toBeVisible();
  await page.getByRole("link", { name: "हिन्दी", exact: true }).click();
  await expect(page).toHaveURL(/\/hi$/);
  await expect(page.locator("html")).toHaveAttribute("dir", "ltr");
  await expect(page.getByRole("link", { name: "मुखपृष्ठ" })).toBeVisible();
});

test("Turkish — a Turkish question is answered in Turkish from the Arabic sources", async ({
  page,
}) => {
  await page.goto("/tr");
  await page.getByRole("textbox").first().fill("Yolcu namazı ne kadar süre kısaltabilir?");
  await page.getByRole("button", { name: /^Gönder/ }).click();
  await expect(page.getByText("Özet", { exact: true })).toBeVisible();
  await expect(page.getByRole("link", { name: "Kaynağı aç" }).first()).toBeVisible();
});

test("Malay — a Malay question is answered in Malay from the Arabic sources", async ({ page }) => {
  await page.goto("/ms");
  await expect(page.locator("html")).toHaveAttribute("lang", "ms");
  await page.getByRole("textbox").first().fill("Berapa lama musafir boleh mengqasarkan solat?");
  await page.getByRole("button", { name: /^Hantar/ }).click();
  await expect(page.getByText("Ringkasan", { exact: true })).toBeVisible();
});
