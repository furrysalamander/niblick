# Font

5x8 font glyphs for ASCII 32 through 127.

```c
import "lib/font.nbl";
```

A glyph is five columns wide and eight rows tall. `font5x8_column(c, col)`
returns one column with the top pixel in bit 7. `text_draw_char` draws at the
top-left pixel and clips to the 8x16 display.

## Functions

| Call | Returns | Notes |
|---|---|---|
| `font5x8_column(char c, nibble col)` | `char` | Return one 8-bit column (top-to-bottom) for a character. |
| `font5x8_width(char c)` | `nibble` |  |
| `text_draw_char(char base, nibble x, char y, char c)` | `void` | Draw one glyph at (x, y) in a 32-nibble framebuffer.  The glyph is five columns wide and eight rows tall; drawing is clipped to the 8x16 display. |
