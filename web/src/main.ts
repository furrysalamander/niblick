import "./style.css";
import * as monaco from "monaco-editor/editor/editor.api";
import EditorWorker from "monaco-editor/editor/editor.worker?worker";
import { registerNiblick } from "./niblick-language";
import { NiblickRuntime, type CompileResult } from "./runtime";
import { HELLO_SOURCE } from "./samples";

(self as unknown as { MonacoEnvironment: unknown }).MonacoEnvironment = {
  getWorker: () => new EditorWorker(),
};

registerNiblick(monaco);

const runtimeStatus = document.getElementById("runtime-status")!;
const compileStatus = document.getElementById("compile-status")!;
const sizeStatus = document.getElementById("size-status")!;
const timingStatus = document.getElementById("timing-status")!;
const loading = document.getElementById("loading")!;
const loadingMessage = document.getElementById("loading-message")!;
const compileButton = document.getElementById("compile") as HTMLButtonElement;
const downloadButton = document.getElementById("download") as HTMLButtonElement;
const exampleSelect = document.getElementById("example") as HTMLSelectElement;
const assembly = document.getElementById("assembly")!;
const problems = document.getElementById("problems")!;
const hexSummary = document.getElementById("hex-summary")!;

const editor = monaco.editor.create(document.getElementById("editor")!, {
  value: HELLO_SOURCE,
  language: "niblick",
  theme: "vs-dark",
  automaticLayout: true,
  fontSize: 13,
  tabSize: 4,
  minimap: { enabled: false },
  scrollBeyondLastLine: false,
  renderWhitespace: "selection",
});

const model = editor.getModel()!;
const runtime = new NiblickRuntime();
let currentFilename = "/work/main.nbl";
let lastResult: CompileResult | null = null;

function setProblems(items: string[]): void {
  problems.replaceChildren();
  if (items.length === 0) {
    const ok = document.createElement("div");
    ok.className = "problem ok";
    ok.textContent = "No problems.";
    problems.append(ok);
    return;
  }
  for (const item of items) {
    const row = document.createElement("div");
    row.className = "problem";
    row.textContent = item;
    problems.append(row);
  }
}

function setMarkers(result: CompileResult): void {
  if (result.ok) {
    monaco.editor.setModelMarkers(model, "niblick", []);
    return;
  }
  const basename = currentFilename.split("/").pop() ?? currentFilename;
  const markers: monaco.editor.IMarkerData[] = result.diagnostics
    .filter(
      (diagnostic) =>
        !diagnostic.file ||
        diagnostic.file === currentFilename ||
        diagnostic.file.endsWith(basename),
    )
    .map((diagnostic) => ({
      severity: monaco.MarkerSeverity.Error,
      message: diagnostic.message,
      startLineNumber: Math.max(1, diagnostic.line),
      startColumn: Math.max(1, diagnostic.column),
      endLineNumber: Math.max(1, diagnostic.line),
      endColumn: Math.max(1, diagnostic.column) + 1,
    }));
  monaco.editor.setModelMarkers(model, "niblick", markers);
}

function hexBytes(result: CompileResult): Uint8Array {
  const binary = atob(result.hex);
  const bytes = new Uint8Array(binary.length);
  for (let index = 0; index < binary.length; index += 1) {
    bytes[index] = binary.charCodeAt(index);
  }
  return bytes;
}

function showResult(result: CompileResult): void {
  lastResult = result;
  if (!result.ok) {
    assembly.textContent = "";
    hexSummary.textContent = "";
    compileStatus.textContent = "compile failed";
    sizeStatus.textContent = "";
    downloadButton.disabled = true;
    const messages = result.diagnostics.map(
      (diagnostic) =>
        `${diagnostic.file || result.filename}:${diagnostic.line}:${diagnostic.column}: ${diagnostic.message}`,
    );
    setProblems(messages);
    setMarkers(result);
    return;
  }

  assembly.textContent = result.asm;
  const bytes = hexBytes(result);
  const preview = Array.from(bytes.slice(0, 64))
    .map((byte) => byte.toString(16).padStart(2, "0"))
    .join(" ");
  hexSummary.textContent = `${bytes.length} bytes\n\n${preview}${bytes.length > 64 ? " ..." : ""}`;
  compileStatus.textContent = `${result.words} words, ${result.ram} RAM nibbles, ${Math.round(result.compileMs ?? 0)} ms`;
  sizeStatus.textContent = `${result.words} / 4096 words, ${result.ram} / 208 RAM nibbles`;
  setProblems([]);
  setMarkers(result);
  downloadButton.disabled = false;
}

async function compile(): Promise<void> {
  if (!runtime.ready) {
    return;
  }
  compileButton.disabled = true;
  compileStatus.textContent = "compiling";
  const started = performance.now();
  try {
    const result = await runtime.compile(editor.getValue(), currentFilename);
    showResult(result);
    timingStatus.textContent = `compile ${Math.round(performance.now() - started)} ms; runtime ${Math.round(runtime.startupMs)} ms`;
  } catch (error) {
    const message = error instanceof Error ? error.message : String(error);
    compileStatus.textContent = "compile failed";
    setProblems([message]);
    timingStatus.textContent = "";
  } finally {
    compileButton.disabled = false;
  }
}

async function loadExample(path: string): Promise<void> {
  try {
    const source = await runtime.loadExample(path);
    editor.setValue(source);
    currentFilename = `/work/examples/${path}`;
    monaco.editor.setModelMarkers(model, "niblick", []);
    setProblems([]);
    await compile();
  } catch (error) {
    const message = error instanceof Error ? error.message : String(error);
    setProblems([message]);
  }
}

async function boot(): Promise<void> {
  try {
    await runtime.init((message) => {
      loadingMessage.textContent = message;
      runtimeStatus.textContent = "loading";
    });
    loading.classList.add("hidden");
    runtimeStatus.textContent = `ready ${Math.round(runtime.startupMs)} ms`;
    compileButton.disabled = false;

    const examples = await runtime.listExamples();
    exampleSelect.replaceChildren();
    for (const item of examples) {
      const option = document.createElement("option");
      option.value = item.path;
      option.textContent = item.name;
      exampleSelect.append(option);
    }
    const hello = examples.find((item) => item.name === "hello");
    if (hello !== undefined) {
      exampleSelect.value = hello.path;
      await loadExample(hello.path);
    } else {
      await compile();
    }
  } catch (error) {
    const message = error instanceof Error ? error.message : String(error);
    loadingMessage.textContent = message;
    runtimeStatus.textContent = "runtime error";
    setProblems([message]);
    console.error(error);
  }
}

compileButton.addEventListener("click", () => {
  void compile();
});

downloadButton.addEventListener("click", () => {
  if (lastResult === null || !lastResult.ok) {
    return;
  }
  const bytes = hexBytes(lastResult);
  const buffer = new ArrayBuffer(bytes.byteLength);
  new Uint8Array(buffer).set(bytes);
  const blob = new Blob([buffer], { type: "application/octet-stream" });
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = "niblick.hex";
  anchor.click();
  URL.revokeObjectURL(url);
});

exampleSelect.addEventListener("change", () => {
  if (exampleSelect.value) {
    void loadExample(exampleSelect.value);
  }
});

for (const tab of document.querySelectorAll<HTMLButtonElement>(".tab")) {
  tab.addEventListener("click", () => {
    for (const button of document.querySelectorAll<HTMLButtonElement>(".tab")) {
      button.classList.toggle("active", button === tab);
    }
    for (const body of document.querySelectorAll<HTMLElement>(".tab-body")) {
      body.classList.toggle("hidden", body.id !== `tab-${tab.dataset.tab}`);
    }
  });
}

editor.addCommand(monaco.KeyMod.CtrlCmd | monaco.KeyCode.Enter, () => {
  void compile();
});

void boot();
