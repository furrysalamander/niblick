# Strings

RAM and flash string operations and integer formatting.

```c
import "lib/string.nbl";
```

RAM strings are byte strings terminated by `0x00`. Addresses are nibble
addresses; each character advances by two. Flash strings are `flashptr`
values.

`str_from_dec16` needs 6 bytes, `str_from_dec32` needs 11 bytes,
`str_from_hex16` needs 5 bytes, and `str_from_hex32` needs 9 bytes. The
`str_from_*` functions return the digit count and always terminate the buffer.

`str_compare` returns `STR_LT`, `STR_EQ`, or `STR_GT`.

## Constants

| Name | Type | Value |
|---|---|---|
| `STR_LT` | `nibble` | `15` |
| `STR_EQ` | `nibble` | `0` |
| `STR_GT` | `nibble` | `1` |

## Functions

| Call | Returns | Notes |
|---|---|---|
| `str_len(char addr)` | `char` |  |
| `str_eq(char a, char b)` | `nibble` | 1 when the strings are identical, including the terminator. |
| `str_copy(char dst, char src)` | `void` |  |
| `str_cat(char dst, char src)` | `void` |  |
| `str_chr(char addr, char ch)` | `char` | Address of the first match, or 0 when absent.  RAM variables start at 0x40, so 0 is safe as "not found". |
| `str_len_flash(flashptr p)` | `char` |  |
| `str_copy_flash(char dst, flashptr src)` | `void` |  |
| `str_from_dec8(char addr, char value)` | `nibble` |  |
| `str_to_dec8(char addr)` | `char` |  |
| `str_from_hex8(char addr, char value)` | `nibble` |  |
| `str_hex_digit(char c)` | `char` |  |
| `str_to_hex8(char addr)` | `char` |  |
| `str_match_at(char addr, flashptr needle)` | `nibble` |  |
| `str_find(char addr, flashptr needle)` | `char` |  |
| `str_contains(char addr, flashptr needle)` | `nibble` |  |
| `str_starts_with(char addr, flashptr prefix)` | `nibble` |  |
| `str_eq_flash(char addr, flashptr s)` | `nibble` |  |
| `str_cat_flash(char dst, flashptr src)` | `void` |  |
| `str_compare(char a, char b)` | `nibble` |  |
| `str_upper(char addr)` | `void` |  |
| `str_lower(char addr)` | `void` |  |
| `str_reverse(char addr)` | `void` |  |
| `str_trim(char addr)` | `char` | Trim leading/trailing spaces in place; returns the new string start. |
| `str_from_dec16(char addr, uint16_t value)` | `nibble` |  |
| `str_to_dec16(char addr)` | `uint16_t` |  |
| `str_from_dec32(char addr, uint32_t value)` | `nibble` |  |
| `str_to_dec32(char addr)` | `uint32_t` |  |
| `str_from_hex16(char addr, uint16_t value)` | `nibble` |  |
| `str_to_hex16(char addr)` | `uint16_t` |  |
| `str_from_hex32(char addr, uint32_t value)` | `nibble` |  |
| `str_to_hex32(char addr)` | `uint32_t` |  |
