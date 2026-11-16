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

export type CompileResult = {
  ok: boolean;
  filename: string;
  asm: string;
  hex: string;
  hex_size: number;
  words: number;
  ram: number;
  diagnostics: Diagnostic[];
  compileMs?: number;
};

export type RuntimeProgress = (message: string) => void;

function assetUrl(path: string): string {
  return new URL(`${import.meta.env.BASE_URL}${path}`, window.location.href).href;
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

  async compile(source: string, filename: string): Promise<CompileResult> {
    const pyodide = this.pyodide;
    if (pyodide === null) {
      throw new Error("the Python runtime is not ready");
    }
    const started = performance.now();
    pyodide.globals.set("__niblick_source", source);
    pyodide.globals.set("__niblick_filename", filename);
    const result = await pyodide.runPythonAsync(
      "niblick.web.compile_source_json(__niblick_source, __niblick_filename)",
    );
    return {
      ...(JSON.parse(result) as CompileResult),
      compileMs: performance.now() - started,
    };
  }

  async listExamples(): Promise<Array<{ name: string; path: string }>> {
    const response = await fetch(assetUrl("examples/manifest.json"));
    if (!response.ok) {
      return [];
    }
    return (await response.json()) as Array<{ name: string; path: string }>;
  }

  async loadExample(path: string): Promise<string> {
    const response = await fetch(assetUrl(`examples/${path}`));
    if (!response.ok) {
      throw new Error(`examples/${path}: HTTP ${response.status}`);
    }
    return await response.text();
  }
}
