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

- `nibble` (u4), `char` (u8, two nibbles), and `flashptr` (12-bit code address)
- Globals, locals, fixed-size RAM arrays, and `const` flash arrays
- Functions, parameters, returns, and tail-call optimization
- `if`/`else`, `while`, `for`, `break`, `continue`
- Arithmetic, bitwise operators, comparisons, `&&`, `||`, `!`
- Flash strings and `RET`-table iteration
- UART runtime: `uart_init`, `uart_putc`, `uart_getc`, `uart_available`, `uart_puts`
- RAM helpers: `peek`, `poke`, `memset`, `uart_write`, `delay`
- Direct I/O: `in`, `out`
- GPIO: `gpio_read`, `gpio_write`, `gpio_set`, `gpio_clear`, `gpio_toggle`, `gpio_test`, `gpio_alt`, `uart_route`
- System/SFR helpers: `display_page`, `display_poke`, `display_peek`, `random`, `seed`, `dimmer`, `key_status`, `key_code`, `key_any`, `key_alt`, `key_just`, `key_last`, `leds_enable`, `matrix_enable`
- Rejection of non-tail recursion with a compile-time error
- Code/RAM size reporting and a headless emulator test harness

Not implemented yet:

- General (non-tail) recursion
- Multiplication, division, shifts
- General pointers and pointer arithmetic
- Structs, floats, varargs, dynamic allocation
- Register allocation, local overlay, and a broader peephole/optimization pipeline
- UART interrupt-driven or buffered I/O beyond the hardware FIFO

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
python3 -m badgec examples/hello.badge --symbols --callgraph --map-json hello.map.json
```

## Language sketch

```c
const char greeting[] = "Hello, Supercon!\n";

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

The image uses about 2475 of 4096 words and 164 of 208 RAM nibbles. The
compiler's condition lowering, copy propagation, and spill elimination left
roughly 1600 words of headroom for new features.

The physical `KeyReg` mapping was measured with `examples/keymap.badge`; see
`docs/keys.md`.

## Library modules

`lib/` contains opt-in BadgeC modules for UART formatting, strings, math,
nibble memory and bit operations, key helpers, and clock/sync helpers:

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
