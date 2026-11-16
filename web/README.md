# Niblick web editor

Browser build of the Niblick compiler, assembler, and emulator. The Python
code runs under Pyodide; Monaco provides the source editor.

Hosted build: <https://furrysalamander.github.io/niblick/>

## Features

- Compile `.nbl` sources with `lib/` imports and Monaco diagnostics
- Editable multi-file projects with `.nbl` and imported `.asm` modules
- Project zip import/export with browser auto-save
- Standard Monaco editor features: find, folding, hover, Ctrl+click/F12 go to
  definition, references, and the context menu
- Read-only assembly view with Voja4 highlighting
- Source ↔ assembly cursor and hover highlighting; clicking either pane jumps
  the other pane's scroll position
- Source-line colors in both panes, with a toggle
- Read-only tabs for imported library sources
- `xxd`-style hexdump with copy and `.hex` download
- Example selector for the checked-in programs
- WebSerial flashing at 9600 8N1 in Chromium/Edge, with a download fallback
- Emulator with run, pause, step, reset, LED matrix, UART, and front-panel keys

## Emulator panel

The emulator tab shows `R0`–`R9` in two columns. Each register has four bit
indicators, a hex value, and a decimal value. The status strip below the
registers shows `PC`, `SP`, `C`/`Z`/`V`, instruction and cycle counts, the
clock rate, the `ALT` state, and the last `KeyReg` code.

The front panel is a subset of the badge panel. Only controls with a
confirmed `KeyReg` mapping are shown:

| Control | `KeyReg` |
|---|---:|
| `ALT` | `KeyStatus.AltPress` |
| `CLOCK` / `STEP` / `DEP+` | 0 |
| `OPCODE 8` | 1 |
| `OPCODE 4` | 2 |
| `OPCODE 2` | 3 |
| `OPCODE 1` | 4 |

`MODE`, `DATA IN`, `OPERAND X`, `OPERAND Y`, and the other command buttons
are omitted because the emulator does not model the badge's front-panel
controller. The `UART` panel has a clear button; input is sent to the
emulated serial port. See [`docs/keys.md`](../docs/keys.md) for the hardware
mapping.

## Projects

The editor keeps one project in the browser. A project has a `.nbl` entry
file and any number of editable `.nbl` and `.asm` files. Imports resolve
relative to the importing file, then against the bundled runtime roots, as in
the command-line compiler. Files outside the project root, such as `lib/`
imports, open as read-only tabs.

Use the **Project** menu beside the source tabs to create a project, add,
rename, or delete files, change the entry point, and import or export a zip.
The entry tab is marked with a dot. `.asm` files are assembly modules imported
from a `.nbl` file:

```c
import "drivers/display.asm";

extern fn void display_init();
```

See [`docs/asm-imports.md`](../docs/asm-imports.md) for the module ABI and
placeholder syntax.

The project is auto-saved to `localStorage` under `niblick.project.v1` and
restored on reload. Export clears the dirty flag; auto-save does not replace a
zip export as a backup.

### Zip format

Exported archives contain the project files plus `niblick.json`:

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

`lib/` is not copied into the archive; imports resolve against the runtime
that loads the project. Import strips one common top-level directory, ignores
unsupported files such as `README.md` and `__MACOSX`, and infers the entry from
`main.nbl` or the first `.nbl` file when no manifest is present. Limits are
200 files, 1 MiB per file, and 4 MiB total. Absolute paths, `..` segments, and
binary files are rejected.

## Build assets

The web app needs the compiler and assembler wheels plus a runtime archive of
`lib/` and `examples/`:

```bash
../.venv/bin/python ../tools/build_web_assets.py
```

Generated assets are written to `public/wheels/`, `public/runtime.zip`, and
`public/examples/`. They are not committed.

## Development

```bash
npm install
npm run dev
```

## Load order

`index.html` contains the shell styles inline. `src/main.ts` is a small
bootstrap that paints the shell and then dynamically imports `src/app.ts`.
The Monaco and Pyodide app chunk loads after the first paint, so the header,
toolbar, and loading state are styled immediately.

## Production build

```bash
npm run build
```

Set `VITE_BASE` when serving from a subpath. For GitHub Pages at
`https://furrysalamander.github.io/niblick/`:

```bash
VITE_BASE=/niblick/ npm run build
```

The GitHub Pages workflow should run `tools/build_web_assets.py` before the
Vite build.

## Tests

```bash
npm run build
npm run test:e2e
```

The Playwright tests use the system Chrome channel and wait for Pyodide to
install the local wheels and compile `hello.nbl`. Project tests cover creating
files, zip import/export, path validation, auto-save, and editing imported
assembly.

## GitHub Pages

The site is deployed at <https://furrysalamander.github.io/niblick/>.
`.github/workflows/pages.yml` builds the Python assets, runs the Vite build,
and deploys `web/dist` with GitHub Actions. Set the repository Pages source to
**GitHub Actions**. The workflow reads the Pages base path from
`actions/configure-pages`, so it works for both project sites
(`/niblick/`) and user sites (`/`).

## Runtime

- Pyodide version: `0.29.5`, loaded from jsDelivr in `src/runtime.ts`
- Compiler and assembler wheel names come from `public/wheels/manifest.json`
- Runtime archive: `runtime.zip` containing `lib/` and `examples/`

## License

GPL-3.0-only. See `../LICENSE`.

Monaco is MIT-licensed. Pyodide is MPL-2.0. `supercon6-assembler` is
MIT-licensed. `fflate` is MIT-licensed. See `../THIRD_PARTY_NOTICES.md`.
