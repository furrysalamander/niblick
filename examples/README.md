# BadgeC examples

| File | What it shows |
|---|---|
| `hello.badge` | Flash string + UART transmit |
| `serial_echo.badge` | UART receive, `uart_getc`, `uart_putc` |
| `flash_walk.badge` | `flash_next` over a `const char[]` and `const nibble[]` indexing |
| `gpio_blink.badge` | GPIO output + approximate busy delay |
| `tetris.badge` | LED-matrix Tetris; OPCODE 8/1/4/2 = left/right/rotate/soft drop |

Compile one with:

```bash
python3 -m badgec examples/hello.badge --run
```

Generated `.asm` and `.hex` files are ignored by git; `make clean` removes
them.
