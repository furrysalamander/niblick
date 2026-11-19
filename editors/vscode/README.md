# Niblick VS Code extension

Language support for Niblick and the Supercon.6 (Voja4) badge.

## Development

```bash
cd editors/vscode
npm install
npm run compile
```

Open this folder in VS Code and press F5.

The extension starts the language server with:

```bash
python3 -m niblick.lsp --stdio
```

It auto-detects a workspace `.venv` or `venv` first. Install the server
dependencies from the repository root:

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -e ".[lsp]"
```

Full documentation is in `../../docs/toolchain/vscode.md`.

## License

GPL-3.0-only. See `LICENSE`.
