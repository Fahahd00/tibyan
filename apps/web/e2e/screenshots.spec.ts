import { test } from "@playwright/test";

// Visual review helper (not run in CI): SCREENSHOTS=1 npx playwright test screenshots
test.skip(!process.env.SCREENSHOTS, "set SCREENSHOTS=1 to capture review screenshots");

const out = process.env.SCREENSHOT_DIR ?? "playwright-report/screens";

for (const [name, viewport] of [
  ["desktop", { width: 1440, height: 1000 }],
  ["mobile", { width: 390, height: 844 }],
] as const) {
  test(`capture ${name}`, async ({ page }) => {
    await page.setViewportSize(viewport);
    await page.goto("/ar");
    await page.screenshot({ path: `${out}/${name}-home-ar.png`, fullPage: true });
    await page.goto("/ar/about");
    await page.screenshot({ path: `${out}/${name}-about-ar.png`, fullPage: true });
    await page.goto("/ar/sources");
    await page.screenshot({ path: `${out}/${name}-sources-ar.png`, fullPage: true });
    await page.goto("/ar");
    await page.getByRole("textbox").first().fill("ما المدة التي يقصر فيها المسافر الصلاة؟");
    await page.getByRole("button", { name: /^إرسال/ }).click();
    await page.getByText("الخلاصة", { exact: true }).first().waitFor();
    await page.getByRole("button", { name: /كيف وصلنا/ }).click();
    await page.getByText("المصادر التي تم البحث فيها").waitFor();
    await page
      .locator("article")
      .first()
      .screenshot({ path: `${out}/${name}-answer-ar.png` });
    await page.goto("/ar");
    await page.getByRole("textbox").first().fill("طلقت زوجتي وأنا غضبان فهل يقع الطلاق؟");
    await page.getByRole("button", { name: /^إرسال/ }).click();
    await page.getByText("هذه المسألة تحتاج إلى جهة مختصة").waitFor();
    await page
      .locator("article")
      .first()
      .screenshot({ path: `${out}/${name}-escalation-ar.png` });
    await page.goto("/en");
    await page.screenshot({ path: `${out}/${name}-home-en.png` });
  });
}
