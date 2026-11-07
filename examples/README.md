# BadgeC examples

| File | What it shows |
|---|---|
| `hello.badge` | Flash string + UART transmit |
| `serial_echo.badge` | UART receive, `uart_getc`, `uart_putc` |
| `flash_walk.badge` | `flash_next` over a `const char[]` and `const nibble[]` indexing |
| `gpio_blink.badge` | GPIO output + approximate busy delay |
| `hw_test.badge` | 67-check hardware self-test; waits for a `0x01` UART command |
| `keymap.badge` | Prints `KeyReg`/`KeyStatus` for each front-panel button |
| `hello_loop.badge` | Repeating UART hello, useful for link checks |
| `sao_hello.badge` | UART hello routed to the SAO header |
| `tetris.badge` | LED-matrix Tetris; OPCODE 8/1/4/2 = left/right/rotate/soft drop |
| `stdlib_demo.badge` | Imports `lib/` modules for UART, strings, math, bits, keys, clock, and display |
| `word_math.badge` | 16-bit words, casts, and `* / %` |

Compile one with:

```bash
python3 -m badgec examples/hello.badge --run
```

Generated `.asm` and `.hex` files are ignored by git; `make clean` removes
them.
