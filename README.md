# Niblick

Niblick compiles a C-like language to the 12-bit assembly of the Hackaday
Supercon.6 2022 (Voja4) badge, assembles it to a `.hex` file with
`supercon6-assembler`, and includes a headless emulator for tests.

**Web editor:** <https://furrysalamander.github.io/niblick/>

## Target

| Item | Value |
|---|---|
| Data width | 4 bits |
| Code space | 4096 12-bit words |
| Data RAM | 256 nibbles |
| General registers | 10 |
| Hardware call stack | 5 entries |
| Display | 8x16 LED matrix |
| Serial | 9600 8N1 UART |

## Install

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -e ".[dev]"
```

## Usage

```bash
.venv/bin/python -m niblick examples/hello.nbl --run
```

The compiler writes `<source>.asm` and `<source>.hex` next to the source.
Options:

```bash
python3 -m niblick examples/hello.nbl --no-assemble
python3 -m niblick examples/serial_echo.nbl --map
python3 -m niblick examples/hello.nbl --run --trace --trace-limit 20 --dump-uart
python3 -m niblick examples/hello.nbl --symbols --callgraph --stack
python3 -m niblick examples/hello.nbl --run --trace-io --io-trace-limit 200
python3 -m niblick examples/hello.nbl --map-json hello.map.json
```

## Supported

- Explicit-width integer types: `nibble`/`u4`, `i4`, `char`/`u8`/`byte`, `i8`,
  `uint16_t`/`u16`, `i16`, `uint32_t`/`u32`, `i32`, `int64_t`, `uint64_t`,
  `bool`, and `flashptr`
- C aliases: `int8_t`, `uint8_t`, `int16_t`, `uint16_t`, `int32_t`,
  `uint32_t`, `short`, `int`, and `long`
- `half`/`f16` and `float`/`f32`
- Signed arithmetic, division, modulo, arithmetic right shift, and signed
  comparisons
- Destination-width expression typing
- Globals, locals, fixed-size RAM arrays, `const` flash arrays, scalar `const`
  values, and constant-expression array lengths
- Brace initializers for RAM arrays and single structs
- Structs with scalar fields, field access, arrays of structs, by-value
  parameters, and return values
- Functions, parameters, returns, and tail-call optimization
- `if`/`else`, `while`, `for`, `break`, and `continue`
- Arithmetic, bitwise, shift, comparison, and logical operators
- Compound assignment, `++`/`--` statements, unary `+`, and `?:`
- Explicit casts to integer, `bool`, and float types
- NUL-terminated text strings, full escapes, and adjacent string literal
  concatenation
- `print()` compile-time formatting with `{}`, `{:d}`, `{:x}`, `{:b}`, `{:c}`,
  and `{:s}` placeholders
- `import` for `lib/` modules and `lib/drivers/` device drivers
- Imported `.asm` modules with `extern fn`, `${...}` placeholders, call-graph
  scanning, and `no-optimize` markers
- Inline `asm { ... }` blocks with lexical `${...}` placeholders and local
  labels
- Flash strings and `RET`-table iteration
- Intrinsics: `peek`, `poke`, `peek8`, `poke8`, `in`, `out`, flash tables,
  constant-mask GPIO, UART bytes, and `delay`
- Constant-address lowering, single-statement function and void inlining, frame overlay,
  copy propagation, dead-write elimination, branch relaxation, and tail calls
- Code and RAM size reports, per-function sizes, stack-cost reports, I/O
  tracing, and an emulator test harness
- VS Code extension with syntax highlighting, diagnostics, document symbols,
  hover, completion, go-to-definition, references, rename, and an emulator
  debugger

## Not supported

- General (non-tail) recursion
- General pointers and pointer arithmetic
- `switch`, `do`/`while`, `enum`, `typedef`, `sizeof`, `static`, `volatile`,
  and `goto`
- Nested structs, struct fields that are arrays, nested aggregate
  initializers, varargs, and dynamic allocation
- Local `const` arrays
- Preprocessor directives
- Full register allocation and a broader peephole pipeline
- UART interrupt-driven or buffered I/O beyond the hardware FIFO

32-bit `*`, `/`, and `%` use a 24-nibble scratch block allocated only when the
program uses them. A 32-bit divide takes milliseconds at 250 kHz. See
`docs/compiler.md` and `docs/stdlib.md`.

## Language

```c
const char greeting[] = "Hello, Supercon!\n";
const nibble LED_CLOCK = 1;
const nibble LED_DATA = 2;

char rxbuf[16];
nibble count;

fn nibble add(nibble a, nibble b) {
    return a + b;
}

fn nibble count_down(nibble n, nibble acc) {
    if (n == 0) {
        return acc;
    }
    return count_down(n - 1, acc + 1);   // tail call
}

fn main() {
    uart_init(3);
    uart_puts(greeting);
    count = count_down(10, 0);

    while (uart_available() == 0) {
    }
    rxbuf[0] = uart_getc();
}
```

`char` is unsigned 8-bit. A RAM `char[]` uses two nibbles per element. A
`const char[]` is stored in program memory as a `RET` table: two code words per
character, read with `flash_next(&p)` or `flash_read_char(ptr)`. Text strings
terminate with `0x00`.

## Architecture

```text
source.nbl
   -> lexer -> parser -> AST
   -> Niblick code generator (fixed-register expression convention)
   -> badge assembly
   -> supercon6-assembler
   -> .hex
```

Imported `.asm` modules are read by the loader and appended at link time;
`extern fn` declarations provide their signatures and static parameter slots.

Expression results use fixed registers:

| Type | Result |
|---|---|
| `nibble` | `R1` |
| `char` | `R1` (low), `R2` (high) |
| `flashptr` | `R1` (low), `R2` (middle), `R3` (high) |

Nested expression temporaries use `0x20..0x3F`. Variables and arrays use
`0x40..0xEF`. `GOSUB`/`RET` use the hardware call stack at `0x10..0x1F`.

Tail calls compile to `GOTO`, so tail recursion does not consume a hardware
stack level. Non-tail recursion is rejected because the hardware stack has five
entries and there is no stack-relative addressing.

## Web editor

`web/` contains a browser editor: Monaco for source, Pyodide for the compiler,
assembler, and emulator, and WebSerial for flashing in Chromium/Edge. The
assembly view links source and generated assembly by cursor and mouse, and the
hex view is an `xxd`-style dump. Build the runtime assets before starting Vite:

```bash
.venv/bin/python tools/build_web_assets.py
cd web
npm install
npm run dev
```

The production build is `npm run build`; set `VITE_BASE` when serving from a
GitHub Pages subpath. The hosted editor is at
<https://furrysalamander.github.io/niblick/>. See `web/README.md` for the
asset layout and Playwright test.

## Testing

```bash
python3 -m pytest
```

The test suite covers emulator instruction semantics, end-to-end programs,
the standard library, frame overlay, z3-checked peephole identities, and
Hypothesis-generated arithmetic properties.

The `fidelity` extra installs the upstream headless emulator for cross-checks:

```bash
python3 -m pip install -e ".[fidelity]"
python3 -m pytest tests/test_upstream_emulator.py
```

The emulator in `niblick/emulator.py` models the CPU and a UART FIFO. It does
not model clock speed, LED persistence, or every SFR side effect.

## Hardware workflow

The badge serial load protocol is 9600 8N1. Put the badge in **DIR** mode,
press **LOAD**, then send the `.hex` file:

```bash
stty -F /dev/ttyUSB0 raw 9600
cat examples/hello.hex > /dev/ttyUSB0
```

Helper scripts:

```bash
python3 scripts/flash.py /dev/ttyUSB0 examples/hello.hex
python3 scripts/monitor.py /dev/ttyUSB0
```

Hardware self-test:

```bash
python3 -m niblick examples/hw_test.nbl
# load examples/hw_test.hex, press RUN, then:
python3 scripts/hw_test.py /dev/ttyUSB0
```

The self-test waits for a `0x01` byte, prints a PASS/FAIL line per check, and
ends with `DONE pass=XX fail=YY`.

The badge is a 3 V device. Use a 3.3 V USB-UART adapter or Tigard; do not use
RS-232 voltage levels. See `docs/serial.md` and `docs/toolchain.md`.

## Examples

Sizes are the compiler's `code+data` word count and data-RAM nibble count.

| File | Function | Size | RAM | Test |
|---|---|---:|---:|---|
| `hello.nbl` | UART greeting | 142 | 5 | `tests/test_examples.py` |
| `hello_loop.nbl` | UART loop | 159 | 5 | `tests/test_examples.py` |
| `serial_echo.nbl` | UART echo | 187 | 7 | `tests/test_examples.py` |
| `gpio_blink.nbl` | GPIO output | 49 | 1 | `tests/test_examples.py` |
| `inline_asm.nbl` | Inline assembly | 8 | 2 | `tests/test_inline_asm.py` |
| `struct_demo.nbl` | Struct fields and arrays | 645 | 11 | `tests/test_structs.py` |
| `stdlib_demo.nbl` | Standard library | 2093 | 105 | `tests/test_stdlib.py` |
| `u16_math.nbl` | 16-bit arithmetic | 1294 | 32 | `tests/test_examples.py` |
| `u32_math.nbl` | 32-bit arithmetic | 2289 | 97 | `tests/test_examples.py` |
| `math32_test.nbl` | 32-bit hardware test | 2758 | 68 | `tests/test_examples.py` |
| `audio_demo.nbl` | Square-wave audio | 514 | 25 | `tests/test_examples.py` |
| `pdm_demo.nbl` | PDM playback | 170 | 7 | `tests/test_examples.py` |
| `sao_hello.nbl` | SAO header output | 158 | 5 | `tests/test_examples.py` |
| `keymap.nbl` | Key-map measurement | 240 | 5 | `docs/keys.md` |
| `hw_test.nbl` | Hardware self-test | 3429 | 121 | `scripts/hw_test.py` |
| `cube.nbl` | 3D wireframe cube | 1795 | 149 | `tests/test_cube.py` |
| `tetris.nbl` | Tetris | 2573 | 134 | `tests/test_examples.py` |
| `wave.nbl` | Signed wave field | 1054 | 156 | `tests/test_wave.py` |
| `water.nbl` | Falling-sand water | 1894 | 132 | `tests/test_water.py` |
| `text_scroll.nbl` | Scrolling text | 1925 | 71 | `tests/test_examples.py` |
| `pi.nbl` | Pi digits | 2850 | 173 | `tests/test_pi.py` |
| `flash_walk.nbl` | Flash table walk | 105 | 7 | `tests/test_examples.py` |
| `w5500_probe.nbl` | W5500 link probe | 414 | 12 | `tests/test_examples.py` |
| `w5500_udp.nbl` | W5500 UDP sender | 1941 | 46 | `tests/test_examples.py` |
| `w5500_http.nbl` | W5500 TCP listener | 2561 | 60 | `tests/test_examples.py` |
| `w5500_tcp_diag.nbl` | W5500 TCP diagnostics | 908 | 21 | `tests/test_examples.py` |
| `w5500_dashboard.nbl` | W5500 HTTP dashboard | 3899 | 142 | `tests/test_examples.py` |
| `mc_void.nbl` | Minecraft 1.8.9 server | 4064 | 129 | `tests/test_mc_void.py` |

### Tetris controls

| Key | Action |
|---|---|
| OPCODE `8` | Left |
| OPCODE `1` | Right |
| OPCODE `4` | Rotate |
| OPCODE `2` | Soft drop |

The game starts at the slowest fall setting and increments the speed every 8
cleared lines. The global `Dimmer` PWM drives line-clear flashes and the
game-over fade. The `KeyReg` mapping is in `docs/keys.md`.

### Cube

`cube.nbl` uses a fixed-point yaw sweep, a 30° camera pitch, a wider horizontal
scale, and a fixed roll. A Bresenham line routine fills a 16x16 off-screen
framebuffer with four columns of margin on each side. Copying the middle eight
columns clips off-screen edges. The demo uses no UART or input.

### Wave field

`wave.nbl` runs a 4x8 height field on the 8x16 matrix. Heights are signed
nibbles stored as two's complement, and each cell is drawn as a 2x2 block. A
centre impulse is injected every 48 frames. The update uses
`lib/signed.nbl`:

```c
next_height = sum(neighbours) / 2 - previous_height
```

### Falling water

`water.nbl` is a falling-sand cellular automaton on the full 8x16 matrix. Each
cell uses two bits (water and a moved-this-frame flag) in 64 nibbles. Gravity
cycles through down, left, up, and right every 16 simulation frames. The
visible page updates one pixel at a time.

### W5500 Ethernet

`w5500_udp.nbl` bit-bangs SPI to a Wiznet W5500 and sends UDP datagrams.

| Setting | Value |
|---|---|
| Badge address | `192.168.1.50` |
| Host address | `192.168.1.10` |
| Badge source port | `5000` |
| Host destination port | `5001` |
| Payload | `hello from badge\n` |

Default SPI wiring is in `lib/boards/voja4.nbl`: `OUT2=SCLK`, `OUT3=MOSI`,
`OUT1=CS`, `IN0=MISO`, and `OUT0=W5500 RST`. The W5500 requires a clean 3.3 V
supply at roughly 130 mA; a separate supply with common ground is recommended.

Run `w5500_probe.nbl` first to confirm `VERSIONR == 0x04` and the PHY link.
`w5500_http.nbl` adds a TCP listener on port 80:

```bash
curl http://192.168.1.50/
```

`w5500_dashboard.nbl` adds matrix-pattern and dimmer controls.

### Minecraft 1.8.9

`mc_void.nbl` implements a Minecraft Java Edition 1.8.9 (protocol 47) server.
It answers the server-list ping and allows one vanilla 1.8.9 client to join a
16x16 stone platform at y=64 in creative mode.

| Setting | Value |
|---|---|
| Address | `192.168.1.50:25565` |
| Client | vanilla 1.8.9 / protocol 47, offline mode |
| Players | one |
| Encryption / compression | none |
| World storage | none |
| Login name | `Player` |
| Limits | 4064 / 4096 words, 129 / 208 RAM nibbles, max call depth 4 |

The server sends no Encryption Request. The world is one chunk section with a
16x16 stone platform, full block and sky light, and the void biome. Players can
break blocks and place stone on all six faces; the server confirms changes with
Block Change packets and treats stone as authoritative. The platform
regenerates on reconnect.

Run `w5500_probe.nbl` first, then flash `mc_void.hex` and connect with a 1.8.9
client. The protocol path is covered by `tests/test_mc_void.py`, which runs the
firmware against a localhost 1.8.9 client through `tests/w5500_sim.py`. See
`docs/minecraft.md` for the packet sequence and limits.

## Library modules

`lib/` contains opt-in modules for UART, GPIO, display/framebuffer, keys,
clock/sync, AutoOff power, random numbers, byte and nibble memory, strings,
math, two's-complement helpers, Q4.4 fixed point, a Q4.4 sine table, a 5x8
font with scrolling text, square-wave audio, PDM playback, and bit-banged SPI.
Device drivers are under `lib/drivers/`.

```c
import "lib/uart.nbl";
import "lib/string.nbl";

char buf[16];

fn main() {
    uart_route(1);
    uart_init(3);
    str_copy_flash(&buf, "hi");
    uart_print_str(&buf);
    uart_nl();
}
```

Imports resolve relative to the importing file, then the repository root.
Unused module functions and pure globals are removed. See `docs/stdlib.md`,
`docs/drivers/w5500.md`, and `examples/stdlib_demo.nbl`.

The compiler keeps intrinsics for pointer-free memory access, flash tables,
raw I/O, constant-mask GPIO, hot UART bytes, the delay loop, and the W5500 fast
SPI path. `docs/stdlib.md` documents the intrinsic set.

## Documentation

- `docs/isa.md` — instruction set and code-generation notes
- `docs/memory-map.md` — data/code memory and SFRs
- `docs/serial.md` — UART and load/save workflow
- `docs/stdlib.md` — standard library, intrinsics, and module reference
- `docs/pins.md` — Voja4 I/O pin map and board assignments
- `docs/types.md` — type spellings, operators, literals, strings, and typing
- `docs/structs.md` — struct syntax, layout, and limits
- `docs/drivers/w5500.md` — W5500 Ethernet driver
- `docs/runtime-abi.md` — calling convention and runtime
- `docs/compiler.md` — compiler internals and optimizations
- `docs/asm-imports.md` — imported `.asm` modules, `extern fn`, placeholders, and optimizer markers
- `docs/inline-asm.md` — raw `asm { ... }` blocks
- `docs/vscode.md` — VS Code language support and language-server development
- `docs/debugging.md` — emulator debugger, breakpoints, variables, and debug maps
- `docs/testing.md` — test layers and hardware development loop
- `docs/keys.md` — front-panel controls and measured key codes
- `docs/toolchain.md` — assembler and emulator usage
- `docs/upstream-errata.md` — upstream manual contradictions
- `RELEASING.md` — publish checklist

## Assembler dependency

Niblick uses the upstream
[Supercon.6 assembler](https://github.com/Hack-a-Day/2022-Supercon6-Badge-Tools)
through the `supercon6-assembler` package. `pip` installs it from a pinned git
revision; the source is not vendored here.

## License

Niblick is licensed under the GNU General Public License, version 3. The
assembler is MIT-licensed and distributed as a separate package. See
`THIRD_PARTY_NOTICES.md` for details.
