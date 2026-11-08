# Imported assembly modules

BadgeC can link hand-written assembly from `.asm` files. This is the
recommended way to keep reusable driver routines out of the compiler's core
runtime while still calling them from normal BadgeC code.

```c
// lib/w5500.badge
import "asm/w5500.asm";

extern fn word w5500_tx_pointer();
```

```asm
; lib/asm/w5500.asm
fn_w5500_tx_pointer:
    ...
    RET R0, 0
```

An `import "file.asm";` is resolved with the same rules as a `.badge` import:
relative to the importing file first, then the repository root and
`BADGEC_PATH` entries. Each file is read once; reachable routine sections are
appended to the generated assembly in import order.

## Extern declarations

Only function declarations are currently supported:

```c
extern fn void spi_init();
extern fn char spi_xfer(char out);
extern word read16(nibble addr);       // C-style spelling also works
```

An `extern fn` gets the normal BadgeC calling convention:

- every parameter has a static RAM slot allocated by the compiler;
- the caller stores arguments into those slots before `GOSUB fn_name`;
- the assembly reads them with `${param}` placeholders;
- the result is left in `R1` (`nibble`), `R1:R2` (`char`), `R1..R4`
  (`word`), or `R1..R8` (`dword`);
- `void` functions return with `RET R0, 0`.

The assembly must define a matching `fn_<name>:` label. If an extern function
is called but no label exists, compilation fails.

## Placeholders

Imported assembly can refer to BadgeC symbols with `${...}`:

| Placeholder | Expands to |
|---|---|
| `${name}` | RAM address of a global/parameter, scalar `const` value, or flash label for a `const` array |
| `${name+1}` / `${name-1}` | RAM address plus/minus a constant |
| `${&name}` | Address of a RAM variable or flash label |
| `${function.param}` | A specific function's parameter address |
| `${CONST << 2}` | A normal BadgeC constant expression |

Within a `fn_*` block, `${param}` resolves against that function's parameters
first, then globals. Outside a function block, only globals are available.
Assembly comments are not substituted.

A `char` parameter at `${p}` occupies two nibbles: `${p}` is low and
`${p+1}` is high. A `word` occupies four nibbles, and so on.

Example:

```asm
fn_spi_xfer:
    MOV R0, [${out}]
    MOV R1, R0
    MOV R0, [${out+1}]
    MOV R2, R0
    ...
    RET R0, 0
```

## Calls and linking

The compiler scans imported assembly for `GOSUB` and `GOTO`:

- `GOSUB __bc_*` marks a compiler runtime routine as used, so the existing
  runtime linker keeps only that routine and its dependencies;
- `GOSUB fn_*` adds a normal call-graph edge;
- `GOTO fn_*` adds a tail-call edge;
- `GOTO .local` is a local loop inside the routine.

Calls must be inside a `fn_*` block. `GOSUB` to a local label is not
supported, because it makes the hardware stack depth harder to model
statically.

Functions and globals referenced only from imported assembly are kept alive
during dead-declaration elimination. Conversely, a `fn_*` section whose
extern function is not reachable from `main`, a kept C function, or another
kept assembly routine is stripped along with its parameter slots, just like
an unused BadgeC function. A source file without any `fn_*` label is treated
as data and kept whole; data before the first `fn_*` label is always kept.
Put shared tables before the first entry point: any labels after a `fn_*`
section belong to that section and disappear if the function is removed.

## Labels and restrictions

- Entry points are global labels named `fn_<function>` in lowercase, matching
  the BadgeC declaration exactly.
- Local labels start with `.` and are scoped by the assembler to the preceding
  global label.
- `__bc_*` labels are reserved for the compiler runtime.
- Every `fn_*` entry point must have an `extern fn` declaration.
- Raw `MOV JSR`, `MOV PCL`, `MOV PCM`, and `MOV PCH` are rejected; use
  `GOSUB`/`GOTO` so the compiler can see calls.
- `ORG`, `BYTE`, and `ASCII` are rejected in imported assembly. Use `NIBBLE`
  for data tables; BadgeC emits flash data as `NIBBLE` directives because the
  vendored assembler miscounts `BYTE`/`ASCII` when resolving later labels.
- `EXR 0` and `EXR` with more than ten registers are rejected because they
  touch compiler/runtime state.
- The assembler has one global symbol namespace. Avoid reusing labels across
  imported files; duplicates are reported during compilation.

## Optimization control

Imported assembly goes through the same conservative optimizer as the
built-in runtime by default. That means peephole removal, copy propagation,
dead register-write removal, and `GOTO` → `JR` relaxation can change the
exact instruction sequence. For timing-sensitive code, mark a region or file
opaque:

```asm
; @badgec: no-optimize
fn_delay_loop:
    MOV R0, R0
    ...
    RET R0, 0
```

or:

```asm
fn_delay_loop:
; @badgec: no-optimize-begin
    MOV R0, R0
    ...
; @badgec: no-optimize-end
    RET R0, 0
```

Opaque regions are emitted exactly as written. Their words are still counted
for size reporting and branch relaxation outside the region.

## Worked example: `w5500_tx_pointer`

`lib/asm/w5500.asm` contains the W5500 socket-0 TX pointer routine. It is no
longer part of `badgec/runtime/runtime.asm`; `lib/w5500.badge` declares it and
imports the assembly file. The routine calls the generic
`__bc_spi_xfer_fast` runtime helper, so the compiler's scanner adds that
runtime routine to the linked set automatically.
