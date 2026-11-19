# SPI

Bit-banged SPI mode-0 master.

```c
import "lib/spi.nbl";
```

`spi_init()` selects bank 0, drives CS high, and clears SCLK and MOSI. Pin
constants are in {doc}`board`. Transfers are MSB first and sample MISO on the
rising edge. `spi_begin()` asserts CS; `spi_end()` releases it.

## Functions

| Call | Returns | Notes |
|---|---|---|
| `spi_init()` | `void` |  |
| `spi_begin()` | `void` |  |
| `spi_end()` | `void` |  |
| `spi_xfer(char out)` | `char` | Exchange one byte, MSB first, mode 0 (sample MISO on the rising edge). |
