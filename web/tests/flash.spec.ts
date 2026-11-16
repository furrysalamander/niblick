import { expect, test } from "@playwright/test";

test("flashes the hex over a mock serial port", async ({ page }) => {
  await page.addInitScript(() => {
    const written: number[] = [];
    const port = {
      open: async () => {},
      close: async () => {},
      writable: new WritableStream<Uint8Array>({
        write(chunk) {
          written.push(...chunk);
        },
      }),
    };
    Object.defineProperty(navigator, "serial", {
      configurable: true,
      value: {
        requestPort: async () => port,
        getPorts: async () => [port],
      },
    });
    (window as unknown as { __serialWritten: number[] }).__serialWritten =
      written;
  });

  await page.goto("/");
  await expect(page.locator("#compile-status")).toContainText("words", {
    timeout: 180_000,
  });

  await page.getByRole("button", { name: "Flash badge" }).click();
  await page.getByRole("button", { name: "Connect" }).click();
  await expect(page.locator("#serial-status")).toContainText("connected");
  await page.getByRole("button", { name: "Send .hex" }).click();
  await expect(page.locator("#flash-log")).toContainText("flash complete", {
    timeout: 120_000,
  });

  const result = await page.evaluate(() => {
    const bytes = (
      window as unknown as { __serialWritten: number[] }
    ).__serialWritten;
    return { length: bytes.length, head: bytes.slice(0, 6) };
  });
  expect(result.head).toEqual([0, 255, 0, 255, 165, 195]);
  expect(result.length).toBeGreaterThan(1024);
});
