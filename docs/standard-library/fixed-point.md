# Fixed point

Signed Q4.4 fixed-point arithmetic. `0x10` represents 1.0.

```c
import "lib/fixed.nbl";
```

A Q4.4 value is a signed `char` with four integer bits and four fractional
bits. `q4_4_from_int` converts `-8..7`; `q4_4_to_int` truncates toward zero.
`q4_4_div` by zero returns 0.

## Functions

| Call | Returns | Notes |
|---|---|---|
| `q4_4_add(char a, char b)` | `char` |  |
| `q4_4_sub(char a, char b)` | `char` |  |
| `q4_4_neg(char v)` | `char` |  |
| `q4_4_mul(char a, char b)` | `char` |  |
| `q4_4_div(char a, char b)` | `char` |  |
| `q4_4_from_int(nibble v)` | `char` | Convert a signed integer nibble (-8..7) to Q4.4. |
| `q4_4_to_int(char v)` | `nibble` | Convert Q4.4 to a signed integer nibble, truncating toward zero. |
| `q4_4_min(char a, char b)` | `char` |  |
| `q4_4_max(char a, char b)` | `char` |  |
| `q4_4_clamp(char v, char low, char high)` | `char` |  |
