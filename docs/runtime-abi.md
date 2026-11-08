# BadgeC runtime ABI

Status: **implemented v0**. This describes the contract used by
`badgec/compiler.py` and `badgec/runtime/runtime.asm`.

The design is shaped by the Voja4's limits: 4-bit data, `R0` is the only
data-memory gateway, there is no stack-relative addressing, and the
hardware return stack has only five entries.

## Values

| Type | Representation |
|---|---|
| `nibble` | One register or one RAM nibble; `0..15` |
| `char` | Two nibbles, low first then high; `0..255` |
| `word` | Four nibbles, low first; `0..65535` |
| `dword` | Eight nibbles, low first; `0..4294967295` |
| `flashptr` | Three nibbles: low, middle, high (12-bit code address) |
| `void` | No value |

An expression result is left in fixed registers:

| Type | Registers |
|---|---|
| `nibble` | `R1` |
| `char` | `R1` = low, `R2` = high |
| `word` | `R1` = low, `R2`, `R3`, `R4` = high |
| `dword` | `R1` = low through `R8` = high |
| `flashptr` | `R1` = low, `R2` = middle, `R3` = high |

`R0` is reserved for instructions that only work through it:

- `MOV [NN],R0` / `MOV R0,[NN]` (direct data memory)
- `MOV [XY],R0` / `MOV R0,[XY]` (indirect data memory)
- `CP R0,N`, `ADD R0,N`, `OR/AND/XOR R0,N`

## User function calls

BadgeC uses **static parameter slots**, not register argument passing:

1. The compiler allocates a fixed RAM slot for every parameter and local.
2. At a call site, each argument expression is evaluated and stored directly
   into the callee's parameter slot.
3. The caller executes `GOSUB fn_name`.
4. The callee returns with `RET R0,0`. A `nibble` result is in `R1`; a `char`
   result is low in `R1`, high in `R2`.
5. The caller treats `R0`–`R9` as clobbered. Live expression values are
   always parked in RAM temporaries before a call, so no callee-saved
   register convention is needed.

Static slots avoid software frame pointers and keep the code small. The
trade-off is that functions are non-reentrant and storage is not overlaid
yet. The inliner removes tiny `return <expr>` functions entirely, which
also removes their parameter slots.

### Tail calls

A call in tail position compiles to `GOTO`, not `GOSUB`:

```asm
; return f(a, b);
<evaluate args into temporaries>
<copy temporaries into f's parameter slots>
GOTO fn_f
```

The callee's `RET` returns directly to the original caller. Tail recursion
therefore uses **constant** hardware stack depth. Self-tail calls evaluate
all arguments into temporaries before overwriting the parameter slots, so
`return f(b, a)` does not clobber `a` before it is used.

Non-tail recursion is rejected at compile time.

## Runtime library ABI

The UART and flash helpers are hand-written assembly. They are called with
the same expression-result registers:

| Routine | Input | Output |
|---|---|---|
| `__bc_uart_init` | `R1` = baud index | none |
| `__bc_uart_putc` | `R1` = low, `R2` = high | none |
| `__bc_uart_getc` | none | `R1` = low, `R2` = high |
| `__bc_uart_available` | none | `R1` = count (0..15) |
| `__bc_uart_puts` | `R1/R2/R3` = flash pointer | none; stops at `0xFF` |
| `__bc_flash_read_char` | `R1/R2/R3` = flash pointer | `R1/R2` = char |
| `__bc_flash_read_nibble` | `R1/R2/R3` = flash pointer | `R1` = nibble |
| `__bc_flash_read_word` | `R1/R2/R3` = flash pointer | `R1..R4` = word |
| `__bc_flash_read_dword` | `R1/R2/R3` = flash pointer | `R1..R8` = dword |
| `__bc_mul4` | `R1` = a, `R2` = b | `R1:R2` = product |
| `__bc_mul8` | `R1:R2`, `R3:R4` | `R1..R4` = 16-bit product |
| `__bc_mul16` | `R1..R4`, `R5..R8` | `R1..R4` = low word |
| `__bc_divmod8` | `R1:R2`, `R3:R4` | quotient `R1:R2`, remainder `R3:R4` |
| `__bc_divmod16` | `R1..R4`, `R5..R8` | quotient `R1..R4`, remainder `R5..R8` |
| `__bc_mul32` | `R4:R5`, `R6:R7` = operand pointers | `R1..R8` = low 32-bit product |
| `__bc_divmod32` | `R4:R5`, `R6:R7` = operand pointers | quotient/remainder written to the buffers |

All runtime routines may clobber `R0`–`R9`. They do not preserve flags.
Internally, the flash reader uses `R6/R7/R8` as the 12-bit pointer and
`R5` as a scratch nibble.

## User assembly modules

Hand-written routines can live in imported `.asm` files instead of the core
runtime. They use the same static-slot calling convention as BadgeC
functions:

```c
import "my_driver.asm";

extern fn char read_byte(char addr_lo);
```

```asm
fn_read_byte:
    MOV R0, [${addr_lo}]
    ...
    RET R0, 0
```

Parameters are allocated in RAM by the compiler; the assembly reads them with
`${param}`. Results follow the normal expression-result registers. The
compiler scans `GOSUB`/`GOTO` in imported assembly so runtime linking, the
call graph, and stack reports remain accurate. See
[asm-imports.md](asm-imports.md) for placeholders, labels, restrictions, and
optimizer markers.

### UART details

- `SerCtrl` at `0xF5`: baud index (`3` = 9600, the reset default).
- `SerHigh` at `0xF7`: write high nibble first.
- `SerLow` at `0xF6`: writing it starts transmission.
- `Received` at `0xF8`: receive count, saturating at 15.
- Reading `SerHigh` then `SerLow` consumes one received byte. The runtime
  waits for `Received > 0` before reading.

The badge firmware blocks on the PIC24 TX buffer when `SerLow` is written,
so the runtime does not need a separate TX-ready poll.

## GPIO and SFR helpers

The GPIO helpers honor `WrFlags.IOPos`:

- `gpio_read()` reads `IN` at `0x0B` or `InB` at `0xFB`.
- `gpio_write(n)` writes `OUT` at `0x0A` or `OutB` at `0xFA`.
- `gpio_set/clear/toggle(mask)` read the output latch, modify it, and write
  it back.
- `gpio_test(mask)` reads the input port and returns `1` if any masked bit
  is set.

These routines are **not linked** when every call uses a constant mask:
the compiler emits `BSET`/`BCLR`/`BTG`/`BIT` directly (see
`docs/stdlib.md`). This matters for hot bit-bang loops and the hardware
stack budget.

Other SFR helpers are direct memory operations:

| Helper | SFR |
|---|---|
| `display_page(page)` | `Page` at `0xF0` |
| `display_poke(page,index,value)` | RAM address `(page<<4) | index` |
| `display_peek(page,index)` | RAM address `(page<<4) | index` |
| `random()` | `Random` at `0xFF` |
| `seed(n)` | `Random` at `0xFF` |
| `dimmer(n)` | `Dimmer` at `0xFE` |
| `key_status()` | `KeyStatus` at `0xFC` |
| `key_code()` | `KeyReg` at `0xFD` |
| `key_any/key_alt/key_just/key_last()` | individual `KeyStatus` bits |

The `WrFlags` helpers are `gpio_alt`, `uart_route`, `leds_enable`, and
`matrix_enable`. They take a nonzero/nibble value for enable and preserve
the other `WrFlags` bits.

`uart_write(buf, len)` transmits `len` bytes (`1..15`) from a RAM `char[]`.
`memset(buf, value, len)` fills `len` elements (`1..15`) of a RAM
`nibble[]` or `char[]`.

## Memory layout

| Range | Use |
|---|---|
| `0x00..0x0F` | registers and SFRs |
| `0x10..0x1F` | hardware subroutine stack (5 × 3 nibbles) |
| `0x20..0x37` | compile-time expression temporaries |
| `0x38..0x3F` | word multiply/divide runtime scratch |
| user RAM | optional 24-nibble dword multiply/divide scratch |
| `0x40..0xEF` | globals, parameters, locals, RAM arrays |
| `0xF0..0xFF` | SFR page |

## Call depth

`main` is entered with `GOTO`, so it runs at depth 0. Each non-tail
`GOSUB` consumes one hardware stack entry. BadgeC rejects programs whose
maximum non-tail user call depth exceeds 4, leaving one entry of headroom
for runtime helpers.

Runtime stack costs from user code:

| Call | Stack levels used |
|---|---:|
| `uart_init`, `uart_putc`, `uart_getc`, `uart_available` | 1 |
| `flash_next` | 2 |
| `flash_read_nibble`, `flash_read_char` | 2–3 |
| `uart_puts` | 3 |

These costs are why deep user call chains should use tail calls or
inlining. The compiler derives them from the runtime assembly itself
(including `GOSUB` chains and flash-table `MOV JSR` calls). `--stack`
prints the deepest user path, each function's entry depth, every runtime
call site, and a warning when a call would exceed the five hardware stack
entries.

## Flash data

A flash `char[]` is stored as `RET R0,nibble` words: low nibble first, then
high nibble. A flash `nibble[]` is one `RET` word per element. Strings use
`0xFF` as the terminator.

BadgeC emits flash bytes as pairs of `NIBBLE` directives rather than
`BYTE`, because the upstream assembler miscounts a `BYTE`/`ASCII` directive
when resolving a later label. See [isa.md](isa.md).

## `main`

`main` is entered by `GOTO fn_main`, not `GOSUB`. It never returns to a
caller; `return` from `main` compiles to `JR -1`, which is the badge's
idle loop.
