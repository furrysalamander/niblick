# Intrinsics

Intrinsics are recognized by the compiler. They lower to inline instructions or
to routines in `niblick/runtime/runtime.asm`. They are not declared with
`fn` and cannot be redefined.

## Memory

| Call | Returns | Behavior |
|---|---|---|
| `peek(addr)` | `nibble` | Read one nibble from 8-bit data address `addr` |
| `poke(addr, value)` | `void` | Write one nibble |
| `peek8(addr)` | `char` | Read a byte from `addr` (low) and `addr + 1` (high) |
| `poke8(addr, value)` | `void` | Write a byte to `addr` and `addr + 1` |
| `flash_read_char(p)` | `char` | Read a byte from code address `p` |
| `flash_read_nibble(p)` | `nibble` | Read a nibble from code address `p` |
| `flash_next(&p)` | `char` | Read a byte and advance `p` by two code words |

`flash_next` requires a mutable `flashptr` variable. The address is advanced
in place.

## I/O

| Call | Returns | Behavior |
|---|---|---|
| `in()` | `nibble` | Read the bank-0 input port |
| `out(value)` | `void` | Write the bank-0 output latch |
| `gpio_set(mask)` | `void` | Set output bits in `mask` |
| `gpio_clear(mask)` | `void` | Clear output bits in `mask` |
| `gpio_toggle(mask)` | `void` | Toggle output bits in `mask` |
| `gpio_test(mask)` | `nibble` | Return 1 when any bit in `mask` is set |

`mask` is a `nibble`. A constant mask lowers to `BSET`, `BCLR`, `BTG`, or
`BIT`. A variable mask calls the runtime routine. `gpio_test` with a
single-bit constant mask lowers to `BIT`.

## UART

| Call | Returns | Behavior |
|---|---|---|
| `uart_putc(c)` | `void` | Write one byte |
| `uart_getc()` | `char` | Wait for and read one byte |

`lib/uart.nbl` adds setup, buffering helpers, and formatting. See
{doc}`uart`.

## Timing

| Call | Behavior |
|---|---|
| `delay(n)` | Busy loop; `n` is a `nibble` |

The duration depends on the `Clock` SFR. `lib/time.nbl` implements Sync-based
delays.

## W5500 fast path

| Call | Returns | Behavior |
|---|---|---|
| `w5500_spi_tx_fast(v)` | `void` | Write one byte through the W5500 SPI fast path |
| `w5500_spi_xfer_fast(v)` | `char` | Exchange one byte through the W5500 SPI fast path |

These intrinsics are part of `lib/drivers/w5500.nbl`. They are not general SPI
API. See {doc}`spi` and {doc}`drivers/w5500`.

## Formatting

| Call | Behavior |
|---|---|
| `print(format, ...)` | Compile-time format expansion; see {doc}`formatting` |

`print` is a statement, not an expression. The format string must be a
literal.

## Nibble helpers

| Call | Returns | Behavior |
|---|---|---|
| `high_nibble(c)` | `nibble` | High nibble of a `char` |
| `low_nibble(c)` | `nibble` | Low nibble of a `char` |

## Internal builtins

The compiler also uses `__nib_f16_bits`, `__nib_f16_from_bits`,
`__nib_f32_bits`, and `__nib_f32_from_bits` for float bit access. They are not
part of the public library interface. See {doc}`../internals/soft-float`.
