# BadgeC standard library

BadgeC has two library layers:

- **Builtins** are recognized by the compiler and lowered to inline code or
  calls into `badgec/runtime/runtime.asm`.
- **Modules** are ordinary BadgeC files under `lib/`, pulled in with
  `import`.

```c
import "lib/uart.badge";
import "lib/string.badge";

char buf[16];

fn main() {
    uart_route(1);
    uart_init(3);
    str_copy_flash(&buf, "hi");
    uart_print_str(&buf);
    uart_nl();
}
```

Imports resolve relative to the importing file first, then the repository
root; `BADGEC_PATH` can add more search roots. Each file is loaded once and
import cycles are reported. Imported declarations are compiled together with
the main program, and the compiler removes any function or pure global that
is still unreachable, so an unused module costs neither code nor RAM.

`&array` yields the base **nibble address** of a RAM array. A `char` occupies
two consecutive nibbles, so byte strings advance by 2 per character. String
modules use `0xFF` as the terminator, matching flash strings and
`uart_puts`.

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
| `peek8(addr)` | `char` | Read a full byte (`addr` and `addr + 1`) |
| `poke8(addr, value)` | `void` | Write a full byte across two nibbles |
| `memset(buf, value, len)` | `void` | Fill `len` elements (`1..15`) of a RAM array |
| `memcpy(dst, src, len)` | `void` | Copy `len` elements (`1..15`) between same-type RAM arrays |

`memset`/`memcpy` accept a named RAM array as the buffer argument, not a
general pointer. `len` is a nibble, so up to 15 elements per call. Repeated
calls or a user loop can handle larger buffers.

## Numbers, casts, and operators

Integer types are `nibble` (4-bit), `char` (8-bit), and `word` (16-bit), all
unsigned. Widening is implicit; narrowing needs a cast:

```c
word w = 1000;
char low = (char)w;      // low byte
nibble n = (nibble)w;    // low nibble
word again = (word)low;  // zero-extended
```

| Call | Returns | Notes |
|---|---|---|
| `high_nibble(c)` | `nibble` | High nibble of a char |
| `low_nibble(c)` | `nibble` | Low nibble of a char |

| Operator | Behavior |
|---|---|
| `+ - & \| ^` | Common width, wrapping |
| `<< >>` | Constant count, unrolled; full-width or more gives zero |
| `*` | Widens one step: `nibble*nibble -> char`, `char*char -> word`, `word*word -> word` (low 16 bits) |
| `/ %` | Common width, unsigned; division by zero gives zero |

`<<`/`>>` use a constant count; variable counts are rejected for now. The
`lib/math.badge` helpers remain as thin wrappers for older code.

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

## Library modules

These live in `lib/` and are opt-in via `import`. Unused functions and pure
globals are removed, so importing a module is free unless you call it.

### `lib/uart.badge`

| Call | Notes |
|---|---|
| `uart_nl()` | Send LF |
| `uart_print_nibble(v)` | One hex digit, `0..F` |
| `uart_print_hex8(c)` | Two hex digits |
| `uart_print_bin8(c)` | Eight binary digits |
| `uart_print_dec8(c)` | Decimal, no leading zeros (`0..255`) |
| `uart_print_hex16(w)` | Four hex digits |
| `uart_print_dec16(w)` | Decimal `0..65535`, no leading zeros |
| `uart_print_str(addr)` | RAM byte string, `0xFF` terminated |
| `uart_print_hexdump(addr, len)` | `len` bytes as hex plus a newline |
| `uart_read_nibble()` | Read one hex digit |
| `uart_read_hex8()` | Read two hex digits into a char |
| `uart_read_line(addr, max)` | Read until CR/LF; returns byte count |

### `lib/string.badge`

Byte strings in RAM at a nibble address; terminator `0xFF`.

| Call | Notes |
|---|---|
| `str_len(addr)` | Length in bytes |
| `str_eq(a, b)` | `1` when identical |
| `str_copy(dst, src)` | Copy including terminator |
| `str_cat(dst, src)` | Append `src` at the end of `dst` |
| `str_chr(addr, ch)` | Address of the first match, or `0` |
| `str_len_flash(p)` | Length of a flash string |
| `str_copy_flash(dst, p)` | Copy a flash string into RAM |

### `lib/math.badge`

All values unsigned. Callers must not pass a zero divisor.

| Call | Returns |
|---|---|
| `math_min(a, b)`, `math_max(a, b)` | `nibble` |
| `math_clamp(v, low, high)` | `nibble` |
| `math_abs_diff(a, b)` | `nibble` |
| `math_mul(a, b)` | `char` (`a,b` are nibbles) |
| `math_div(a, b)`, `math_mod(a, b)` | nibble / nibble |
| `math_div8(c, b)` | `char` / nibble |
| `math_mod8(c, b)` | remainder as a nibble |
| `math_isqrt(c)` | nibble |
| `math_pow2(n)` | `char`; zero when `n >= 8` |

### `lib/mem.badge`

These operate on **nibbles**, one address step per element.

| Call | Notes |
|---|---|
| `mem_fill(addr, value, len)` | Fill `len` nibbles |
| `mem_zero(addr, len)` | Fill with zero |
| `mem_copy(dst, src, len)` | Copy `len` nibbles |
| `mem_cmp(a, b, len)` | `0` equal, `1` different |
| `mem_swap(a, b)` | Swap two nibbles |
| `mem_bit_test(addr, bit)` | `1` when set |
| `mem_bit_set/clear/toggle(addr, bit)` | Bit operations |
| `mem_popcount(v)` | Number of set bits in a nibble |

### `lib/display.badge`

Page helpers write directly to the 16-nibble display pages. Framebuffer
helpers treat a 32-nibble RAM array as 8×16 pixels, two nibbles per row,
row-major; pass `&screen` as the base address.

| Call | Notes |
|---|---|
| `display_fill(page, value)` | Fill all 16 nibbles of a page |
| `display_clear(page)` / `display_invert(page)` | Clear / invert a page |
| `display_copy(src, dst)` | Copy one page to another |
| `pixel_get(base, x, y)` | `1` when the pixel is set |
| `pixel_set(base, x, y, on)` | Set or clear a pixel |
| `pixel_toggle(base, x, y)` / `pixel_clear(base, x, y)` | Pixel edits |
| `hline(base, x0, x1, y, on)` / `vline(...)` | Row / column |
| `fill_rect(base, x0, y0, x1, y1, on)` | Filled rectangle |
| `clear_screen(base)` | Zero all 32 nibbles |

`display_page(high_nibble(&screen))` selects the page that contains the
buffer, which is useful when the allocator chooses the address.

### `lib/key.badge`

| Call | Notes |
|---|---|
| `key_op8()` / `key_op4()` / `key_op2()` / `key_op1()` | Measured `KeyReg` codes |
| `key_dep()` | DEP+ / CLOCK / STEP code (`0`) |
| `key_wait()` | Block for a new press, return its code |
| `key_wait_release()` | Wait for press and release |
| `key_wait_any()` | Wait for any non-ALT key |
| `key_name(code)` | Flash string name |

### `lib/time.badge`

| Call | Notes |
|---|---|
| `time_clock_set(divider)` / `time_clock_get()` | `Clock` SFR |
| `time_sync_set(divider)` | `Sync` SFR |
| `time_sync_seen()` | Read and clear `UserSync` |
| `time_sync_wait()` | Block until the next `UserSync` |
| `time_delay_frames(n)` | Wait for `n` sync frames |

## Missing / planned

- A `printf`-style formatter (the language has no varargs)
- General pointer arithmetic and `char *` parameters
- Byte-oriented `mem*` helpers (current ones are nibble-oriented)
- `*`, `/`, and `%` operators (library helpers exist)
- Variable shift counts
- `malloc` / free
- Interrupt-driven UART
- A calibrated millisecond delay
- A font/text drawing library on top of `lib/display.badge`
- Bit-banged I2C/SPI helpers
