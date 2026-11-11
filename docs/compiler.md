# BadgeC compiler internals

## Pipeline

```text
.badge source
  -> badgec/loader.py       resolve imports; collect .asm modules
  -> badgec/lexer.py        tokens
  -> badgec/parser.py       AST (badgec/ast_nodes.py)
  -> badgec/inline.py       inline tiny/statement wrappers, remove dead declarations
  -> badgec/compiler.py     semantic checks, allocation, code generation
  -> badgec/asm_link.py     scan imported assembly for calls and symbols
  -> badgec/asm_opt.py      peepholes, copy propagation, branch relaxation
  -> .asm
  -> supercon6-assembler      .hex
  -> badgec/emulator.py     headless execution / tests
```

There is deliberately no heavyweight IR yet. The current generator is a
direct AST-to-assembly backend with a fixed-register expression convention.
This keeps the first working compiler small and makes the hardware
constraints explicit. The pass boundaries are still clean enough to add an
IR and optimizer later.

## Expression convention

Every expression leaves its result in fixed registers:

| Type | Registers |
|---|---|
| `nibble` | `R1` |
| `char` | `R1` = low, `R2` = high |
| `word` | `R1` = low, `R2`, `R3`, `R4` = high |
| `dword` | `R1` = low through `R8` = high |
| `flashptr` | `R1` = low, `R2` = middle, `R3` = high |

`R0` is reserved for the instructions that can only access memory through
it (`MOV [NN],R0`, `MOV R0,[NN]`, `CP R0,N`, `ADD R0,N`).

Nested binary expressions park the left operand in a temporary slot, evaluate
the right operand, then reload and combine. Most functions use the shared
`0x20..0x37` scratch area. If an expression keeps a temporary live across a
call, the compiler gives that function a private small scratch area at the top
of its frame, so the callee cannot clobber it. No runtime stack pointer is
needed; all slot addresses are known at compile time.

## Memory allocation

| Region | Use |
|---|---|
| `0x00..0x0F` | registers and SFRs |
| `0x10..0x1F` | hardware subroutine stack |
| `0x20..0x37` | shared expression temporaries (24 nibbles) |
| `0x38..0x3F` | word multiply/divide runtime scratch (8 nibbles) |
| user RAM | optional 24-nibble dword mul/div scratch, allocated on demand |
| `0x40..0xEF` | globals, parameters, locals, RAM arrays (176 nibbles) |
| `0xF0..0xFF` | SFR page |

RAM allocation is static, but function frames are overlaid. The compiler
builds a conservative frame-interference graph:

- a caller and its transitive callees never share a frame;
- callees evaluated in the same statement never share a frame;
- functions reachable from a nested argument call never share a frame;
- imported assembly call edges are included.

Functions in separate branches share the same slot block, so their parameter
and local slots are reused. A function that needs call-safe temporaries gets
a frame scratch area sized by a probe compile that records the maximum number
of live temporaries at every call site. The fixed-register calling convention
and the lack of a software frame pointer are unchanged.

## Imports

`import "lib/uart.badge";` is resolved by `badgec/loader.py` before semantic
analysis. Imports are looked up relative to the importing file, then relative
to the repository root and any `BADGEC_PATH` entries. Each file is parsed
once, cycles are rejected, and the declarations are merged into a single
`ast.Program`.

`import "lib/drivers/asm/w5500.asm";` imports assembly instead. The file is read and
kept as text on the program; it is not parsed as BadgeC. Assembly modules
declare their entry points with `extern fn ...;` and are scanned for labels,
`GOSUB`/`GOTO` targets, placeholders, and runtime calls before linking. See
[asm-imports.md](asm-imports.md).

Inline `asm { ... }` statements are kept as raw text on the AST and lowered at
the current statement position. They resolve `${...}` against the current
lexical scope and are wrapped in opaque optimizer markers. See
[inline-asm.md](inline-asm.md).

The compiler also emits `; @badgec-src file:line` markers. The optimized
assembly is scanned into a PC-to-source map by `badgec/debugmap.py`, exposed
with `--debug-map`, and consumed by the emulator debugger. See
[debugging.md](debugging.md).

Dead-declaration elimination runs after inlining:

- functions unreachable from `main` (or a kept global initializer) are
  removed;
- globals that are not referenced by reachable code and whose initializer has
  no calls are removed, including unreferenced const flash tables;
- functions and globals referenced only by imported assembly placeholders or
  `fn_*` calls are kept;
- an imported assembly `fn_*` section whose extern function is unreachable is
  stripped, and its parameter slots are not allocated.

This is what makes importing a module free when only part of it is used.
Error locations inside imported files report that file's path and line for
`.`asm` modules; `.badge` AST nodes still carry a line but not a filename, so
errors in imported BadgeC report the entry file's name.

## Print formatting

`print("text {} {:x}\n", a, b);` is expanded at compile time. The format
string must be a literal, and `lib/uart.badge` must be imported because the
expansion emits calls to `uart_puts` and the `uart_print_*` helpers. Each
placeholder is checked against the argument type, so `{}`/`{:d}` choose the
decimal formatter, `{:x}` the hex formatter, `{:b}` binary, `{:c}` a character,
and `{:s}` a string. The expansion runs before dead-declaration
elimination, so unused formatters are still removed. See
[stdlib.md](stdlib.md#print-formatting).

## Calls, tail calls, and recursion

Non-tail calls use `GOSUB`/`RET` and consume one of the five hardware stack
entries. Tail calls compile to `GOTO`, so they consume no stack entry and
the callee's `RET` returns directly to the original caller.

After code generation, `validate_call_graph()`:

- rejects any cycle containing a non-tail edge;
- allows cycles made entirely of tail edges;
- computes the maximum non-tail depth from `main`;
- rejects depth > 4, leaving one hardware stack level of headroom for the
  UART/flash runtime.

`GOTO` is a two-word pseudo-op. Conditional branches use `SKIP ...,2`
before a `GOTO` so both words are skipped when the condition is true.
Getting this wrong lands in the middle of a `GOTO`; the integration tests
cover it.

## Types and coercions

Integer widths are `nibble` (4), `char` (8), `word` (16), and `dword` (32).
Widening is implicit and zero-extends into the higher result registers.
Narrowing is rejected unless an explicit cast is used:

```c
char low = (char)wide;
nibble nib = (nibble)wide;
word back = (word)byte;
dword wide = (dword)word_value;
```

`const` arrays are read-only and live in flash; RAM arrays are mutable.

Scalar `const` declarations are folded at compile time and occupy no RAM:

```c
const nibble EPD_SER   = 1;
const nibble EPD_SRCLK = 2;
const nibble EPD_CLK   = EPD_SER | EPD_SRCLK;

gpio_set(EPD_CLK);
```

The initializer may be any integer constant expression built from literals,
other scalar consts, casts, unary `- ~ !`, arithmetic, shifts, bitwise
operators, and comparisons. Results follow the same width and widening rules
as runtime code, so `word * word` still truncates to 16 bits. A scalar const
whose initializer is dynamic is rejected; use a normal variable instead.
Taking `&CONST` is also rejected. Local scalar consts work the same way.

Scalar consts still appear in `--map` and `--map-json`, with `address: null`
and their folded value.

Native signed types are not implemented. Signed arithmetic is available as
raw-bit helpers in `lib/signed.badge` (`nibble` = 4-bit signed, `char` =
8-bit signed, `word` = 16-bit signed) and Q4.4 fixed point in
`lib/fixed.badge`. This keeps the type system and code generator small while
a signed-heavy application is evaluated. A native signed type would affect
coercion, comparison, arithmetic shift, division, literal typing, and
address/print handling; the helper library is the current prototype for
deciding whether that cost is justified.

`char` is unsigned 0..255, `word` is unsigned 0..65535, and `dword` is
unsigned 0..4294967295. String literals and `const char[]` are flash objects
with a `0xFF` terminator. `flash_next(&p)` is a compiler intrinsic:
it loads the 3-nibble cursor, calls the RET-table reader, and writes the
advanced cursor back without using a RAM buffer.

## Flash data

Flash data is emitted as `RET R0,nibble` words. For a `char`, the low nibble
comes first, then the high nibble, matching the badge demos and the
assembler's `BYTE` directive.

BadgeC emits **pairs of `NIBBLE` directives** rather than `BYTE` because the
upstream assembler miscounts `BYTE`/`ASCII` when a later label is resolved.
Each `NIBBLE` is one word, so labels after a table are correct.

## Current optimizations

- Constant folding for integer arithmetic and comparisons.
- Scalar `const` globals and locals with constant initializers are replaced
  by immediates, saving both their RAM and their startup stores. Const
  expression folding is also used for GPIO masks and constant assignments.
- Direct `peek`/`poke`/`out`/`in` lowering.
- Constant-address `peek`/`poke`/`peek8`/`poke8` lowering to direct
  `MOV R0,[NN]` / `MOV [NN],R0` instructions.
- Compile-time `print()` expansion into typed UART formatting calls.
- Whole-program inlining of tiny `return <expr>` functions and small
  single-statement void wrappers. Parameters used more than once are guarded
  by a side-effect check. Char arguments are wrapped in an internal `ToChar`
  node so substituted literals keep 8-bit semantics.
- Dead-function elimination based on reachability from `main` and global
  initializers.
- Runtime stripping: only the `__bc_*` routines reachable from used builtins
  are emitted.
- Imported `.asm` modules with `extern fn` declarations, scoped `${...}`
  symbol placeholders, call-graph/runtime-linker scanning, and per-file or
  per-region `; @badgec: no-optimize` markers.
- Inline `asm { ... }` statements with lexical `${...}` placeholders, local
  labels, call-graph/runtime-linking integration, and optimizer opacity.
- Call-graph frame overlay for parameter and local slots.
- Per-function call-safe temporary scratch, sized by a probe compile and
  allocated inside the function's overlaid frame.
- Peephole removal of redundant `MOV`s.
- Basic-block copy propagation: a `MOV Rd,Rs` is dropped when `Rd` already
  holds `Rs`'s value.
- Dead register-write elimination with conservative block-boundary liveness.
  Skip windows are protected so their word count cannot change.
- Direct condition lowering: comparisons branch straight from `CP`/`SUB`
  flags instead of materialising a 0/1 value. `if (!x)` and constant
  conditions are folded, and single-operand zero tests use `OR R1,R1`.
- Constant array indices fold to direct memory operands; constant stores
  skip the R1/R2 staging moves.
- Binary operands stay in registers (`R3`/`R4`) when the right operand cannot
  clobber them, replacing RAM spill traffic.
- Address arithmetic uses operand registers directly and drops carry
  correction for page-aligned arrays.
- Constant-count `<<`/`>>` are unrolled; variable counts use a small loop.
  All integer widths are supported.
- `*` widens one step (`nibble*nibble -> char`, `char*char -> word`) and
  keeps `word*word -> word`, `dword*dword -> dword` (low 32 bits). Constant
  powers of two become shifts.
- `/` and `%` use unsigned binary long division; constant powers of two
  become shifts and masks. Division by zero returns zero.
- Explicit `(nibble)`, `(char)`, `(word)`, and `(dword)` casts.
- 32-bit multiply/divide use a 24-nibble scratch block allocated only when
  the program actually uses those operators.
- Constant-mask `gpio_set`/`gpio_clear`/`gpio_toggle` lower to
  `BSET`/`BCLR`/`BTG R3,n`; single-bit `gpio_test` lowers to `BIT R3,n`.
  Multi-bit tests and variable masks still call the runtime, and the GPIO
  runtime is stripped when every use takes the fast path.
- `import` with cycle detection and dead-declaration elimination.
- Branch relaxation from two-word `GOTO` to one-word `JR` when in range,
  including adjustment of a preceding `SKIP` count.
- Tail-call elimination.
- Static call-depth checking.
- Code-size regression budgets in `tests/test_size.py`.

## Planned optimizations

1. More aggressive size-aware inlining, including small multi-statement bodies.
2. Peephole rules for constant branches and wider delete/replace patterns.
3. Short-`if` skip fusion for bodies of four words or fewer.
4. Loop rotation to remove the unconditional back-edge.
5. Faster 32-bit multiply/divide (the current routines are size-conscious).

## Current code-size pressure

The Tetris demo is now around **2577 / 4096 words** and **134 / 176 usable
RAM nibbles**. That leaves roughly 1500 words for new features. The
`hello.badge` example is about **146 words** after constant-address lowering,
small void inlining, and frame overlay. The dword-heavy
`dword_math.badge` demo is about **2295 words** and **97 RAM nibbles**.

`tests/test_examples.py` prevents an example from silently exceeding the
4096-word limit, and `tests/test_size.py` keeps Tetris under a 2800-word
budget.

## Size and stack reports

`--symbols` now reports per-function word counts, linked runtime routine
sizes, flash-data size, startup overhead, and the total:

```text
  functions:
    spi_byte -> void [fn_spi_byte] 29 words p:char@0x40
    main -> void [fn_main] 142 words
  runtime:
    __bc_uart_putc: 6 words
  startup/other: 2 words
  total: 2577 words
```

`--map-json` carries the same data (`functions[].words`, `runtime_words`,
`flash_words`, `startup_words`, `asm_words`). The counts are computed from
the final optimized assembly using the same word-size model as branch
relaxation; a test checks that the buckets add up to the assembled total.

`--stack` prints the maximum non-tail user depth, the deepest user path,
each function's entry depth, every runtime call site with its stack cost,
and the linked runtime routines. Runtime costs are derived from the runtime
assembly, including internal `GOSUB`s and flash-table `MOV JSR` calls, so
they stay in sync with `docs/runtime-abi.md`. A call that would need more
than the five hardware stack entries produces a compile warning:

```text
warning: driver.badge:42: leaf calls __bc_gpio_test at user depth 4;
runtime cost 2 needs 6 stack levels (the hardware stack has 5)
```

The existing hard limit of four non-tail user levels from `main` is
unchanged.

## Verification tools

- `z3-solver` proves the address-lowering and peephole identities in
  `tests/test_peephole_z3.py`.
- `hypothesis` generates nibble expressions and compares the compiled
  emulator result with a Python reference in `tests/test_hypothesis_compiler.py`.
- `ruff` and `mypy` run in CI and in the pre-commit hook.
- `pytest-cov` reports compiler coverage in CI.

## Error handling

User-facing errors carry `file:line:column` where possible. The CLI catches
`BadgeError` and prints a single line without a traceback. Internal
exceptions are not hidden; they indicate a compiler bug.

Editor tooling reuses the front end through `badgec/analysis.py` and
`badgec/symbols.py`; the LSP server in `badgec/lsp.py` exposes diagnostics,
document symbols, hover, completion, go-to-definition, references, and rename.
See [vscode.md](vscode.md).
