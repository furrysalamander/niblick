import { expect, test } from "@playwright/test";

test("loads and steps the emulator", async ({ page }) => {
  await page.goto("/");
  await expect(page.locator("#compile-status")).toContainText("words", {
    timeout: 180_000,
  });

  await page.locator('.tab[data-tab="emulator"]').click();
  await expect(page.locator("#emu-state")).toHaveText("ready", {
    timeout: 60_000,
  });
  await expect(page.locator("#tab-emulator .emu-reg[data-reg]")).toHaveCount(10);
  await expect(page.locator("#tab-emulator .reg-bits i")).toHaveCount(40);
  await expect(page.locator("#tab-emulator [data-key]")).toHaveCount(5);
  await expect(page.locator("#tab-emulator [data-alt]")).toHaveCount(1);
  await expect(page.locator("#tab-emulator")).not.toContainText("OPERAND");
  await expect(page.locator("#tab-emulator")).not.toContainText("DATA IN");
  await expect(page.locator("#tab-emulator")).not.toContainText("MODE");
  await expect(page.locator("#emu-pc")).toHaveText("0x000");

  await page.locator('#tab-emulator [data-key="1"]').click();
  await expect(page.locator("#emu-key")).toHaveText("1");
  await page.locator('#tab-emulator [data-key="0"]').click();
  await expect(page.locator("#emu-key")).toHaveText("0");

  const before = await page.locator("#emu-pc").textContent();
  await page.locator("#emu-step").click();
  await expect(page.locator("#emu-pc")).not.toHaveText(before ?? "", {
    timeout: 60_000,
  });
});

test("runs the program and shows UART output", async ({ page }) => {
  await page.goto("/");
  await expect(page.locator("#compile-status")).toContainText("words", {
    timeout: 180_000,
  });

  await page.locator('.tab[data-tab="emulator"]').click();
  await expect(page.locator("#emu-state")).toHaveText("ready", {
    timeout: 60_000,
  });
  await page.locator("#emu-run").click();
  await expect(page.locator("#emu-uart")).toContainText("Hello, Supercon!", {
    timeout: 60_000,
  });
});
