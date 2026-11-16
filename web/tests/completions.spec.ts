import { expect, test } from "@playwright/test";

test("offers semantic completions from imported modules", async ({ page }) => {
  await page.goto("/");
  await expect(page.locator("#compile-status")).toContainText("words", {
    timeout: 180_000,
  });

  const editor = page.locator(".monaco-editor").first();
  await editor.click();
  await page.keyboard.press("Control+Home");
  for (let index = 0; index < 4; index += 1) {
    await page.keyboard.press("ArrowDown");
  }
  await page.keyboard.press("Home");
  await page.keyboard.press("Shift+End");
  await page.keyboard.type("ua;");
  await page.keyboard.press("ArrowLeft");
  await page.waitForTimeout(1500);

  await expect(page.locator(".suggest-widget.visible")).toBeVisible();
  const labels = await page
    .locator(".suggest-widget .monaco-list-row .label-name")
    .allTextContents();
  expect(labels).toContain("uart_init");
});
