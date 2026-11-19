# Power

Auto-off counter and sleep control.

```c
import "lib/power.nbl";
```

`AutoOff` counts down in 10-minute units. Writing 0 enters sleep immediately.
`power_auto_off_minutes` rounds down and saturates at `POWER_MAX`.

## Constants

| Name | Type | Value |
|---|---|---|
| `POWER_MAX` | `nibble` | `15` |
| `POWER_10_MIN` | `nibble` | `1` |
| `POWER_150_MIN` | `nibble` | `15` |

## Functions

| Call | Returns | Notes |
|---|---|---|
| `power_keep_awake()` | `void` |  |
| `power_auto_off(nibble units)` | `void` |  |
| `power_auto_off_minutes(char minutes)` | `void` | minutes is rounded down to 10-minute units and saturates at 150 minutes. 0 sleeps immediately. |
| `power_sleep()` | `void` |  |
| `power_remaining()` | `nibble` |  |
