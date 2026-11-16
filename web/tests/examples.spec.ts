import { expect, test } from "@playwright/test";

test("falls back to examples in the runtime archive", async ({ page }) => {
  await page.route("**/examples/**", (route) =>
    route.fulfill({ status: 404, body: "" }),
  );

  await page.goto("/");
  await expect(page.locator("#example option")).toHaveCount(29, {
    timeout: 180_000,
  });
  await expect(page.locator("#compile-status")).toContainText("words", {
    timeout: 180_000,
  });
  await expect(page.locator("#example")).toHaveValue("hello.nbl");
});
