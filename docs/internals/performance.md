# Size and performance

## Limits

| Resource | Limit |
|---|---:|
| Code space | 4096 12-bit words |
| Data RAM | 256 nibbles |
| Usable compiler RAM | 176 nibbles (`0x40..0xEF`) |
| Hardware call stack | 5 entries |
| Non-tail user call depth | 4 |

## Code-size budgets

| Program | Words | RAM |
|---|---:|---:|
| `hello.nbl` | 142 | 5 |
| `tetris.nbl` | 2573 | 134 |
| `u32_math.nbl` | 2289 | 97 |
| `mc_void.nbl` | 4064 | 129 |

`tests/test_examples.py` enforces the 4096-word limit.
`tests/test_size.py` keeps Tetris under a 2800-word budget.

## Costs

- A 32-bit multiply or divide uses a 24-nibble scratch block allocated only
  when the program uses those operators.
- A 32-bit divide takes milliseconds at 250 kHz.
- A 64-bit variable costs 16 nibbles. 64-bit expressions also reserve a result
  buffer and temporary slots. See {doc}`wide-arithmetic`.
- A `half` costs 4 nibbles; a `float` costs 8 nibbles. See {doc}`soft-float`.
- Struct size is the exact sum of its fields. See
  {doc}`../language/structs`.
- Runtime helpers are stripped when unreachable.
- Function parameter and local slots are overlaid across functions that cannot
  be active at the same time.

## Reports

Use `--symbols`, `--stack`, `--map`, and `--map-json` to measure a program.
See {doc}`../toolchain/diagnostics`.
