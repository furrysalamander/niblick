# BadgeC — a compiler for the Supercon.6 (Voja4) badge

BadgeC is a small C-like cross-compiler for the Hackaday Supercon.6 2022
badge. It compiles to the badge's 12-bit assembly, uses the vendored
assembler to produce a `.hex` file, and includes a headless emulator for
fast tests.

The badge CPU is extremely small: 4-bit data, 4,096 12-bit code words,
256 nibbles of data RAM, 10 general registers, and a 5-level hardware call
stack. BadgeC is designed around those constraints rather than pretending
it is a normal 8-bit machine.

## Status

Working today:

- `nibble` (u4), `char` (u8), `word` (u16), `dword` (u32), and `flashptr` (12-bit code address)
- Globals, locals, fixed-size RAM arrays, `const` flash arrays, and scalar `const` values folded to immediates
- Functions, parameters, returns, and tail-call optimization
- `if`/`else`, `while`, `for`, `break`, `continue`
- Arithmetic (`+ - * / %`), bitwise operators, constant and variable shifts, comparisons, `&&`, `||`, `!`
- Explicit casts: `(nibble)`, `(char)`, `(word)`, `(dword)`
- `import` for the opt-in modules in `lib/` (UART formatting, strings, math, memory, keys, time, display)
- Imported `.asm` modules with `extern fn` declarations, `${...}` symbol placeholders, call-graph/runtime-linker scanning, and per-file/per-region `no-optimize` markers
- Inline `asm { ... }` blocks inside BadgeC functions, with lexical `${...}` placeholders, local labels, call-graph integration, and optimizer opacity
- VS Code extension with BadgeC/Voja4 assembly highlighting, compiler diagnostics, document symbols, hover, completion, go-to-definition, references, rename, and an emulator debugger
- Flash strings and `RET`-table iteration
- UART runtime: `uart_init`, `uart_putc`, `uart_getc`, `uart_available`, `uart_puts`
- RAM helpers: `peek`, `poke`, `memset`, `uart_write`, `delay`
- Direct I/O: `in`, `out`
- GPIO: `gpio_read`, `gpio_write`, `gpio_set`, `gpio_clear`, `gpio_toggle`, `gpio_test`, `gpio_alt`, `uart_route`
- System/SFR helpers: `display_page`, `display_poke`, `display_peek`, `random`, `seed`, `dimmer`, `key_status`, `key_code`, `key_any`, `key_alt`, `key_just`, `key_last`, `leds_enable`, `matrix_enable`
- Rejection of non-tail recursion with a compile-time error
- Code/RAM size reporting, per-function sizes, stack-cost reports, I/O tracing, and a headless emulator test harness

Not implemented yet:

- General (non-tail) recursion
- 64-bit integers and floating point
- Native signed types (raw-bit signed helpers live in `lib/signed.badge`)
- General pointers and pointer arithmetic
- Structs, varargs, dynamic allocation
- Register allocation, local overlay, and a broader peephole/optimization pipeline
- UART interrupt-driven or buffered I/O beyond the hardware FIFO

32-bit `*`, `/`, and `%` are implemented but deliberately size-conscious:
they use a 24-nibble scratch block allocated only when the program uses
them, and a 32-bit divide takes milliseconds at 250 kHz. See
`docs/compiler.md` and `docs/stdlib.md`.

## Quick start

```bash
python3 -m badgec examples/hello.badge --run
```

This writes `examples/hello.asm` and `examples/hello.hex`, then runs the
program in the emulator. To emit assembly only:

```bash
python3 -m badgec examples/hello.badge --no-assemble
```

To print the global memory map:

```bash
python3 -m badgec examples/serial_echo.badge --map
```

Diagnostics:

```bash
python3 -m badgec examples/hello.badge --run --trace --trace-limit 20 --dump-uart
python3 -m badgec examples/hello.badge --symbols --callgraph --stack
python3 -m badgec examples/hello.badge --run --trace-io --io-trace-limit 200
python3 -m badgec examples/hello.badge --map-json hello.map.json
```

## Language sketch

```c
const char greeting[] = "Hello, Supercon!\n";
const nibble LED_CLOCK = 1;
const nibble LED_DATA  = 2;

char rxbuf[16];
nibble count;

fn nibble add(nibble a, nibble b) {
    return a + b;
}

fn nibble count_down(nibble n, nibble acc) {
    if (n == 0) {
        return acc;
    }
    return count_down(n - 1, acc + 1);   // tail call -> GOTO
}

fn main() {
    uart_init(3);                         // 3 = 9600 baud
    uart_puts(greeting);
    count = count_down(10, 0);

    while (uart_available() == 0) {
    }
    rxbuf[0] = uart_getc();
}
```

`char` is unsigned 8-bit. A RAM `char[]` costs two nibbles per element.
A `const char[]` lives in program memory as a `RET` table: two code words
per character, read with `flash_next(&p)` or `flash_read_char(ptr)`.
Strings use `0xFF` as the terminator.

## Architecture

```text
source.badge
   -> lexer -> parser -> AST
   -> BadgeC code generator (fixed-register expression convention)
   -> badge assembly
   -> vendored assemble.py
   -> .hex
```

Imported `.asm` modules are read by the loader and appended at link time;
`extern fn` declarations give the compiler their signatures and static
parameter slots.

Expression results use fixed registers:

| Type | Result |
|---|---|
| `nibble` | `R1` |
| `char` | `R1` (low), `R2` (high) |
| `flashptr` | `R1` (low), `R2` (middle), `R3` (high) |

Nested expression temporaries live in `0x20..0x3F`. Variables and arrays
are allocated from `0x40..0xEF`. The hardware call stack at `0x10..0x1F`
is used by `GOSUB`/`RET`.

Tail calls compile to `GOTO`, so tail recursion does not consume a
hardware stack level. Non-tail recursion is rejected because the hardware
stack is only five entries deep and there is no stack-relative addressing.

## Testing

```bash
python3 -m pytest
```

The test suite covers the emulator's instruction semantics and end-to-end
BadgeC programs: loops, char arrays, functions, tail recursion, flash
string iteration, UART transmit/receive, and error cases.

The emulator lives in `badgec/emulator.py` and models the CPU plus a small
UART FIFO so serial programs can be tested without hardware. It does not
model real-time clock speed, LED persistence, or every SFR side effect.

## Hardware workflow

The badge's serial load protocol is raw 9600 8N1. Put the badge in **DIR**
mode, press **LOAD**, then send the `.hex` file:

```bash
stty -F /dev/ttyUSB0 raw 9600
cat examples/hello.hex > /dev/ttyUSB0
```

Or use the helper:

```bash
python3 scripts/flash.py /dev/ttyUSB0 examples/hello.hex
```

To watch serial output:

```bash
python3 scripts/monitor.py /dev/ttyUSB0
```

Hardware self-test:

```bash
python3 -m badgec examples/hw_test.badge
# load examples/hw_test.hex, press RUN, then:
python3 scripts/hw_test.py /dev/ttyUSB0
```

The self-test waits for a single `0x01` byte, so it has no sync race. It
prints a PASS/FAIL line for each check and a final `DONE pass=XX fail=YY`
summary.

The badge is a 3 V device. Use a 3.3 V USB-UART adapter or Tigard; do not
use RS-232 voltage levels. See `docs/serial.md` and `docs/toolchain.md`.

## LED-matrix demo: Tetris

`examples/tetris.badge` is a playable 8×16 Tetris demo:

- OPCODE `8` = left
- OPCODE `1` = right
- OPCODE `4` = rotate
- OPCODE `2` = soft drop

It starts at the slowest fall setting and speeds up every **8 cleared
lines**. The badge's global `Dimmer` PWM is used for line-clear flashes and
the game-over fade.

The image uses about 2494 of 4096 words and 164 of 208 RAM nibbles. The
compiler's condition lowering, copy propagation, and spill elimination left
roughly 1600 words of headroom for new features.

The physical `KeyReg` mapping was measured with `examples/keymap.badge`; see
`docs/keys.md`.

## LED-matrix demo: spinning cube

`examples/cube.badge` draws a rotating 3D wireframe cube on the 8×16 matrix.
It uses a fixed-point yaw sweep, a fixed 30° camera pitch, a slightly wider
horizontal scale, and a small fixed roll. Bresenham line drawing fills a 16×16
off-screen framebuffer with four columns of margin on each side. Copying only
the middle eight columns gives true clipping: off-screen edges disappear
instead of being pinned to the outermost columns.

The demo is about 1792 words and 165 RAM nibbles; it needs no UART or input
and starts spinning as soon as it runs.

## LED-matrix demo: signed wave field

`examples/wave.badge` runs a 4×8 height-field wave on the 8×16 matrix. Heights
are signed nibbles stored as raw two's complement, and the display draws each
cell as a 2×2 block. A centre impulse is injected every 48 frames.

The update uses `lib/signed.badge` for sign extension, arithmetic shifts, and
clamping:

```c
next_height = sum(neighbours) / 2 - previous_height
```

It is about 1027 words and 164 RAM nibbles. This is the small-scale prototype
for deciding whether native signed types are worth adding; the helpers are
currently sufficient.

## LED-matrix demo: falling water

`examples/water.badge` is a falling-sand style water cellular automaton on the
full 8×16 matrix. Each cell is empty or water, water falls in the current
gravity direction, slides diagonally when blocked, and spreads sideways when
it piles up. Water is just a lit LED; the display edges are the only walls.

The amount of water is fixed at startup (a centred five-row band), and
gravity cycles through down, left, up, and right every 16 simulation frames.
The water therefore sloshes around the box instead of settling permanently.

The 8×16 grid uses two bits per cell (water and a "moved this frame" bit) in
64 nibbles. The visible page is updated one pixel at a time, without clearing
the whole screen, so there is no full-frame blank. The demo is about 1910
words and 139 RAM nibbles.

## Ethernet demo: W5500 UDP

`examples/w5500_udp.badge` bit-bangs SPI to a Wiznet W5500 and sends UDP
datagrams to a host.

- Badge: `192.168.1.50`
- Host: `192.168.1.10`
- Badge source port: `5000`
- Host destination port: `5001`
- Payload: `hello from badge\n`

Default SPI wiring: `OUT2=SCLK`, `OUT3=MOSI`, `OUT1=CS`, `IN0=MISO`, and
`OUT0=W5500 RST` if reset is controlled by the badge. The W5500 needs a clean
3.3 V supply and roughly 130 mA; a separate 3.3 V supply with common ground is
recommended.

Use `examples/w5500_probe.badge` first to confirm `VERSIONR == 0x04` and check
the PHY link before running the UDP demo. `examples/w5500_http.badge` adds a
minimal TCP listener on port 80:

```bash
curl http://192.168.1.50/
```

`examples/w5500_dashboard.badge` adds a compact interactive page with matrix
pattern and dimmer buttons. It is deliberately minified to fit the badge's
4096-word flash: about **4031 words**.

## Minecraft 1.8.9 void server

`examples/mc_void.badge` turns the badge and W5500 into a minimal Minecraft
Java Edition 1.8.9 (protocol 47) server. It answers the server-list ping and
lets one vanilla 1.8.9 client join a small 16x16 stone platform in an
otherwise empty void world in creative mode.

- Badge: `192.168.1.50:25565`
- Client: vanilla 1.8.9 / protocol 47, offline mode
- One player, no encryption, no compression, no world storage
- **4045 / 4096 words**, **133 / 208 RAM nibbles**, max call depth 4

Use a 1.8.9 client; modern clients can display the MOTD but cannot join. The
server never sends an Encryption Request, so it behaves like an offline-mode
server. The Login Success name is fixed to `Player` to keep the packet in
flash, and the world is one chunk section with a 16x16 stone platform at
y=64, full light, and the void biome. Players can break blocks and place
stone on all six faces; the server confirms changes with Block Change
packets. The client may keep showing a different creative block locally until
reconnect; the server's authoritative placement is always stone. There is no
world storage, so the platform regenerates on reconnect. Run
`examples/w5500_probe.badge` first to confirm the W5500 link, then flash
`examples/mc_void.hex` and connect with a 1.8.9 client.

The protocol path is covered by `tests/test_mc_void.py`, which runs the
firmware in the emulator against a localhost 1.8.9 protocol client through the
W5500/TCP model in `tests/w5500_sim.py`. The same status/login/chunk/keepalive
exchange has also been run against the badge hardware over Ethernet; a real
vanilla client is the remaining check. See [docs/minecraft.md](docs/minecraft.md)
for the packet sequence and firmware limits.

## Library modules

`lib/` contains opt-in BadgeC modules for UART formatting, strings, math,
two's-complement signed helpers and Q4.4 fixed point, nibble memory and bit
operations, key helpers, clock/sync helpers, bit-banged SPI, and a minimal
W5500 Ethernet driver. `lib/asm/` contains hand-written assembly modules
exposed to BadgeC with `extern fn` declarations.

```c
import "lib/uart.badge";
import "lib/string.badge";

char buf[16];

fn main() {
    uart_route(1);
    uart_init(3);
    str_copy_flash(&buf, "hi");
    uart_print_str(&buf);
    uart_nl();
}
```

Imports resolve relative to the importing file and then the repository root.
Unused module functions and pure globals are removed, so an import costs
nothing until you use it. See `docs/stdlib.md` and
`examples/stdlib_demo.badge`.

## Documentation

- `docs/isa.md` — instruction set and code-generation notes
- `docs/memory-map.md` — data/code memory and SFRs
- `docs/serial.md` — UART details and load/save workflow
- `docs/stdlib.md` — builtins and runtime routines
- `docs/runtime-abi.md` — BadgeC calling convention and runtime
- `docs/compiler.md` — compiler internals and optimization roadmap
- `docs/asm-imports.md` — imported `.asm` modules, `extern fn`, placeholders, and optimizer markers
- `docs/inline-asm.md` — raw `asm { ... }` blocks inside BadgeC functions
- `docs/vscode.md` — VS Code language support and language-server development
- `docs/debugging.md` — emulator debugger, breakpoints, variables, and debug maps
- `docs/testing.md` — test layers and hardware development loop
- `docs/keys.md` — measured front-panel key codes
- `docs/toolchain.md` — assembler/emulator usage
- `docs/upstream/` — vendored manuals and license/provenance notes

## Vendored tools

The upstream Hack-a-Day tools and manuals are vendored under
`vendor/2022-Supercon6-Badge-Tools/` and copied into `docs/upstream/`.
The assembler is MIT-licensed; the emulator is GPLv3. Preserve their
licenses. See `docs/upstream/README.md`.

## Roadmap

1. Peephole optimizer and constant folding.
2. Size-aware inlining and call-graph local overlay.
3. Multiplication/division/shift runtime routines.
4. General `flashptr` arithmetic and 2D const tables.
5. Hardware validation with the Tigard and the real badge.
6. Optional C front-end experiments on top of the existing IR/backend.
