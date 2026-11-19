# Niblick web editor

Browser build of the Niblick compiler, assembler, and emulator. Python runs
under Pyodide; Monaco provides the editor.

Hosted build: <https://furrysalamander.github.io/niblick/>

User and developer documentation is in `../docs/toolchain/web-editor.md`.

## Build

```bash
../.venv/bin/python ../tools/build_web_assets.py
npm install
npm run dev
```

Generated assets are written to `public/wheels/`, `public/runtime.zip`, and
`public/examples/`. They are not committed.

## Production

```bash
npm run build
VITE_BASE=/niblick/ npm run build
```

## Tests

```bash
npm run build
npm run test:e2e
```

## Runtime assets

- Pyodide `0.29.5`, loaded from jsDelivr in `src/runtime.ts`
- Compiler and assembler wheel manifest: `public/wheels/manifest.json`
- Runtime archive: `runtime.zip` containing `lib/` and `examples/`
