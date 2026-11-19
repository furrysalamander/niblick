# Time

Clock and Sync control, plus busy and frame-based delays.

```c
import "lib/time.nbl";
```

`Clock` selects the CPU clock divider. `Sync` selects the `UserSync` flag rate.
Reading `RdFlags` clears `UserSync`; `time_sync_seen()` performs that read.

`time_delay_ms` uses `Sync=0` for one-millisecond ticks. The first tick can be
up to one millisecond early because writing `Sync` does not reset the divider.

## Constants

| Name | Type | Value |
|---|---|---|
| `CLOCK_250K` | `nibble` | `0` |
| `CLOCK_100K` | `nibble` | `1` |
| `CLOCK_30K` | `nibble` | `2` |
| `CLOCK_10K` | `nibble` | `3` |
| `CLOCK_3K` | `nibble` | `4` |
| `CLOCK_1K` | `nibble` | `5` |
| `CLOCK_500` | `nibble` | `6` |
| `CLOCK_200` | `nibble` | `7` |
| `CLOCK_100` | `nibble` | `8` |
| `CLOCK_50` | `nibble` | `9` |
| `CLOCK_20` | `nibble` | `10` |
| `CLOCK_10` | `nibble` | `11` |
| `CLOCK_5` | `nibble` | `12` |
| `CLOCK_2` | `nibble` | `13` |
| `CLOCK_1` | `nibble` | `14` |
| `CLOCK_0_5` | `nibble` | `15` |
| `SYNC_1000HZ` | `nibble` | `0` |
| `SYNC_600HZ` | `nibble` | `1` |
| `SYNC_400HZ` | `nibble` | `2` |
| `SYNC_250HZ` | `nibble` | `3` |
| `SYNC_150HZ` | `nibble` | `4` |
| `SYNC_100HZ` | `nibble` | `5` |
| `SYNC_60HZ` | `nibble` | `6` |
| `SYNC_40HZ` | `nibble` | `7` |
| `SYNC_25HZ` | `nibble` | `8` |
| `SYNC_15HZ` | `nibble` | `9` |
| `SYNC_10HZ` | `nibble` | `10` |
| `SYNC_6HZ` | `nibble` | `11` |
| `SYNC_4HZ` | `nibble` | `12` |
| `SYNC_2_5HZ` | `nibble` | `13` |
| `SYNC_1_5HZ` | `nibble` | `14` |
| `SYNC_1HZ` | `nibble` | `15` |

## Functions

| Call | Returns | Notes |
|---|---|---|
| `time_delay(nibble units)` | `void` | Approximate busy delay; one unit is a 15x15 inner loop. Duration depends on `Clock`. |
| `time_clock_set(nibble divider)` | `void` |  |
| `time_clock_get()` | `nibble` |  |
| `time_sync_set(nibble divider)` | `void` |  |
| `time_sync_get()` | `nibble` |  |
| `time_sync_seen()` | `nibble` | Reading this clears the current UserSync flag. |
| `time_sync_wait()` | `void` |  |
| `time_delay_frames(nibble count)` | `void` |  |
| `time_delay_ms(uint16_t ms)` | `void` | Wait for ms millisecond ticks using Sync=0.  The first tick can be up to one millisecond early because writing Sync does not reset the divider. |
| `time_delay_ticks(nibble ticks, nibble divider)` | `void` | Wait for a number of ticks at the given Sync divider. |
