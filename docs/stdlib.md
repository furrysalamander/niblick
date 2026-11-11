# BadgeC standard library

BadgeC has three library layers:

- **Intrinsics** are recognized by the compiler and lowered to inline code or
  calls into `badgec/runtime/runtime.asm`.
- **Standard modules** are ordinary BadgeC files under `lib/`, pulled in with
  `import`.
- **Drivers** are device-specific modules under `lib/drivers/`, also imported
  explicitly. They are not part of the standard library.

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
modules use `0xFF` as the terminator, matching flash strings and `uart_puts`.

## Why some helpers are builtins

The compiler has no inlining or call-graph local overlay yet. A BadgeC function
uses static parameter and local slots in user RAM, and its body is compiled by
the normal code generator. Hand-written runtime assembly is smaller, uses
registers instead of RAM slots, and does not add a user call-depth level.
That is why a small set of hot or deeply nested helpers stays intrinsic:

| Intrinsic | Reason |
|---|---|
| `peek`, `poke`, `peek8`, `poke8` | BadgeC has no pointer dereference |
| `flash_read_char`, `flash_read_nibble`, `flash_next` | Code-memory access and flash iteration |
| `in`, `out` | Raw page-0 I/O port operations |
| `gpio_set`, `gpio_clear`, `gpio_toggle`, `gpio_test` | Constant masks lower to `BSET`/`BCLR`/`BTG`/`BIT` |
| `gpio_alt` | Tiny WrFlags route helper; kept for size, RAM, and stack depth |
| `uart_putc`, `uart_getc` | Hot UART handshake/FIFO byte access |
| `delay` | Hot busy loop used by drivers at deep call sites |
| `high_nibble`, `low_nibble` | Tiny hot formatting helpers |
| `w5500_spi_tx_fast`, `w5500_spi_xfer_fast` | W5500-specific runtime fast paths, not standard API |
| `mul*`, `divmod*`, flash word/dword reads | Compiler-generated arithmetic and data access |

Everything else is ordinary library code. When a library wrapper is used, its
parameter and local slots remain allocated for the life of the program, so
RAM-constrained programs should prefer the intrinsic where one exists.

## Intrinsics

| Call | Returns | Notes |
|---|---|---|
| `peek(addr)` / `poke(addr, value)` | `nibble` / `void` | One nibble at an 8-bit data address |
| `peek8(addr)` / `poke8(addr, value)` | `char` / `void` | One byte across two nibbles |
| `flash_read_char(p)` / `flash_read_nibble(p)` | `char` / `nibble` | Random read from a flash table |
| `flash_next(&p)` | `char` | Intrinsic iterator; advances a `flashptr` by 2 words |
| `in()` / `out(v)` | `nibble` / `void` | Raw bank-0 I/O port |
| `gpio_set(mask)` / `gpio_clear(mask)` / `gpio_toggle(mask)` | `void` | Constant masks become single bit instructions |
| `gpio_test(mask)` | `nibble` | `BIT` for a single-bit constant mask |
| `gpio_alt(enable)` | `void` | Set/clear `WrFlags.IOPos` (bit 1) |
| `uart_putc(c)` / `uart_getc()` | `void` / `char` | Blocking UART byte I/O |
| `delay(n)` | `void` | Approximate 15x15 busy delay |
| `high_nibble(c)` / `low_nibble(c)` | `nibble` | Byte halves |

## UART

`lib/uart.badge` provides the driver and formatting helpers.

| Call | Returns | Notes |
|---|---|---|
| `uart_init(baud)` | `void` | Baud index `0..7`; `3` = 9600 |
| `uart_available()` | `nibble` | Bytes waiting, saturating at 15 |
| `uart_puts(s)` / `puts(s)` | `void` | Stream a flash string until `0xFF` |
| `uart_write(addr, len)` | `void` | Send `len` bytes (`1..15`) from a RAM `char[]`; pass `&buf` |
| `uart_putc(c)` / `putchar(c)` | `void` | Send one byte |
| `uart_getc()` | `char` | Wait for and return one byte |
| `uart_error()` | `nibble` | Sticky UART error; reading clears it |
| `uart_baud()` | `nibble` | Current baud index; reading also clears the error |
| `uart_drain()` | `void` | Read and discard all currently available bytes |
| `uart_route(enable)` | `void` | UART on main connector (`1`) or SAO (`0`) |
| `uart_nl()` | `void` | Send LF |
| `uart_print_nibble(v)` | `void` | One hex digit |
| `uart_print_hex8(c)` | `void` | Two hex digits |
| `uart_print_bin8(c)` | `void` | Eight binary digits |
| `uart_print_dec8(c)` | `void` | Decimal `0..255` |
| `uart_print_hex16(w)` / `uart_print_dec16(w)` | `void` | 16-bit formatting |
| `uart_print_hex32(d)` / `uart_print_dec32(d)` | `void` | 32-bit formatting |
| `uart_print_dec8_signed(c)` / `uart_print_dec16_signed(w)` | `void` | Signed raw two's-complement |
| `uart_print_str(addr)` | `void` | RAM byte string |
| `uart_print_hexdump(addr, len)` | `void` | Hex dump plus newline |
| `uart_read_nibble()` / `uart_read_hex8()` | `nibble` / `char` | Read hex input |
| `uart_read_line(addr, max)` | `nibble` | Read until CR/LF; returns count |

## GPIO

`lib/gpio.badge` provides bank-aware read/write; the optimization builtins
remain available for output bits.

| Call | Returns | Notes |
|---|---|---|
| `gpio_read()` | `nibble` | Read the active input port (honors `IOPos`) |
| `gpio_write(v)` | `void` | Write the active output latch |
| `gpio_set/clear/toggle/test` | see above | Intrinsics with constant-mask lowering |
| `gpio_alt(enable)` | `void` | Intrinsic: move OUT/IN to `0xFA`/`0xFB` |

## Display

`lib/display.badge` covers pages, the 8x16 framebuffer, PWM, and matrix
control. A framebuffer is 32 nibbles: two nibbles per row, row-major; `base`
is the array's nibble address (`&screen`).

| Call | Returns | Notes |
|---|---|---|
| `display_page(page)` / `display_page_get()` | `void` / `nibble` | `Page` SFR |
| `display_poke(page, index, value)` / `display_peek(page, index)` | `void` / `nibble` | Page data access |
| `display_show(base)` | `void` | Select the two pages containing a framebuffer |
| `dimmer(n)` / `dimmer_get()` | `void` / `nibble` | LED PWM duty |
| `leds_enable(enable)` / `matrix_enable(enable)` | `void` | ALU panel LEDs / matrix |
| `display_fill(page, value)` / `display_clear(page)` / `display_invert(page)` | `void` | Whole-page operations |
| `display_copy(src, dst)` | `void` | Copy one page |
| `pixel_get(base, x, y)` | `nibble` | Pixel test |
| `pixel_set(base, x, y, on)` / `pixel_toggle` / `pixel_clear` | `void` | Pixel edits |
| `hline(base, x0, x1, y, on)` / `vline` | `void` | Straight lines |
| `fill_rect(base, x0, y0, x1, y1, on)` | `void` | Filled rectangle |
| `clear_screen(base)` | `void` | Zero all 32 nibbles |
| `display_shift_left(base)` | `void` | Shift the framebuffer one pixel left |
| `display_set_column(base, x, bits)` | `void` | Set one column from an 8-bit value |

Bit 3 is the leftmost pixel in each nibble and bit 0 the rightmost, matching
the badge hardware.

## Keys

`lib/key.badge` exposes the debounced key state. Reading `KeyStatus` clears
`JustPress`; use the `*_of(status)` helpers when testing several bits from one
read.

| Call | Returns | Notes |
|---|---|---|
| `key_status()` / `key_code()` | `nibble` | Raw `KeyStatus` / `KeyReg` |
| `KEY_ALT`, `KEY_ANY`, `KEY_LAST`, `KEY_JUST` | constants | Status bit masks |
| `key_alt_of(status)` / `key_any_of` / `key_just_of` / `key_last_of` | `nibble` | Test an already-read status |
| `key_alt()` / `key_any()` / `key_just()` / `key_last()` | `nibble` | Convenience wrappers; each reads status |
| `key_down(code)` | `nibble` | Named key is currently held |
| `key_op8/op4/op2/op1()`, `key_dep()` | `nibble` | Measured key codes |
| `key_wait()` / `key_wait_release()` / `key_wait_any()` | `nibble` | Blocking helpers |
| `key_name(code)` | `flashptr` | Flash string name |

## Time

`lib/time.badge` provides Clock/Sync control and delays.

| Call | Notes |
|---|---|
| `time_clock_set(index)` / `time_clock_get()` | `Clock` SFR |
| `time_sync_set(index)` / `time_sync_get()` | `Sync` SFR |
| `time_sync_seen()` | Read and clear `UserSync` |
| `time_sync_wait()` | Block until the next `UserSync` |
| `time_delay_frames(count)` | Wait for sync frames |
| `time_delay(units)` | Approximate busy delay |
| `time_delay_ms(ms)` | Millisecond-ish delay using `Sync=0` (1 ms ticks) |
| `time_delay_ticks(ticks, divider)` | Wait for ticks at a chosen Sync divider |

Clock constants: `CLOCK_250K`, `CLOCK_100K`, `CLOCK_30K`, `CLOCK_10K`,
`CLOCK_3K`, `CLOCK_1K`, `CLOCK_500`, `CLOCK_200`, `CLOCK_100`, `CLOCK_50`,
`CLOCK_20`, `CLOCK_10`, `CLOCK_5`, `CLOCK_2`, `CLOCK_1`, `CLOCK_0_5`.

Sync constants: `SYNC_1000HZ` through `SYNC_1HZ`.

## Power and status

`lib/power.badge` exposes the `AutoOff` down-counter:

| Call | Notes |
|---|---|
| `power_keep_awake()` | Write 15 to `AutoOff` |
| `power_auto_off(units)` | Write raw 10-minute units; 0 sleeps |
| `power_auto_off_minutes(minutes)` | Convert minutes to 10-minute units |
| `power_sleep()` | Write 0: enter SLEEP immediately |
| `power_remaining()` | Read the current counter |

`lib/system.badge` provides raw status/control access:

| Call | Notes |
|---|---|
| `system_wr_flags()` / `system_wr_flags_set(flags)` | `WrFlags` raw access |
| `system_rd_flags()` | Raw `RdFlags`; clears `UserSync` |
| `system_vflag()` | `RdFlags.Vflag`; also clears `UserSync` |
| `system_user_sync()` | `RdFlags.UserSync` |
| `system_ser_ctrl()` | Raw `SerCtrl`; clears the UART error |
| `system_uart_error()` / `system_uart_baud()` | UART error / baud; each clears the error |
| `system_page()` / `system_dimmer()` | `Page` / `Dimmer` read-back |

Constants: `WR_LEDS_OFF`, `WR_MATRIX_OFF`, `WR_IO_POS`, `WR_RX_TX_POS`,
`RD_VFLAG`, `RD_USER_SYNC`.

## Random

`lib/random.badge`:

| Call | Returns | Notes |
|---|---|---|
| `random()` | `nibble` | Read the hardware PRNG; each read advances it |
| `seed(n)` / `rand_seed(n)` | `void` | Reseed; `15` requests true random |
| `rand_byte()` / `rand_word()` | `char` / `word` | Multi-read helpers |
| `rand_below(n)` | `nibble` | Uniform `0..n-1` |
| `rand_range(lo, hi)` | `nibble` | Inclusive range |
| `rand_true()` | `nibble` | Request a true-random seed, then read |

## Memory

`lib/mem.badge` starts with nibble helpers and adds byte-oriented, 16/32-bit,
search, and checksum helpers. Addresses are nibble addresses; a byte occupies
two consecutive nibbles.

| Call | Notes |
|---|---|
| `mem_fill(addr, value, len)` / `mem_zero` / `mem_copy` / `mem_cmp` / `mem_swap` | Nibble arrays |
| `mem_fill8(addr, value, len)` / `mem_zero8` / `mem_copy8` / `mem_cmp8` / `mem_swap8` | Byte arrays |
| `mem_move8(dst, src, len)` | Overlap-safe byte move |
| `mem_search8(addr, len, value)` | Address of first match, or 0 |
| `mem_reverse8(addr, len)` | Reverse a byte range |
| `mem_popcount8(value)` | Number of set bits |
| `mem_sum8(addr, len)` / `mem_crc8(addr, len, seed)` | 8-bit sum / CRC-8/ATM |
| `mem_peek16_le/be(addr)` / `mem_poke16_le/be(addr, value)` | 16-bit access |
| `mem_peek32_le/be(addr)` / `mem_poke32_le/be(addr, value)` | 32-bit access |
| `mem_bit_test/set/clear/toggle(addr, bit)` | Nibble bit operations |

## Strings

`lib/string.badge` handles RAM byte strings terminated by `0xFF`.

| Call | Notes |
|---|---|
| `str_len(addr)` / `str_eq(a, b)` | Length / exact compare |
| `str_copy(dst, src)` / `str_cat(dst, src)` | Copy / append |
| `str_chr(addr, ch)` | Address of first match, or 0 |
| `str_len_flash(p)` / `str_copy_flash(dst, p)` | Flash strings |
| `str_from_dec8(addr, value)` / `str_from_hex8(addr, value)` | Format into RAM |
| `str_to_dec8(addr)` / `str_to_hex8(addr)` | Parse from RAM |
| `str_find(addr, needle)` | Address of a flash substring, or 0 |
| `str_contains` / `str_starts_with` / `str_eq_flash` | Flash-string tests |
| `str_cat_flash(dst, p)` | Append a flash string |
| `str_compare(a, b)` | `STR_LT`, `STR_EQ`, or `STR_GT` |
| `str_upper(addr)` / `str_lower(addr)` | In-place case conversion |
| `str_reverse(addr)` / `str_trim(addr)` | In-place reverse / trim; trim returns the new start |

## Math

`lib/math.badge`:

| Call | Returns | Notes |
|---|---|---|
| `math_min(a, b)` / `math_max` / `math_clamp` | `nibble` | Nibble helpers |
| `math_min8` / `math_max8` / `math_clamp8` / `math_abs_diff8` | `char` | 8-bit helpers |
| `math_map8(v, in_min, in_max, out_min, out_max)` | `char` | Clamped unsigned linear map |
| `math_mul`, `math_div`, `math_mod`, `math_div8`, `math_mod8` | various | Nibble/char arithmetic |
| `math_isqrt(c)` / `math_sqrt16(w)` | `nibble` / `char` | Integer square roots |
| `math_pow2(n)` | `char` | Power of two |
| `math_gcd8(a, b)` / `math_lcm8(a, b)` | `char` / `word` | GCD / LCM |
| `math_sign8(v)` / `math_wrap8(v, mod)` / `math_div_round8(a, b)` | raw sign / wrapped / rounded | Signed and rounding helpers |

`lib/signed.badge` interprets raw bits as two's complement and provides
comparison, clamp, sign-extension, arithmetic-shift, multiply, divide, and
modulo helpers. `lib/fixed.badge` adds Q4.4 fixed point.

`lib/trig.badge` provides a 32-step Q4.4 sine/cosine table:

```c
char s = sin_q4_4(8);   // 0x10 = 1.0
char c = cos_q4_4(0);   // 0x10 = 1.0
```

## Font and text

`lib/font.badge` contains a 5x8 font covering ASCII 32..127 and
`text_draw_char(base, x, y, c)`. The glyph data is adapted from the upstream
Hack-a-Day 2022 Supercon.6 Hamlet scroller demo by Voja Antonic; see
[THIRD_PARTY_NOTICES.md](../THIRD_PARTY_NOTICES.md).

`lib/textscroll.badge` provides a horizontal scroller:

```c
nibble screen[32];

fn main() {
    matrix_enable(1);
    dimmer(15);
    clear_screen(&screen);
    text_scroll_loop(&screen, "HELLO  ", SYNC_10HZ);
}
```

The scroller uses the top eight rows of the 8x16 framebuffer and advances one
column per `UserSync` tick. A 5x8 glyph is five columns wide, so static text
can show at most one full glyph across an eight-column row; the scroller is the
natural way to display longer strings.

## Audio and PDM

`lib/audio.badge` bit-bangs a square wave on `OUT0` by default. Connect the
pin to a low-pass filter and an amplifier. The note table is calibrated for
`CLOCK_100K`; the upstream Tom Keddie demos used the same clock and frequencies
(C4 261 Hz, D4 293 Hz, E4 330 Hz, G4 392 Hz, A4 440 Hz, B4 494 Hz, C5 523 Hz).

| Call | Notes |
|---|---|
| `audio_init()` | Select `CLOCK_100K` |
| `audio_tone_raw(half_period, cycles)` | Raw square wave |
| `audio_note(note, cycles)` | Note 0..15 from the table; 15 is a rest |
| `audio_play(melody)` | Flash note/duration byte pairs, terminated by `0xFF` |
| `audio_silence()` | Drive the output low |

`lib/pdm.badge` implements the upstream first-order PDM encoder. It drives
OUT bits 1–3 (bit 0 stays 1) and expects a low-pass filter and amplifier.
`pdm_encode(sample)` is the tight-loop primitive; `pdm_play(samples)` and
`pdm_play_loop(samples)` stream a flash sample table terminated by `0xFF`.

Audio timing depends on the Clock SFR, the compiler version, and the actual
instruction mix. Measure the pitch on hardware and adjust the note table or
`audio_tone_raw` counts if needed.

## SPI and drivers

`lib/spi.badge` is a generic bit-banged SPI mode-0 master. The W5500 Ethernet
driver is a separate device driver under `lib/drivers/`; see
[drivers/w5500.md](drivers/w5500.md).

## Missing / planned

- A `printf`-style formatter (the language has no varargs)
- General pointer arithmetic, `char *` parameters, and structs
- Native signed types and 64-bit integers
- Q8.8 fixed point
- `malloc` / free
- Interrupt-driven UART
- Bit-banged I2C/1-Wire helpers
- A fully calibrated millisecond/audio timing model
- More static-text layout helpers for the 5x8 font
