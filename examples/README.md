# Niblick examples

| File | What it shows |
|---|---|
| `hello.nbl` | Flash string + UART transmit |
| `serial_echo.nbl` | UART receive, `uart_getc`, `uart_putc` |
| `flash_walk.nbl` | `flash_next` over a `const char[]` and `const nibble[]` indexing |
| `gpio_blink.nbl` | GPIO output + approximate busy delay |
| `hw_test.nbl` | Hardware self-test; waits for a `0x01` UART command |
| `keymap.nbl` | Prints `KeyReg`/`KeyStatus` for each front-panel button |
| `hello_loop.nbl` | Repeating UART hello, useful for link checks |
| `sao_hello.nbl` | UART hello routed to the SAO header |
| `tetris.nbl` | LED-matrix Tetris; OPCODE 8/1/4/2 = left/right/rotate/soft drop |
| `cube.nbl` | Spinning 3D wireframe cube on the LED matrix |
| `wave.nbl` | 4×8 signed-nibble wave field from `lib/signed.nbl` |
| `water.nbl` | Falling-water cellular automaton with changing gravity |
| `stdlib_demo.nbl` | Imports `lib/` modules for UART, strings, math, trig, memory, random, keys, clock, power, and display; demonstrates `print()` formatting |
| `struct_demo.nbl` | Struct fields and arrays of structs |
| `text_scroll.nbl` | 5x8 scrolling text on the LED matrix |
| `audio_demo.nbl` | Square-wave melody on OUT0, including `NOTE_REST` |
| `pdm_demo.nbl` | First-order PDM sample playback on OUT1-3 |
| `inline_asm.nbl` | Raw `asm { ... }` block with `${...}` variable placeholders |
| `u16_math.nbl` | 16-bit integers, casts, and `* / %` |
| `u32_math.nbl` | 32-bit integers, casts, and 32-bit arithmetic |
| `math32_test.nbl` | 32-bit arithmetic self-test; send `0x01` over UART |
| `pi.nbl` | Computes pi to 44 decimal places over UART, then scrolls it on the LED matrix |
| `w5500_probe.nbl` | Read W5500 `VERSIONR`/`PHYCFGR` over SPI and print on UART |
| `w5500_udp.nbl` | Send UDP datagrams from `192.168.1.50` to `192.168.1.10:5001` |
| `w5500_http.nbl` | Minimal HTTP server at `http://192.168.1.50/` |
| `w5500_dashboard.nbl` | Compact interactive LED-matrix/dimmer web controls |
| `w5500_tcp_diag.nbl` | Print socket-0 state after CLOSE, OPEN, and LISTEN |
| `mc_void.nbl` | Minimal Minecraft 1.8.9 server; join a void world over Ethernet |

Compile one with:

```bash
python3 -m niblick examples/hello.nbl --run
```

Generated `.asm` and `.hex` files are ignored by git; `make clean` removes
them.
