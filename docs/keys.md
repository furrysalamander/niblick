# Front-panel key mapping

`KeyReg` at `0xFD` reports a 4-bit code for the last key pressed. The
physical mapping is not the obvious button-label order, so it was measured
on hardware with `examples/keymap.badge`.

## Confirmed mapping

| Physical button | `KeyReg` |
|---|---:|
| OPCODE `8` | 1 |
| OPCODE `4` | 2 |
| OPCODE `2` | 3 |
| OPCODE `1` | 4 |
| DEP+ / CLOCK / STEP | 0 |

Only these five have been confirmed so far. The remaining front-panel keys
have not been mapped.

`KeyStatus` at `0xFC` supplies:

| Bit | Meaning |
|---:|---|
| 3 | `AltPress` |
| 2 | `AnyPress` |
| 1 | `LastPress` |
| 0 | `JustPress` |

Reading `KeyStatus` clears `JustPress`. Use `key_just()` to wait for a new
press, then `key_code()` to read `KeyReg`.

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
