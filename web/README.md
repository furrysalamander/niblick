# Niblick web editor

Browser build of the Niblick compiler and assembler. The Python compiler runs
under Pyodide; Monaco provides the source editor.

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

## Production build

```bash
npm run build
```

Set `VITE_BASE` when serving from a subpath. For GitHub Pages at
`https://<user>.github.io/niblick/`:

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

The Playwright test uses the system Chrome channel and waits for Pyodide to
install the local wheels and compile `hello.nbl`.

## Runtime

- Pyodide version: `0.29.5`, loaded from jsDelivr in `src/runtime.ts`
- Compiler and assembler wheel names come from `public/wheels/manifest.json`
- Runtime archive: `runtime.zip` containing `lib/` and `examples/`

## License

GPL-3.0-only. See `../LICENSE`.

Monaco is MIT-licensed. Pyodide is MPL-2.0. `supercon6-assembler` is
MIT-licensed. See `../THIRD_PARTY_NOTICES.md`.
