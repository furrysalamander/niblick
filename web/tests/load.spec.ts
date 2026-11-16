import { expect, test } from "@playwright/test";

test("paints and styles the shell before the app chunk loads", async ({
  page,
}) => {
  let release = () => {};
  const gate = new Promise<void>((resolve) => {
    release = resolve;
  });
  await page.route("**/assets/app-*.js", async (route) => {
    await gate;
    await route.continue();
  });

  try {
    await page.goto("/");
    await expect(page.locator("#loading")).toBeVisible();
    await expect(page.locator("#loading-message")).toContainText(
      "Loading editor and compiler",
    );
    const background = await page.evaluate(
      () => getComputedStyle(document.body).backgroundColor,
    );
    expect(background).toBe("rgb(17, 19, 24)");
  } finally {
    release();
  }
});
