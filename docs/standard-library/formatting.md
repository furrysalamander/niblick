# Print formatting

`print()` is a compile-time formatter. The format string must be a literal and
`lib/uart.nbl` must be imported.

```c
import "lib/uart.nbl";
import "lib/string.nbl";

nibble n;
uint16_t w;
char buf[8];

n = 5;
w = 1234;
str_copy_flash(&buf, "hi");
print("n={} w={:x}\n", n, w);
print("ram={:s}\n", &buf);
print("flash={}\n", "hello");
```

## Placeholders

| Placeholder | Meaning |
|---|---|
| `{}` / `{:d}` | Decimal integer, or a flash string for `flashptr` |
| `{:x}` | Hex, fixed width for the argument type |
| `{:b}` | Binary, fixed width for the argument type |
| `{:c}` | One character |
| `{:s}` | String: `flashptr` or a RAM string address |
| `{{` / `}}` | Literal braces |

Decimal formatting follows the argument type: unsigned values print unsigned,
signed values print a leading `-` when negative, and `bool` prints as `0` or
`1`. Hex and binary formatting show the raw bits at the argument width.

The expansion emits calls such as `uart_puts`, `uart_print_dec16`,
`uart_print_dec16_signed`, and `uart_print_hex8`. There is no runtime format
parser and no argument block. Only formatters used by the program are linked.

Dynamic format strings, width specifiers, and precision specifiers are
rejected.

## UART setup

```c
uart_route(1);
uart_init(3);
print("ready\n");
```

See {doc}`uart` for baud indices and routing.
