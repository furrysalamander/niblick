import { expect, test } from "@playwright/test";

test("compiles examples and downloads the hex", async ({ page }) => {
  const errors: string[] = [];
  page.on("console", (message) => {
    if (message.type() === "error") {
      errors.push(message.text());
    }
  });
  page.on("pageerror", (error) => errors.push(String(error)));

  await page.goto("/");
  await expect(page.locator("#runtime-status")).toContainText("ready", {
    timeout: 180_000,
  });
  await expect(page.locator("#compile-status")).toContainText("words", {
    timeout: 180_000,
  });
  await expect(page.locator("#assembly")).toContainText("fn_main");
  await expect(page.locator("#size-status")).toContainText("142 / 4096");
  await expect(page.locator("#problems")).toContainText("No problems");

  const downloadPromise = page.waitForEvent("download");
  await page.getByRole("button", { name: "Download .hex" }).click();
  const download = await downloadPromise;
  expect(download.suggestedFilename()).toBe("niblick.hex");

  await page.locator("#example").selectOption("inline_asm.nbl");
  await expect(page.locator("#compile-status")).toContainText("8 words", {
    timeout: 180_000,
  });
  await expect(page.locator("#assembly")).toContainText("ADD R0, 4");

  expect(errors).toEqual([]);
});
