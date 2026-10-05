import { expect, test } from "@playwright/test";

test("Fatwa checker — an authentic quote is found word for word, an altered one contradicts the fatwa", async ({
  page,
}) => {
  await page.goto("/ar/verify");
  await page.getByRole("button", { name: "نص صحيح" }).click();
  await expect(page.getByText("موجود بنصّه", { exact: true })).toBeVisible();
  await expect(page.locator("mark").first()).toBeVisible(); // the statement highlighted in the original
  await expect(page.getByRole("link", { name: "فتح الفتوى" })).toHaveAttribute(
    "href",
    /^https:\/\/binbaz\.org\.sa\/fatwas\/3338/,
  );
  await page.getByRole("button", { name: "نص محرّف" }).click();
  await expect(page.getByText("يخالف ما في الفتوى", { exact: true })).toBeVisible();
});

test("Pilgrims — their own page, questions in their language, and a QR code to print @mobile", async ({
  page,
}) => {
  await page.goto("/ur/hajj");
  await expect(page.getByRole("heading", { level: 1 })).toHaveText("ضیوفِ رحمٰن");
  await expect(
    page.getByRole("img", { name: "اپنی زبان میں پوچھنے کے لیے کوڈ اسکین کریں" }),
  ).toBeVisible();
  await expect(page.getByRole("button", { name: "کیا بغیر وضو طواف درست ہے؟" })).toBeVisible();
});

test("Share card — a verified answer becomes an image with its quote, source and a QR code", async ({
  page,
}) => {
  await page.goto("/ar");
  await page.getByRole("textbox").first().fill("ما المدة التي يقصر فيها المسافر الصلاة؟");
  await page.getByRole("button", { name: /^إرسال/ }).click();
  await page.getByRole("button", { name: "مشاركة كصورة" }).click();
  const dialog = page.getByRole("dialog", { name: "بطاقة الإجابة" });
  await expect(dialog.getByRole("img")).toBeVisible();
  const size = await dialog
    .getByRole("img")
    .evaluate((img: HTMLImageElement) => [img.naturalWidth, img.naturalHeight]);
  expect(size).toEqual([1080, 1350]);
  await expect(dialog.getByRole("link", { name: "تحميل الصورة" })).toHaveAttribute(
    "download",
    "tibyan.png",
  );
});

test("Easy mode — larger text and one big voice button, remembered on the next visit @mobile", async ({
  page,
}) => {
  await page.goto("/ar");
  const toggle = page.getByRole("button", { name: /^الوضع الميسّر/ });
  await toggle.click();
  await expect(page.locator("html")).toHaveAttribute("data-easy", "on");
  await expect(page.getByRole("button", { name: "اضغط هنا وتكلّم بسؤالك" })).toBeVisible();
  await page.reload();
  await expect(page.locator("html")).toHaveAttribute("data-easy", "on");
  await page.getByRole("button", { name: /^الوضع الميسّر/ }).click();
  await expect(page.locator("html")).not.toHaveAttribute("data-easy", "on");
});

test("Home — no longer lists the sources under the principles", async ({ page }) => {
  await page.goto("/ar");
  await expect(page.getByRole("heading", { name: "مبادئ تِبْيان" })).toBeAttached();
  await expect(page.getByText(/^نبحث في/)).toHaveCount(0);
});

test("Governance — overview, content gaps, sources by priority and a paged audit log", async ({
  page,
}) => {
  test.skip(!process.env.ADMIN_TOKEN, "set ADMIN_TOKEN to test the governance console");
  await page.goto("/ar/admin");
  await page.getByLabel("رمز المشرف").fill(process.env.ADMIN_TOKEN ?? "");
  await page.getByRole("button", { name: "دخول" }).click();
  await expect(page.getByRole("heading", { name: "نظرة عامة" })).toBeVisible();
  await expect(page.getByText("تكلفة النماذج اليوم")).toBeVisible();
  await expect(page.getByRole("heading", { name: "فجوات المحتوى" })).toBeVisible();
  const sources = page.getByRole("heading", { name: "المصادر وحالتها" }).locator("..");
  await expect(sources.getByText("binbaz", { exact: true })).toBeVisible();
  await expect(sources.getByText("hadeethenc", { exact: true })).toBeVisible();
  const audit = page.locator("section", {
    has: page.getByRole("heading", { name: "سجل التدقيق" }),
  });
  await expect(audit.locator("li")).toHaveCount(12);
  await page.getByRole("button", { name: "الأسئلة", exact: true }).click();
  await expect(audit.locator("li").first()).toContainText("سؤال");
});
