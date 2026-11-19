# UART

UART setup, byte I/O, formatting, and line input.

```c
import "lib/uart.nbl";
```

## Setup

```c
uart_route(1);   // main I/O connector
uart_init(3);    // baud index 3: 9600
```

`uart_init(baud)` writes the low three bits of `SerCtrl`. `uart_route(1)`
selects the main I/O connector; `uart_route(0)` selects the SAO header.

`uart_available()` returns the unread-byte count saturated at 15.
`uart_error()` returns nonzero when the sticky error bit is set and clears it.
`uart_baud()` returns the baud index and also clears the error bit.

`uart_puts` and `puts` read flash strings. `uart_write` sends `len` bytes from
a RAM `char[]`; pass `&buf`. `uart_print_str` sends a RAM byte string.
`uart_print_hexdump` prints `len` bytes as hex.

## Functions

| Call | Returns | Notes |
|---|---|---|
| `uart_init(nibble baud)` | `void` |  |
| `uart_available()` | `nibble` |  |
| `uart_puts(flashptr s)` | `void` | Send a flash string (literal, const char[], or flashptr). |
| `uart_write(char addr, nibble len)` | `void` | Send len bytes from a RAM char array (pass &buf). |
| `putchar(char c)` | `void` |  |
| `puts(flashptr s)` | `void` |  |
| `uart_error()` | `nibble` | Reading SerCtrl clears the sticky error bit. |
| `uart_baud()` | `nibble` |  |
| `uart_drain()` | `void` |  |
| `uart_route(nibble enable)` | `void` | Route the UART to the main I/O connector (enable) or SAO header (disable). |
| `uart_nl()` | `void` |  |
| `uart_print_nibble(nibble v)` | `void` |  |
| `uart_print_hex8(char v)` | `void` |  |
| `uart_print_bin4(nibble v)` | `void` |  |
| `uart_print_bin8(char v)` | `void` |  |
| `uart_print_bin16(uint16_t v)` | `void` |  |
| `uart_print_bin32(uint32_t v)` | `void` |  |
| `uart_print_dec8(char v)` | `void` |  |
| `uart_print_hex16(uint16_t v)` | `void` |  |
| `uart_print_dec16(uint16_t v)` | `void` |  |
| `uart_print_dec8_signed(char v)` | `void` | Signed decimal formatting for raw two's-complement values. |
| `uart_print_dec16_signed(uint16_t v)` | `void` |  |
| `uart_print_hex32(uint32_t v)` | `void` |  |
| `uart_print_dec32(uint32_t v)` | `void` |  |
| `uart_print_dec32_signed(int32_t v)` | `void` |  |
| `uart_print_str(char addr)` | `void` |  |
| `uart_print_hexdump(char addr, nibble len)` | `void` |  |
| `uart_hex_value(char c)` | `char` |  |
| `uart_read_hex8()` | `char` |  |
| `uart_read_nibble()` | `nibble` |  |
| `uart_read_line(char addr, nibble max)` | `nibble` | Read bytes until CR or LF.  Returns the number of bytes stored.  The buffer is terminated with 0x00 and is not echoed. |
