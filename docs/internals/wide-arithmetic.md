# 64-bit arithmetic

64-bit values occupy sixteen nibbles. Results use a dedicated memory buffer
rather than the register result convention.

## Representation

| Type | Nibbles | Byte order |
|---|---:|---|
| `uint64_t`, `u64` | 16 | Low nibble first |
| `int64_t`, `i64` | 16 | Low nibble first, two's complement |

A 64-bit variable costs sixteen nibbles of RAM. The compiler also reserves a
result buffer and temporary slots while a 64-bit expression is evaluated.

## Helpers

`lib/wide.nbl` provides the runtime helpers. The loader adds the module when a
program uses 64-bit arithmetic.

| Helper | Operation |
|---|---|
| `__nib_mul64(a, b)` | Unsigned multiply |
| `__nib_div64(a, b)` | Unsigned divide |
| `__nib_mod64(a, b)` | Unsigned modulo |
| `__nib_smul64(a, b)` | Signed multiply |
| `__nib_sdiv64(a, b)` | Signed divide |
| `__nib_smod64(a, b)` | Signed modulo |
| `uart_print_dec64(v)` | Unsigned decimal output |
| `uart_print_dec64_signed(v)` | Signed decimal output |
| `uart_print_hex64(v)` | Hex output |
| `uart_print_bin64(v)` | Binary output |

The print helpers are in `lib/wide.nbl` so programs that do not use 64-bit
values do not link them.

## Behavior

- Division by zero returns 0.
- Signed division truncates toward zero.
- Signed modulo takes the dividend's sign.
- The most-negative value divided by `-1` wraps to itself.

## Limits

64-bit multiply and divide are iterative and use several temporary slots. Use
them only where the range is required. The print helpers can exceed the
five-entry hardware call stack for some formats; verify stack depth with
`--stack`.
