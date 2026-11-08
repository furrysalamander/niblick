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
  const config = vscode.workspace.getConfiguration("badgec");
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

function makeServerOptions(): ServerOptions {
  const includePaths = vscode.workspace
    .getConfiguration("badgec")
    .get<string[]>("includePaths", []);
  const env: { [key: string]: string | undefined } = { ...process.env };
  const root = workspaceRoot();
  env.PYTHONPATH = [root, env.PYTHONPATH].filter(Boolean).join(path.delimiter);
  if (includePaths.length > 0) {
    env.BADGEC_PATH = includePaths.join(path.delimiter);
  }

  return {
    command: pythonExecutable(),
    args: ["-m", "badgec.lsp", "--stdio"],
    transport: TransportKind.stdio,
    options: {
      cwd: root,
      env: env as NodeJS.ProcessEnv,
    },
  };
}

function makeClientOptions(): LanguageClientOptions {
  return {
    documentSelector: [
      { scheme: "file", language: "badgec" },
      { scheme: "file", language: "voja4-asm" },
    ],
    synchronize: {
      configurationSection: "badgec",
      fileEvents: vscode.workspace.createFileSystemWatcher("**/*.{badge,asm}"),
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
    "badgec",
    "BadgeC Language Server",
    makeServerOptions(),
    makeClientOptions(),
  );

  await client.start();
}

async function fixBadgeLanguageMode(
  document: vscode.TextDocument,
): Promise<void> {
  if (
    document.uri.scheme === "file" &&
    document.fileName.toLowerCase().endsWith(".badge") &&
    document.languageId === "plaintext"
  ) {
    try {
      await vscode.languages.setTextDocumentLanguage(document, "badgec");
    } catch (error) {
      outputChannel.appendLine(
        `Could not switch ${document.fileName} to BadgeC: ${String(error)}`,
      );
    }
  }
}

export async function activate(context: vscode.ExtensionContext): Promise<void> {
  outputChannel = vscode.window.createOutputChannel("BadgeC");
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
    vscode.commands.registerCommand("badgec.restartServer", async () => {
      outputChannel.appendLine("Restarting BadgeC language server...");
      try {
        await startClient();
        outputChannel.appendLine("BadgeC language server restarted.");
      } catch (error) {
        outputChannel.appendLine(`Restart failed: ${String(error)}`);
      }
    }),
  );

  context.subscriptions.push(
    vscode.workspace.onDidChangeConfiguration(async (event) => {
      if (event.affectsConfiguration("badgec")) {
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
      "BadgeC language server failed to start. " +
      "Install the Python extra with `pip install -e \".[lsp]\"` " +
      "or set `badgec.pythonPath` to the right interpreter.";
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
