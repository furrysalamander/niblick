import * as monaco from "monaco-editor/editor/editor.api";
import type { AsmMapping, CompileResult } from "./runtime";
import { colorClassFor } from "./colors";

export type AsmViewCallbacks = {
  openSource: (file: string, line: number) => void;
  hoverSource: (file: string | null, line: number | null) => void;
  status: (text: string) => void;
};

function displayPath(path: string): string {
  const examples = path.indexOf("/examples/");
  if (examples >= 0) {
    return path.slice(examples + "/examples/".length);
  }
  const work = path.indexOf("/work/");
  if (work >= 0) {
    return path.slice(work + "/work/".length);
  }
  const parts = path.split("/");
  return parts.slice(Math.max(0, parts.length - 2)).join("/");
}

export class AsmView {
  private editor: monaco.editor.IStandaloneCodeEditor;
  private callbacks: AsmViewCallbacks;
  private byAsm = new Map<number, AsmMapping>();
  private bySource = new Map<string, Map<number, number[]>>();
  private colorDecorations: monaco.editor.IEditorDecorationsCollection;
  private cursorDecorations: monaco.editor.IEditorDecorationsCollection;
  private hoverDecorations: monaco.editor.IEditorDecorationsCollection;
  private colorEnabled = true;
  private follow = true;

  constructor(
    container: HTMLElement,
    callbacks: AsmViewCallbacks,
  ) {
    this.callbacks = callbacks;
    this.editor = monaco.editor.create(container, {
      value: "",
      language: "voja4-asm",
      theme: "vs-dark",
      readOnly: true,
      automaticLayout: false,
      fontSize: 12,
      minimap: { enabled: false },
      scrollBeyondLastLine: false,
      renderLineHighlight: "none",
      lineNumbers: "on",
    });
    this.colorDecorations = this.editor.createDecorationsCollection([]);
    this.cursorDecorations = this.editor.createDecorationsCollection([]);
    this.hoverDecorations = this.editor.createDecorationsCollection([]);

    this.editor.onMouseMove((event) => {
      const line = event.target.position?.lineNumber;
      if (line === undefined) {
        return;
      }
      const mapping = this.byAsm.get(line);
      if (mapping === undefined) {
        this.callbacks.hoverSource(null, null);
        this.callbacks.status("");
        return;
      }
      this.callbacks.hoverSource(mapping.file, mapping.source_line);
      this.callbacks.status(
        `${displayPath(mapping.file)}:${mapping.source_line}`,
      );
    });

    this.editor.onMouseLeave(() => {
      this.callbacks.hoverSource(null, null);
      this.callbacks.status("");
    });

    this.editor.onMouseDown((event) => {
      const line = event.target.position?.lineNumber;
      if (line === undefined) {
        return;
      }
      const mapping = this.byAsm.get(line);
      if (mapping !== undefined) {
        this.callbacks.openSource(mapping.file, mapping.source_line);
      }
    });
  }

  clear(): void {
    this.editor.setValue("");
    this.byAsm.clear();
    this.bySource.clear();
    this.colorDecorations.set([]);
    this.cursorDecorations.set([]);
    this.hoverDecorations.set([]);
  }

  setResult(result: CompileResult): void {
    this.editor.setValue(result.asm);
    this.byAsm.clear();
    this.bySource.clear();
    for (const mapping of result.asm_map) {
      this.byAsm.set(mapping.line, mapping);
      let lines = this.bySource.get(mapping.file);
      if (lines === undefined) {
        lines = new Map();
        this.bySource.set(mapping.file, lines);
      }
      const group = lines.get(mapping.source_line);
      if (group === undefined) {
        lines.set(mapping.source_line, [mapping.line]);
      } else {
        group.push(mapping.line);
      }
    }
    this.applyColorDecorations();
  }

  setColorEnabled(enabled: boolean): void {
    this.colorEnabled = enabled;
    this.applyColorDecorations();
  }

  setFollow(enabled: boolean): void {
    this.follow = enabled;
  }

  layout(): void {
    this.editor.layout();
  }

  updateFromSource(file: string, line: number, reveal: boolean): void {
    const lines = this.linesFor(file, line);
    this.cursorDecorations.set(this.decorationsFor(lines, "asm-cursor-line"));
    if (lines.length > 0) {
      this.callbacks.status(`${displayPath(file)}:${line}`);
      if (reveal && this.follow) {
        this.editor.revealLineInCenterIfOutsideViewport(lines[0]);
      }
    } else {
      this.callbacks.status("");
    }
  }

  updateHoverFromSource(file: string, line: number): void {
    const lines = this.linesFor(file, line);
    this.hoverDecorations.set(this.decorationsFor(lines, "asm-hover-line"));
    if (lines.length > 0) {
      this.callbacks.status(`${displayPath(file)}:${line}`);
      if (this.follow) {
        this.editor.revealLineInCenterIfOutsideViewport(lines[0]);
      }
    }
  }

  clearHover(): void {
    this.hoverDecorations.set([]);
  }

  private linesFor(file: string, line: number): number[] {
    return this.bySource.get(file)?.get(line) ?? [];
  }

  private decorationsFor(
    lines: number[],
    className: string,
  ): monaco.editor.IModelDeltaDecoration[] {
    return lines.map((line) => ({
      range: new monaco.Range(line, 1, line, 1),
      options: {
        isWholeLine: true,
        className,
        overviewRuler: {
          color: "#d8a657",
          position: monaco.editor.OverviewRulerLane.Center,
        },
      },
    }));
  }

  private applyColorDecorations(): void {
    if (!this.colorEnabled) {
      this.colorDecorations.set([]);
      return;
    }
    const mappings = [...this.byAsm.values()].sort((a, b) => a.line - b.line);
    const ranges: Array<{
      start: number;
      end: number;
      file: string;
      line: number;
    }> = [];
    for (const mapping of mappings) {
      const last = ranges[ranges.length - 1];
      if (
        last !== undefined &&
        last.file === mapping.file &&
        last.line === mapping.source_line &&
        mapping.line === last.end + 1
      ) {
        last.end = mapping.line;
      } else {
        ranges.push({
          start: mapping.line,
          end: mapping.line,
          file: mapping.file,
          line: mapping.source_line,
        });
      }
    }
    this.colorDecorations.set(
      ranges.map((range) => ({
        range: new monaco.Range(range.start, 1, range.end, 1),
        options: {
          isWholeLine: true,
          className: colorClassFor(range.file, range.line),
        },
      })),
    );
  }

}
