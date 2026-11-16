import { expect, test } from "@playwright/test";

test("provides hover, context menu, and go to definition", async ({
  page,
}) => {
  await page.goto("/");
  await expect(page.locator("#compile-status")).toContainText("words", {
    timeout: 180_000,
  });

  const line = page
    .locator("#editor .view-line")
    .filter({ hasText: "uart_puts" })
    .first();
  const token = line.locator("span").filter({ hasText: "uart_puts" }).nth(1);
  const box = await token.boundingBox();
  expect(box).not.toBeNull();
  if (box === null) {
    return;
  }
  const x = box.x + 40;
  const y = box.y + box.height / 2;

  await page.mouse.move(x, y);
  await expect(page.locator(".monaco-hover:visible")).toContainText("uart_puts", {
    timeout: 30_000,
  });

  await page.mouse.click(x, y, { button: "right" });
  await expect(page.locator(".monaco-menu")).toBeVisible();
  await expect(page.locator(".monaco-menu")).toContainText(
    "Command Palette",
  );
  await expect(page.locator(".monaco-menu")).toContainText(
    "Go to Definition",
  );
  await page.keyboard.press("Escape");

  await page.keyboard.down("Control");
  await page.mouse.click(x, y);
  await page.keyboard.up("Control");
  await expect(page.locator("#source-tabs .source-tab.active")).toHaveText(
    "lib/uart.nbl",
  );
});
