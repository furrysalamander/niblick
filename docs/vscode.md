# VS Code language support

The repository includes a VS Code extension under `editors/vscode/`. It
provides BadgeC and Voja4 assembly syntax highlighting plus a language server
for diagnostics and document symbols.

## Prerequisites

For the language server, either create a project `.venv` (the extension
auto-detects `.venv/bin/python` and `venv/bin/python`):

```bash
cd /path/to/hackaday_supercon_2026
python3 -m venv .venv
.venv/bin/python -m pip install -e ".[lsp]"
```

or install the `lsp` extra into whatever interpreter you configure through
`badgec.pythonPath`:

```bash
python3 -m pip install -e ".[lsp]"
```

The `lsp` extra installs `pygls`.

For building the extension:

- Node.js 20 or newer
- VS Code 1.85 or newer

## Run from source

```bash
cd editors/vscode
npm install
npm run compile
```

Open `editors/vscode/` in VS Code and press F5. This launches an Extension
Development Host with the BadgeC extension loaded. Open a `.badge` file from
the main repository; the language server is started with `python3 -m
badgec.lsp --stdio`.

## Install locally

Build a `.vsix`:

```bash
cd editors/vscode
npm run package
```

Then install it:

```bash
code --install-extension badgec-vscode-0.1.0.vsix
```

Or use **Extensions: Install from VSIX...** in the command palette.

## Features

- Syntax highlighting for `.badge` files.
- Syntax highlighting for Voja4 assembly files.
- Compiler diagnostics on change, with a short debounce.
- Diagnostics for imported `.asm` modules.
- Document symbols for functions, extern functions, globals, consts, and
  assembly entry points.
- Snippets for functions, loops, imports, assembly modules, and assembly
  routines.

## File associations

The extension contributes the `badgec` language for `.badge` files. This
repository also pins the association in `.vscode/settings.json` so an editor
that was opened before the extension was installed cannot stay stuck in
`plaintext`:

```json
"files.associations": {
  "*.badge": "badgec",
  "lib/asm/*.asm": "voja4-asm"
}
```

The extension deliberately does **not** claim every `.asm` file, because that
would override other assemblers. This repository's `.vscode/settings.json`
associates `lib/asm/*.asm` with `voja4-asm`.

For another project, add:

```json
"files.associations": {
  "path/to/asm/*.asm": "voja4-asm"
}
```

## Settings

| Setting | Default | Meaning |
|---|---|---|
| `badgec.pythonPath` | auto-detect | Python interpreter used to launch the server; empty means auto-detect `.venv`/`venv`, then `python3` |
| `badgec.includePaths` | `[]` | Extra import roots, also passed through `BADGEC_PATH` |

## Commands

- **BadgeC: Restart Language Server**

## Troubleshooting

If diagnostics do not appear:

1. Make sure the folder is trusted. Use **Workspaces: Manage Workspace
   Trust** and trust this workspace. VS Code can keep local extensions
   inactive in Restricted Mode.
2. Check the language mode in the bottom-right of the editor. It should say
   **BadgeC**. If it says **Plain Text**, click it and choose **BadgeC**, or
   reload the window.
3. Open the **BadgeC** output channel.
4. Check that `python3 -m badgec.lsp --stdio` runs in the repository
   environment.
5. Install the server extra with `pip install -e ".[lsp]"`.
6. Set `badgec.pythonPath` to the correct virtualenv or interpreter.
7. Run **BadgeC: Restart Language Server**.

The server logs startup errors to stderr; the extension forwards them to the
output channel and shows a one-time error notification.

## Architecture

```text
VS Code
  └─ editors/vscode TypeScript client
       └─ stdio
            └─ python3 -m badgec.lsp
                 ├─ badgec.analysis
                 ├─ badgec.loader
                 ├─ badgec.parser
                 └─ badgec.asm_link
```

The client only handles editor integration, grammars, snippets, and starting
the server. Compiler and project knowledge stays in Python.

## Known limitations

- The parser and compiler still stop at the first error, so the editor
  publishes one diagnostic per analysis pass.
- Hover, completion, go-to-definition, references, and rename are not
  implemented yet. They will build on `badgec.analysis`.
- The language server analyzes the open file as its entry point, using open
  buffers as source overrides.
- A file without `main` is checked with all of its functions active, so a
  very large library can report RAM pressure that a real entry point would
  prune away.
