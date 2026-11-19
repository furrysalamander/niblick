# Emulator

`niblick.emulator.Emulator` implements the Voja4 CPU and a UART model for
tests and the debugger.

## Command line

```bash
python3 -m niblick examples/hello.nbl --run
python3 -m niblick examples/hello.nbl --run --trace --trace-limit 20
python3 -m niblick examples/hello.nbl --run --trace-io --io-trace-limit 200
```

See {doc}`../getting-started/cli` for all run and dump options.

## Python API

```python
from niblick.emulator import Emulator

emu = Emulator()
emu.load_hex("examples/hello.hex")
steps = emu.run(max_steps=100000)
print(steps, emu.cycle_count, emu.elapsed_seconds)
print(bytes(emu.uart_tx))
```

| Member | Type | Meaning |
|---|---|---|
| `load_hex(path)` | method | Load and validate a `.hex` file |
| `load_bytes(data)` | method | Load a `.hex` container or raw little-endian words |
| `load_words(words)` | method | Load 12-bit instruction words |
| `reset()` | method | Clear CPU state and RAM; keep the loaded program |
| `step()` | method | Execute one instruction |
| `run(max_steps=100000)` | method | Execute until halt or step limit; return step count |
| `halt()` | method | Request that `run` stop |
| `set_input(value, bank=None)` | method | Set the 4-bit input port |
| `receive_uart(data)` | method | Queue bytes for `uart_getc` |
| `press_key(key)`, `release_key(key)`, `press_alt()`, `release_alt()` | method | Front-panel input |
| `trace_io(limit=2000)`, `stop_io_trace()` | method | Record OUT/OUTB/IN/INB events |
| `display_pages()` | method | Return the left and right visible pages |
| `state()` | method | Return a state snapshot |
| `.program` | `list[int]` | 4096 instruction words |
| `.ram` | `list[int]` | 256 nibbles |
| `.pc`, `.sp`, `.C`, `.Z`, `.V` | attributes | CPU state |
| `.uart_tx`, `.uart_rx` | `list[int]` | UART byte buffers |
| `.uart_error` | `bool` | Sticky UART error state |
| `.instruction_count`, `.cycle_count` | attributes | Execution counters |
| `.io_trace` | `list[IoTraceEvent] | None` | Stored I/O events |
| `.io_trace_total` | attribute | Total events seen |

`reset()` clears RAM and control state; the loaded program is retained.

## Model

| Item | Behavior |
|---|---|
| Data RAM | 256 nibbles; registers are `ram[0..15]` |
| Program | 4096 12-bit words |
| UART TX | Bytes written through `SerHigh`/`SerLow` |
| UART RX | Byte queue read through `SerHigh`/`SerLow` |
| `Received` | Queue length, saturated at 15 |
| Buttons | `press_key`, `release_key`, `press_alt` |
| `Random` | Deterministic 16-bit LCG |
| `Sync` | Approximated from instruction count |
| `AutoOff` | Writing 0 halts the CPU |
| Display | Visible page pair |
| Counters | Instruction and cycle counts, estimated time |
| I/O trace | OUT, OUTB, IN, INB events |

The emulator does not model LED brightness, real-time clock accuracy, or
electrical behavior.

## I/O tracing

```python
emu = Emulator()
emu.load_hex("driver.hex")
emu.set_input(0)
emu.trace_io(limit=2000)
emu.run(5_000_000)
for event in emu.io_trace:
    print(event.kind, hex(event.address), event.bit, event.before, event.after)
```

Events have `kind` (`write`, `bit`, or `read`), `address`, `before`, `after`,
`pc`, `step`, and an optional `bit`.

## Step limits

`run` stops only on `.halted` or the step limit. Intentional `JR -1` loops are
not auto-detected.
