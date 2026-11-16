import { expect, test } from "@playwright/test";

test("links source lines to assembly and opens library tabs", async ({
  page,
}) => {
  await page.goto("/");
  await expect(page.locator("#compile-status")).toContainText("words", {
    timeout: 180_000,
  });

  const tabs = page.locator("#source-tabs .source-tab");
  await expect(tabs).toHaveCount(2);
  await expect(tabs.nth(0)).toHaveText("hello.nbl");
  await expect(tabs.nth(1)).toHaveText("lib/uart.nbl");

  const asmLibraryLine = page
    .locator("#asm-editor .view-line")
    .filter({ hasText: "fn_uart_puts:" })
    .first();
  await asmLibraryLine.hover();
  await expect(page.locator("#asm-status")).toContainText(
    "lib/uart.nbl:14",
  );
  await expect(
    page.locator("#source-tabs .source-tab.hovered"),
  ).toContainText("lib/uart.nbl");

  await asmLibraryLine.click();
  await expect(tabs.filter({ hasText: "lib/uart.nbl" })).toHaveClass(
    /active/,
  );
  await expect(page.locator("#editor .view-lines")).toContainText("UART");

  await tabs.filter({ hasText: "hello.nbl" }).click();

  await expect
    .poll(
      async () =>
        page.locator('#editor [class*="asm-color-"]').count(),
    )
    .toBeGreaterThan(0);
  await page.locator("#asm-color").uncheck();
  await expect
    .poll(
      async () =>
        page.locator('#editor [class*="asm-color-"]').count(),
    )
    .toBe(0);
  await page.locator("#asm-color").check();

  const sourceLine = page
    .locator("#editor .view-line")
    .filter({ hasText: "uart_puts(msg);" })
    .first();
  await sourceLine.hover();
  await expect(page.locator("#asm-status")).toContainText("hello.nbl:7");
  await sourceLine.click();
  await expect(page.locator("#asm-editor .view-lines")).toContainText(
    "while5",
  );

  await page.locator("#editor").click();
  await page.keyboard.press("Control+Home");
  for (let index = 0; index < 6; index += 1) {
    await page.keyboard.press("ArrowDown");
  }
  await expect(page.locator("#asm-status")).toContainText("hello.nbl:7", {
    timeout: 30_000,
  });
  await expect
    .poll(async () => page.locator("#asm-editor .asm-cursor-line").count())
    .toBeGreaterThan(0);
});
