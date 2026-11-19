# VS Code language support

The repository includes a VS Code extension under `editors/vscode/`. It
provides Niblick and Voja4 assembly syntax highlighting plus a language server
for diagnostics and document symbols.

## Prerequisites

For the language server, either create a project `.venv` (the extension
auto-detects `.venv/bin/python` and `venv/bin/python`):

```bash
cd /path/to/niblick
python3 -m venv .venv
.venv/bin/python -m pip install -e ".[lsp]"
```

or install the `lsp` extra into the interpreter selected by
`niblick.pythonPath`:

```bash
python3 -m pip install -e ".[lsp]"
```

The `lsp` extra installs `pygls`.

For building the extension:

- Node.js 22 or newer
- VS Code 1.146 or newer

## Run from source

```bash
cd editors/vscode
npm install
npm run compile
```

Open `editors/vscode/` in VS Code and press F5. This launches an Extension
Development Host with the Niblick extension loaded. Open a `.nbl` file from
the main repository; the language server is started with `python3 -m
niblick.lsp --stdio`.

## Install locally

Build a `.vsix`:

```bash
cd editors/vscode
npm run package
```

Then install it:

```bash
code --install-extension niblick-vscode-1.0.0.vsix
```

Or use `Extensions: Install from VSIX...` in the command palette.

## Features

- Syntax highlighting for `.nbl` files.
- Syntax highlighting for Voja4 assembly files.
- Compiler diagnostics on change, with a short debounce.
- Diagnostics for imported `.asm` modules.
- Document symbols for functions, extern functions, globals, consts, and
  assembly entry points.
- Hover for function signatures, types, constants, and assembly symbols.
- Completion for keywords, types, functions, globals, parameters, locals,
  assembly mnemonics, registers, and labels.
- Go-to-definition for functions, globals, parameters, locals, and imported
  assembly entry points.
- Find all references across Niblick, inline asm, and imported assembly.
- Rename functions, globals, parameters, locals, and assembly entry points
  across files.
- Compile current file and run it in the Niblick emulator from the command
  palette.
- Debug launch configurations with breakpoints, stepping, registers, flags,
  globals, and UART output. See [debugging.md](debugging.md).
- Snippets for functions, loops, imports, assembly modules, and assembly
  routines.

## File associations

The extension contributes the `niblick` language for `.nbl` files. This
repository pins the association in `.vscode/settings.json`:

```json
"files.associations": {
  "*.nbl": "niblick",
  "**/*.asm": "voja4-asm"
}
```

The extension does not claim every `.asm` file. This repository's
`.vscode/settings.json` associates all workspace `.asm` files with `voja4-asm`.

For another project, add:

```json
"files.associations": {
  "path/to/asm/*.asm": "voja4-asm"
}
```

## Settings

| Setting | Default | Meaning |
|---|---|---|
| `niblick.pythonPath` | auto-detect | Python interpreter used to launch the server; empty means auto-detect `.venv`/`venv`, then `python3` |
| `niblick.includePaths` | `[]` | Extra import roots, also passed through `NIBLICK_PATH` |

## Commands

- `Niblick: Compile Current File`: compile the active `.nbl` file into
  `.niblick-build/` and show compiler output.
- `Niblick: Run Current File in Emulator`: compile and run the active `.nbl`
  file with the headless emulator.
- `Niblick: Restart Language Server`

Debugging uses the normal VS Code Run and Debug view with a `niblick` launch
configuration. See {doc}`debugging`.

## Diagnostics

If diagnostics do not appear, check the language mode in the status bar, the
Niblick output channel, and `niblick.pythonPath`. The language server logs
startup errors to stderr; the extension forwards them to the output channel.

## Architecture

```text
VS Code
  └─ editors/vscode TypeScript client
       └─ stdio
            └─ python3 -m niblick.lsp
                 ├─ niblick.analysis
                 ├─ niblick.loader
                 ├─ niblick.parser
                 └─ niblick.asm_link
```

The client only handles editor integration, grammars, snippets, and starting
the server. Compiler and project knowledge stays in Python.

## Known limitations

- The parser and compiler stop at the first error, so the editor
  publishes one diagnostic per analysis pass.
- The language server analyzes the open file as its entry point, using open
  buffers as source overrides.
- A file without `main` is checked with all of its functions active, so a
  very large library can report RAM pressure that a real entry point would
  prune away.
