# Text scrolling

Horizontal text scroller for a 32-nibble framebuffer.

```c
import "lib/textscroll.nbl";
```

`base` is a page-aligned 32-nibble framebuffer. `divider` selects the
`UserSync` rate, for example `SYNC_10HZ`. The scroller uses the top eight rows
of the 8x16 display and shifts one column per sync tick. `text_scroll_once`
restores the previous `Sync` divider; `text_scroll_loop` repeats forever.

## Functions

| Call | Returns | Notes |
|---|---|---|
| `text_scroll_once(char base, flashptr s, nibble divider)` | `void` | Scroll a flash string once.  Restores the previous Sync divider. |
| `text_scroll_loop(char base, flashptr s, nibble divider)` | `void` | Scroll a flash string forever, restarting at the beginning. |
