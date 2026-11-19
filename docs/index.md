# Niblick

Niblick compiles a C-like language to the 12-bit instruction set of the
Hackaday Supercon.6 2022 (Voja4) badge. The compiler emits assembly and a
`.hex` image, and includes a headless emulator for tests.

- [Live editor](https://furrysalamander.github.io/niblick/)
- [Source repository](https://github.com/furrysalamander/niblick)

The target has 4-bit data, 4096 12-bit code words, 256 nibbles of data RAM,
10 general registers, a five-entry hardware call stack, an 8x16 LED matrix,
and a 9600 8N1 UART. See {doc}`internals/isa` for the machine model.

## Documentation

| Section | Contents |
|---|---|
| {doc}`getting-started/install` | Install the compiler, compile a program, and run it in the emulator |
| {doc}`language/index` | Syntax, types, expressions, statements, functions, structs, imports, and limitations |
| {doc}`standard-library/index` | Intrinsics, formatting, and the public modules under `lib/` |
| {doc}`toolchain/emulator` | Emulator, diagnostics, debugger, VS Code extension, and web editor |
| {doc}`internals/compiler` | Compiler pipeline, runtime ABI, instruction set, memory map, and numeric helpers |
| {doc}`project/repo-layout` | Repository layout, contributing, tests, release process, and documentation style |

```{toctree}
:hidden:
:maxdepth: 2
:caption: Getting started

getting-started/install
getting-started/quickstart
getting-started/cli
```

```{toctree}
:hidden:
:maxdepth: 2
:caption: Language

language/index
language/syntax
language/types
language/expressions
language/semantics
language/declarations
language/statements
language/functions
language/structs
language/imports
language/inline-asm
language/asm-modules
language/limitations
```

```{toctree}
:hidden:
:maxdepth: 2
:caption: Standard library

standard-library/index
standard-library/intrinsics
standard-library/formatting
standard-library/uart
standard-library/gpio
standard-library/board
standard-library/display
standard-library/keys
standard-library/time
standard-library/power
standard-library/system
standard-library/random
standard-library/memory
standard-library/strings
standard-library/math
standard-library/fixed-point
standard-library/trig
standard-library/audio
standard-library/pdm
standard-library/spi
standard-library/font
standard-library/textscroll
standard-library/drivers/w5500
```

```{toctree}
:hidden:
:maxdepth: 2
:caption: Toolchain

toolchain/emulator
toolchain/diagnostics
toolchain/debugging
toolchain/vscode
toolchain/web-editor
```

```{toctree}
:hidden:
:maxdepth: 2
:caption: Internals

internals/compiler
internals/runtime-abi
internals/isa
internals/memory-map
internals/soft-float
internals/wide-arithmetic
internals/performance
```

```{toctree}
:hidden:
:maxdepth: 2
:caption: Examples

examples/index
```

```{toctree}
:hidden:
:maxdepth: 2
:caption: Project

project/repo-layout
project/contributing
project/testing
project/releasing
project/docs-style
```
