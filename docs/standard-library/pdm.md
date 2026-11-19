# PDM

First-order PDM sample playback on `OUT1` through `OUT3`.

```c
import "lib/pdm.nbl";
```

`pdm_init()` selects `CLOCK_250K` and clears the error accumulator. The encoder
drives `OUT1` through `OUT3`; bit 0 stays high. A sample table is a flash byte
table terminated by `0xFF`. `pdm_play_loop` restarts at the beginning after the
terminator.

## Functions

| Call | Returns | Notes |
|---|---|---|
| `pdm_init()` | `void` |  |
| `pdm_silence()` | `void` |  |
| `pdm_encode(nibble sample)` | `void` | Encode one 4-bit sample.  Call this in a tight loop for streaming audio. |
| `pdm_play(flashptr samples)` | `void` | Play a flash sample table terminated by 0xFF. |
| `pdm_play_loop(flashptr samples)` | `void` | Play a flash sample table forever. |
