# Testing

## Fast loop

```bash
python3 -m pytest
python3 -m niblick examples/hello.nbl --run
python3 -m niblick examples/flash_walk.nbl --run --map
```

The emulator is deterministic and exercises UART transmit and receive without
hardware.

## Test layers

| Layer | Files | Coverage |
|---|---|---|
| Emulator semantics | `tests/test_emulator.py` | Instructions, flags, memory, stack, jumps, flash tables |
| Lexer and parser | `tests/test_parser.py` | Tokens, strings, literals, for-update, syntax errors |
| End-to-end compiler | `tests/test_compiler.py` | Source to assembly to hex to emulator behavior |
| Imported assembly | `tests/test_asm_imports.py` | `.asm` imports, `extern fn`, placeholders, runtime linking, optimizer markers |
| Inline assembly | `tests/test_inline_asm.py` | `asm` blocks, scoped placeholders, labels, runtime calls, optimizer opacity |
| Editor analysis | `tests/test_analysis.py`, `tests/test_lsp.py` | Source positions, loader overrides, diagnostics, symbols, hover, completion, definitions, references, rename |
| Diagnostics | `tests/test_diagnostics.py` | Structured errors, JSON output, assembly-to-source mapping |
| Debugger | `tests/test_debugmap.py`, `tests/test_debug.py` | PC-to-source maps, breakpoints, stepping, variables, stack frames |
| W5500 | `tests/test_mc_void.py`, `tests/test_spi_fast.py` | Fast SPI helpers and a 1.8.9 exchange through a W5500/TCP model |
| Standard library | `tests/test_library.py`, `tests/test_stdlib.py`, `tests/test_signed_lib.py` | UART, GPIO, display, keys, time, power, system, random, memory, strings, math, trig, audio, PDM |
| Inlining and overlay | `tests/test_compiler.py`, `tests/test_overlay.py` | Single-statement inlining, side-effect guards, frame interference, slot reuse |
| Print formatting | `tests/test_print.py` | Literal format parsing, typed placeholders, generated UART helpers, errors |
| Structs | `tests/test_structs.py` | Layout, field access, arrays of structs, rejected forms |
| Board constants | `tests/test_board.py` | Output and input masks, default SPI and W5500 assignments |
| Optimizer proofs | `tests/test_peephole_z3.py` | Z3 proofs for address lowering and peephole identities |
| Property tests | `tests/test_hypothesis_compiler.py` | Generated nibble expressions against a Python reference |
| CLI | `tests/test_cli.py` | Output paths, error reporting, `.hex` generation |
| Examples | `tests/test_examples.py` | Every checked-in example compiles and fits |
| Documentation | `tests/test_docs.py` | Links, headings, style rules, and library coverage |

LSP tests are skipped when `pygls` is not installed. Install the `lsp` extra to
run them.

## Emulator model

See {doc}`../toolchain/emulator` for the Python API, model coverage, and I/O
tracing.

## Adding a compiler test

Use the helper in `tests/test_compiler.py`:

```python
compiler, hex_path = build(tmp_path, """
    nibble x;
    fn main() { x = 3 + 4; }
""")
emu = run(hex_path)
assert emu.ram[ram_nibble(compiler, "x")] == 7
```

`build()` parses, compiles, assembles, and returns the compiler plus the `.hex`
path. `run()` loads and executes it.

## Tooling

```bash
python3 -m pip install -e ".[dev]"
ruff check .
mypy niblick/compiler.py niblick/format.py niblick/inline.py niblick/asm_opt.py niblick/loader.py niblick/emulator.py niblick/parser.py niblick/types.py
python3 -m pytest --cov=niblick
python3 -m pip_audit
pre-commit install
```

## CI

The CI workflow runs the Python test matrix, Ruff and mypy, coverage, the VS
Code extension build and package, the web editor build and Playwright tests,
and dependency audits for Python, the web editor, and the extension.
