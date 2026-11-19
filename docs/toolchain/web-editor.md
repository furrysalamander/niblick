# Web editor

The web editor compiles and runs Niblick programs in the browser. Python runs
under Pyodide; Monaco provides the source editor.

Hosted build: <https://furrysalamander.github.io/niblick/>

## Features

- Compile `.nbl` sources with `lib/` imports and Monaco diagnostics.
- Editable projects with `.nbl` and imported `.asm` files.
- Project zip import and export.
- Find, folding, hover, go-to-definition, references, and context menu.
- Read-only assembly view with Voja4 highlighting.
- Source and assembly cursor highlighting.
- Read-only tabs for imported library sources.
- `xxd`-style hex dump with copy and `.hex` download.
- Example selector.
- WebSerial flashing at 9600 8N1 in Chromium and Edge.
- Emulator with run, pause, step, reset, LED matrix, UART, and front-panel keys.

## Projects

A project has one `.nbl` entry file and any number of editable `.nbl` and
`.asm` files. Imports resolve relative to the importing file, then against the
bundled runtime roots, as in the command-line compiler. Files outside the
project root open as read-only tabs.

The project is stored in `localStorage` under `niblick.project.v1`. Export
writes a zip archive; auto-save does not replace a zip backup.

## Zip format

An exported archive contains the project files and `niblick.json`:

```text
niblick.json
main.nbl
src/input.nbl
drivers/display.asm
```

```json
{
  "format": "niblick-project",
  "version": 1,
  "name": "my-project",
  "entry": "main.nbl"
}
```

`lib/` is not copied into the archive. Import strips one common top-level
directory, ignores unsupported files such as `README.md` and `__MACOSX`, and
infers the entry from `main.nbl` or the first `.nbl` file when no manifest is
present. Limits are 200 files, 1 MiB per file, and 4 MiB total. Absolute paths,
`..` segments, and binary files are rejected.

## Emulator panel

The emulator tab shows `R0` through `R9` in two columns. Each register has four
bit indicators, a hex value, and a decimal value. The status strip shows `PC`,
`SP`, `C`/`Z`/`V`, instruction and cycle counts, clock rate, `ALT` state, and
the last `KeyReg` code.

The front panel exposes controls with confirmed `KeyReg` mappings:

| Control | `KeyReg` |
|---|---:|
| `ALT` | `KeyStatus.AltPress` |
| `CLOCK` / `STEP` / `DEP+` | 0 |
| `OPCODE 8` | 1 |
| `OPCODE 4` | 2 |
| `OPCODE 2` | 3 |
| `OPCODE 1` | 4 |

`MODE`, `DATA IN`, `OPERAND X`, `OPERAND Y`, and other command buttons are not
modeled. The `UART` panel sends input to the emulated serial port.

## Development

```bash
.venv/bin/python tools/build_web_assets.py
cd web
npm install
npm run dev
```

Generated assets are written to `web/public/wheels/`, `web/public/runtime.zip`,
and `web/public/examples/`.

## Production build

```bash
cd web
npm run build
```

Set `VITE_BASE` when serving from a subpath:

```bash
VITE_BASE=/niblick/ npm run build
```

## Tests

```bash
cd web
npm run build
npm run test:e2e
```

The Playwright tests use the system Chrome channel and wait for Pyodide to
install the local wheels and compile `hello.nbl`.
