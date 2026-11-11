# BadgeC examples

| File | What it shows |
|---|---|
| `hello.badge` | Flash string + UART transmit |
| `serial_echo.badge` | UART receive, `uart_getc`, `uart_putc` |
| `flash_walk.badge` | `flash_next` over a `const char[]` and `const nibble[]` indexing |
| `gpio_blink.badge` | GPIO output + approximate busy delay |
| `hw_test.badge` | Hardware self-test; waits for a `0x01` UART command |
| `keymap.badge` | Prints `KeyReg`/`KeyStatus` for each front-panel button |
| `hello_loop.badge` | Repeating UART hello, useful for link checks |
| `sao_hello.badge` | UART hello routed to the SAO header |
| `tetris.badge` | LED-matrix Tetris; OPCODE 8/1/4/2 = left/right/rotate/soft drop |
| `cube.badge` | Spinning 3D wireframe cube on the LED matrix |
| `wave.badge` | 4×8 signed-nibble wave field from `lib/signed.badge` |
| `water.badge` | Falling-water cellular automaton with changing gravity |
| `stdlib_demo.badge` | Imports `lib/` modules for UART, strings, math, trig, memory, random, keys, clock, power, and display; demonstrates `print()` formatting |
| `text_scroll.badge` | 5x8 scrolling text on the LED matrix |
| `audio_demo.badge` | Square-wave melody on OUT0, including `NOTE_REST` |
| `pdm_demo.badge` | First-order PDM sample playback on OUT1-3 |
| `inline_asm.badge` | Raw `asm { ... }` block with `${...}` variable placeholders |
| `word_math.badge` | 16-bit words, casts, and `* / %` |
| `dword_math.badge` | 32-bit words, casts, and 32-bit arithmetic |
| `math32_test.badge` | 32-bit arithmetic self-test; send `0x01` over UART |
| `w5500_probe.badge` | Read W5500 `VERSIONR`/`PHYCFGR` over SPI and print on UART |
| `w5500_udp.badge` | Send UDP datagrams from `192.168.1.50` to `192.168.1.10:5001` |
| `w5500_http.badge` | Minimal HTTP server at `http://192.168.1.50/` |
| `w5500_dashboard.badge` | Compact interactive LED-matrix/dimmer web controls |
| `w5500_tcp_diag.badge` | Print socket-0 state after CLOSE, OPEN, and LISTEN |
| `mc_void.badge` | Minimal Minecraft 1.8.9 server; join a void world over Ethernet |

Compile one with:

```bash
python3 -m badgec examples/hello.badge --run
```

Generated `.asm` and `.hex` files are ignored by git; `make clean` removes
them.
