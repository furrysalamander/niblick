# Examples

| File | Demonstrates |
|---|---|
| `hello.nbl` | Flash string and UART transmit |
| `serial_echo.nbl` | UART receive, `uart_getc`, `uart_putc` |
| `flash_walk.nbl` | `flash_next` over `const char[]` and `const nibble[]` |
| `gpio_blink.nbl` | GPIO output and busy delay |
| `hw_test.nbl` | Hardware self-test; waits for `0x01` on UART |
| `keymap.nbl` | Prints `KeyReg` and `KeyStatus` for each button |
| `hello_loop.nbl` | Repeating UART hello |
| `sao_hello.nbl` | UART hello routed to the SAO header |
| `tetris.nbl` | LED-matrix Tetris |
| `cube.nbl` | 3D wireframe cube |
| `wave.nbl` | 4x8 signed-nibble wave field |
| `water.nbl` | Falling-water cellular automaton |
| `stdlib_demo.nbl` | Imports for UART, strings, math, trig, memory, random, keys, clock, power, and display |
| `struct_demo.nbl` | Struct fields and arrays of structs |
| `text_scroll.nbl` | 5x8 scrolling text |
| `audio_demo.nbl` | Square-wave melody on `OUT0` |
| `pdm_demo.nbl` | PDM sample playback on `OUT1` through `OUT3` |
| `inline_asm.nbl` | Inline `asm` block with `${...}` placeholders |
| `u16_math.nbl` | 16-bit integers, casts, `*`, `/`, and `%` |
| `u32_math.nbl` | 32-bit integers, casts, and arithmetic |
| `math32_test.nbl` | 32-bit arithmetic self-test |
| `pi.nbl` | Pi digits over UART and on the LED matrix |
| `w5500_probe.nbl` | W5500 `VERSIONR` and `PHYCFGR` probe |
| `w5500_udp.nbl` | UDP sender |
| `w5500_http.nbl` | Minimal HTTP server |
| `w5500_dashboard.nbl` | LED-matrix and dimmer controls |
| `w5500_tcp_diag.nbl` | Socket-state diagnostics |
| `mc_void.nbl` | Minecraft 1.8.9 void server |

## Tetris controls

| Key | Action |
|---|---|
| `OPCODE 8` | Left |
| `OPCODE 1` | Right |
| `OPCODE 4` | Rotate |
| `OPCODE 2` | Soft drop |

## Build and run

```bash
python3 -m niblick examples/hello.nbl --run
python3 -m niblick examples/tetris.nbl --symbols
```

Generated `.asm` and `.hex` files are ignored by Git. `make clean` removes
them.
