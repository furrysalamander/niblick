import * as monaco from "monaco-editor/editor/editor.main";
import EditorWorker from "monaco-editor/editor/editor.worker?worker";
import { registerNiblick } from "./niblick-language";
import { registerVoja4Asm } from "./voja4-asm-language";
import { AsmView } from "./asm-view";
import { formatHexdump } from "./hexdump";
import { colorClassFor } from "./colors";
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
import {
  NEW_ASM_SOURCE,
  NEW_PROJECT_SOURCE,
  buildProjectZip,
  clearStoredProject,
  joinProjectPath,
  languageForPath,
  loadStoredProject,
  projectDownloadName,
  readProjectZip,
  relativeProjectPath,
  saveProject,
  validateSourcePath,
  type ProjectSnapshot,
} from "./project";
import { HELLO_SOURCE } from "./samples";

(self as unknown as { MonacoEnvironment: unknown }).MonacoEnvironment = {
  getWorker: () => new EditorWorker(),
};

const runtime = new NiblickRuntime();

registerVoja4Asm(monaco);

registerNiblick(monaco, {
  complete: (source, line, column) =>
    runtime.completions(source, activePath, line, column, projectOverrides()),
  definition: (source, line, column) =>
    runtime.definition(source, activePath, line, column, projectOverrides()),
  hover: (source, line, column) =>
    runtime.hover(source, activePath, line, column, projectOverrides()),
  references: (source, line, column) =>
    runtime.references(source, activePath, line, column, projectOverrides()),
});

const runtimeStatus = document.getElementById("runtime-status")!;
const compileStatus = document.getElementById("compile-status")!;
const sizeStatus = document.getElementById("size-status")!;
const timingStatus = document.getElementById("timing-status")!;
const loading = document.getElementById("loading")!;
const loadingMessage = document.getElementById("loading-message")!;
const compileButton = document.getElementById("compile") as HTMLButtonElement;
const downloadButton = document.getElementById("download") as HTMLButtonElement;
const exampleSelect = document.getElementById("example") as HTMLSelectElement;
const sourceTabs = document.getElementById("source-tabs")!;
const projectAdd = document.getElementById("project-add") as HTMLButtonElement;
const projectMenuButton = document.getElementById(
  "project-menu-button",
) as HTMLButtonElement;
const projectMenu = document.getElementById("project-menu")!;
const projectTitle = document.getElementById("project-title")!;
const projectStatus = document.getElementById("project-status")!;
const projectImport = document.getElementById(
  "project-import",
) as HTMLInputElement;
const projectDialog = document.getElementById(
  "project-dialog",
) as HTMLDialogElement;
const projectForm = document.getElementById("project-form") as HTMLFormElement;
const projectDialogTitle = document.getElementById("project-dialog-title")!;
const projectDialogDescription = document.getElementById(
  "project-dialog-description",
)!;
const projectDialogError = document.getElementById("project-dialog-error")!;
const projectNameLabel = document.getElementById("project-name-label")!;
const projectNameInput = document.getElementById(
  "project-name",
) as HTMLInputElement;
const projectPathLabel = document.getElementById("project-path-label")!;
const projectPathInput = document.getElementById(
  "project-path",
) as HTMLInputElement;
const projectDialogConfirm = document.getElementById(
  "project-dialog-confirm",
) as HTMLButtonElement;
const projectDialogCancel = document.getElementById(
  "project-dialog-cancel",
) as HTMLButtonElement;
const problems = document.getElementById("problems")!;
const asmStatus = document.getElementById("asm-status")!;
const asmFollow = document.getElementById("asm-follow") as HTMLInputElement;
const asmColor = document.getElementById("asm-color") as HTMLInputElement;
const hexDump = document.getElementById("hex-dump")!;
const hexInfo = document.getElementById("hex-info")!;
const hexCopy = document.getElementById("hex-copy") as HTMLButtonElement;
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
const emuPc = document.getElementById("emu-pc")!;
const emuSp = document.getElementById("emu-sp")!;
const emuFlags = document.getElementById("emu-flags")!;
const emuInstr = document.getElementById("emu-instr")!;
const emuCycles = document.getElementById("emu-cycles")!;
const emuClock = document.getElementById("emu-clock")!;
const emuAlt = document.getElementById("emu-alt")!;
const emuKey = document.getElementById("emu-key")!;
const emuUart = document.getElementById("emu-uart")!;
const emuUartInput = document.getElementById("emu-uart-input") as HTMLInputElement;
const emuUartNewline = document.getElementById("emu-uart-newline") as HTMLInputElement;
const emuUartSend = document.getElementById("emu-uart-send") as HTMLButtonElement;
const emuUartClear = document.getElementById("emu-uart-clear") as HTMLButtonElement;
const registerRows = Array.from(
  document.querySelectorAll<HTMLElement>(".emu-reg"),
);
let previousRegisters: number[] = [];

const initialRoot = "/work/project";
const initialEntryPath = joinProjectPath(initialRoot, "main.nbl");
const initialModel = monaco.editor.createModel(
  HELLO_SOURCE,
  "niblick",
  monaco.Uri.file(initialEntryPath),
);
const editor = monaco.editor.create(document.getElementById("editor")!, {
  model: initialModel,
  language: "niblick",
  theme: "vs-dark",
  automaticLayout: false,
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

let projectRoot = initialRoot;
let projectName = "untitled";
let entryPath = initialEntryPath;
let activePath = entryPath;
let projectDirty = false;
let lastExamplePath = "";
let saveTimer: number | null = null;
let suppressSave = false;
const models = new Map<string, monaco.editor.ITextModel>([
  [entryPath, initialModel],
]);
const projectFiles = new Set<string>([entryPath]);
const trackedModels = new Set<string>([entryPath]);
initialModel.onDidChangeContent(() => {
  markDirty();
});
const viewStates = new Map<
  string,
  monaco.editor.ICodeEditorViewState | null
>();
const sourceHoverDecorations = editor.createDecorationsCollection([]);

const asmView = new AsmView(document.getElementById("asm-editor")!, {
  openSource: (file, line) => {
    openSource(file, line);
  },
  hoverSource: (file, line) => {
    hoverSource(file, line);
  },
  status: (text) => {
    asmStatus.textContent = text;
  },
});

const flasher = new Flasher();
let lastResult: CompileResult | null = null;
let flashBusy = false;
let emulatorState: EmulatorState | null = null;
let emulatorRunning = false;
let emulatorBusy = false;
let emulatorGeneration = 0;
let sourceColorEnabled = true;
const sourceColorIds = new Map<string, string[]>();

function selectTab(name: string): void {
  for (const button of document.querySelectorAll<HTMLButtonElement>(".tab")) {
    button.classList.toggle("active", button.dataset.tab === name);
  }
  for (const body of document.querySelectorAll<HTMLElement>(".tab-body")) {
    body.classList.toggle("hidden", body.id !== `tab-${name}`);
  }
  if (name === "assembly") {
    requestAnimationFrame(() => {
      asmView.layout();
      asmView.updateFromSource(
        activePath,
        editor.getPosition()?.lineNumber ?? 1,
      );
    });
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

function sourceName(path: string): string {
  const relative = relativeProjectPath(projectRoot, path);
  if (relative !== null) {
    return relative;
  }
  const work = path.indexOf("/work/");
  if (work >= 0) {
    return path.slice(work + "/work/".length);
  }
  const parts = path.split("/");
  return parts.slice(Math.max(0, parts.length - 2)).join("/");
}

function resolveSourcePath(file: string): string | null {
  if (models.has(file)) {
    return file;
  }
  const base = file.split("/").pop();
  for (const path of models.keys()) {
    if (path.endsWith(`/${base}`)) {
      return path;
    }
  }
  return null;
}

function setProjectStatus(message: string, error = false): void {
  projectStatus.textContent = message;
  projectStatus.classList.toggle("error", error);
  if (statusTimer !== null) {
    window.clearTimeout(statusTimer);
    statusTimer = null;
  }
  if (message !== "") {
    statusTimer = window.setTimeout(() => {
      projectStatus.textContent = "";
      projectStatus.classList.remove("error");
      statusTimer = null;
    }, 4000);
  }
}

let statusTimer: number | null = null;

function trackProjectModel(
  path: string,
  model: monaco.editor.ITextModel,
): void {
  projectFiles.add(path);
  if (trackedModels.has(path)) {
    return;
  }
  trackedModels.add(path);
  model.onDidChangeContent(() => {
    if (projectFiles.has(path)) {
      markDirty();
    }
  });
}

function markDirty(): void {
  projectDirty = true;
  scheduleSave();
}

function scheduleSave(): void {
  if (suppressSave) {
    return;
  }
  if (saveTimer !== null) {
    window.clearTimeout(saveTimer);
  }
  saveTimer = window.setTimeout(() => {
    saveTimer = null;
    persistProject();
  }, 300);
}

function projectSnapshot(): ProjectSnapshot {
  const files: Record<string, string> = {};
  for (const path of projectFiles) {
    const relative = relativeProjectPath(projectRoot, path);
    const model = models.get(path);
    if (relative !== null && model !== undefined) {
      files[relative] = model.getValue();
    }
  }
  const entry = relativeProjectPath(projectRoot, entryPath) ?? "";
  const active = relativeProjectPath(projectRoot, activePath) ?? entry;
  return { name: projectName, entry, active, files };
}

function projectOverrides(): Record<string, string> {
  const overrides: Record<string, string> = {};
  for (const path of projectFiles) {
    const model = models.get(path);
    if (model !== undefined) {
      overrides[path] = model.getValue();
    }
  }
  return overrides;
}

function persistProject(): void {
  if (suppressSave || projectFiles.size === 0) {
    return;
  }
  const snapshot = projectSnapshot();
  if (snapshot.entry === "" || !(snapshot.entry in snapshot.files)) {
    return;
  }
  const error = saveProject(snapshot);
  if (error !== null) {
    setProjectStatus("auto-save failed; export the project", true);
  }
}

function disposeModel(path: string): void {
  const model = models.get(path);
  if (model === undefined) {
    return;
  }
  if (path === activePath) {
    const fallback = models.get(entryPath);
    if (fallback !== undefined && fallback !== model) {
      activePath = entryPath;
      editor.setModel(fallback);
    }
  }
  models.delete(path);
  viewStates.delete(path);
  sourceColorIds.delete(path);
  projectFiles.delete(path);
  trackedModels.delete(path);
  model.dispose();
}

function updateProjectMenu(): void {
  const activeIsProject = projectFiles.has(activePath);
  const activeIsEntry = activePath === entryPath;
  for (const button of projectMenu.querySelectorAll<HTMLButtonElement>(
    "[data-project-action]",
  )) {
    const action = button.dataset.projectAction;
    if (action === "rename" || action === "delete") {
      button.disabled = !activeIsProject;
    } else if (action === "entry") {
      button.disabled =
        !activeIsProject ||
        activeIsEntry ||
        !activePath.toLowerCase().endsWith(".nbl");
    } else if (action === "export") {
      button.disabled = projectFiles.size === 0;
    }
  }
}

function renderSourceTabs(): void {
  sourceTabs.replaceChildren();
  const projectPaths = Array.from(projectFiles).sort((left, right) => {
    if (left === entryPath) {
      return -1;
    }
    if (right === entryPath) {
      return 1;
    }
    return sourceName(left).localeCompare(sourceName(right));
  });
  const imported = Array.from(models.keys())
    .filter((path) => !projectFiles.has(path))
    .sort((left, right) => sourceName(left).localeCompare(sourceName(right)));
  for (const path of [...projectPaths, ...imported]) {
    const button = document.createElement("button");
    button.className = "source-tab";
    if (path === activePath) {
      button.classList.add("active");
    }
    if (!projectFiles.has(path)) {
      button.classList.add("readonly");
    }
    if (path === entryPath) {
      button.classList.add("entry");
    }
    if (path.toLowerCase().endsWith(".asm")) {
      button.classList.add("asm");
    }
    button.textContent = sourceName(path);
    button.title =
      path === entryPath
        ? `${sourceName(path)} (entry point)`
        : sourceName(path);
    button.dataset.path = path;
    button.addEventListener("click", () => {
      setActiveSource(path);
    });
    sourceTabs.append(button);
  }
  projectTitle.textContent = projectName;
  updateProjectMenu();
}

function setActiveSource(path: string): void {
  const next = models.get(path);
  if (next === undefined) {
    return;
  }
  if (path === activePath && editor.getModel() === next) {
    return;
  }
  viewStates.set(activePath, editor.saveViewState());
  activePath = path;
  editor.setModel(next);
  editor.updateOptions({ readOnly: !projectFiles.has(path) });
  const state = viewStates.get(path);
  if (state !== undefined && state !== null) {
    editor.restoreViewState(state);
  }
  sourceHoverDecorations.clear();
  renderSourceTabs();
  scheduleSave();
  const line = editor.getPosition()?.lineNumber ?? 1;
  asmView.updateFromSource(activePath, line);
}

function updateSourceModels(result: CompileResult): void {
  const wanted = new Set<string>(Object.keys(result.sources));
  for (const [path, text] of Object.entries(result.sources)) {
    const relative = relativeProjectPath(projectRoot, path);
    if (relative !== null) {
      let model = models.get(path);
      if (model === undefined) {
        model = monaco.editor.createModel(
          text,
          languageForPath(path),
          monaco.Uri.file(path),
        );
        models.set(path, model);
      }
      trackProjectModel(path, model);
      continue;
    }
    let model = models.get(path);
    if (model === undefined) {
      model = monaco.editor.createModel(
        text,
        languageForPath(path),
        monaco.Uri.file(path),
      );
      models.set(path, model);
    } else if (model.getValue() !== text) {
      model.setValue(text);
    }
  }
  for (const path of Array.from(models.keys())) {
    if (wanted.has(path) || projectFiles.has(path)) {
      continue;
    }
    disposeModel(path);
  }
  if (!models.has(activePath)) {
    activePath = entryPath;
    const model = models.get(entryPath);
    if (model !== undefined) {
      editor.setModel(model);
      editor.updateOptions({ readOnly: false });
    }
  }
  renderSourceTabs();
  applySourceColors(result);
  scheduleSave();
}

function applySourceColors(result: CompileResult | null): void {
  const byFile = new Map<string, Map<number, string>>();
  if (result !== null && result.ok && sourceColorEnabled) {
    for (const mapping of result.asm_map) {
      let lines = byFile.get(mapping.file);
      if (lines === undefined) {
        lines = new Map();
        byFile.set(mapping.file, lines);
      }
      lines.set(
        mapping.source_line,
        colorClassFor(mapping.file, mapping.source_line),
      );
    }
  }
  for (const [path, model] of models) {
    const oldIds = sourceColorIds.get(path) ?? [];
    const lines = byFile.get(path);
    if (lines === undefined) {
      model.deltaDecorations(oldIds, []);
      sourceColorIds.set(path, []);
      continue;
    }
    const decorations = [...lines.entries()].map(([line, className]) => ({
      range: new monaco.Range(line, 1, line, 1),
      options: { isWholeLine: true, className },
    }));
    sourceColorIds.set(path, model.deltaDecorations(oldIds, decorations));
  }
}

function clearSourceColors(): void {
  applySourceColors(null);
}

function openSource(file: string, line: number): void {
  const path = resolveSourcePath(file);
  if (path === null) {
    asmStatus.textContent = `${sourceName(file)}:${line} (no source tab)`;
    return;
  }
  setActiveSource(path);
  const model = models.get(path)!;
  const target = Math.max(1, Math.min(line, model.getLineCount()));
  editor.setPosition({ lineNumber: target, column: 1 });
  editor.revealLineInCenterIfOutsideViewport(target);
  asmView.updateFromSource(path, target);
}

function hoverSource(file: string | null, line: number | null): void {
  sourceHoverDecorations.clear();
  for (const tab of sourceTabs.querySelectorAll<HTMLElement>(
    ".source-tab.hovered",
  )) {
    tab.classList.remove("hovered");
  }
  if (file === null || line === null) {
    return;
  }
  const path = resolveSourcePath(file);
  if (path === null) {
    asmStatus.textContent = `${sourceName(file)}:${line}`;
    return;
  }
  if (path !== activePath) {
    const tab = sourceTabs.querySelector<HTMLElement>(
      `.source-tab[data-path="${CSS.escape(path)}"]`,
    );
    tab?.classList.add("hovered");
    asmStatus.textContent = `${sourceName(file)}:${line}`;
    return;
  }
  if (!asmFollow.checked) {
    asmStatus.textContent = `${sourceName(file)}:${line}`;
    return;
  }
  const model = models.get(path)!;
  const target = Math.max(1, Math.min(line, model.getLineCount()));
  sourceHoverDecorations.set([
    {
      range: new monaco.Range(target, 1, target, 1),
      options: { isWholeLine: true, className: "source-hover-line" },
    },
  ]);
  asmStatus.textContent = `${sourceName(file)}:${line}`;
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

function renderRegisters(values: number[], animate: boolean): void {
  for (const row of registerRows) {
    const index = Number(row.dataset.reg ?? 0);
    const value = values[index] ?? 0;
    const bits = row.querySelectorAll<HTMLElement>(".reg-bits i");
    for (let bit = 0; bit < 4; bit += 1) {
      bits[bit]?.classList.toggle(
        "on",
        ((value >> (3 - bit)) & 1) !== 0,
      );
    }
    const hex = row.querySelector<HTMLElement>(".reg-hex");
    const dec = row.querySelector<HTMLElement>(".reg-dec");
    if (hex !== null) {
      hex.textContent = `0x${value.toString(16).toUpperCase()}`;
    }
    if (dec !== null) {
      dec.textContent = String(value);
    }
    if (animate && previousRegisters[index] !== value) {
      row.classList.remove("changed");
      void row.offsetWidth;
      row.classList.add("changed");
      window.setTimeout(() => row.classList.remove("changed"), 500);
    }
  }
  previousRegisters = values.slice(0, 10);
}

function clearRegisters(): void {
  previousRegisters = [];
  renderRegisters(Array(10).fill(0), false);
}

function resetStatus(): void {
  emuPc.textContent = "0x000";
  emuSp.textContent = "0";
  emuFlags.textContent = "C0 Z0 V0";
  emuInstr.textContent = "0";
  emuCycles.textContent = "0";
  emuClock.textContent = "250000 Hz";
  emuAlt.textContent = "0";
  emuKey.textContent = "—";
}

function renderEmulator(state: EmulatorState): void {
  emulatorState = state;
  renderMatrix(state.display_left, state.display_right);
  renderRegisters(state.registers.slice(0, 10), true);
  emuPc.textContent = `0x${state.pc.toString(16).padStart(3, "0")}`;
  emuSp.textContent = String(state.sp);
  emuFlags.textContent =
    `C${state.C ? 1 : 0} Z${state.Z ? 1 : 0} V${state.V ? 1 : 0}`;
  emuInstr.textContent = String(state.instructions);
  emuCycles.textContent = String(state.cycles);
  emuClock.textContent = `${state.clock_hz} Hz`;
  emuAlt.textContent = state.alt_down ? "1" : "0";
  emuKey.textContent = state.last_key === null ? "—" : String(state.last_key);
  emuState.textContent = state.halted
    ? "halted"
    : emulatorRunning
      ? "running"
      : "ready";
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
    clearRegisters();
    resetStatus();
    setEmulatorControls(false);
    return;
  }

  setEmulatorControls(false);
  emuState.textContent = "loading";
  clearRegisters();
  resetStatus();
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
    clearRegisters();
    resetStatus();
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

function clearMarkers(): void {
  for (const model of models.values()) {
    monaco.editor.setModelMarkers(model, "niblick", []);
  }
}

function setMarkers(result: CompileResult): void {
  clearMarkers();
  if (result.ok) {
    return;
  }
  const byModel = new Map<
    monaco.editor.ITextModel,
    monaco.editor.IMarkerData[]
  >();
  for (const diagnostic of result.diagnostics) {
    const resolved =
      diagnostic.file === ""
        ? entryPath
        : resolveSourcePath(diagnostic.file);
    const model =
      (resolved === null ? undefined : models.get(resolved)) ??
      models.get(entryPath);
    if (model === undefined) {
      continue;
    }
    const markers = byModel.get(model) ?? [];
    markers.push({
      severity: diagnostic.severity.toLowerCase().startsWith("warn")
        ? monaco.MarkerSeverity.Warning
        : monaco.MarkerSeverity.Error,
      message: diagnostic.message,
      startLineNumber: Math.max(1, diagnostic.line),
      startColumn: Math.max(1, diagnostic.column),
      endLineNumber: Math.max(1, diagnostic.line),
      endColumn: Math.max(1, diagnostic.column) + 1,
    });
    byModel.set(model, markers);
  }
  for (const [model, markers] of byModel) {
    monaco.editor.setModelMarkers(model, "niblick", markers);
  }
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
    asmView.clear();
    clearSourceColors();
    hexDump.textContent = "";
    hexInfo.textContent = "";
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

  asmView.setResult(result);
  updateSourceModels(result);
  const bytes = hexBytes(result);
  hexDump.textContent = formatHexdump(bytes);
  hexInfo.textContent = `${bytes.length} bytes / ${result.words} words`;
  compileStatus.textContent = `${result.words} words, ${result.ram} RAM nibbles, ${Math.round(result.compileMs ?? 0)} ms`;
  sizeStatus.textContent = `${result.words} / 4096 words, ${result.ram} / 208 RAM nibbles`;
  setProblems([]);
  setMarkers(result);
  downloadButton.disabled = false;
  updateFlashAvailability();
  asmView.updateFromSource(
    activePath,
    editor.getPosition()?.lineNumber ?? 1,
  );
  void loadEmulator();
}

async function compile(): Promise<void> {
  if (!runtime.ready) {
    return;
  }
  const model = models.get(entryPath);
  if (model === undefined) {
    compileStatus.textContent = "no entry";
    compileButton.disabled = true;
    return;
  }
  compileButton.disabled = true;
  compileStatus.textContent = "compiling";
  emulatorRunning = false;
  emuRun.textContent = "Run";
  const started = performance.now();
  try {
    const result = await runtime.compile(
      model.getValue(),
      entryPath,
      projectOverrides(),
    );
    showResult(result);
    timingStatus.textContent = `compile ${Math.round(performance.now() - started)} ms`;
  } catch (error) {
    const message = error instanceof Error ? error.message : String(error);
    compileStatus.textContent = "compile failed";
    setProblems([message]);
    timingStatus.textContent = "";
  } finally {
    compileButton.disabled = !runtime.ready || !models.has(entryPath);
  }
}

type DialogValues = { name: string; path: string };

type DialogConfig = {
  title: string;
  description: string;
  confirm: string;
  name?: { value: string; placeholder?: string };
  path?: { value: string; placeholder?: string };
  hideCancel?: boolean;
  validate?: (values: DialogValues) => string | null;
};

let dialogResolve: ((values: DialogValues | null) => void) | null = null;
let dialogValidate: ((values: DialogValues) => string | null) | null = null;

function openProjectDialog(
  config: DialogConfig,
): Promise<DialogValues | null> {
  if (projectDialog.open) {
    projectDialog.close("cancel");
  }
  projectDialogTitle.textContent = config.title;
  projectDialogDescription.textContent = config.description;
  projectDialogError.textContent = "";
  projectDialogConfirm.textContent = config.confirm;
  projectDialogCancel.hidden = config.hideCancel ?? false;
  projectNameLabel.classList.toggle("hidden", config.name === undefined);
  projectPathLabel.classList.toggle("hidden", config.path === undefined);
  projectNameInput.value = config.name?.value ?? "";
  projectNameInput.placeholder = config.name?.placeholder ?? "";
  projectPathInput.value = config.path?.value ?? "";
  projectPathInput.placeholder = config.path?.placeholder ?? "";
  dialogValidate = config.validate ?? null;
  projectDialog.returnValue = "";
  const promise = new Promise<DialogValues | null>((resolve) => {
    dialogResolve = resolve;
  });
  projectDialog.showModal();
  const focus =
    config.name !== undefined
      ? projectNameInput
      : config.path !== undefined
        ? projectPathInput
        : projectDialogConfirm;
  window.setTimeout(() => {
    focus.focus();
    if ("select" in focus) {
      focus.select();
    }
  }, 0);
  return promise;
}

async function showMessageDialog(
  title: string,
  description: string,
): Promise<void> {
  await openProjectDialog({
    title,
    description,
    confirm: "Close",
    hideCancel: true,
  });
}

async function confirmReplace(description: string): Promise<boolean> {
  const values = await openProjectDialog({
    title: "Replace project?",
    description,
    confirm: "Replace",
  });
  return values !== null;
}

function resetCompileOutput(): void {
  lastResult = null;
  asmView.clear();
  clearSourceColors();
  hexDump.textContent = "";
  hexInfo.textContent = "";
  compileStatus.textContent = "not compiled";
  sizeStatus.textContent = "";
  downloadButton.disabled = true;
  setProblems([]);
  clearMarkers();
  updateFlashAvailability();
  void loadEmulator();
}

function validateProjectSnapshot(snapshot: ProjectSnapshot): void {
  if (!snapshot.entry.toLowerCase().endsWith(".nbl")) {
    throw new Error("A project needs a .nbl entry file.");
  }
  if (!(snapshot.entry in snapshot.files)) {
    throw new Error("The project entry file is missing.");
  }
  for (const [path, text] of Object.entries(snapshot.files)) {
    validateSourcePath(path);
    if (typeof text !== "string") {
      throw new Error(`Invalid content for ${path}.`);
    }
  }
}

async function replaceProject(
  snapshot: ProjectSnapshot,
  root: string,
): Promise<void> {
  validateProjectSnapshot(snapshot);
  if (saveTimer !== null) {
    window.clearTimeout(saveTimer);
    saveTimer = null;
  }
  suppressSave = true;
  try {
    editor.setModel(null);
    for (const model of models.values()) {
      model.dispose();
    }
    models.clear();
    projectFiles.clear();
    trackedModels.clear();
    viewStates.clear();
    sourceColorIds.clear();
    sourceHoverDecorations.clear();

    projectRoot = root;
    projectName = snapshot.name.trim() || "untitled";
    entryPath = joinProjectPath(root, snapshot.entry);
    for (const [relative, text] of Object.entries(snapshot.files)) {
      const path = joinProjectPath(root, relative);
      const model = monaco.editor.createModel(
        text,
        languageForPath(path),
        monaco.Uri.file(path),
      );
      models.set(path, model);
      trackProjectModel(path, model);
    }
    activePath =
      snapshot.active === ""
        ? entryPath
        : joinProjectPath(root, snapshot.active);
    if (!models.has(activePath)) {
      activePath = entryPath;
    }
    const activeModel = models.get(activePath);
    if (activeModel === undefined) {
      throw new Error("The project entry model could not be created.");
    }
    editor.setModel(activeModel);
    editor.updateOptions({ readOnly: false });
    projectDirty = false;
    renderSourceTabs();
    resetCompileOutput();
  } finally {
    suppressSave = false;
  }
  persistProject();
  await compile();
}

function fileTemplate(relative: string): string {
  return relative.toLowerCase().endsWith(".asm")
    ? NEW_ASM_SOURCE
    : `// ${relative}\n`;
}

async function newProject(): Promise<void> {
  const values = await openProjectDialog({
    title: "New project",
    description:
      "Creates a fresh project and replaces the current files. Export first if you need a copy.",
    confirm: "Create",
    name: { value: "untitled" },
    path: { value: "main.nbl", placeholder: "main.nbl" },
    validate: ({ name, path }) => {
      if (name.trim() === "") {
        return "Enter a project name.";
      }
      try {
        const entry = validateSourcePath(path);
        if (!entry.toLowerCase().endsWith(".nbl")) {
          return "The entry file must use the .nbl extension.";
        }
      } catch (error) {
        return error instanceof Error ? error.message : String(error);
      }
      return null;
    },
  });
  if (values === null) {
    return;
  }
  const entry = validateSourcePath(values.path);
  const snapshot: ProjectSnapshot = {
    name: values.name.trim(),
    entry,
    active: entry,
    files: { [entry]: NEW_PROJECT_SOURCE },
  };
  exampleSelect.value = "";
  lastExamplePath = "";
  await replaceProject(snapshot, "/work/project");
  setProjectStatus("new project created");
}

async function addProjectFile(): Promise<void> {
  const values = await openProjectDialog({
    title: "Add file",
    description: "Add a Niblick source or an imported assembly module.",
    confirm: "Add",
    path: { value: "", placeholder: "src/input.nbl or drivers/display.asm" },
    validate: ({ path }) => {
      try {
        const relative = validateSourcePath(path);
        if (models.has(joinProjectPath(projectRoot, relative))) {
          return "That file already exists.";
        }
      } catch (error) {
        return error instanceof Error ? error.message : String(error);
      }
      return null;
    },
  });
  if (values === null) {
    return;
  }
  const relative = validateSourcePath(values.path);
  const path = joinProjectPath(projectRoot, relative);
  const model = monaco.editor.createModel(
    fileTemplate(relative),
    languageForPath(path),
    monaco.Uri.file(path),
  );
  models.set(path, model);
  trackProjectModel(path, model);
  activePath = path;
  editor.setModel(model);
  editor.updateOptions({ readOnly: false });
  sourceHoverDecorations.clear();
  markDirty();
  persistProject();
  renderSourceTabs();
  setProjectStatus(`added ${relative}`);
  asmView.updateFromSource(activePath, 1);
  editor.focus();
}

async function renameActiveFile(): Promise<void> {
  if (!projectFiles.has(activePath)) {
    return;
  }
  const oldRelative = relativeProjectPath(projectRoot, activePath);
  if (oldRelative === null) {
    return;
  }
  const oldPath = activePath;
  const values = await openProjectDialog({
    title: "Rename file",
    description:
      "The entry path is updated automatically. Import statements are not rewritten.",
    confirm: "Rename",
    path: { value: oldRelative },
    validate: ({ path }) => {
      try {
        const relative = validateSourcePath(path);
        const next = joinProjectPath(projectRoot, relative);
        if (next !== oldPath && models.has(next)) {
          return "That file already exists.";
        }
      } catch (error) {
        return error instanceof Error ? error.message : String(error);
      }
      return null;
    },
  });
  if (values === null) {
    return;
  }
  const newRelative = validateSourcePath(values.path);
  const newPath = joinProjectPath(projectRoot, newRelative);
  if (newPath === oldPath) {
    return;
  }
  const oldModel = models.get(oldPath);
  if (oldModel === undefined) {
    return;
  }
  const viewState = editor.saveViewState();
  const model = monaco.editor.createModel(
    oldModel.getValue(),
    languageForPath(newPath),
    monaco.Uri.file(newPath),
  );
  models.delete(oldPath);
  projectFiles.delete(oldPath);
  trackedModels.delete(oldPath);
  viewStates.delete(oldPath);
  sourceColorIds.delete(oldPath);
  models.set(newPath, model);
  trackProjectModel(newPath, model);
  if (entryPath === oldPath) {
    entryPath = newPath;
  }
  activePath = newPath;
  editor.setModel(model);
  editor.updateOptions({ readOnly: false });
  if (viewState !== null) {
    editor.restoreViewState(viewState);
  }
  sourceHoverDecorations.clear();
  oldModel.dispose();
  markDirty();
  persistProject();
  renderSourceTabs();
  setProjectStatus(`renamed to ${newRelative}`);
  void compile();
}

function chooseEntry(exclude: string): string {
  const candidates = Array.from(projectFiles)
    .filter(
      (path) =>
        path !== exclude && path.toLowerCase().endsWith(".nbl"),
    )
    .sort((left, right) => {
      const main = joinProjectPath(projectRoot, "main.nbl");
      if (left === main) {
        return -1;
      }
      if (right === main) {
        return 1;
      }
      return sourceName(left).localeCompare(sourceName(right));
    });
  return candidates[0] ?? "";
}

async function deleteActiveFile(): Promise<void> {
  if (!projectFiles.has(activePath)) {
    return;
  }
  const path = activePath;
  const relative = relativeProjectPath(projectRoot, path) ?? sourceName(path);
  const deletingEntry = path === entryPath;
  const nextEntry = deletingEntry ? chooseEntry(path) : entryPath;
  if (deletingEntry && nextEntry === "") {
    await showMessageDialog(
      "Cannot delete entry",
      "A project needs at least one .nbl entry file.",
    );
    return;
  }
  const values = await openProjectDialog({
    title: "Delete file?",
    description: `${relative} will be removed from the project.`,
    confirm: "Delete",
  });
  if (values === null) {
    return;
  }
  entryPath = nextEntry;
  disposeModel(path);
  if (!models.has(activePath)) {
    activePath = entryPath;
    const model = models.get(entryPath);
    if (model !== undefined) {
      editor.setModel(model);
      editor.updateOptions({ readOnly: false });
    }
  }
  renderSourceTabs();
  markDirty();
  persistProject();
  setProjectStatus(`deleted ${relative}`);
  await compile();
}

function setActiveAsEntry(): void {
  if (
    !projectFiles.has(activePath) ||
    !activePath.toLowerCase().endsWith(".nbl")
  ) {
    return;
  }
  entryPath = activePath;
  markDirty();
  persistProject();
  renderSourceTabs();
  setProjectStatus(`entry set to ${sourceName(activePath)}`);
  void compile();
}

async function importProjectZip(file: File): Promise<void> {
  try {
    const data = new Uint8Array(await file.arrayBuffer());
    const snapshot = readProjectZip(
      data,
      file.name.replace(/\.zip$/i, ""),
    );
    if (
      projectDirty &&
      !(await confirmReplace(
        "Importing this zip replaces the current project. Export it first if you need a copy.",
      ))
    ) {
      return;
    }
    exampleSelect.value = "";
    lastExamplePath = "";
    await replaceProject(snapshot, "/work/project");
    setProjectStatus(
      `imported ${Object.keys(snapshot.files).length} files`,
    );
  } catch (error) {
    const message = error instanceof Error ? error.message : String(error);
    await showMessageDialog("Import failed", message);
  }
}

function exportProject(): void {
  try {
    const snapshot = projectSnapshot();
    const bytes = buildProjectZip(snapshot);
    const buffer = new ArrayBuffer(bytes.byteLength);
    new Uint8Array(buffer).set(bytes);
    const blob = new Blob([buffer], { type: "application/zip" });
    const url = URL.createObjectURL(blob);
    const anchor = document.createElement("a");
    anchor.href = url;
    anchor.download = projectDownloadName(snapshot.name);
    anchor.click();
    URL.revokeObjectURL(url);
    projectDirty = false;
    setProjectStatus(
      `exported ${Object.keys(snapshot.files).length} files`,
    );
  } catch (error) {
    const message = error instanceof Error ? error.message : String(error);
    setProjectStatus(`export failed: ${message}`, true);
  }
}

async function loadExample(path: string): Promise<void> {
  try {
    if (
      projectDirty &&
      !(await confirmReplace(
        `Loading ${path} replaces the current project.`,
      ))
    ) {
      exampleSelect.value = lastExamplePath;
      return;
    }
    const source = await runtime.loadExample(path);
    const snapshot: ProjectSnapshot = {
      name: path.replace(/\.nbl$/i, ""),
      entry: path,
      active: path,
      files: { [path]: source },
    };
    await replaceProject(snapshot, "/work/examples");
    exampleSelect.value = path;
    lastExamplePath = path;
  } catch (error) {
    const message = error instanceof Error ? error.message : String(error);
    setProblems([message]);
    exampleSelect.value = lastExamplePath;
  }
}

async function boot(): Promise<void> {
  try {
    await runtime.init((message) => {
      loadingMessage.textContent = message;
      runtimeStatus.textContent = "loading";
    });
    loading.classList.add("hidden");
    runtimeStatus.textContent = "ready";
    compileButton.disabled = false;

    const examples = await runtime.listExamples();
    exampleSelect.replaceChildren();
    const placeholder = document.createElement("option");
    placeholder.value = "";
    placeholder.textContent = "Load example…";
    placeholder.disabled = true;
    exampleSelect.append(placeholder);
    for (const item of examples) {
      const option = document.createElement("option");
      option.value = item.path;
      option.textContent = item.name;
      exampleSelect.append(option);
    }

    const stored = loadStoredProject();
    if (stored !== null) {
      try {
        exampleSelect.value = "";
        lastExamplePath = "";
        await replaceProject(stored, "/work/project");
        setProjectStatus("restored saved project");
      } catch {
        clearStoredProject();
        const hello = examples.find((item) => item.name === "hello");
        if (hello !== undefined) {
          await loadExample(hello.path);
        } else {
          await compile();
        }
      }
    } else {
      const hello = examples.find((item) => item.name === "hello");
      if (hello !== undefined) {
        await loadExample(hello.path);
      } else {
        await compile();
      }
    }
  } catch (error) {
    const message = error instanceof Error ? error.message : String(error);
    loadingMessage.textContent = message;
    runtimeStatus.textContent = "runtime error";
    setProblems([message]);
    console.error(error);
  }
}

editor.onDidChangeCursorPosition((event) => {
  asmView.updateFromSource(activePath, event.position.lineNumber);
});

editor.onMouseDown((event) => {
  const line = event.target.position?.lineNumber;
  if (line !== undefined) {
    asmView.revealSource(activePath, line);
  }
});

editor.onMouseMove((event) => {
  const line = event.target.position?.lineNumber;
  if (line !== undefined) {
    asmView.updateHoverFromSource(activePath, line);
  }
});

editor.onMouseLeave(() => {
  asmView.clearHover();
});

asmFollow.addEventListener("change", () => {
  asmView.setFollow(asmFollow.checked);
  if (!asmFollow.checked) {
    sourceHoverDecorations.clear();
  }
});

asmColor.addEventListener("change", () => {
  asmView.setColorEnabled(asmColor.checked);
  sourceColorEnabled = asmColor.checked;
  applySourceColors(lastResult);
});

hexCopy.addEventListener("click", async () => {
  const text = hexDump.textContent ?? "";
  if (text.length === 0) {
    return;
  }
  try {
    await navigator.clipboard.writeText(text);
    hexCopy.textContent = "Copied";
    window.setTimeout(() => {
      hexCopy.textContent = "Copy hexdump";
    }, 1000);
  } catch {
    hexCopy.textContent = "Copy failed";
    window.setTimeout(() => {
      hexCopy.textContent = "Copy hexdump";
    }, 1000);
  }
});

asmView.setFollow(asmFollow.checked);
asmView.setColorEnabled(asmColor.checked);
sourceColorEnabled = asmColor.checked;

window.addEventListener("resize", () => {
  editor.layout();
  asmView.layout();
});

window.addEventListener("beforeunload", () => {
  persistProject();
});
renderSourceTabs();

monaco.editor.registerEditorOpener({
  openCodeEditor(_source, resource, selectionOrPosition) {
    const path = resolveSourcePath(resource.path);
    if (path === null) {
      return false;
    }
    setActiveSource(path);
    const model = models.get(path);
    if (model === undefined) {
      return false;
    }
    let line = 1;
    if (selectionOrPosition !== undefined) {
      line =
        "startLineNumber" in selectionOrPosition
          ? selectionOrPosition.startLineNumber
          : selectionOrPosition.lineNumber;
    }
    const target = Math.max(1, Math.min(line, model.getLineCount()));
    editor.setPosition({ lineNumber: target, column: 1 });
    editor.revealLineInCenterIfOutsideViewport(target);
    asmView.updateFromSource(path, target);
    return true;
  },
});

compileButton.addEventListener("click", () => {
  void compile();
});

projectForm.addEventListener("submit", (event) => {
  event.preventDefault();
  const values = {
    name: projectNameInput.value.trim(),
    path: projectPathInput.value.trim(),
  };
  const error = dialogValidate?.(values) ?? null;
  if (error !== null) {
    projectDialogError.textContent = error;
    return;
  }
  projectDialog.close("confirm");
});

projectDialogCancel.addEventListener("click", () => {
  projectDialog.close("cancel");
});

for (const input of [projectNameInput, projectPathInput]) {
  input.addEventListener("input", () => {
    projectDialogError.textContent = "";
  });
}

projectDialog.addEventListener("close", () => {
  const confirmed = projectDialog.returnValue === "confirm";
  const values = confirmed
    ? {
        name: projectNameInput.value.trim(),
        path: projectPathInput.value.trim(),
      }
    : null;
  const resolve = dialogResolve;
  dialogResolve = null;
  dialogValidate = null;
  resolve?.(values);
});

function closeProjectMenu(): void {
  projectMenu.classList.add("hidden");
  projectMenuButton.setAttribute("aria-expanded", "false");
}

function toggleProjectMenu(): void {
  const opening = projectMenu.classList.contains("hidden");
  if (opening) {
    updateProjectMenu();
    projectMenu.classList.remove("hidden");
    projectMenuButton.setAttribute("aria-expanded", "true");
  } else {
    closeProjectMenu();
  }
}

projectMenuButton.addEventListener("click", (event) => {
  event.stopPropagation();
  toggleProjectMenu();
});

projectAdd.addEventListener("click", () => {
  closeProjectMenu();
  void addProjectFile();
});

projectMenu.addEventListener("click", (event) => {
  const target = (event.target as HTMLElement).closest<HTMLButtonElement>(
    "[data-project-action]",
  );
  if (target === null || target.disabled) {
    return;
  }
  closeProjectMenu();
  switch (target.dataset.projectAction) {
    case "new":
      void newProject();
      break;
    case "add":
      void addProjectFile();
      break;
    case "rename":
      void renameActiveFile();
      break;
    case "delete":
      void deleteActiveFile();
      break;
    case "entry":
      setActiveAsEntry();
      break;
    case "import":
      projectImport.click();
      break;
    case "export":
      exportProject();
      break;
  }
});

document.addEventListener("click", (event) => {
  if (
    !projectMenu.contains(event.target as Node) &&
    event.target !== projectMenuButton
  ) {
    closeProjectMenu();
  }
});

document.addEventListener("keydown", (event) => {
  if (event.key === "Escape") {
    closeProjectMenu();
  }
});

projectImport.addEventListener("change", () => {
  const file = projectImport.files?.[0];
  projectImport.value = "";
  if (file !== undefined) {
    void importProjectZip(file);
  }
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
  emuState.textContent = emulatorRunning ? "running" : "ready";
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

function wireMomentary(
  button: HTMLButtonElement,
  set: (down: boolean) => Promise<void>,
): void {
  let queue: Promise<void> = Promise.resolve();
  const enqueue = (down: boolean): void => {
    queue = queue.then(() => set(down));
  };
  const setPressed = (pressed: boolean): void => {
    button.classList.toggle("pressed", pressed);
  };
  button.addEventListener("pointerdown", (event) => {
    event.preventDefault();
    setPressed(true);
    enqueue(true);
  });
  button.addEventListener("pointerup", () => {
    setPressed(false);
    enqueue(false);
  });
  button.addEventListener("pointerleave", () => {
    setPressed(false);
    enqueue(false);
  });
  button.addEventListener("pointercancel", () => {
    setPressed(false);
    enqueue(false);
  });
  button.addEventListener("click", (event) => {
    if (event.detail !== 0) {
      return;
    }
    setPressed(true);
    enqueue(true);
    enqueue(false);
    window.setTimeout(() => setPressed(false), 120);
  });
}

for (const button of document.querySelectorAll<HTMLButtonElement>(
  "#tab-emulator [data-key]",
)) {
  const key = Number(button.dataset.key);
  wireMomentary(button, (down) => sendKey(key, down));
}

for (const button of document.querySelectorAll<HTMLButtonElement>(
  "#tab-emulator [data-alt]",
)) {
  wireMomentary(button, (down) => sendAlt(down));
}

emuUartClear.addEventListener("click", () => {
  emuUart.textContent = "";
});

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
