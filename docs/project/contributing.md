# Contributing

## Setup

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -e ".[dev,lsp,fidelity,docs]"
```

## Checks

```bash
python3 -m pytest
ruff check .
mypy niblick/compiler.py niblick/format.py niblick/inline.py niblick/asm_opt.py niblick/loader.py niblick/emulator.py niblick/parser.py niblick/types.py
```

## Examples

```bash
make examples
```

`make examples` compiles every file in `examples/`. This is slower than the
test suite and reports the same size limits.

## Documentation

```bash
make docs
make docs-serve
```

The documentation build treats warnings as errors. See {doc}`docs-style` for
the writing rules and `tests/test_docs.py` for the automated checks.

## Commits

- Keep compiler changes separate from documentation changes where practical.
- Add or update a test for behavior changes.
- Run the checks above before committing.
- Do not commit generated `.asm`, `.hex`, or build output.

## Release

See {doc}`releasing`.
