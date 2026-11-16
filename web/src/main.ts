import "./style.css";
import * as monaco from "monaco-editor/editor/editor.api";
import "monaco-editor/editor/contrib/suggest/browser/suggestController";
import "monaco-editor/editor/contrib/suggest/browser/suggestInlineCompletions";
import "monaco-editor/editor/contrib/snippet/browser/snippetController2";
import EditorWorker from "monaco-editor/editor/editor.worker?worker";
import { registerNiblick } from "./niblick-language";
import {
  NiblickRuntime,
  type CompileResult,
  type EmulatorState,
} from "./runtime";
import {
  DEFAULT_FLASH_OPTIONS,
  Flasher,
  serialSupported,
} from "./flasher";
import { HELLO_SOURCE } from "./samples";

(self as unknown as { MonacoEnvironment: unknown }).MonacoEnvironment = {
  getWorker: () => new EditorWorker(),
};

const runtime = new NiblickRuntime();

registerNiblick(monaco, (source, line, column) =>
  runtime.completions(source, currentFilename, line, column),
);

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
const flashButton = document.getElementById("flash") as HTMLButtonElement;
const serialStatus = document.getElementById("serial-status")!;
const serialConnect = document.getElementById("serial-connect") as HTMLButtonElement;
const serialSend = document.getElementById("serial-send") as HTMLButtonElement;
const serialPadding = document.getElementById("serial-padding") as HTMLInputElement;
const flashLog = document.getElementById("flash-log")!;
const emuMatrix = document.getElementById("emu-matrix") as HTMLCanvasElement;
const emuRun = document.getElementById("emu-run") as HTMLButtonElement;
const emuStep = document.getElementById("emu-step") as HTMLButtonElement;
const emuReset = document.getElementById("emu-reset") as HTMLButtonElement;
const emuSpeed = document.getElementById("emu-speed") as HTMLSelectElement;
const emuState = document.getElementById("emu-state")!;
const emuUart = document.getElementById("emu-uart")!;
const emuUartInput = document.getElementById("emu-uart-input") as HTMLInputElement;
const emuUartNewline = document.getElementById("emu-uart-newline") as HTMLInputElement;
const emuUartSend = document.getElementById("emu-uart-send") as HTMLButtonElement;

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
  quickSuggestions: { other: true, comments: false, strings: false },
  suggestOnTriggerCharacters: true,
  wordBasedSuggestions: "currentDocument",
  acceptSuggestionOnEnter: "on",
  tabCompletion: "on",
  snippetSuggestions: "inline",
});

const model = editor.getModel()!;
const flasher = new Flasher();
let currentFilename = "/work/main.nbl";
let lastResult: CompileResult | null = null;
let flashBusy = false;
let emulatorState: EmulatorState | null = null;
let emulatorRunning = false;
let emulatorBusy = false;
let emulatorGeneration = 0;

function selectTab(name: string): void {
  for (const button of document.querySelectorAll<HTMLButtonElement>(".tab")) {
    button.classList.toggle("active", button.dataset.tab === name);
  }
  for (const body of document.querySelectorAll<HTMLElement>(".tab-body")) {
    body.classList.toggle("hidden", body.id !== `tab-${name}`);
  }
}

function appendFlashLog(message: string): void {
  const timestamp = new Date().toLocaleTimeString();
  flashLog.textContent += `[${timestamp}] ${message}\n`;
  flashLog.scrollTop = flashLog.scrollHeight;
}

function updateFlashAvailability(): void {
  const supported = serialSupported();
  const hasProgram = lastResult !== null && lastResult.ok;
  flashButton.disabled = !hasProgram;
  serialConnect.disabled = flashBusy || !supported || !hasProgram;
  serialSend.disabled =
    flashBusy || !supported || !hasProgram || !flasher.connected;
  if (!supported) {
    serialStatus.textContent = "WebSerial unavailable; use Download .hex";
  } else if (flasher.connected) {
    serialStatus.textContent = "connected; press LOAD, then Send";
  } else {
    serialStatus.textContent = "not connected";
  }
}

function renderMatrix(left: number[], right: number[]): void {
  const context = emuMatrix.getContext("2d");
  if (context === null) {
    return;
  }
  const cell = 20;
  const columns = 8;
  const rows = 16;
  emuMatrix.width = columns * cell;
  emuMatrix.height = rows * cell;
  context.fillStyle = "#0b0d11";
  context.fillRect(0, 0, emuMatrix.width, emuMatrix.height);
  for (let y = 0; y < rows; y += 1) {
    const leftBits = left[y] ?? 0;
    const rightBits = right[y] ?? 0;
    for (let x = 0; x < columns; x += 1) {
      const bit =
        x < 4
          ? (leftBits >> (3 - x)) & 1
          : (rightBits >> (3 - (x - 4))) & 1;
      context.fillStyle = bit ? "#d8a657" : "#1b2028";
      context.fillRect(x * cell + 2, y * cell + 2, cell - 4, cell - 4);
    }
  }
}

function renderEmulator(state: EmulatorState): void {
  emulatorState = state;
  renderMatrix(state.display_left, state.display_right);
  const registers = state.registers
    .slice(0, 10)
    .map((value, index) => `R${index}=${value}`)
    .join(" ");
  emuState.textContent =
    `PC=0x${state.pc.toString(16).padStart(3, "0")} SP=${state.sp} ` +
    `C=${state.C ? 1 : 0} Z=${state.Z ? 1 : 0} V=${state.V ? 1 : 0}\n` +
    `instructions=${state.instructions} cycles=${state.cycles} ` +
    `clock=${state.clock_hz} Hz\n${registers}`;
  const text = new TextDecoder().decode(new Uint8Array(state.uart_tx));
  if (emuUart.textContent !== text) {
    emuUart.textContent = text;
    emuUart.scrollTop = emuUart.scrollHeight;
  }
  if (state.halted) {
    emulatorRunning = false;
    emuRun.textContent = "Run";
  }
}

function setEmulatorControls(enabled: boolean): void {
  emuRun.disabled = !enabled;
  emuStep.disabled = !enabled;
  emuReset.disabled = !enabled;
  emuUartSend.disabled = !enabled;
}

async function loadEmulator(): Promise<void> {
  emulatorRunning = false;
  emuRun.textContent = "Run";
  emulatorGeneration += 1;
  const generation = emulatorGeneration;
  const program = lastResult;
  if (program === null || !program.ok) {
    emulatorState = null;
    emuState.textContent = "not loaded";
    emuUart.textContent = "";
    renderMatrix([], []);
    setEmulatorControls(false);
    return;
  }

  setEmulatorControls(false);
  emuState.textContent = "loading";
  try {
    const result = await runtime.emulatorLoad(program.hex);
    if (generation !== emulatorGeneration) {
      return;
    }
    if (!result.ok || result.state === undefined) {
      throw new Error(
        result.diagnostics?.[0]?.message ?? "emulator load failed",
      );
    }
    renderEmulator(result.state);
    setEmulatorControls(true);
  } catch (error) {
    const message = error instanceof Error ? error.message : String(error);
    emulatorState = null;
    emuState.textContent = `error: ${message}`;
    setEmulatorControls(false);
  }
}

async function emulatorFrame(): Promise<void> {
  if (!emulatorRunning || emulatorBusy) {
    return;
  }
  emulatorBusy = true;
  try {
    const result = await runtime.emulatorStep(Number(emuSpeed.value));
    if (result.ok && result.state !== undefined) {
      renderEmulator(result.state);
    }
  } catch (error) {
    emulatorRunning = false;
    emuRun.textContent = "Run";
    const message = error instanceof Error ? error.message : String(error);
    emuState.textContent = `error: ${message}`;
  } finally {
    emulatorBusy = false;
    if (emulatorRunning) {
      requestAnimationFrame(() => {
        void emulatorFrame();
      });
    }
  }
}

async function sendKey(key: number, down: boolean): Promise<void> {
  const result = await runtime.emulatorKey(key, down);
  if (result.ok && result.state !== undefined) {
    renderEmulator(result.state);
  }
}

async function sendAlt(down: boolean): Promise<void> {
  const result = await runtime.emulatorAlt(down);
  if (result.ok && result.state !== undefined) {
    renderEmulator(result.state);
  }
}

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
    updateFlashAvailability();
    void loadEmulator();
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
  updateFlashAvailability();
  void loadEmulator();
}

async function compile(): Promise<void> {
  if (!runtime.ready) {
    return;
  }
  compileButton.disabled = true;
  compileStatus.textContent = "compiling";
  emulatorRunning = false;
  emuRun.textContent = "Run";
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
    selectTab(tab.dataset.tab ?? "assembly");
  });
}

flashButton.addEventListener("click", () => {
  selectTab("flash");
  appendFlashLog("press Connect, put the badge in DIR mode, press LOAD, then Send");
});

serialConnect.addEventListener("click", async () => {
  try {
    await flasher.connect();
    appendFlashLog("serial port connected");
  } catch (error) {
    const message = error instanceof Error ? error.message : String(error);
    appendFlashLog(`connect failed: ${message}`);
  }
  updateFlashAvailability();
});

serialSend.addEventListener("click", async () => {
  if (lastResult === null || !lastResult.ok) {
    return;
  }
  flashBusy = true;
  updateFlashAvailability();
  try {
    const padding = Math.max(
      0,
      Number.parseInt(serialPadding.value, 10) || 0,
    );
    await flasher.flash(
      hexBytes(lastResult),
      { ...DEFAULT_FLASH_OPTIONS, paddingBytes: padding },
      appendFlashLog,
    );
    appendFlashLog("flash complete; the badge should be running");
    serialStatus.textContent = "sent; badge should be running";
  } catch (error) {
    const message = error instanceof Error ? error.message : String(error);
    appendFlashLog(`flash failed: ${message}`);
  } finally {
    flashBusy = false;
    updateFlashAvailability();
  }
});

emuRun.addEventListener("click", () => {
  if (emulatorState === null) {
    return;
  }
  emulatorRunning = !emulatorRunning;
  emuRun.textContent = emulatorRunning ? "Pause" : "Run";
  if (emulatorRunning) {
    void emulatorFrame();
  }
});

emuStep.addEventListener("click", async () => {
  emulatorRunning = false;
  emuRun.textContent = "Run";
  const result = await runtime.emulatorStep(1);
  if (result.ok && result.state !== undefined) {
    renderEmulator(result.state);
  }
});

emuReset.addEventListener("click", () => {
  emulatorRunning = false;
  emuRun.textContent = "Run";
  void loadEmulator();
});

for (const button of document.querySelectorAll<HTMLButtonElement>(
  "#tab-emulator [data-key]",
)) {
  const key = Number(button.dataset.key);
  const press = (event: PointerEvent) => {
    event.preventDefault();
    void sendKey(key, true);
  };
  const release = () => {
    void sendKey(key, false);
  };
  button.addEventListener("pointerdown", press);
  button.addEventListener("pointerup", release);
  button.addEventListener("pointerleave", release);
  button.addEventListener("pointercancel", release);
}

for (const button of document.querySelectorAll<HTMLButtonElement>(
  "#tab-emulator [data-alt]",
)) {
  const press = (event: PointerEvent) => {
    event.preventDefault();
    void sendAlt(true);
  };
  const release = () => {
    void sendAlt(false);
  };
  button.addEventListener("pointerdown", press);
  button.addEventListener("pointerup", release);
  button.addEventListener("pointerleave", release);
  button.addEventListener("pointercancel", release);
}

emuUartSend.addEventListener("click", async () => {
  const text =
    emuUartInput.value + (emuUartNewline.checked ? "\n" : "");
  if (text.length === 0) {
    return;
  }
  const result = await runtime.emulatorInput(new TextEncoder().encode(text));
  if (result.ok && result.state !== undefined) {
    renderEmulator(result.state);
  }
  emuUartInput.value = "";
});

emuUartInput.addEventListener("keydown", (event) => {
  if (event.key === "Enter") {
    event.preventDefault();
    emuUartSend.click();
  }
});

setEmulatorControls(false);
renderMatrix([], []);

if (serialSupported()) {
  appendFlashLog("WebSerial is available in this browser");
} else {
  appendFlashLog(
    "WebSerial is not available; use Download .hex and scripts/flash.py",
  );
}
updateFlashAvailability();

editor.addCommand(monaco.KeyMod.CtrlCmd | monaco.KeyCode.Enter, () => {
  void compile();
});

void boot();
