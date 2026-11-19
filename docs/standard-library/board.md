# Board constants

```c
import "lib/boards/voja4.nbl";
```

`lib/boards/voja4.nbl` defines nibble masks for the Voja4 I/O connector.

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

`OUT0` and `IN0` both have mask 1. They address separate output and input
ports.

## Default SPI and W5500 assignments

| Constant | Value |
|---|---|
| `SPI_SCLK` | `OUT2` |
| `SPI_MOSI` | `OUT3` |
| `SPI_MISO` | `IN0` |
| `W5500_CS` | `OUT1` |
| `W5500_RST` | `OUT0` |
| `SPI_CS` | Alias for `W5500_CS` |

See {doc}`spi` and {doc}`drivers/w5500`.
