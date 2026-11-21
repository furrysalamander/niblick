# Compiler internals

## Pipeline

```text
.nbl source
  -> niblick/loader.py       resolve imports; collect .asm modules
  -> niblick/lexer.py        tokens
  -> niblick/parser.py       AST (niblick/ast_nodes.py)
  -> niblick/inline.py       inline single-statement wrappers; remove dead declarations
  -> niblick/compiler.py     semantic checks, allocation, code generation
  -> niblick/asm_link.py     scan imported assembly for calls and symbols
  -> niblick/asm_opt.py      peepholes, copy propagation, branch relaxation
  -> .asm
  -> bundled assembler       .hex
  -> niblick/emulator.py     headless execution and tests
```

The compiler is a direct AST-to-assembly backend. There is no intermediate
representation. Pass boundaries are `loader`, `lexer`, `parser`, `inline`,
`compiler`, `asm_link`, and `asm_opt`.

## Expression convention

Every expression leaves its result in fixed registers:

| Width | Registers |
|---|---|
| 4-bit (`nibble`, `i4`, `bool`) | `R1` |
| 8-bit (`char`, `i8`) | `R1` low, `R2` high |
| 16-bit (`uint16_t`, `i16`) | `R1` low through `R4` high |
| 32-bit (`uint32_t`, `i32`) | `R1` low through `R8` high |
| 64-bit (`uint64_t`, `i64`) | 16-nibble memory result buffer |
| `flashptr` | `R1` low, `R2` middle, `R3` high |

`R0` is reserved for instructions that access memory only through `R0`:
`MOV [NN],R0`, `MOV R0,[NN]`, `CP R0,N`, and `ADD R0,N`.

Nested binary expressions park the left operand in a temporary slot, evaluate
the right operand, then reload and combine. Most functions use the shared
`0x20..0x37` scratch area. If an expression keeps a temporary live across a
call, the compiler gives that function a private scratch area at the top of its
frame. Slot addresses are known at compile time; there is no stack pointer.

## Memory allocation

| Region | Use |
|---|---|
| `0x00..0x0F` | Registers and fixed SFRs |
| `0x10..0x1F` | Hardware subroutine stack |
| `0x20..0x37` | Shared expression temporaries (24 nibbles) |
| `0x38..0x3F` | 16-bit multiply/divide runtime scratch |
| User RAM | Optional 24-nibble 32-bit multiply/divide scratch |
| `0x40..0xEF` | Globals, parameters, locals, RAM arrays (176 nibbles) |
| `0xF0..0xFF` | SFR page |

RAM allocation is static. Function frames are overlaid using a conservative
frame-interference graph:

- A caller and its transitive callees never share a frame.
- Callees evaluated in the same statement never share a frame.
- Functions reachable from a nested argument call never share a frame.
- Imported assembly call edges are included.

Functions in separate branches share a slot block. A function that needs
call-safe temporaries gets a frame scratch area sized by a probe compile that
records the maximum number of live temporaries at every call site.

## Imports

`import "lib/uart.nbl";` is resolved by `niblick/loader.py` before semantic
analysis. Imports resolve relative to the importing file, then the repository
root and `NIBLICK_PATH` entries. Each file is parsed once, cycles are rejected,
and declarations merge into one `ast.Program`.

`import "lib/drivers/asm/w5500.asm";` reads assembly as text. Assembly modules
declare entry points with `extern fn` and are scanned for labels, `GOSUB` and
`GOTO` targets, placeholders, and runtime calls. See
{doc}`../language/asm-modules`.

Inline `asm { ... }` statements are kept as raw text and lowered at the current
statement position. They resolve `${...}` against the current lexical scope and
are wrapped in optimizer markers. See {doc}`../language/inline-asm`.

The compiler emits `; @niblick-src file:line` markers. `niblick/debugmap.py`
scans the optimized assembly into a PC-to-source map for `--debug-map` and the
debugger. See {doc}`../toolchain/debugging`.

Dead-declaration elimination runs after inlining:

- Functions unreachable from `main` or a retained global initializer are
  removed.
- Globals not referenced by reachable code and whose initializer has no calls
  are removed, including unreferenced const flash tables.
- Functions and globals referenced by imported assembly placeholders or
  `fn_*` calls are kept.
- An imported assembly `fn_*` section whose extern function is unreachable is
  stripped, and its parameter slots are not allocated.

## Print expansion

`print("text {} {:x}\n", a, b);` expands at compile time. The format string must
be a literal, and `lib/uart.nbl` must be imported. The expansion runs before
dead-declaration elimination, so unused formatters are removed. See
{doc}`../standard-library/formatting`.

## Calls and recursion

Non-tail calls use `GOSUB` and `RET` and consume one of the five hardware stack
entries. Tail calls compile to `GOTO`, consume no stack entry, and return
directly to the original caller.

`validate_call_graph()` runs after code generation:

- Reject any cycle containing a non-tail edge.
- Allow cycles made entirely of tail edges.
- Compute maximum non-tail depth from `main`.
- Reject depth greater than 4, leaving one hardware stack level for runtime
  helpers.

`GOTO` is a two-word pseudo-op. Conditional branches use `SKIP ...,2` before a
`GOTO` so both words are skipped when the condition is true.

## Optimizations

- Constant folding for integer arithmetic and comparisons.
- Scalar `const` globals and locals with constant initializers replaced by
  immediates, saving RAM and startup stores.
- Direct `peek`/`poke`/`out`/`in` lowering.
- Constant-address `peek`/`poke`/`peek8`/`poke8` lowering to direct
  `MOV R0,[NN]` and `MOV [NN],R0`.
- Compile-time `print()` expansion.
- Whole-program inlining of single-statement `return <expr>` functions and
  single-statement void wrappers. Parameters used more than once are guarded by
  a side-effect check.
- Dead-function elimination from `main` and global initializers.
- Runtime stripping: only reachable `__nib_*` routines are emitted.
- Imported `.asm` modules with `extern fn`, scoped placeholders, call-graph
  scanning, and `; @niblick: no-optimize` markers.
- Inline `asm` statements with lexical placeholders, local labels, and
  optimizer opacity.
- Call-graph frame overlay for parameter and local slots.
- Per-function call-safe temporary scratch.
- Peephole removal of redundant `MOV`s.
- Basic-block copy propagation.
- Dead register-write elimination with conservative block-boundary liveness.
- Direct condition lowering from `CP`/`SUB` flags.
- Constant array indices folded to direct memory operands.
- Binary operands kept in `R3`/`R4` when the right operand cannot clobber them.
- Address arithmetic uses operand registers directly and drops carry correction
  for page-aligned arrays.
- Constant-count shifts unrolled; variable counts use a loop.
- `*` widens one step. Constant powers of two become shifts.
- `/` and `%` use long division; constant powers of two become shifts and
  masks.
- Explicit integer and `(bool)` casts.
- 32-bit multiply and divide use a 24-nibble scratch block allocated on demand.
- Constant-mask GPIO lowers to `BSET`, `BCLR`, `BTG`, or `BIT`.
- Branch relaxation from two-word `GOTO` to one-word `JR` when in range.
- Tail-call elimination.
- Static call-depth checking.

## Reports

`--symbols` reports per-function word counts, linked runtime routine sizes,
flash-data size, startup overhead, and the total.

```text
  functions:
    spi_byte -> void [fn_spi_byte] 29 words p:char@0x40
    main -> void [fn_main] 142 words
  runtime:
    __nib_uart_putc: 6 words
  startup/other: 2 words
  total: 2573 words
```

`--map-json` carries the same data in `functions[].words`, `runtime_words`,
`flash_words`, `startup_words`, and `asm_words`. Counts come from the final
optimized assembly using the same word-size model as branch relaxation.

`--stack` prints maximum non-tail depth, the deepest path, per-function entry
depth, runtime call sites with stack cost, and linked runtime routines. A call
that would exceed the five hardware stack entries produces a warning.

## Errors

User-facing errors carry `file:line:column` where possible. The CLI catches
`NiblickError` and prints one line without a traceback. Internal exceptions
indicate a compiler bug.

Editor tooling reuses the front end through `niblick/analysis.py` and
`niblick/symbols.py`. The LSP server in `niblick/lsp.py` implements diagnostics,
document symbols, hover, completion, go-to-definition, references, and rename.
See {doc}`../toolchain/vscode`.
