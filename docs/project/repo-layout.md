# Repository layout

| Path | Contents |
|---|---|
| `niblick/` | Compiler, parser, lexer, loader, optimizer, assembler wrapper, emulator, debugger, LSP |
| `niblick/runtime/` | Hand-written runtime assembly |
| `niblick/_vendor/` | Vendored third-party assembler |
| `lib/` | Standard library modules |
| `lib/boards/` | Board pin and wiring constants |
| `lib/drivers/` | Device drivers |
| `lib/drivers/asm/` | Imported assembly driver modules |
| `examples/` | Niblick example programs |
| `tests/` | Pytest suite and emulator models |
| `scripts/` | Serial and hardware helper scripts |
| `tools/` | Web asset build and documentation tools |
| `web/` | Browser editor |
| `editors/vscode/` | VS Code extension |
| `docs/` | Documentation source |

## Key modules

| Module | Role |
|---|---|
| `niblick/cli.py` | Command-line entry point |
| `niblick/loader.py` | Import resolution and program loading |
| `niblick/lexer.py` | Tokenizer |
| `niblick/parser.py` | Parser and AST construction |
| `niblick/compiler.py` | Semantic checks, allocation, code generation |
| `niblick/asm_opt.py` | Assembly optimizer |
| `niblick/asm_link.py` | Imported assembly scanner and linker |
| `niblick/runtime_linker.py` | Runtime routine selection |
| `niblick/emulator.py` | Headless CPU and UART model |
| `niblick/debug.py` | Debug service |
| `niblick/lsp.py` | Language server |
| `niblick/analysis.py` | Editor analysis |
| `niblick/symbols.py` | Symbol extraction |
| `niblick/web.py` | Browser bridge for Pyodide |

## Build outputs

Generated `.asm`, `.hex`, and `.map.json` files are written next to the source
or into `--output-dir`. `make clean` removes generated example outputs and
build directories.
