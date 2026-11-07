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

Integer types are `nibble` (4-bit), `char` (8-bit), `word` (16-bit), and
`dword` (32-bit), all unsigned. Widening is implicit; narrowing needs a cast:

```c
dword wide = 100000;
char low = (char)wide;       // low byte
nibble n = (nibble)wide;     // low nibble
word mid = (word)wide;       // low word
dword again = (dword)mid;    // zero-extended
```

Scalar `const` values are compile-time immediates, so pin names can be used
directly in the fast GPIO path:

```c
const nibble EPD_SER   = 1;
const nibble EPD_SRCLK = 2;
const nibble EPD_DATA  = 4;
const nibble EPD_CLOCK = EPD_SRCLK | EPD_DATA;

gpio_set(EPD_SER);
gpio_toggle(EPD_CLOCK);   // lowers to BTG R3,1 / BTG R3,2
```

They consume no RAM. The initializer can use literals, other scalar consts,
casts, arithmetic, shifts, bitwise operators, and comparisons.

| Call | Returns | Notes |
|---|---|---|
| `high_nibble(c)` | `nibble` | High nibble of a char |
| `low_nibble(c)` | `nibble` | Low nibble of a char |

| Operator | Behavior |
|---|---|
| `+ - & \| ^` | Common width, wrapping |
| `<< >>` | Constant count, unrolled; full-width or more gives zero |
| `*` | Widens one step: `nibble*nibble -> char`, `char*char -> word`; `word*word -> word`, `dword*dword -> dword` (low bits) |
| `/ %` | Common width, unsigned; division by zero gives zero |

`<<`/`>>` accept both constant counts (unrolled) and variable counts (a
small loop). All widths are supported. The `lib/math.badge` helpers remain
as thin wrappers for older code.

32-bit `*`, `/`, and `%` reserve a 24-nibble scratch block in user RAM, but
only when those operators are used. This keeps dword-free programs at the
full 176-nibble budget.

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

When `mask` is a compile-time constant (`0..15`), `gpio_set`, `gpio_clear`,
and `gpio_toggle` lower directly to `BSET`/`BCLR`/`BTG R3,n` with no runtime
call. A single-bit `gpio_test` lowers to `BIT R3,n` and a four-word 0/1
materialization. Multi-bit `gpio_test` and non-constant masks keep the
runtime path. This also removes the GPIO helpers' stack cost from hot
bit-bang loops.

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
| `uart_print_hex32(d)` | Eight hex digits |
| `uart_print_dec32(d)` | Decimal `0..4294967295`, no leading zeros |
| `uart_print_dec8_signed(c)` | Signed decimal for a raw two's-complement char |
| `uart_print_dec16_signed(w)` | Signed decimal for a raw two's-complement word |
| `uart_print_str(addr)` | RAM byte string, `0xFF` terminated |
| `uart_print_hexdump(addr, len)` | `len` bytes as hex plus a newline |
| `uart_read_nibble()` | Read one hex digit |
| `uart_read_hex8()` | Read two hex digits into a char |
| `uart_read_line(addr, max)` | Read until CR/LF; returns byte count |

### `lib/spi.badge`

Bit-banged SPI mode 0 on the main I/O connector. Default pins:

| Signal | Badge pin |
|---|---|
| `SCLK` | OUT2 |
| `MOSI` | OUT3 |
| `CS` | OUT1 |
| `MISO` | IN0 |

| Call | Notes |
|---|---|
| `spi_init()` | Select GPIO bank 0, CS high, clock/data low |
| `spi_begin()` / `spi_end()` | Assert / release CS |
| `spi_xfer(byte)` | Exchange one byte, MSB first |

### `lib/w5500.badge`

Minimal W5500 register/socket access over `lib/spi.badge`. Assumes W5500
`RST` is on OUT0.

| Call | Notes |
|---|---|
| `w5500_reset()` | Release RST high; does not pulse it low |
| `w5500_read(bsb, addr_hi, addr_lo)` | Read one register byte |
| `w5500_write(bsb, addr_hi, addr_lo, value)` | Write one register byte |
| `w5500_read16` / `w5500_write16` | 16-bit big-endian registers |
| `w5500_version()` | `VERSIONR`, should return `0x04` |
| `w5500_phy()` | `PHYCFGR`; bit 0 is link status |
| `w5500_open_udp(port_hi, port_lo)` | Open socket 0 as UDP |
| `w5500_open_tcp(port_hi, port_lo)` | Open socket 0 as a TCP listener |
| `w5500_send_flash(msg)` | Send a flash string through socket 0 |
| `w5500_discard_rx()` | Read and discard up to 200 received bytes |

`examples/w5500_udp.badge` configures badge `192.168.1.50`, sends
`hello from badge\n` to `192.168.1.10:5001` from source port `5000`, and
prints status on the main UART.

`examples/w5500_http.badge` runs a minimal TCP listener on port 80 and returns
a short `200 OK` response. With the host at `192.168.1.10`:

```bash
curl http://192.168.1.50/
```

The W5500 needs a clean 3.3 V supply and about 130 mA. Do not assume the
badge's battery `+3V` rail is suitable; use a separate 3.3 V supply with a
common ground for bring-up.

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

### `lib/signed.badge`

BadgeC's types are unsigned, so these helpers interpret the raw bits of
`nibble`, `char`, and `word` as two's complement:

| Raw type | Signed range |
|---|---|
| `nibble` | -8 .. 7 |
| `char` | -128 .. 127 |
| `word` | -32768 .. 32767 |

Negative values are passed and returned as raw bit patterns (`15`, `255`,
`0xFFFF`). Unused helpers are removed by the compiler.

| Call | Notes |
|---|---|
| `s_neg4/8/16(v)` | Two's-complement negate |
| `s_abs4/8/16(v)` | Magnitude as raw bits |
| `s_is_neg4/8/16(v)` | `1` when negative |
| `s_lt4/8/16(a,b)`, `s_le...`, `s_gt...`, `s_ge...` | Signed comparisons |
| `s_min4/8/16`, `s_max4/8/16` | Signed min/max |
| `s_clamp4/8/16(v, low, high)` | Signed clamp |
| `s_ext4(v)` | Sign-extend nibble to char |
| `s_ext8(v)` | Sign-extend char to word |
| `s_ext16(v)` | Sign-extend word to dword |
| `s_sar4/8/16(v, n)` | Arithmetic right shift |
| `s_mul4(a,b)` | 8-bit signed product of two nibbles |
| `s_mul4_nib(a,b)` | Low nibble of `s_mul4` |
| `s_mul8(a,b)` | Low 8 bits of the signed product |
| `s_mul16(a,b)` | Low 16 bits of the signed product |
| `s_div4/8/16`, `s_mod4/8/16` | Signed division / remainder |

Signed division truncates toward zero, division by zero returns `0`, and the
most-negative value divided by `-1` wraps to itself. The result of `s_mul8`
and `s_mul16` is the low half of the exact signed product.

### `lib/fixed.badge`

Q4.4 signed fixed point in a `char`: raw value divided by 16, range
-8.0 .. +7.9375, resolution 1/16.

| Call | Notes |
|---|---|
| `q4_4_add/sub(a,b)` | Wrapping add/subtract |
| `q4_4_neg(v)` | Negate |
| `q4_4_mul(a,b)` | Q4.4 multiply, wrapping |
| `q4_4_div(a,b)` | Q4.4 divide, wrapping; zero divisor gives 0 |
| `q4_4_from_int(v)` | Signed nibble to Q4.4 |
| `q4_4_to_int(v)` | Q4.4 to signed nibble, truncating toward zero |
| `q4_4_min/max(a,b)` | Signed min/max |
| `q4_4_clamp(v, low, high)` | Signed clamp |

Q4.4 is a pragmatic format for 8-bit signed quantities on this CPU. A
16-bit Q8.8 module would need signed 32-bit products and arithmetic shifts,
which are deliberately not part of this prototype.

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
- 64-bit integers
- Native signed types; `lib/signed.badge` currently provides raw-bit helpers
- Signed 32-bit arithmetic and Q8.8 fixed point
- `malloc` / free
- Interrupt-driven UART
- A calibrated millisecond delay
- A font/text drawing library on top of `lib/display.badge`
- Bit-banged I2C/SPI helpers
