# Voja4 pin map

The badge exposes four output bits and four input bits on the main I/O
connector. Pins are accessed as **bit masks**, not bit indices, through the
GPIO helpers.

All board-specific assignments live in `lib/boards/voja4.badge`:

```c
import "lib/boards/voja4.badge";
```

## Output pins

| Constant | Mask | Bit |
|---|---:|---:|
| `OUT0` | 1 | 0 |
| `OUT1` | 2 | 1 |
| `OUT2` | 4 | 2 |
| `OUT3` | 8 | 3 |

## Input pins

| Constant | Mask | Bit |
|---|---:|---:|
| `IN0` | 1 | 0 |
| `IN1` | 2 | 1 |
| `IN2` | 4 | 2 |
| `IN3` | 8 | 3 |

`gpio_read()` and `gpio_write()` operate on the whole 4-bit port. The
constant-mask helpers operate on individual bits:

```c
gpio_set(OUT2);
gpio_clear(OUT2);
gpio_toggle(OUT2);
if (gpio_test(IN0)) {
    ...
}
```

Remember that `OUT0` and `IN0` are both mask `1`; they are only distinguished
by which port operation uses them. Writing `IN0` with `gpio_set` would modify
`OUT0`, because the output and input ports are separate.

## Default wiring

| Signal | Constant | Mask |
|---|---|---:|
| W5500 reset | `W5500_RST` | 1 (`OUT0`) |
| W5500 chip select | `W5500_CS` | 2 (`OUT1`) |
| SPI clock | `SPI_SCLK` | 4 (`OUT2`) |
| SPI MOSI | `SPI_MOSI` | 8 (`OUT3`) |
| SPI MISO | `SPI_MISO` | 1 (`IN0`) |

`SPI_CS` remains as a backwards-compatible alias for `W5500_CS`; new code
should use `W5500_CS`.

The SPI and W5500 drivers use GPIO bank 0 (`WrFlags.IOPos = 0`). If a project
needs bank 1, use `gpio_alt(1)` and keep the bank state consistent across all
drivers.

## Changing the wiring

Edit `lib/boards/voja4.badge` rather than changing constants in individual
drivers. `lib/spi.badge`, `lib/drivers/w5500.badge`, and the W5500 examples all
import that board file.

If a project adds an SD card or SPI flash, give each device its own chip-select
mask in the board file and keep the unused chip selects high.
