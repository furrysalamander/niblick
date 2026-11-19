# Trigonometry

32-step Q4.4 sine and cosine table.

```c
import "lib/trig.nbl";
```

`TRIG_STEPS` is 32. `TRIG_90` is 8, one quarter turn. Angles are modulo 32.
Results are Q4.4 values; `0x10` is 1.0.

## Constants

| Name | Type | Value |
|---|---|---|
| `sin_q4_4_table` | `char[]` | table |
| `TRIG_STEPS` | `char` | `32` |
| `TRIG_90` | `nibble` | `8` |

## Functions

| Call | Returns | Notes |
|---|---|---|
| `sin_q4_4(char angle)` | `char` |  |
| `cos_q4_4(char angle)` | `char` |  |
