# Testing and development workflow

## Fast loop

```bash
python3 -m pytest              # unit + integration tests
python3 -m badgec examples/hello.badge --run
python3 -m badgec examples/flash_walk.badge --run --map
```

The emulator is the primary development loop. It is fast, deterministic,
and can exercise UART transmit/receive without hardware.

## Test layers

| Layer | File(s) | What it covers |
|---|---|---|
| Emulator semantics | `tests/test_emulator.py` | All 31 instructions, flags, memory, stack, jumps, flash tables |
| Lexer/parser | `tests/test_parser.py` | Tokens, strings, literals, for-update, syntax errors |
| End-to-end compiler | `tests/test_compiler.py` | Source -> asm -> hex -> emulator behavior |
| CLI/assembler wrapper | `tests/test_cli.py` | Output paths, error reporting, `.hex` generation |
| Examples | `tests/test_examples.py` | Every checked-in example still compiles and fits |

## Emulator model

`badgec/emulator.py` implements the CPU core and a small UART model:

- `.ram` is 256 nibbles; registers are `ram[0..15]`.
- `.program` is 4096 12-bit words.
- `.uart_tx` collects bytes written through `SerHigh`/`SerLow`.
- `.uart_rx` is a byte queue read through `SerHigh`/`SerLow`; `Received`
  returns the queue length (saturating at 15).
- `run(max_steps)` stops only on `.halted` or the step limit; intentional
  `JR -1` loops are not auto-detected.

The emulator now also models:

- button state (`press_key`, `release_key`, `press_alt`) and `KeyStatus`/`KeyReg`
- the `Random` SFR with a deterministic 16-bit LCG
- `Sync`/`RdFlags.UserSync`
- the visible display pages (`display_pages()`)
- UART FIFO, `Received`, and the `SerCtrl` error bit
- instruction/cycle counts and an estimated elapsed time from the `Clock` SFR

It still does not model LED brightness, real-time clock accuracy, or
electrical behavior. Validate those on hardware.

## Adding a compiler test

Use the helper in `tests/test_compiler.py`:

```python
compiler, hex_path = build(tmp_path, """
    nibble x;
    fn main() { x = 3 + 4; }
""")
emu = run(hex_path)
assert emu.ram[ram_nibble(compiler, "x")] == 7
```

`build()` parses, compiles, assembles, and returns the compiler (for symbol
addresses) plus the `.hex` path. `run()` loads and executes it.

## Diagnostics

```bash
python3 -m badgec example.badge --run --trace --trace-limit 20
python3 -m badgec example.badge --symbols --callgraph
python3 -m badgec example.badge --map-json build/example.map.json
python3 -m badgec example.badge --run --dump-ram --dump-uart --dump-sfr
```

`--trace` prints the PC, raw instruction word, decoded instruction, selected
registers, stack pointer, and flags. The emulator also reports instruction
and cycle counts and an estimated elapsed time at the current `Clock` setting.

## Hardware self-test

`examples/hw_test.badge` is a 54-check self-test that waits for a single
`0x01` UART byte. It exercises arithmetic, loops, tail recursion, RAM
arrays, memset/memcpy, peek/poke, flash tables, flash iteration, UART TX/RX,
GPIO, display paging, dimmer, random, WrFlags, key reads, and delay.

```bash
python3 -m badgec examples/hw_test.badge
# load examples/hw_test.hex and press RUN
python3 scripts/hw_test.py /dev/ttyUSB0
```

It reports `DONE pass=XX fail=YY` and returns to `READY`, so it can be
triggered repeatedly without re-uploading.

## Key mapping

`examples/keymap.badge` prints the `KeyReg` and `KeyStatus` value for each
button press:

```bash
python3 -m badgec examples/keymap.badge
# load examples/keymap.hex, press RUN
python3 scripts/monitor.py /dev/ttyUSB0
```

The confirmed mapping is in [keys.md](keys.md). Update it when new buttons
are measured.

## Tetris smoke test

`examples/tetris.badge` exercises the display, keys, random pieces, PWM
flashes, and a large amount of compiled code. It is near the code-space
limit, so `tests/test_examples.py` is the regression guard.

## Hardware loop

1. Compile and inspect the `.hex` size.
2. Run in the emulator.
3. Connect a 3.3 V UART adapter/Tigard to the badge expansion header.
4. Put the badge in DIR mode and press LOAD.
5. Send the `.hex` at 9600 8N1:

```bash
python3 scripts/flash.py /dev/ttyUSB0 examples/hello.hex
```

If the badge does not run the program:

- verify GND is common and the adapter is 3.3 V;
- confirm the badge baud setting (default 9600);
- try a master reset (disconnect batteries) if the serial state looks stuck;
- keep a known-good example such as `hello.badge` for wiring checks.

## CI suggestion

```yaml
- run: python3 -m pip install -e '.[dev]'
- run: python3 -m pytest
- run: make examples
```
