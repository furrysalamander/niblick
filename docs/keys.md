# Front-panel key mapping

`KeyReg` at `0xFD` reports a 4-bit code for the last key pressed. The
physical mapping is not the obvious button-label order, so it was measured
on hardware with `examples/keymap.badge`.

Import `lib/key.badge` to use the helpers below. `lib/key.badge` only names
the five codes that have been confirmed on hardware; the raw `key_status()`
and `key_code()` intrinsics work for any code.

## Confirmed mapping

| Physical button | `KeyReg` |
|---|---:|
| OPCODE `8` | 1 |
| OPCODE `4` | 2 |
| OPCODE `2` | 3 |
| OPCODE `1` | 4 |
| DEP+ / CLOCK / STEP | 0 |

Only these five have been confirmed so far. The remaining front-panel keys
have not been mapped. `key_op1()`, `key_op2()`, `key_op4()`, `key_op8()`, and
`key_dep()` return the confirmed codes; use `key_name(code)` for a flash
string label.

`KeyStatus` at `0xFC` supplies:

| Bit | Meaning |
|---:|---|
| 3 | `AltPress` |
| 2 | `AnyPress` |
| 1 | `LastPress` |
| 0 | `JustPress` |

Reading `KeyStatus` clears `JustPress`. Use `key_just()` to wait for a new
press, then `key_code()` to read `KeyReg`. The `*_of(status)` helpers
(`key_alt_of`, `key_any_of`, `key_just_of`, `key_last_of`) test bits from an
already-read status value.

## Measuring more keys

Build and load `examples/keymap.badge`, then press buttons one at a time:

```bash
python3 -m badgec examples/keymap.badge
# load examples/keymap.hex, press RUN
python3 scripts/monitor.py /dev/ttyUSB0
```

The program prints:

```text
KEY=1 STATUS=6
KEY=4 STATUS=6
```

Update this table when new keys are measured.
