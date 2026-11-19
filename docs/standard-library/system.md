# System

Raw status and control SFR access.

```c
import "lib/system.nbl";
```

`system_rd_flags()`, `system_vflag()`, and `system_ser_ctrl()` have read side
effects: reading `RdFlags` clears `UserSync`, and reading `SerCtrl` clears the
UART error bit. The dedicated `system_uart_error()` and `system_uart_baud()`
helpers also read `SerCtrl`.

## Constants

| Name | Type | Value |
|---|---|---|
| `WR_LEDS_OFF` | `nibble` | `8` |
| `WR_MATRIX_OFF` | `nibble` | `4` |
| `WR_IO_POS` | `nibble` | `2` |
| `WR_RX_TX_POS` | `nibble` | `1` |
| `RD_VFLAG` | `nibble` | `2` |
| `RD_USER_SYNC` | `nibble` | `1` |

## Functions

| Call | Returns | Notes |
|---|---|---|
| `system_wr_flags()` | `nibble` |  |
| `system_wr_flags_set(nibble flags)` | `void` |  |
| `system_rd_flags()` | `nibble` |  |
| `system_vflag()` | `nibble` |  |
| `system_user_sync()` | `nibble` |  |
| `system_ser_ctrl()` | `nibble` |  |
| `system_uart_error()` | `nibble` |  |
| `system_uart_baud()` | `nibble` |  |
| `system_page()` | `nibble` |  |
| `system_dimmer()` | `nibble` |  |
