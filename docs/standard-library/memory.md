# Memory

Nibble and byte memory operations, 16-bit and 32-bit access, search, and
checksums.

```c
import "lib/mem.nbl";
```

Addresses are nibble addresses. A byte occupies two consecutive nibbles, so
`*8` helpers advance by two addresses per element. `mem_move8` handles
overlapping ranges; `mem_copy8` does not. `mem_search8` returns the address of
the first match, or 0. `mem_crc8` uses CRC-8/ATM with polynomial `0x07`.

## Functions

| Call | Returns | Notes |
|---|---|---|
| `mem_fill(char addr, nibble value, char len)` | `void` |  |
| `mem_zero(char addr, char len)` | `void` |  |
| `mem_copy(char dst, char src, char len)` | `void` |  |
| `mem_cmp(char a, char b, char len)` | `nibble` | 0 when the ranges match, 1 when they differ. |
| `mem_swap(char a, char b)` | `void` |  |
| `mem_bit_test(char addr, nibble bit)` | `nibble` |  |
| `mem_bit_set(char addr, nibble bit)` | `void` |  |
| `mem_bit_clear(char addr, nibble bit)` | `void` |  |
| `mem_bit_toggle(char addr, nibble bit)` | `void` |  |
| `mem_popcount(nibble v)` | `nibble` |  |
| `mem_fill8(char addr, char value, char len)` | `void` |  |
| `mem_zero8(char addr, char len)` | `void` |  |
| `mem_copy8(char dst, char src, char len)` | `void` |  |
| `mem_cmp8(char a, char b, char len)` | `nibble` |  |
| `mem_swap8(char a, char b)` | `void` |  |
| `mem_peek16_le(char addr)` | `uint16_t` |  |
| `mem_peek16_be(char addr)` | `uint16_t` |  |
| `mem_poke16_le(char addr, uint16_t value)` | `void` |  |
| `mem_poke16_be(char addr, uint16_t value)` | `void` |  |
| `mem_peek32_le(char addr)` | `uint32_t` |  |
| `mem_peek32_be(char addr)` | `uint32_t` |  |
| `mem_poke32_le(char addr, uint32_t value)` | `void` |  |
| `mem_poke32_be(char addr, uint32_t value)` | `void` |  |
| `mem_search8(char addr, char len, char value)` | `char` |  |
| `mem_reverse8(char addr, char len)` | `void` |  |
| `mem_popcount8(char value)` | `nibble` |  |
| `mem_sum8(char addr, char len)` | `char` |  |
| `mem_crc8(char addr, char len, char seed)` | `char` | CRC-8/ATM (polynomial 0x07). |
| `mem_move8(char dst, char src, char len)` | `void` |  |
