# BadgeC compiler internals

## Pipeline

```text
.badge source
  -> badgec/loader.py       resolve imports into one AST
  -> badgec/lexer.py        tokens
  -> badgec/parser.py       AST (badgec/ast_nodes.py)
  -> badgec/inline.py       inline tiny functions, remove dead declarations
  -> badgec/compiler.py     semantic checks, allocation, code generation
  -> badgec/asm_opt.py      peepholes, copy propagation, branch relaxation
  -> .asm
  -> vendor assembler       .hex
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
| `flashptr` | `R1` = low, `R2` = middle, `R3` = high |

`R0` is reserved for the instructions that can only access memory through
it (`MOV [NN],R0`, `MOV R0,[NN]`, `CP R0,N`, `ADD R0,N`).

Nested binary expressions park the left operand in a static temporary slot
in `0x20..0x3F`, evaluate the right operand, then reload and combine. No
runtime stack pointer is needed for expression temporaries; the slot
addresses are known at compile time.

## Memory allocation

| Region | Use |
|---|---|
| `0x00..0x0F` | registers and SFRs |
| `0x10..0x1F` | hardware subroutine stack |
| `0x20..0x3F` | compile-time expression temporaries (32 nibbles) |
| `0x40..0xEF` | globals, parameters, locals, RAM arrays (176 nibbles) |
| `0xF0..0xFF` | SFR page |

RAM allocation is static. A function's parameters and locals keep the same
addresses for the whole program. This is safe while the call graph is
acyclic or tail-recursive, and it avoids software frame pointers. The
trade-off is that two functions that are never active at the same time
still get separate storage. A call-graph overlay or inliner is a future
optimization.

## Imports

`import "lib/uart.badge";` is resolved by `badgec/loader.py` before semantic
analysis. Imports are looked up relative to the importing file, then relative
to the repository root and any `BADGEC_PATH` entries. Each file is parsed
once, cycles are rejected, and the declarations are merged into a single
`ast.Program`.

Dead-declaration elimination runs after inlining:

- functions unreachable from `main` (or a kept global initializer) are
  removed;
- globals that are not referenced by reachable code and whose initializer has
  no calls are removed, including unreferenced const flash tables.

This is what makes importing a module free when only part of it is used.
Error locations inside imported files currently report the entry file's
name, because AST nodes carry a line but not a filename.

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

Only widening from `nibble` to `char` is implicit. Narrowing is rejected
because silently discarding the high nibble is a common source of bugs on a
4-bit machine. `const` arrays are read-only and live in flash; RAM arrays
are mutable.

`char` is unsigned 0..255. String literals and `const char[]` are flash
objects with a `0xFF` terminator. `flash_next(&p)` is a compiler intrinsic:
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
- Direct `peek`/`poke`/`out`/`in` lowering.
- Whole-program inlining of tiny `return <expr>` functions, with a
  side-effect guard for parameters used more than once. Char arguments are
  wrapped in an internal `ToChar` node so substituted literals keep 8-bit
  semantics.
- Dead-function elimination based on reachability from `main` and global
  initializers.
- Runtime stripping: only the `__bc_*` routines reachable from used builtins
  are emitted.
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
- Constant-count `<<`/`>>` are unrolled for nibble and char values.
- `import` with cycle detection and dead-declaration elimination.
- Branch relaxation from two-word `GOTO` to one-word `JR` when in range,
  including adjustment of a preceding `SKIP` count.
- Tail-call elimination.
- Static call-depth checking.
- Code-size regression budgets in `tests/test_size.py`.

## Planned optimizations

1. Size-aware inlining for small functions with no static locals.
2. Call-graph local overlay to reduce RAM.
3. Short-`if` skip fusion for bodies of four words or fewer.
4. Strength reduction for multiply/divide and shifts once those operators
   are implemented.
5. Loop rotation to remove the unconditional back-edge.

## Current code-size pressure

The Tetris demo is now around **2475 / 4096 words** and **164 / 208 RAM
nibbles**, down from 4004 words before the condition-lowering and peephole
work. That leaves roughly 1600 words for new features.

`tests/test_examples.py` prevents an example from silently exceeding the
4096-word limit, and `tests/test_size.py` keeps Tetris under a 2600-word
budget.

## Error handling

User-facing errors carry `file:line:column` where possible. The CLI catches
`BadgeError` and prints a single line without a traceback. Internal
exceptions are not hidden; they indicate a compiler bug.
