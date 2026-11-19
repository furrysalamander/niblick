# Math

Integer helpers, square roots, mapping, GCD, and LCM.

```c
import "lib/math.nbl";
```

Functions without an `8` or `16` suffix operate on `nibble` arguments.
`math_isqrt` returns the largest `r` with `r*r <= n`. `math_sqrt16` returns the
same result for a 16-bit input, with a `char` result. `math_map8` clamps input
outside `in_min..in_max`.

## Functions

| Call | Returns | Notes |
|---|---|---|
| `math_min(nibble a, nibble b)` | `nibble` |  |
| `math_max(nibble a, nibble b)` | `nibble` |  |
| `math_clamp(nibble v, nibble low, nibble high)` | `nibble` |  |
| `math_abs_diff(nibble a, nibble b)` | `nibble` |  |
| `math_mul(nibble a, nibble b)` | `char` | a * b, with a and b in 0..15.  The result fits in a char. |
| `math_div(nibble a, nibble b)` | `nibble` | Quotient and remainder for nibble / nibble. |
| `math_mod(nibble a, nibble b)` | `nibble` |  |
| `math_div8(char a, nibble b)` | `char` | char / nibble.  The quotient can be up to 255. |
| `math_mod8(char a, nibble b)` | `nibble` |  |
| `math_isqrt(char n)` | `nibble` | Largest r with r*r <= n. |
| `math_pow2(nibble n)` | `char` |  |
| `math_min8(char a, char b)` | `char` |  |
| `math_max8(char a, char b)` | `char` |  |
| `math_clamp8(char v, char low, char high)` | `char` |  |
| `math_abs_diff8(char a, char b)` | `char` |  |
| `math_map8(char v, char in_min, char in_max, char out_min, char out_max)` | `char` | Unsigned linear map.  Values outside in_min..in_max are clamped. |
| `math_sqrt16(uint16_t n)` | `char` | Largest r with r*r <= n; the result fits in a char. |
| `math_gcd8(char a, char b)` | `char` |  |
| `math_lcm8(char a, char b)` | `uint16_t` |  |
| `math_sign8(char v)` | `nibble` | Raw two's-complement sign: 15 = -1, 0 = zero, 1 = +1. |
| `math_wrap8(char v, char mod)` | `char` |  |
| `math_div_round8(char a, char b)` | `char` |  |
