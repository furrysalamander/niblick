# Runtime ABI

This is the contract used by `niblick/compiler.py` and
`niblick/runtime/runtime.asm`.

## Values

| Type | Representation |
|---|---|
| `nibble`, `u4`, `i4`, `bool` | One register or one RAM nibble |
| `char`, `u8`, `i8` | Two nibbles, low first |
| `uint16_t`, `u16`, `i16`, `int`, `short` | Four nibbles, low first |
| `uint32_t`, `u32`, `i32`, `long` | Eight nibbles, low first |
| `uint64_t`, `u64`, `i64`, `int64_t` | Sixteen nibbles; results use a memory buffer |
| `flashptr` | Three nibbles: low, middle, high |
| `void` | No value |

Signed and unsigned types share the same layout. Signed values are two's
complement; widening sign-extends.

Expression results use fixed registers:

| Width | Registers |
|---|---|
| 4-bit | `R1` |
| 8-bit | `R1` low, `R2` high |
| 16-bit | `R1` low through `R4` high |
| 32-bit | `R1` low through `R8` high |
| `flashptr` | `R1` low, `R2` middle, `R3` high |

`R0` is reserved for instructions that access memory only through it:
`MOV [NN],R0`, `MOV R0,[NN]`, `MOV [XY],R0`, `MOV R0,[XY]`, `CP R0,N`,
`ADD R0,N`, and the immediate logical forms.

## User function calls

Niblick uses static parameter slots, not register argument passing.

1. The compiler allocates a fixed RAM slot for every parameter and local.
2. At a call site, each argument expression is evaluated and stored into the
   callee's parameter slot.
3. The caller executes `GOSUB fn_name`.
4. The callee returns with `RET R0,0`. A `nibble` result is in `R1`; a `char`
   result is low in `R1`, high in `R2`.
5. The caller treats `R0` through `R9` as clobbered. Temporaries that must
   survive a call live in the caller's frame.

Functions are non-reentrant. Parameter and local slots are overlaid across
functions that cannot be active at the same time. A function that keeps an
expression temporary live across a call gets a private temporary area in its
own frame.

## Tail calls

A call in tail position compiles to `GOTO`:

```text
; return f(a, b);
<evaluate args into temporaries>
<copy temporaries into f's parameter slots>
GOTO fn_f
```

The callee's `RET` returns to the original caller. Tail recursion uses constant
hardware stack depth. Self-tail calls evaluate all arguments into temporaries
before overwriting parameter slots. Non-tail recursion is rejected.

## Runtime library ABI

The UART and flash helpers are hand-written assembly and use the expression
result registers:

| Routine | Input | Output |
|---|---|---|
| `__nib_uart_putc` | `R1` low, `R2` high | none |
| `__nib_uart_getc` | none | `R1` low, `R2` high |
| `__nib_gpio_set/clear/toggle` | `R1` mask | none |
| `__nib_gpio_test` | `R1` mask | `R1` 0/1 |
| `__nib_gpio_read` | none | `R1` input nibble |
| `__nib_gpio_write` | `R1` output nibble | none |
| `__nib_delay` | `R1` units | none |
| `__nib_w5500_spi_tx_fast` | `R1:R2` char | none |
| `__nib_w5500_spi_xfer_fast` | `R1:R2` char | `R1:R2` char |
| `__nib_flash_read_char` | `R1/R2/R3` flash pointer | `R1/R2` char |
| `__nib_flash_read_nibble` | `R1/R2/R3` flash pointer | `R1` nibble |
| `__nib_flash_read_word` | `R1/R2/R3` flash pointer | `R1..R4` 16-bit |
| `__nib_flash_read_dword` | `R1/R2/R3` flash pointer | `R1..R8` 32-bit |
| `__nib_mul4` | `R1`, `R2` | `R1:R2` product |
| `__nib_mul8` | `R1:R2`, `R3:R4` | `R1..R4` product |
| `__nib_mul16` | `R1..R4`, `R5..R8` | `R1..R4` low 16 bits |
| `__nib_divmod8` | `R1:R2`, `R3:R4` | quotient `R1:R2`, remainder `R3:R4` |
| `__nib_divmod16` | `R1..R4`, `R5..R8` | quotient `R1..R4`, remainder `R5..R8` |
| `__nib_sdivmod8` | `R1:R2`, `R3:R4` | signed quotient and remainder |
| `__nib_sdivmod16` | `R1..R4`, `R5..R8` | signed quotient and remainder |
| `__nib_mul32` | `R4:R5`, `R6:R7` pointer pair | `R1..R8` low 32-bit product |
| `__nib_divmod32` | `R4:R5`, `R6:R7` pointer pair | quotient and remainder buffers |

Runtime routines may clobber `R0` through `R9` and do not preserve flags. The
flash reader uses `R6`, `R7`, and `R8` as the 12-bit pointer and `R5` as a
scratch nibble.

## User assembly modules

Imported `.asm` routines use the same static-slot convention:

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

Parameters are allocated in RAM and read with `${param}`. Results use the normal
expression-result registers. The compiler scans `GOSUB` and `GOTO` in imported
assembly so runtime linking, the call graph, and stack reports stay accurate.
See {doc}`../language/asm-modules`.

## GPIO and SFR helpers

- `gpio_read()` reads `IN` at `0x0B` or `InB` at `0xFB`.
- `gpio_write(n)` writes `OUT` at `0x0A` or `OutB` at `0xFA`.
- `gpio_set`, `gpio_clear`, and `gpio_toggle` read, modify, and write the output
  latch.
- `gpio_test` reads the input port and returns 1 if any masked bit is set.

The GPIO runtime routines are not linked when every call uses a constant mask.
The compiler emits `BSET`, `BCLR`, `BTG`, or `BIT` directly.

Other SFR helpers are ordinary library functions:

| Helper | Module |
|---|---|
| `display_page`, `display_poke`, `display_peek`, `dimmer` | `lib/display.nbl` |
| `random`, `seed` | `lib/random.nbl` |
| `key_status`, `key_code` | `lib/key.nbl` |
| `gpio_alt`, `uart_route`, `leds_enable`, `matrix_enable` | `lib/gpio`, `lib/uart`, `lib/display` |
| `uart_write` | `lib/uart.nbl` |
| `mem_fill`, `mem_copy`, `mem_*` | `lib/mem.nbl` |

## Memory layout

The compiler uses these regions. The full data-memory map is in
{doc}`memory-map`.

| Range | Use |
|---|---|
| `0x20..0x37` | Compile-time expression temporaries |
| `0x38..0x3F` | 16-bit multiply/divide runtime scratch |
| `0x35..0x37` | Signed division sign scratch during a runtime call |
| User RAM | Optional 24-nibble 32-bit multiply/divide scratch |
| `0x40..0xEF` | Globals, parameters, locals, RAM arrays |

## Call depth

`main` runs at depth 0. Each non-tail `GOSUB` consumes one hardware stack entry.
The compiler rejects a maximum non-tail user depth above 4.

| Call | Stack levels |
|---|---:|
| `uart_putc`, `uart_getc` | 1 |
| `flash_next` | 2 |
| `flash_read_nibble`, `flash_read_char` | 3 |
| GPIO runtime fallback | 2 |
| Signed 8-bit and 16-bit `/` and `%` | 2 |
| `delay`, `w5500_spi_tx_fast`, `w5500_spi_xfer_fast` | 1 |

`uart_init`, `uart_available`, and `uart_puts` are library functions and add a
normal user frame around the runtime byte primitive.

`--stack` prints the deepest user path, per-function entry depth, runtime call
sites with cost, and a warning when a call would exceed the five hardware stack
entries.

## Flash data

A flash `char[]` is stored as `RET R0,nibble` words: low nibble first, then high
nibble. A flash `nibble[]` is one `RET` word per element. Strings use `0x00` as
the terminator.

The compiler emits flash bytes as pairs of `NIBBLE` directives.

## `main`

`main` is entered by `GOTO fn_main`, not `GOSUB`. It never returns to a caller;
`return` from `main` compiles to `JR -1`.
