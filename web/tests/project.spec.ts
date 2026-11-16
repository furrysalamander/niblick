import { expect, test, type Page } from "@playwright/test";
import { strFromU8, strToU8, unzipSync, zipSync } from "fflate";
import fs from "node:fs/promises";

const MAIN_WITH_ASM = `import "add.asm";
extern fn nibble add3(nibble x);
nibble result;
fn main() {
    result = add3(4);
    while (1) { }
}
`;

const ADD_ASM = `fn_add3:
    MOV R0, [\${x}]
    ADD R0, 3
    MOV R1, R0
    RET R0, 0
`;

function projectZip(
  files: Record<string, string>,
  manifest?: Record<string, unknown>,
): Uint8Array {
  const entries: Record<string, string> = { ...files };
  if (manifest !== undefined) {
    entries["niblick.json"] = JSON.stringify(manifest);
  }
  return zipSync(
    Object.fromEntries(
      Object.entries(entries).map(([path, value]) => [
        path,
        strToU8(value),
      ]),
    ),
  );
}

async function openProjectMenu(page: Page): Promise<void> {
  await page.locator("#project-menu-button").click();
  await expect(page.locator("#project-menu")).toBeVisible();
}

async function importZip(
  page: Page,
  name: string,
  bytes: Uint8Array,
): Promise<void> {
  await page.setInputFiles("#project-import", {
    name,
    mimeType: "application/zip",
    buffer: Buffer.from(bytes),
  });
}

test("creates project files and restores them after reload", async ({
  page,
}) => {
  await page.goto("/");
  await expect(page.locator("#compile-status")).toContainText("words", {
    timeout: 180_000,
  });

  await openProjectMenu(page);
  await page.locator('[data-project-action="new"]').click();
  await page.locator("#project-name").fill("demo");
  await page.locator("#project-path").fill("main.nbl");
  await page.locator("#project-dialog-confirm").click();
  await expect(page.locator("#source-tabs .source-tab")).toHaveCount(1, {
    timeout: 30_000,
  });
  await expect(page.locator("#source-tabs .source-tab")).toHaveText(
    "main.nbl",
  );

  await page.locator("#project-add").click();
  await page.locator("#project-path").fill("src/util.nbl");
  await page.locator("#project-dialog-confirm").click();
  await expect(page.locator("#source-tabs")).toContainText("src/util.nbl");

  await page.locator("#project-add").click();
  await page.locator("#project-path").fill("drivers/foo.asm");
  await page.locator("#project-dialog-confirm").click();
  await expect(page.locator("#source-tabs")).toContainText(
    "drivers/foo.asm",
  );
  await expect(page.locator("#source-tabs .source-tab.entry")).toHaveText(
    "main.nbl",
  );
  await expect(page.locator("#source-tabs .source-tab.active")).toHaveText(
    "drivers/foo.asm",
  );

  await openProjectMenu(page);
  await page.locator('[data-project-action="rename"]').click();
  await page.locator("#project-path").fill("drivers/bar.asm");
  await page.locator("#project-dialog-confirm").click();
  await expect(page.locator("#source-tabs")).toContainText(
    "drivers/bar.asm",
  );
  await expect(page.locator("#source-tabs")).not.toContainText(
    "drivers/foo.asm",
  );

  await page.reload();
  await expect(page.locator("#compile-status")).toContainText("words", {
    timeout: 180_000,
  });
  await expect(page.locator("#source-tabs .source-tab")).toHaveCount(3, {
    timeout: 30_000,
  });
  await expect(page.locator("#source-tabs")).toContainText("main.nbl");
  await expect(page.locator("#source-tabs")).toContainText(
    "src/util.nbl",
  );
  await expect(page.locator("#source-tabs .source-tab.active")).toHaveText(
    "drivers/bar.asm",
  );

  await openProjectMenu(page);
  await page.locator('[data-project-action="delete"]').click();
  await expect(page.locator("#project-dialog-title")).toHaveText(
    "Delete file?",
  );
  await page.locator("#project-dialog-confirm").click();
  await expect(page.locator("#source-tabs .source-tab")).toHaveCount(2);
  await expect(page.locator("#source-tabs")).not.toContainText(
    "drivers/bar.asm",
  );
  await expect(page.locator("#source-tabs .source-tab.active")).toHaveText(
    "main.nbl",
  );
});

test("imports a folder-stripped zip and exports a manifest", async ({
  page,
}) => {
  await page.goto("/");
  await expect(page.locator("#compile-status")).toContainText("words", {
    timeout: 180_000,
  });

  await importZip(
    page,
    "imported.zip",
    projectZip({
      "demo/main.nbl": MAIN_WITH_ASM,
      "demo/add.asm": ADD_ASM,
      "demo/README.txt": "ignored",
    }),
  );
  await expect(page.locator("#source-tabs")).toContainText("add.asm", {
    timeout: 60_000,
  });
  await expect(page.locator("#compile-status")).toContainText("14 words", {
    timeout: 60_000,
  });
  await expect(page.locator("#problems")).toContainText("No problems");
  await expect(page.locator("#source-tabs .source-tab.entry")).toHaveText(
    "main.nbl",
  );

  const downloadPromise = page.waitForEvent("download");
  await openProjectMenu(page);
  await page.locator('[data-project-action="export"]').click();
  const download = await downloadPromise;
  expect(download.suggestedFilename()).toBe("imported.zip");
  const downloadPath = await download.path();
  expect(downloadPath).not.toBeNull();
  const data = new Uint8Array(await fs.readFile(downloadPath!));
  const files = unzipSync(data);
  expect(new Set(Object.keys(files))).toEqual(
    new Set(["niblick.json", "add.asm", "main.nbl"]),
  );
  const manifest = JSON.parse(
    strFromU8(files["niblick.json"]),
  ) as Record<string, unknown>;
  expect(manifest).toMatchObject({
    format: "niblick-project",
    version: 1,
    name: "imported",
    entry: "main.nbl",
  });
  expect(strFromU8(files["main.nbl"])).toContain('import "add.asm";');
});

test("rejects unsafe zip paths", async ({ page }) => {
  await page.goto("/");
  await expect(page.locator("#compile-status")).toContainText("words", {
    timeout: 180_000,
  });

  await importZip(
    page,
    "unsafe.zip",
    projectZip({ "../escape.nbl": "fn main() { }\n" }),
  );
  await expect(page.locator("#project-dialog")).toBeVisible({
    timeout: 10_000,
  });
  await expect(page.locator("#project-dialog-title")).toHaveText(
    "Import failed",
  );
  await expect(
    page.locator("#project-dialog-description"),
  ).toContainText("relative path");
  await page.locator("#project-dialog-confirm").click();
  await expect(page.locator("#source-tabs")).toContainText("hello.nbl");
  await expect(page.locator("#source-tabs")).not.toContainText(
    "escape.nbl",
  );
});

test("compiles edits to an imported assembly module", async ({ page }) => {
  await page.goto("/");
  await expect(page.locator("#compile-status")).toContainText("words", {
    timeout: 180_000,
  });

  await importZip(
    page,
    "edit.zip",
    projectZip({
      "main.nbl": MAIN_WITH_ASM,
      "add.asm": ADD_ASM,
    }),
  );
  await expect(page.locator("#source-tabs")).toContainText("add.asm", {
    timeout: 60_000,
  });
  await expect(page.locator("#compile-status")).toContainText("14 words", {
    timeout: 60_000,
  });

  await page
    .locator("#source-tabs .source-tab")
    .filter({ hasText: "add.asm" })
    .click();
  await page.locator("#editor").click();
  await page.keyboard.press("Control+End");
  await page.keyboard.type("\nBOGUS\n");
  await page.locator("#compile").click();
  await expect(page.locator("#compile-status")).toHaveText(
    "compile failed",
    { timeout: 60_000 },
  );
  await expect(page.locator("#problems")).toContainText("add.asm");
  await expect(page.locator("#problems")).toContainText("BOGUS");
});
