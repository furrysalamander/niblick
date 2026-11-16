import { spawn } from "child_process";
import * as fs from "fs";
import * as path from "path";
import * as vscode from "vscode";
import {
  LanguageClient,
  LanguageClientOptions,
  ServerOptions,
  TransportKind,
} from "vscode-languageclient/node";

let client: LanguageClient | undefined;
let outputChannel: vscode.OutputChannel;

function workspaceRoot(): string {
  return vscode.workspace.workspaceFolders?.[0]?.uri.fsPath ?? process.cwd();
}

function pythonExecutable(): string {
  const config = vscode.workspace.getConfiguration("niblick");
  const configured = config.get<string>("pythonPath", "").trim();
  if (configured.length > 0) {
    return configured;
  }

  const root = workspaceRoot();
  const candidates = [
    path.join(root, ".venv", "bin", "python"),
    path.join(root, "venv", "bin", "python"),
    path.join(root, ".venv", "Scripts", "python.exe"),
    path.join(root, "venv", "Scripts", "python.exe"),
  ];
  for (const candidate of candidates) {
    if (fs.existsSync(candidate)) {
      return candidate;
    }
  }
  return "python3";
}

function pythonEnvironment(): { [key: string]: string | undefined } {
  const includePaths = vscode.workspace
    .getConfiguration("niblick")
    .get<string[]>("includePaths", []);
  const env: { [key: string]: string | undefined } = { ...process.env };
  const root = workspaceRoot();
  env.PYTHONPATH = [root, env.PYTHONPATH].filter(Boolean).join(path.delimiter);
  if (includePaths.length > 0) {
    env.NIBLICK_PATH = includePaths.join(path.delimiter);
  }
  return env;
}

function makeServerOptions(): ServerOptions {
  return {
    command: pythonExecutable(),
    args: ["-m", "niblick.lsp", "--stdio"],
    transport: TransportKind.stdio,
    options: {
      cwd: workspaceRoot(),
      env: pythonEnvironment() as NodeJS.ProcessEnv,
    },
  };
}

function makeClientOptions(): LanguageClientOptions {
  return {
    documentSelector: [
      { scheme: "file", language: "niblick" },
      { scheme: "file", language: "voja4-asm" },
    ],
    synchronize: {
      configurationSection: "niblick",
      fileEvents: vscode.workspace.createFileSystemWatcher("**/*.{nbl,asm}"),
    },
    outputChannel,
    traceOutputChannel: outputChannel,
  };
}

async function startClient(): Promise<void> {
  if (client) {
    try {
      await client.stop();
    } catch {
      // The old server may already have exited.
    }
  }

  client = new LanguageClient(
    "niblick",
    "Niblick Language Server",
    makeServerOptions(),
    makeClientOptions(),
  );

  await client.start();
}

function activeBadgeFile(): string | undefined {
  const editor = vscode.window.activeTextEditor;
  if (!editor || !editor.document.fileName.toLowerCase().endsWith(".nbl")) {
    void vscode.window.showErrorMessage(
      "Open a .nbl file before running this command.",
    );
    return undefined;
  }
  return editor.document.fileName;
}

function runCompilerCommand(label: string, extraArgs: string[]): void {
  const file = activeBadgeFile();
  if (file === undefined) {
    return;
  }
  const outDir = path.join(workspaceRoot(), ".niblick-build");
  const python = pythonExecutable();
  const args = ["-m", "niblick", file, "-o", outDir, ...extraArgs];
  outputChannel.show(true);
  outputChannel.appendLine(`> ${python} ${args.join(" ")}`);

  const child = spawn(python, args, {
    cwd: workspaceRoot(),
    env: pythonEnvironment() as NodeJS.ProcessEnv,
  });
  child.stdout?.on("data", (data) => outputChannel.append(data.toString()));
  child.stderr?.on("data", (data) => outputChannel.append(data.toString()));
  child.on("error", (error) => {
    outputChannel.appendLine(`${label} failed to start: ${String(error)}`);
    void vscode.window.showErrorMessage(`${label} failed to start.`);
  });
  child.on("close", (code) => {
    outputChannel.appendLine(`[${label} exited with code ${code ?? "?"}]`);
    if (code !== 0) {
      void vscode.window.showWarningMessage(
        `${label} failed. See the Niblick output channel.`,
      );
    }
  });
}

async function fixBadgeLanguageMode(
  document: vscode.TextDocument,
): Promise<void> {
  if (
    document.uri.scheme === "file" &&
    document.fileName.toLowerCase().endsWith(".nbl") &&
    document.languageId === "plaintext"
  ) {
    try {
      await vscode.languages.setTextDocumentLanguage(document, "niblick");
    } catch (error) {
      outputChannel.appendLine(
        `Could not switch ${document.fileName} to Niblick: ${String(error)}`,
      );
    }
  }
}

export async function activate(context: vscode.ExtensionContext): Promise<void> {
  outputChannel = vscode.window.createOutputChannel("Niblick");
  context.subscriptions.push(outputChannel);

  for (const document of vscode.workspace.textDocuments) {
    await fixBadgeLanguageMode(document);
  }

  context.subscriptions.push(
    vscode.workspace.onDidOpenTextDocument((document) => {
      void fixBadgeLanguageMode(document);
    }),
  );

  context.subscriptions.push(
    vscode.commands.registerCommand("niblick.compile", () => {
      runCompilerCommand("Niblick compile", []);
    }),
  );

  context.subscriptions.push(
    vscode.commands.registerCommand("niblick.run", () => {
      runCompilerCommand("Niblick run", ["--run"]);
    }),
  );

  context.subscriptions.push(
    vscode.commands.registerCommand("niblick.restartServer", async () => {
      outputChannel.appendLine("Restarting Niblick language server...");
      try {
        await startClient();
        outputChannel.appendLine("Niblick language server restarted.");
      } catch (error) {
        outputChannel.appendLine(`Restart failed: ${String(error)}`);
      }
    }),
  );

  context.subscriptions.push(
    vscode.workspace.onDidChangeConfiguration(async (event) => {
      if (event.affectsConfiguration("niblick")) {
        try {
          await startClient();
        } catch (error) {
          outputChannel.appendLine(`Restart failed: ${String(error)}`);
        }
      }
    }),
  );

  try {
    await startClient();
  } catch (error) {
    const message =
      "Niblick language server failed to start. " +
      "Install the Python extra with `pip install -e \".[lsp]\"` " +
      "or set `niblick.pythonPath` to the right interpreter.";
    outputChannel.appendLine(message);
    outputChannel.appendLine(String(error));
    void vscode.window.showErrorMessage(message);
  }
}

export async function deactivate(): Promise<void> {
  if (client) {
    await client.stop();
    client = undefined;
  }
}
