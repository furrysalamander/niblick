import type { PyodideInterface } from "pyodide";

const PYODIDE_VERSION = "0.29.5";
const PYODIDE_CDN = `https://cdn.jsdelivr.net/pyodide/v${PYODIDE_VERSION}/full/`;

export type Diagnostic = {
  file: string;
  line: number;
  column: number;
  message: string;
  severity: string;
  code: string;
};

export type AsmMapping = {
  line: number;
  file: string;
  source_line: number;
};

export type CompileResult = {
  ok: boolean;
  filename: string;
  asm: string;
  hex: string;
  hex_size: number;
  words: number;
  ram: number;
  asm_map: AsmMapping[];
  sources: Record<string, string>;
  diagnostics: Diagnostic[];
  compileMs?: number;
};

export type EmulatorState = {
  pc: number;
  sp: number;
  C: number;
  Z: number;
  V: number;
  registers: number[];
  ram: number[];
  halted: boolean;
  instructions: number;
  cycles: number;
  clock_hz: number;
  uart_tx: number[];
  uart_rx: number[];
  keys_down: number[];
  alt_down: boolean;
  last_key: number | null;
  display_left: number[];
  display_right: number[];
  executed?: number;
};

export type EmulatorResult = {
  ok: boolean;
  state?: EmulatorState;
  diagnostics?: Diagnostic[];
};

export type CompletionSymbol = {
  name: string;
  kind: string;
  detail: string;
  type: string;
};

export type DefinitionLocation = {
  file: string;
  line: number;
  column: number;
};

export type ReferenceLocation = DefinitionLocation & {
  length: number;
};

export type RuntimeProgress = (message: string) => void;

function assetUrl(path: string): string {
  return new URL(`${import.meta.env.BASE_URL}${path}`, window.location.href).href;
}

function bytesToBase64(bytes: Uint8Array): string {
  let binary = "";
  for (const byte of bytes) {
    binary += String.fromCharCode(byte);
  }
  return btoa(binary);
}

export class NiblickRuntime {
  private pyodide: PyodideInterface | null = null;
  private initMs = 0;

  get ready(): boolean {
    return this.pyodide !== null;
  }

  get startupMs(): number {
    return this.initMs;
  }

  async init(progress: RuntimeProgress): Promise<void> {
    const started = performance.now();
    progress("Loading Pyodide");
    const pyodideModule = (await import(
      /* @vite-ignore */ `${PYODIDE_CDN}pyodide.mjs`
    )) as typeof import("pyodide");
    const pyodide = await pyodideModule.loadPyodide({
      indexURL: PYODIDE_CDN,
    });
    progress("Loading package manager");
    await pyodide.loadPackage("micropip");

    progress("Installing Niblick and assembler");
    const wheelResponse = await fetch(assetUrl("wheels/manifest.json"));
    if (!wheelResponse.ok) {
      throw new Error(`wheels/manifest.json: HTTP ${wheelResponse.status}`);
    }
    const wheelManifest = (await wheelResponse.json()) as {
      niblick: string;
      assembler: string;
    };
    const wheels = JSON.stringify([
      assetUrl(`wheels/${wheelManifest.assembler}`),
      assetUrl(`wheels/${wheelManifest.niblick}`),
    ]);
    pyodide.globals.set("__niblick_wheels", wheels);
    await pyodide.runPythonAsync(`
import json
import micropip

for wheel in json.loads(__niblick_wheels):
    await micropip.install(wheel, deps=False)
del __niblick_wheels
`);

    progress("Mounting library and examples");
    const response = await fetch(assetUrl("runtime.zip"));
    if (!response.ok) {
      throw new Error(`runtime.zip: HTTP ${response.status}`);
    }
    const zip = new Uint8Array(await response.arrayBuffer());
    pyodide.FS.writeFile("/tmp/niblick-runtime.zip", zip);
    await pyodide.runPythonAsync(`
import os
import zipfile

os.makedirs("/work", exist_ok=True)
with zipfile.ZipFile("/tmp/niblick-runtime.zip") as archive:
    archive.extractall("/work")
os.environ["NIBLICK_PATH"] = "/work"
import niblick.web
`);

    this.pyodide = pyodide;
    this.initMs = performance.now() - started;
    progress(`Ready in ${Math.round(this.initMs)} ms`);
  }

  async compile(
    source: string,
    filename: string,
    overrides: Record<string, string> = {},
  ): Promise<CompileResult> {
    const pyodide = this.pyodide;
    if (pyodide === null) {
      throw new Error("the Python runtime is not ready");
    }
    const started = performance.now();
    pyodide.globals.set("__niblick_source", source);
    pyodide.globals.set("__niblick_filename", filename);
    pyodide.globals.set("__niblick_overrides", JSON.stringify(overrides));
    const result = await pyodide.runPythonAsync(
      "niblick.web.compile_source_json(__niblick_source, __niblick_filename, overrides_json=__niblick_overrides)",
    );
    return {
      ...(JSON.parse(result) as CompileResult),
      compileMs: performance.now() - started,
    };
  }

  private async jsonCall(
    expression: string,
    args: Record<string, string | number | boolean>,
  ): Promise<unknown> {
    const pyodide = this.pyodide;
    if (pyodide === null) {
      throw new Error("the Python runtime is not ready");
    }
    for (const [key, value] of Object.entries(args)) {
      pyodide.globals.set(`__niblick_${key}`, value);
    }
    const result = await pyodide.runPythonAsync(expression);
    return JSON.parse(result);
  }

  async emulatorLoad(hexBase64: string): Promise<EmulatorResult> {
    return (await this.jsonCall(
      "niblick.web.emulator_load_json(__niblick_hex)",
      { hex: hexBase64 },
    )) as EmulatorResult;
  }

  async emulatorStep(count: number): Promise<EmulatorResult> {
    return (await this.jsonCall(
      "niblick.web.emulator_step_json(__niblick_count)",
      { count },
    )) as EmulatorResult;
  }

  async emulatorKey(key: number, down: boolean): Promise<EmulatorResult> {
    return (await this.jsonCall(
      "niblick.web.emulator_key_json(__niblick_key, __niblick_down)",
      { key, down },
    )) as EmulatorResult;
  }

  async emulatorAlt(down: boolean): Promise<EmulatorResult> {
    return (await this.jsonCall(
      "niblick.web.emulator_alt_json(__niblick_down)",
      { down },
    )) as EmulatorResult;
  }

  async emulatorInput(bytes: Uint8Array): Promise<EmulatorResult> {
    return (await this.jsonCall(
      "niblick.web.emulator_input_json(__niblick_data)",
      { data: bytesToBase64(bytes) },
    )) as EmulatorResult;
  }

  async definition(
    source: string,
    filename: string,
    line: number,
    column: number,
    overrides: Record<string, string> = {},
  ): Promise<DefinitionLocation | null> {
    const result = (await this.jsonCall(
      "niblick.web.definition_json(__niblick_source, __niblick_filename, __niblick_line, __niblick_column, overrides_json=__niblick_overrides)",
      { source, filename, line, column, overrides: JSON.stringify(overrides) },
    )) as { ok: boolean; definition: DefinitionLocation | null };
    return result.ok ? result.definition : null;
  }

  async hover(
    source: string,
    filename: string,
    line: number,
    column: number,
    overrides: Record<string, string> = {},
  ): Promise<string | null> {
    const result = (await this.jsonCall(
      "niblick.web.hover_json(__niblick_source, __niblick_filename, __niblick_line, __niblick_column, overrides_json=__niblick_overrides)",
      { source, filename, line, column, overrides: JSON.stringify(overrides) },
    )) as { ok: boolean; hover: string | null };
    return result.ok ? result.hover : null;
  }

  async references(
    source: string,
    filename: string,
    line: number,
    column: number,
    overrides: Record<string, string> = {},
  ): Promise<ReferenceLocation[]> {
    const result = (await this.jsonCall(
      "niblick.web.references_json(__niblick_source, __niblick_filename, __niblick_line, __niblick_column, overrides_json=__niblick_overrides)",
      { source, filename, line, column, overrides: JSON.stringify(overrides) },
    )) as { ok: boolean; references: ReferenceLocation[] };
    return result.ok ? result.references : [];
  }

  async completions(
    source: string,
    filename: string,
    line: number,
    column: number,
    overrides: Record<string, string> = {},
  ): Promise<CompletionSymbol[]> {
    const result = (await this.jsonCall(
      "niblick.web.completions_json(__niblick_source, __niblick_filename, __niblick_line, __niblick_column, overrides_json=__niblick_overrides)",
      { source, filename, line, column, overrides: JSON.stringify(overrides) },
    )) as { ok: boolean; items: CompletionSymbol[] };
    return result.ok ? result.items : [];
  }

  async listExamples(): Promise<Array<{ name: string; path: string }>> {
    try {
      const response = await fetch(assetUrl("examples/manifest.json"));
      if (response.ok) {
        const items = (await response.json()) as Array<{
          name: string;
          path: string;
        }>;
        if (items.length > 0) {
          return items;
        }
      }
    } catch {
      // Fall through to the runtime archive.
    }
    const result = (await this.jsonCall(
      "niblick.web.list_examples_json()",
      {},
    )) as { ok: boolean; items: Array<{ name: string; path: string }> };
    return result.ok ? result.items : [];
  }

  async loadExample(path: string): Promise<string> {
    try {
      const response = await fetch(assetUrl(`examples/${path}`));
      if (response.ok) {
        return await response.text();
      }
    } catch {
      // Fall through to the runtime archive.
    }
    const result = (await this.jsonCall(
      "niblick.web.read_example_json(__niblick_path)",
      { path },
    )) as { ok: boolean; source: string };
    if (!result.ok) {
      throw new Error(`example ${path} is not available`);
    }
    return result.source;
  }
}
