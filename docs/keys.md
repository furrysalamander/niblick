# Front-panel key mapping

`KeyReg` at `0xFD` reports a 4-bit code for the last key pressed. The
physical mapping is not the obvious button-label order, so it was measured
on hardware with `examples/keymap.nbl`.

Import `lib/key.nbl` to use the helpers below. `lib/key.nbl` only names
the five codes that have been confirmed on hardware; the raw `key_status()`
and `key_code()` intrinsics work for any code.

## Front-panel controls

The badge has three 4-bit entry groups (`OPCODE`, `OPERAND X`, `OPERAND Y`),
each with `8`, `4`, `2`, and `1` buttons and indicators. `DATA IN` switches
between direct bit entry (`BIN`) and `SEL` mode, where the same buttons step
the value up and down.

`MODE` selects the current operating mode. The four command buttons change
labels with that mode:

| Mode | Command buttons |
|---|---|
| DIR | `CARRY`, `SAVE`, `LOAD`, `CLOCK` |
| SS | `HISTORY`, `-ADDR`, `+ADDR`, `STEP` |
| RUN | `FAST`, `PAUSE`, `BREAK`, `RUN` |
| PGM | `ADDRSET`, `-ADDR`, `+ADDR`, `DEP+` |

`ALT` modifies the next button press. In DIR mode it selects the dimmer,
baud rate, and flash address for the three entry groups; in SS/RUN/PGM it
selects sync, clock, and page. `ON-OFF` is a separate button on the bottom
edge. The upstream
[User Manual](https://github.com/Hack-a-Day/2022-Supercon6-Badge-Tools/blob/main/manuals/1.User_Manual_v4.pdf)
has the complete mode-by-mode command table.

Niblick does not model the front-panel controller's mode state. It only
exposes `KeyReg` and `KeyStatus`; `ALT` is reported through
`KeyStatus.AltPress`, and `ON-OFF` does not report a key code.

## Confirmed mapping

| Physical button | `KeyReg` |
|---|---:|
| OPCODE `8` | 1 |
| OPCODE `4` | 2 |
| OPCODE `2` | 3 |
| OPCODE `1` | 4 |
| DEP+ / CLOCK / STEP | 0 |

Only these five have been confirmed so far. The scanner exposes codes `0..13`;
codes `5..13` are not mapped, and several command buttons can share a code
(the measured `DEP+` / `CLOCK` / `STEP` group is code `0`). `key_op1()`,
`key_op2()`, `key_op4()`, `key_op8()`, and `key_dep()` return the confirmed
codes; use `key_name(code)` for a flash string label.

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

Build and load `examples/keymap.nbl`, then press buttons one at a time:

```bash
python3 -m niblick examples/keymap.nbl
# load examples/keymap.hex, press RUN
python3 scripts/monitor.py /dev/ttyUSB0
```

The program prints:

```text
KEY=1 STATUS=6
KEY=4 STATUS=6
```

Update this table when new keys are measured.
