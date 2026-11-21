# Display

Display pages, the 8x16 framebuffer, pixels, lines, rectangles, and column
updates.

```c
import "lib/display.nbl";
```

## Framebuffer layout

A framebuffer is 32 nibbles aligned to two consecutive display pages. Pass the
array's nibble address as `base`, normally `&screen`.

- Row `y` is at `base + y` on the right half, columns 4 through 7.
- Row `y` is at `base + 16 + y` on the left half, columns 0 through 3.
- `base` must be page-aligned.
- Bit 3 is the leftmost pixel in each nibble; bit 0 is the rightmost.

## Functions

| Call | Returns | Notes |
|---|---|---|
| `display_page(nibble page)` | `void` |  |
| `display_page_get()` | `nibble` |  |
| `display_poke(nibble page, nibble index, nibble value)` | `void` |  |
| `display_peek(nibble page, nibble index)` | `nibble` |  |
| `dimmer(nibble value)` | `void` | Set the LED PWM duty (0..15; 15 = brightest). |
| `dimmer_get()` | `nibble` |  |
| `leds_enable(nibble enable)` | `void` | Enable/disable the ALU panel LEDs (WrFlags.LedsOff, bit 3). |
| `matrix_enable(nibble enable)` | `void` | Enable/disable the LED matrix (WrFlags.MatrixOff, bit 2). |
| `display_show(char base)` | `void` | Show the two display pages that contain a 32-nibble framebuffer. |
| `display_fill(nibble page, nibble value)` | `void` |  |
| `display_clear(nibble page)` | `void` |  |
| `display_invert(nibble page)` | `void` |  |
| `display_copy(nibble src, nibble dst)` | `void` |  |
| `disp_addr(char base, nibble x, char y)` | `char` |  |
| `disp_mask(nibble x)` | `nibble` |  |
| `pixel_get(char base, nibble x, char y)` | `nibble` |  |
| `pixel_set(char base, nibble x, char y, nibble on)` | `void` |  |
| `pixel_toggle(char base, nibble x, char y)` | `void` |  |
| `pixel_clear(char base, nibble x, char y)` | `void` |  |
| `hline(char base, nibble x0, nibble x1, char y, nibble on)` | `void` |  |
| `vline(char base, nibble x, char y0, char y1, nibble on)` | `void` |  |
| `fill_rect(char base, nibble x0, char y0, nibble x1, char y1, nibble on)` | `void` |  |
| `clear_screen(char base)` | `void` |  |
| `display_shift_left(char base)` | `void` | Shift a 32-nibble framebuffer one pixel to the left.  Bit 3 is the leftmost pixel in each nibble. |
| `display_set_column(char base, nibble x, char bits)` | `void` | Set the top eight rows of one pixel column from an 8-bit column value. |
