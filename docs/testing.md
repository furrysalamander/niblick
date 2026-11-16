# Testing and development workflow

## Fast loop

```bash
python3 -m pytest              # unit + integration tests
python3 -m niblick examples/hello.nbl --run
python3 -m niblick examples/flash_walk.nbl --run --map
```

The emulator is deterministic and can exercise UART transmit/receive without
hardware.

## Test layers

| Layer | File(s) | What it covers |
|---|---|---|
| Emulator semantics | `tests/test_emulator.py` | All 31 instructions, flags, memory, stack, jumps, flash tables |
| Lexer/parser | `tests/test_parser.py` | Tokens, strings, literals, for-update, syntax errors |
| End-to-end compiler | `tests/test_compiler.py` | Source -> asm -> hex -> emulator behavior |
| Imported assembly | `tests/test_asm_imports.py` | `.asm` imports, `extern fn`, placeholders, runtime linking, optimizer markers |
| Inline assembly | `tests/test_inline_asm.py` | Raw `asm { ... }` blocks, scoped placeholders, labels, runtime calls, optimizer opacity |
| Editor analysis | `tests/test_analysis.py`, `tests/test_lsp.py` | Source positions, loader overrides, diagnostics, symbols, hover, completion, definitions, references, rename, LSP handlers |
| Diagnostics | `tests/test_diagnostics.py` | Structured errors, JSON output, assembler-to-source mapping |
| Debugger | `tests/test_debugmap.py`, `tests/test_debug.py` | PC-to-source maps, breakpoints, stepping, variables, stack frames |
| W5500/Minecraft | `tests/test_mc_void.py`, `tests/test_spi_fast.py` | W5500 driver fast SPI helpers and a 1.8.9 status/login/chunk exchange through a W5500/TCP model |
| Standard library | `tests/test_library.py`, `tests/test_stdlib.py`, `tests/test_signed_lib.py` | UART, GPIO, display/font/text, keys, time/power/system, random, memory, strings, math/trig, audio/PDM |
| Inlining / overlay | `tests/test_compiler.py`, `tests/test_overlay.py` | Single-statement return/void inlining, side-effect guards, frame interference and slot reuse |
| Print formatting | `tests/test_print.py` | Literal format parsing, typed placeholders, generated UART helpers, and error cases |
| Structs | `tests/test_structs.py` | Layout, field access, arrays of structs, and unsupported forms |
| Board pin map | `tests/test_board.py` | Voja4 output/input masks and default SPI/W5500 assignments |
| Optimizer proofs | `tests/test_peephole_z3.py` | Z3 proofs for constant-address lowering and peephole identities |
| Property tests | `tests/test_hypothesis_compiler.py` | Generated nibble expressions versus a Python reference |
| CLI/assembler wrapper | `tests/test_cli.py` | Output paths, error reporting, `.hex` generation |
| Examples | `tests/test_examples.py` | Every checked-in example compiles and fits |

The LSP tests are skipped when `pygls` is not installed. Install the optional
extra with `pip install -e ".[lsp]"` to run them.

## Emulator model

`niblick/emulator.py` implements the CPU core and a UART model:

- `.ram` is 256 nibbles; registers are `ram[0..15]`.
- `.program` is 4096 12-bit words.
- `.uart_tx` collects bytes written through `SerHigh`/`SerLow`.
- `.uart_rx` is a byte queue read through `SerHigh`/`SerLow`; `Received`
  returns the queue length (saturating at 15).
- `run(max_steps)` stops only on `.halted` or the step limit; intentional
  `JR -1` loops are not auto-detected.

The emulator models:

- button state (`press_key`, `release_key`, `press_alt`) and `KeyStatus`/`KeyReg`
- the `Random` SFR with a deterministic 16-bit LCG
- `Sync`/`RdFlags.UserSync` (approximated from instruction count)
- `AutoOff = 0` sleep/halt
- the visible display pages (`display_pages()`)
- UART FIFO, `Received`, and the `SerCtrl` error bit
- instruction/cycle counts and an estimated elapsed time from the `Clock` SFR
- I/O-port tracing through `trace_io()`, and fake inputs through
  `set_input(value, bank=None)`

`set_input` writes both `IN` (`0x0B`) and `INB` (`0xFB`) by default; pass
`bank=0` or `bank=1` to target the bank selected by `WrFlags.IOPos`.

It does not model LED brightness, real-time clock accuracy, or
electrical behavior. Validate those on hardware.

## I/O tracing and fake inputs

For bit-banged drivers, record the OUT/OUTB/IN/INB stream before touching
hardware:

```python
emu = Emulator()
emu.load_hex("driver.hex")
emu.set_input(0)          # fake BUSY bits
emu.trace_io(limit=2000)
emu.run(5_000_000)
for event in emu.io_trace:
    print(event.kind, hex(event.address), event.bit, event.before, event.after)
```

Events are `write`, `bit`, or `read` and include the fetched PC and event
number. `io_trace_total` keeps counting past the limit. From the CLI:

```bash
python3 -m niblick driver.nbl --run --trace-io --io-trace-limit 200
```

A 595 decoder is not part of the emulator; wiring choices
differ between builds.

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
python3 -m niblick example.nbl --run --trace --trace-limit 20
python3 -m niblick example.nbl --symbols --callgraph --stack
python3 -m niblick example.nbl --map-json build/example.map.json
python3 -m niblick example.nbl --run --trace-io --io-trace-limit 200
python3 -m niblick example.nbl --run --dump-ram --dump-uart --dump-sfr
```

`--trace` prints the PC, raw instruction word, decoded instruction, selected
registers, stack pointer, and flags. `--symbols` prints per-function sizes
and the runtime/flash/total breakdown. `--stack` prints the user call depth,
the deepest path, and every runtime call's stack cost. The emulator also
reports instruction and cycle counts and an estimated elapsed time at the
current `Clock` setting.

## Hardware self-test

`examples/hw_test.nbl` is a hardware self-test that waits for a single
`0x01` UART byte. It exercises arithmetic, loops, tail recursion, RAM
arrays, `mem_*` helpers, peek/poke, flash tables, flash iteration, UART TX/RX,
GPIO, display paging, dimmer, random, power/status SFRs, WrFlags, key reads,
and delay.

```bash
python3 -m niblick examples/hw_test.nbl
# load examples/hw_test.hex and press RUN
python3 scripts/hw_test.py /dev/ttyUSB0
```

It reports `DONE pass=XX fail=YY` and returns to `READY`, so it can be
triggered repeatedly without re-uploading.

## Key mapping

`examples/keymap.nbl` prints the `KeyReg` and `KeyStatus` value for each
button press:

```bash
python3 -m niblick examples/keymap.nbl
# load examples/keymap.hex, press RUN
python3 scripts/monitor.py /dev/ttyUSB0
```

The confirmed mapping is in [keys.md](keys.md). Update it when new buttons
are measured.

## 32-bit math test

`examples/math32_test.nbl` exercises 32-bit storage, shifts, casts,
multiply, divide, and modulo. It uses the same `0x01` start byte as the main
self-test:

```bash
python3 -m niblick examples/math32_test.nbl
# load examples/math32_test.hex, press RUN, then:
python3 scripts/hw_test.py /dev/ttyUSB0
```

## Tetris smoke test

`examples/tetris.nbl` exercises the display, keys, random pieces, PWM
flashes, and a large amount of compiled code. `tests/test_size.py` keeps it
under a 2800-word budget, and `tests/test_examples.py` enforces the 4096-word
hard limit.

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
- keep a known-good example such as `hello.nbl` for wiring checks.

## CI suggestion

```yaml
- run: python3 -m pip install -e '.[dev]'
- run: python3 -m pytest
- run: make examples
```

## Tooling

The development extras include `ruff`, `mypy`, `pytest-cov`, `hypothesis`,
`z3-solver`, and `pre-commit`.

```bash
python3 -m pip install -e ".[dev]"
ruff check .
mypy niblick/compiler.py niblick/format.py niblick/inline.py niblick/asm_opt.py niblick/loader.py niblick/emulator.py niblick/parser.py niblick/types.py
python3 -m pytest --cov=niblick
pre-commit install
```

- `tests/test_peephole_z3.py` uses z3 to prove the constant-address and
  peephole identities.
- `tests/test_hypothesis_compiler.py` generates nibble expressions and compares
  compiled emulator results with a Python reference.
- `tests/test_overlay.py` checks the frame-interference rules.
- The CI workflow runs the full matrix, Ruff/mypy, coverage, the extension
  build, and the wheel smoke test.
