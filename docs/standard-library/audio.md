# Audio

Square-wave tone and melody output on `OUT0`.

```c
import "lib/audio.nbl";
```

`AUDIO_MASK` selects the output pin. `audio_init()` selects `CLOCK_100K`.
Notes 0 through 15 are C4 through D#5. `NOTE_REST` is silent. A melody is a
flash table of note/duration byte pairs terminated by `0xFF`. Rest durations
above 15 are split into 15-unit `delay` calls.

Timing depends on `Clock` and the instruction mix.

## Constants

| Name | Type | Value |
|---|---|---|
| `AUDIO_MASK` | `nibble` | `1` |
| `NOTE_REST` | `char` | `0xFE` |

## Functions

| Call | Returns | Notes |
|---|---|---|
| `audio_init()` | `void` |  |
| `audio_silence()` | `void` |  |
| `audio_tone_raw(uint16_t half_period, uint16_t cycles)` | `void` | Raw tone.  half_period is the inner-loop count; cycles is the number of half periods (two cycles = one full wave). |
| `audio_note(char note, uint16_t cycles)` | `void` | Play one note from the table.  Notes 0..15 are C4..D#5; NOTE_REST is silent, and 0xFF terminates a melody. |
| `audio_play(flashptr melody)` | `void` | Play a flash melody of note/duration byte pairs, terminated by 0xFF. |
