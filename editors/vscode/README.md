# Niblick

Niblick language support for the Hackaday Supercon.6 (Voja4) badge.

## Features

- Syntax highlighting for `.nbl` and Voja4 assembly files.
- Compiler diagnostics from the Niblick language server.
- Document symbols, hover, completion, go-to-definition, references, and rename.
- Compile and run commands using the Niblick compiler and emulator.
- Debug launch configurations with breakpoints, stepping, registers, flags, globals, and UART output.
- Snippets for functions, loops, imports, assembly modules, and assembly routines.

## Requirements

- VS Code 1.91 or newer.
- Python 3.11 or newer.
- The `niblick` Python package with the `lsp` extra:

```bash
python -m pip install "niblick[lsp]"
```

The extension auto-detects a workspace `.venv` or `venv`. Set `niblick.pythonPath` to use a specific interpreter.

If the language server cannot start, run `Niblick: Install Python Backend` from the command palette.

## Quick start

1. Open a folder containing `.nbl` files.
2. Open a `.nbl` file.
3. Run `Niblick: Compile Current File` or `Niblick: Run Current File in Emulator`.
4. Use `F5` with a `niblick` launch configuration to debug.

## Commands

| Command | Action |
|---|---|
| `Niblick: Compile Current File` | Compile the active `.nbl` file into `.niblick-build/` |
| `Niblick: Run Current File in Emulator` | Compile and run the active file in the headless emulator |
| `Niblick: Restart Language Server` | Restart the Python language server |
| `Niblick: Install Python Backend` | Run `pip install "niblick[lsp]"` in a terminal |

## Settings

| Setting | Default | Meaning |
|---|---|---|
| `niblick.pythonPath` | auto-detect | Python interpreter used for the language server and compiler |
| `niblick.includePaths` | `[]` | Additional import roots, passed as `NIBLICK_PATH` |

## Debugging

Use a `niblick` launch configuration:

```json
{
  "type": "niblick",
  "request": "launch",
  "name": "Niblick: Run Program",
  "program": "${file}",
  "cwd": "${workspaceFolder}",
  "stopOnEntry": true
}
```

Set `hex` to debug an existing `.hex` file. Set `debugMap` to the matching debug map JSON.

## Documentation

- Documentation: <https://furrysalamander.github.io/niblick/docs/>
- VS Code guide: <https://furrysalamander.github.io/niblick/docs/toolchain/vscode.html>
- Issues: <https://github.com/furrysalamander/niblick/issues>

## Development

```bash
cd editors/vscode
npm install
npm run compile
```

Open this folder in VS Code and press F5.

## License

GPL-3.0-only. See `LICENSE`.
