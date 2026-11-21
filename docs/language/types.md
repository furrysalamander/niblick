# Types

Niblick has explicit-width integer types. There are no general pointers.

`bool`, `flashptr`, `half`, and `float` are distinct types.

## Type spellings

> If you're wondering why the signed vs unsigned stuff is a little inconsistent, that's primarily because signed types were a later addition to the language, and also I figure most people probably won't want to use signed types for the smaller types, and so it felt unwieldy to make signed the default. But for larger types, I'm used to specifying the exact size and signedness when working in other languages anyways, so if you're like me in that regard then you'll probably be fine.

| Canonical | Width | RAM | Signed | Aliases |
|---|---:|---:|---|---|
| `nibble` | 4 | 1 nibble | no | `u4` |
| `i4` | 4 | 1 nibble | yes | |
| `char` | 8 | 2 nibbles | no | `u8`, `byte`, `uint8_t`, `uint_least8_t`, `uint_fast8_t` |
| `i8` | 8 | 2 nibbles | yes | `int8_t`, `int_least8_t`, `int_fast8_t` |
| `uint16_t` | 16 | 4 nibbles | no | `u16`, `uint_least16_t`, `uint_fast16_t` |
| `i16` | 16 | 4 nibbles | yes | `int16_t`, `int_least16_t`, `int_fast16_t`, `short`, `int` |
| `uint32_t` | 32 | 8 nibbles | no | `u32`, `uint_least32_t`, `uint_fast32_t` |
| `i32` | 32 | 8 nibbles | yes | `int32_t`, `int_least32_t`, `int_fast32_t`, `long` |
| `uint64_t` | 64 | 16 nibbles | no | `u64`, `uint_least64_t`, `uint_fast64_t`, `uintmax_t` |
| `i64` | 64 | 16 nibbles | yes | `int64_t`, `int_least64_t`, `int_fast64_t`, `intmax_t` |
| `bool` | logical | 1 nibble | logical | |
| `flashptr` | 12 | 3 nibbles | n/a | |
| `half` | 16 | 4 nibbles | signed | `f16`, `_Float16` |
| `float` | 32 | 8 nibbles | signed | `f32`, `_Float32` |
| `void` | 0 | 0 | n/a | |

`char` is unsigned. `int` is signed 16-bit and `long` is signed 32-bit.
`intptr_t` and `uintptr_t` are not defined.

## `bool`

`bool` is a logical type with one nibble of storage.

- Comparisons, `!`, `&&`, and `||` produce `bool`.
- Assigning an integer to `bool` normalizes it to 0 or 1.
- Converting `bool` to an integer yields 0 or 1.
- `true` and `false` produce 1 and 0.
- Arithmetic converts `bool` to a 4-bit integer, so `true + true` is 2.
- `print()` prints a `bool` as `0` or `1`.

## `flashptr`

`flashptr` is a 12-bit code-memory address. It is used for flash strings and
flash tables.

- `&CONST` on a flash array yields a `flashptr`.
- `flash_next(&p)` advances a `flashptr` by two code words.
- A `flashptr` is not a data address and cannot be dereferenced.

## Floating point

`half` is IEEE-754 binary16. `float` is IEEE-754 binary32. Both are
software implementations.

- Arithmetic rounds to nearest, ties to even.
- Subnormal inputs and results are supported.
- Signed zero, infinities, and canonical quiet NaN follow IEEE-754.
- Float-to-integer conversion truncates toward zero and saturates on overflow.
  NaN converts to 0. Negative values converted to unsigned types become 0.
- `half` and `float` convert to and from integer and 64-bit integer types.

The implementation notes are in {doc}`../internals/soft-float`.

## 64-bit integers

A 64-bit value occupies sixteen nibbles. Expression results use a dedicated
memory buffer. Each 64-bit variable costs sixteen nibbles of RAM, and the
compiler reserves result and temporary slots while evaluating a 64-bit
expression.

64-bit multiply and divide call the helpers in `lib/wide.nbl`. See
{doc}`../internals/wide-arithmetic`.

## Struct types

`struct` declares a RAM-only aggregate with scalar fields. Struct layout and
limits are in {doc}`structs`.
