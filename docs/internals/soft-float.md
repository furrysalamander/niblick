# Soft float

Niblick implements IEEE-754 binary16 (`half`) and binary32 (`float`) in
software. No floating-point instruction exists on the target.

## Modules

| Type | Source | Arithmetic |
|---|---|---|
| `half` | `lib/float16.nbl`, `lib/float16.asm` | Native binary16 |
| `float` | `lib/float32.nbl`, `lib/float32.asm` | Native binary32 |

The loader adds these modules when a program uses the corresponding type.

## Representation

| Type | Bits | RAM | Layout |
|---|---:|---:|---|
| `half` | 16 | 4 nibbles | sign, 5-bit exponent, 10-bit fraction |
| `float` | 32 | 8 nibbles | sign, 8-bit exponent, 23-bit fraction |

Values are stored as IEEE-754 bit patterns. `half` and `float` convert directly
to each other.

## Arithmetic behavior

- Round to nearest, ties to even.
- Guard, round, and sticky bits are used for binary32.
- Subnormal inputs and results are supported.
- Signed zero is preserved.
- Infinities propagate.
- NaN inputs produce a canonical quiet NaN.
- Integer and 64-bit integer values convert to and from both types.
- Float-to-integer conversion truncates toward zero and saturates on overflow.
- NaN converts to 0.
- Negative values converted to unsigned types become 0.
- Narrower integer casts use the saturated 32-bit integer result, then
  truncate.

## Helpers

| Helper | Input | Output |
|---|---|---|
| `__nib_f16_add`, `__nib_f16_sub`, `__nib_f16_mul`, `__nib_f16_div` | two `half` | `half` |
| `__nib_f16_cmp` | two `half` | comparison code |
| `__nib_f16_is_zero` | `half` | `bool` |
| `__nib_f32_add`, `__nib_f32_sub`, `__nib_f32_mul`, `__nib_f32_div` | two `float` | `float` |
| `__nib_f32_cmp` | two `float` | comparison code |
| `__nib_f32_is_zero` | `float` | `bool` |
| `__nib_u32_to_f32`, `__nib_i32_to_f32`, `__nib_u64_to_f32`, `__nib_i64_to_f32` | integer | `float` |
| `__nib_f32_to_u32`, `__nib_f32_to_i32`, `__nib_f32_to_u64`, `__nib_f32_to_i64` | `float` | integer |

The compiler uses `__nib_f16_bits`, `__nib_f16_from_bits`, `__nib_f32_bits`,
and `__nib_f32_from_bits` for raw bit access.

## Cost

A `half` result uses four nibbles. A `float` result uses eight nibbles.
Arithmetic calls the corresponding helper module. Programs that use both
types link both modules. 64-bit conversions use the wide-arithmetic helpers in
{doc}`wide-arithmetic`.
