# Installation

## Requirements

- Python 3.11 or newer
- `pip`

The assembler is bundled with the compiler.

## From a checkout

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -e ".[dev]"
```

For compiler use only:

```bash
python3 -m pip install -e .
```

## Optional extras

| Extra | Contents |
|---|---|
| `dev` | Test suite, type checking, coverage, property tests, dependency audit |
| `lsp` | VS Code language server |
| `fidelity` | Headless emulator for cross-checks |
| `docs` | Sphinx, MyST, Read the Docs theme, live rebuild |

```bash
python3 -m pip install -e ".[docs]"
```

## Verify

```bash
python3 -m niblick examples/hello.nbl --run
```

The command writes `examples/hello.asm` and `examples/hello.hex` and runs the
program in the emulator.
