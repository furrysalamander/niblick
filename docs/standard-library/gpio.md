# GPIO

Bank-aware GPIO port access. The constant-mask bit operations are compiler
intrinsics; this module implements whole-port reads, writes, and bank
selection.

```c
import "lib/gpio.nbl";
```

`gpio_read()` returns the active input port. `gpio_write(value)` writes the
active output latch. Both honor `WrFlags.IOPos`.

`gpio_alt(1)` moves `OUT`/`IN` to `0xFA`/`0xFB` and frees `R10`/`R11`.
`gpio_alt(0)` restores the default port addresses.

The bit operations `gpio_set`, `gpio_clear`, `gpio_toggle`, and `gpio_test`
are compiler intrinsics. See {doc}`intrinsics`.

## Functions

| Call | Returns | Notes |
|---|---|---|
| `gpio_read()` | `nibble` |  |
| `gpio_write(nibble value)` | `void` |  |
| `gpio_alt(nibble enable)` | `void` | Set/clear WrFlags.IOPos (bit 1).  Enable moves OUT/IN to 0xFA/0xFB. |
