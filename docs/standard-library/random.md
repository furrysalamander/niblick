# Random

Hardware PRNG access and range helpers.

```c
import "lib/random.nbl";
```

`random()` reads the hardware `Random` SFR. Each read advances the generator.
`seed(15)` requests a true-random seed; other values select a deterministic
seed. `rand_below` returns a uniform value in `0..n-1`. `rand_range` returns an
inclusive value and returns `lo` when `hi < lo`.

## Functions

| Call | Returns | Notes |
|---|---|---|
| `random()` | `nibble` |  |
| `seed(nibble value)` | `void` |  |
| `rand_seed(nibble value)` | `void` |  |
| `rand_byte()` | `char` |  |
| `rand_word()` | `uint16_t` |  |
| `rand_below(nibble n)` | `nibble` | Uniform 0..n-1.  n = 0 or 1 returns 0. |
| `rand_range(nibble lo, nibble hi)` | `nibble` | Inclusive range.  hi < lo returns lo. |
| `rand_true()` | `nibble` |  |
