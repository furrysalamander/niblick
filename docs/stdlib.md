# BadgeC standard library

BadgeC has no libc. The builtins below are recognized by the compiler and
lowered to inline code or calls into `badgec/runtime/runtime.asm`. They are
the supported “standard library” for now.

## UART

| Call | Returns | Notes |
|---|---|---|
| `uart_init(baud)` | `void` | Baud index `0..7`; `3` = 9600, the reset default |
| `uart_putc(c)` / `putchar(c)` | `void` | Send one 8-bit char |
| `uart_getc()` | `char` | Wait for and return one 8-bit char |
| `uart_available()` | `nibble` | Bytes waiting, saturating at 15 |
| `uart_puts(s)` / `puts(s)` | `void` | Stream a flash string until `0xFF` |
| `uart_write(buf, len)` | `void` | Send `len` bytes (`1..15`) from a RAM `char[]` |

`uart_puts` accepts a string literal, a `const char[]`, or a `flashptr`.
`uart_write` accepts a RAM `char[]` variable and a nibble length.

## Flash tables

| Call | Returns | Notes |
|---|---|---|
| `flash_read_char(p)` | `char` | Random read from a flash `char[]` |
| `flash_read_nibble(p)` | `nibble` | Random read from a flash `nibble[]` |
| `flash_next(&p)` | `char` | Intrinsic iterator; advances the 3-nibble cursor by 2 words |
| `msg[i]` | element type | Flash or RAM array indexing |

Strings use `0xFF` as their terminator.

## RAM arrays

| Call | Returns | Notes |
|---|---|---|
| `peek(addr)` | `nibble` | Read a nibble at an 8-bit data address |
| `poke(addr, value)` | `void` | Write a nibble at an 8-bit data address |
| `memset(buf, value, len)` | `void` | Fill `len` elements (`1..15`) of a RAM array |
| `memcpy(dst, src, len)` | `void` | Copy `len` elements (`1..15`) between same-type RAM arrays |

`memset`/`memcpy` accept a named RAM array as the buffer argument, not a
general pointer. `len` is a nibble, so up to 15 elements per call. Repeated
calls or a user loop can handle larger buffers.

## GPIO

The helpers honor `WrFlags.IOPos`; when `IOPos=0` they use `OUT`/`IN` at
`0x0A`/`0x0B`, and when `IOPos=1` they use `OutB`/`InB` at `0xFA`/`0xFB`.

| Call | Returns | Notes |
|---|---|---|
| `gpio_read()` | `nibble` | Read the 4-bit input port |
| `gpio_write(value)` | `void` | Write the 4-bit output latch |
| `gpio_set(mask)` | `void` | Read the output latch, OR `mask`, write back |
| `gpio_clear(mask)` | `void` | Read the output latch, AND `~mask`, write back |
| `gpio_toggle(mask)` | `void` | Read the output latch, XOR `mask`, write back |
| `gpio_test(mask)` | `nibble` | `1` if any masked input bit is set, else `0` |

The `WrFlags` routing helpers take a boolean (nonzero = enable):

| Call | Effect |
|---|---|
| `gpio_alt(enable)` | Set/clear `WrFlags.IOPos` (bit 1); moves OUT/IN to `0xFA`/`0xFB` |
| `uart_route(enable)` | Set/clear `WrFlags.RxTxPos` (bit 0); UART on SAO vs main connector |
| `leds_enable(enable)` | Enable = clear `WrFlags.LedsOff` (bit 3); disable = set it |
| `matrix_enable(enable)` | Enable = clear `WrFlags.MatrixOff` (bit 2); disable = set it |

`mask` is a nibble, e.g. `gpio_set(0b0010)` for bit 1.

## Display, buttons, and system SFRs

| Call | Returns | Notes |
|---|---|---|
| `display_page(page)` | `void` | Set the `Page` SFR (`0xF0`) |
| `display_poke(page, index, value)` | `void` | Write data address `(page << 4) | index` |
| `display_peek(page, index)` | `nibble` | Read data address `(page << 4) | index` |
| `random()` | `nibble` | Read the `Random` SFR (`0xFF`); each read advances it |
| `seed(n)` | `void` | Write the `Random` SFR; `15` requests a true-random seed |
| `dimmer(n)` | `void` | Set the LED dimmer (`0xFE`); `15` = brightest |
| `key_status()` | `nibble` | Read `KeyStatus` (`0xFC`); clears `JustPress` |
| `key_code()` | `nibble` | Read `KeyReg` (`0xFD`) |
| `key_any()` | `nibble` | `1` if any key other than ALT/ON-OFF is pressed |
| `key_alt()` | `nibble` | `1` if ALT is pressed |
| `key_just()` | `nibble` | `1` if a key was pressed since the last status read |
| `key_last()` | `nibble` | `1` if the key in `KeyReg` is currently pressed |
| `delay(n)` | `void` | Approximate busy delay; `n` units of a 15×15 inner loop |

`delay` is not calibrated to real time. Its duration changes with the
`Clock` SFR and the current CPU speed. Use `Sync`/`RdFlags` for
timing-critical work.

## Missing / planned

- `printf`-style formatted output
- `strlen`, `strcmp`, `strcpy` for RAM arrays
- General pointer arithmetic and `char *` parameters
- `memcpy`/`memset` lengths above 15
- Multiply/divide/shift operators
- `malloc` / free
- Interrupt-driven UART
- A calibrated millisecond delay
- A higher-level display/font library
