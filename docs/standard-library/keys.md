# Keys

```c
import "lib/key.nbl";
```

`lib/key.nbl` exposes the debounced `KeyStatus` and `KeyReg` values.

## Key status bits

| Constant | Bit | Meaning |
|---|---:|---|
| `KEY_ALT` | 3 | `AltPress` |
| `KEY_ANY` | 2 | `AnyPress` |
| `KEY_LAST` | 1 | `LastPress` |
| `KEY_JUST` | 0 | `JustPress` |

Reading `KeyStatus` clears `JustPress`. The `*_of(status)` helpers test an
already-read value.

## Key codes

| Physical button | `KeyReg` | Helper |
|---|---:|---|
| `DEP+` / `CLOCK` / `STEP` | 0 | `key_dep()` |
| `OPCODE 8` | 1 | `key_op8()` |
| `OPCODE 4` | 2 | `key_op4()` |
| `OPCODE 2` | 3 | `key_op2()` |
| `OPCODE 1` | 4 | `key_op1()` |

Codes 5 through 13 are not mapped by the library. `key_name(code)` returns a
flash string such as `"OPCODE 8"` or `"UNKNOWN"`.

## Functions

| Call | Returns | Notes |
|---|---|---|
| `key_status()` | `nibble` | Read `KeyStatus`; clears `JustPress` |
| `key_code()` | `nibble` | Read `KeyReg` |
| `key_alt_of(status)` | `nibble` | Test `AltPress` in a read status value |
| `key_any_of(status)` | `nibble` | Test `AnyPress` |
| `key_last_of(status)` | `nibble` | Test `LastPress` |
| `key_just_of(status)` | `nibble` | Test `JustPress` |
| `key_alt()` | `nibble` | Read status and test `AltPress` |
| `key_any()` | `nibble` | Read status and test `AnyPress` |
| `key_last()` | `nibble` | Read status and test `LastPress` |
| `key_just()` | `nibble` | Read status and test `JustPress` |
| `key_down(code)` | `nibble` | 1 when `KeyReg` equals `code` and `LastPress` is set |
| `key_op8()` | `nibble` | Return key code 1 |
| `key_op4()` | `nibble` | Return key code 2 |
| `key_op2()` | `nibble` | Return key code 3 |
| `key_op1()` | `nibble` | Return key code 4 |
| `key_dep()` | `nibble` | Return key code 0 |
| `key_wait()` | `nibble` | Block until `JustPress`, then return `KeyReg` |
| `key_wait_release()` | `nibble` | Block for a press, then for its release; return the code |
| `key_wait_any()` | `nibble` | Block until `AnyPress`, then return `KeyReg` |
| `key_name(code)` | `flashptr` | Flash string label for a confirmed code |
