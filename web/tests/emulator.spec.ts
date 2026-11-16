import { expect, test } from "@playwright/test";

test("loads and steps the emulator", async ({ page }) => {
  await page.goto("/");
  await expect(page.locator("#compile-status")).toContainText("words", {
    timeout: 180_000,
  });

  await page.locator('.tab[data-tab="emulator"]').click();
  await expect(page.locator("#emu-state")).toContainText("PC=", {
    timeout: 60_000,
  });
  const before = await page.locator("#emu-state").textContent();
  await page.getByRole("button", { name: "Step" }).click();
  await expect(page.locator("#emu-state")).not.toHaveText(before ?? "", {
    timeout: 60_000,
  });
});

test("runs the program and shows UART output", async ({ page }) => {
  await page.goto("/");
  await expect(page.locator("#compile-status")).toContainText("words", {
    timeout: 180_000,
  });

  await page.locator('.tab[data-tab="emulator"]').click();
  await expect(page.locator("#emu-state")).toContainText("PC=", {
    timeout: 60_000,
  });
  await page.getByRole("button", { name: "Run" }).click();
  await expect(page.locator("#emu-uart")).toContainText("Hello, Supercon!", {
    timeout: 60_000,
  });
});
