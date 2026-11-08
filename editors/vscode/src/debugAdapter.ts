import { spawn, spawnSync, ChildProcessWithoutNullStreams } from "child_process";
import * as fs from "fs";
import * as os from "os";
import * as path from "path";
import {
  Breakpoint,
  DebugSession,
  InitializedEvent,
  OutputEvent,
  Scope,
  Source,
  StackFrame,
  StoppedEvent,
  TerminatedEvent,
  Thread,
  Variable,
} from "@vscode/debugadapter";

interface LaunchArguments {
  program: string;
  hex?: string;
  debugMap?: string;
  stopOnEntry?: boolean;
  pythonPath?: string;
  cwd?: string;
}

interface ServiceResponse {
  id?: number;
  ok?: boolean;
  result?: any;
  error?: string;
}

function pythonExecutable(cwd: string, configured?: string): string {
  if (configured && configured.trim().length > 0) {
    return configured;
  }
  const candidates = [
    path.join(cwd, ".venv", "bin", "python"),
    path.join(cwd, "venv", "bin", "python"),
    path.join(cwd, ".venv", "Scripts", "python.exe"),
    path.join(cwd, "venv", "Scripts", "python.exe"),
  ];
  for (const candidate of candidates) {
    if (fs.existsSync(candidate)) {
      return candidate;
    }
  }
  return "python3";
}

function pythonEnvironment(cwd: string): NodeJS.ProcessEnv {
  const env: NodeJS.ProcessEnv = { ...process.env };
  env.PYTHONPATH = [cwd, env.PYTHONPATH].filter(Boolean).join(path.delimiter);
  return env;
}

function runAndCollect(
  command: string,
  args: string[],
  options: { cwd: string; env: NodeJS.ProcessEnv },
): { code: number | null; output: string } {
  const result = spawnSync(command, args, {
    cwd: options.cwd,
    env: options.env,
    encoding: "utf8",
  });
  return {
    code: result.status,
    output: `${result.stdout ?? ""}${result.stderr ?? ""}`,
  };
}

class BadgeCDebugSession extends DebugSession {
  private service?: ChildProcessWithoutNullStreams;
  private nextId = 1;
  private pending = new Map<
    number,
    { resolve: (value: any) => void; reject: (error: Error) => void }
  >();
  private buffer = "";
  private breakpoints: Array<{ file: string; line: number }> = [];
  private running = false;
  private pauseRequested = false;
  private temporaryDir?: string;
  private lastState: any;
  private stopOnEntry = true;

  protected initializeRequest(response: any, args: any): void {
    response.body = response.body || {};
    response.body.supportsConfigurationDoneRequest = true;
    response.body.supportsEvaluateForHovers = true;
    response.body.supportsStepBack = false;
    this.sendResponse(response);
  }

  protected async launchRequest(response: any, args: any): Promise<void> {
    try {
      const launch = args as LaunchArguments;
      const cwd = launch.cwd || process.cwd();
      this.stopOnEntry = launch.stopOnEntry !== false;
      const python = pythonExecutable(cwd, launch.pythonPath);
      const env = pythonEnvironment(cwd);
      let hexPath = launch.hex;
      let debugMap: any = {};

      if (!hexPath) {
        if (!launch.program) {
          throw new Error("launch requires 'program' or 'hex'");
        }
        this.temporaryDir = fs.mkdtempSync(
          path.join(os.tmpdir(), "badgec-debug-"),
        );
        const mapPath = path.join(this.temporaryDir, "debug.json");
        const result = runAndCollect(
          python,
          [
            "-m",
            "badgec",
            launch.program,
            "-o",
            this.temporaryDir,
            "--debug-map",
            mapPath,
          ],
          { cwd, env },
        );
        if (result.code !== 0) {
          throw new Error(result.output || "BadgeC compilation failed");
        }
        hexPath = path.join(
          this.temporaryDir,
          `${path.basename(launch.program, path.extname(launch.program))}.hex`,
        );
        debugMap = JSON.parse(fs.readFileSync(mapPath, "utf8"));
      } else if (launch.debugMap) {
        debugMap = JSON.parse(fs.readFileSync(launch.debugMap, "utf8"));
      }

      this.service = spawn(python, ["-m", "badgec.debug"], {
        cwd,
        env,
      });
      this.service.stdout.setEncoding("utf8");
      this.service.stdout.on("data", (data) => this.onServiceData(data));
      this.service.stderr.on("data", (data) => {
        this.sendEvent(new OutputEvent(String(data), "stderr"));
      });
      this.service.on("exit", () => {
        for (const pending of this.pending.values()) {
          pending.reject(new Error("debug service exited"));
        }
        this.pending.clear();
      });

      this.lastState = await this.command("load", {
        hex: hexPath,
        map: debugMap,
      });
      this.sendResponse(response);
      this.sendEvent(new InitializedEvent());
    } catch (error) {
      this.sendErrorResponse(
        response,
        1001,
        `BadgeC launch failed: ${String(error)}`,
      );
    }
  }

  protected setBreakPointsRequest(response: any, args: any): void {
    const source = args.source?.path ?? "";
    this.breakpoints = (args.breakpoints ?? []).map((bp: any) => ({
      file: source,
      line: bp.line,
    }));
    this.command("setBreakpoints", { breakpoints: this.breakpoints })
      .then((result) => {
        response.body = {
          breakpoints: (result as any[]).map(
            (item) => new Breakpoint(item.verified, item.line),
          ),
        };
        this.sendResponse(response);
      })
      .catch((error) => {
        this.sendErrorResponse(response, 1002, String(error));
      });
  }

  protected configurationDoneRequest(response: any, args: any): void {
    this.sendResponse(response);
    if (this.stopOnEntry) {
      void this.runLoop("step", { kind: "into" });
    } else {
      void this.runLoop("continue");
    }
  }

  protected continueRequest(response: any, args: any): void {
    this.sendResponse(response);
    void this.runLoop("continue");
  }

  protected nextRequest(response: any, args: any): void {
    this.sendResponse(response);
    void this.runLoop("step", { kind: "over" });
  }

  protected stepInRequest(response: any, args: any): void {
    this.sendResponse(response);
    void this.runLoop("step", { kind: "into" });
  }

  protected stepOutRequest(response: any, args: any): void {
    this.sendResponse(response);
    void this.runLoop("step", { kind: "out" });
  }

  protected pauseRequest(response: any, args: any): void {
    this.pauseRequested = true;
    this.sendResponse(response);
  }

  protected threadsRequest(response: any): void {
    response.body = { threads: [new Thread(1, "BadgeC emulator")] };
    this.sendResponse(response);
  }

  protected stackTraceRequest(response: any, args: any): void {
    this.command("stackTrace", {})
      .then((frames: any[]) => {
        response.body = {
          stackFrames: frames.map((frame, index) => {
            const source = frame.file
              ? new Source(path.basename(frame.file), frame.file)
              : undefined;
            return new StackFrame(
              index + 1,
              frame.name || "frame",
              source,
              frame.line || 1,
              1,
            );
          }),
        };
        this.sendResponse(response);
      })
      .catch((error) => this.sendErrorResponse(response, 1003, String(error)));
  }

  protected scopesRequest(response: any, args: any): void {
    response.body = {
      scopes: [
        new Scope("Registers", 1, false),
        new Scope("Flags", 2, false),
        new Scope("Globals", 3, false),
      ],
    };
    this.sendResponse(response);
  }

  protected variablesRequest(response: any, args: any): void {
    const scope =
      args.variablesReference === 1
        ? "registers"
        : args.variablesReference === 2
          ? "flags"
          : "globals";
    this.command("variables", { scope })
      .then((items: any[]) => {
        response.body = {
          variables: items.map((item) => {
            const value =
              typeof item.value === "number"
                ? `0x${item.value.toString(16)} (${item.value})`
                : String(item.value);
            return new Variable(item.name, value, 0);
          }),
        };
        this.sendResponse(response);
      })
      .catch((error) => this.sendErrorResponse(response, 1004, String(error)));
  }

  protected evaluateRequest(response: any, args: any): void {
    this.command("evaluate", { expression: args.expression })
      .then((result) => {
        response.body = {
          result: String(result.result),
          type: result.type,
          variablesReference: 0,
        };
        this.sendResponse(response);
      })
      .catch((error) => this.sendErrorResponse(response, 1005, String(error)));
  }

  protected disconnectRequest(response: any, args: any): void {
    this.service?.kill();
    this.service = undefined;
    if (this.temporaryDir) {
      fs.rmSync(this.temporaryDir, { recursive: true, force: true });
      this.temporaryDir = undefined;
    }
    this.sendResponse(response);
  }

  private onServiceData(data: string): void {
    this.buffer += data;
    let index = this.buffer.indexOf("\n");
    while (index >= 0) {
      const line = this.buffer.slice(0, index).trim();
      this.buffer = this.buffer.slice(index + 1);
      if (line) {
        this.handleServiceMessage(line);
      }
      index = this.buffer.indexOf("\n");
    }
  }

  private handleServiceMessage(line: string): void {
    try {
      const response = JSON.parse(line) as ServiceResponse;
      if (response.id === undefined) {
        return;
      }
      const pending = this.pending.get(response.id);
      if (!pending) {
        return;
      }
      this.pending.delete(response.id);
      if (response.ok) {
        pending.resolve(response.result);
      } else {
        pending.reject(new Error(response.error || "debug service error"));
      }
    } catch (error) {
      this.sendEvent(new OutputEvent(`Bad debug service message: ${String(error)}\n`, "stderr"));
    }
  }

  private command(command: string, args: any): Promise<any> {
    if (!this.service) {
      return Promise.reject(new Error("debug service is not running"));
    }
    const id = this.nextId++;
    return new Promise((resolve, reject) => {
      this.pending.set(id, { resolve, reject });
      this.service!.stdin.write(
        `${JSON.stringify({ id, command, args })}\n`,
      );
    });
  }

  private async runLoop(kind: "continue" | "step", args?: any): Promise<void> {
    if (this.running) {
      return;
    }
    this.running = true;
    try {
      if (kind === "step") {
        const state = await this.command("step", args);
        this.handleState(state);
        return;
      }

      while (this.running) {
        if (this.pauseRequested) {
          this.pauseRequested = false;
          const state = await this.command("state", {});
          this.handleState({ ...state, reason: "pause" });
          return;
        }
        const state = await this.command("continue", { maxSteps: 50000 });
        if (state.reason === "limit") {
          continue;
        }
        this.handleState(state);
        return;
      }
    } catch (error) {
      this.sendEvent(new OutputEvent(`${String(error)}\n`, "stderr"));
      this.sendEvent(new TerminatedEvent());
    } finally {
      this.running = false;
    }
  }

  private handleState(state: any): void {
    this.lastState = state;
    if (Array.isArray(state.uart) && state.uart.length > 0) {
      this.sendEvent(
        new OutputEvent(Buffer.from(state.uart).toString("utf8"), "stdout"),
      );
    }
    if (state.halted) {
      this.sendEvent(new TerminatedEvent());
      return;
    }
    const event = new StoppedEvent(state.reason || "pause", 1);
    (event.body as any).allThreadsStopped = true;
    this.sendEvent(event);
  }
}

DebugSession.run(BadgeCDebugSession);
