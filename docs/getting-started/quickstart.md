# Quick start

## Compile and run

```bash
python3 -m niblick examples/hello.nbl --run
```

The compiler writes `<source>.asm` and `<source>.hex` next to the source file.
`--run` loads the `.hex` into the headless emulator and prints UART output,
register state, and an instruction count.

## Source example

```c
import "lib/uart.nbl";

const char message[] = "Hello, Supercon!\n";

fn main() {
    uart_route(1);
    uart_init(3);
    uart_puts(message);
}
```

## Run in a browser

The hosted editor at <https://furrysalamander.github.io/niblick/> compiles and
runs Niblick programs without a local installation.

## Inspect the build

```bash
python3 -m niblick examples/hello.nbl --symbols --stack
python3 -m niblick examples/hello.nbl --map --callgraph
```

See {doc}`cli` for the complete command reference.
