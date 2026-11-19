# Command-line reference

```text
python3 -m niblick SOURCE [OPTIONS]
```

`SOURCE` is a `.nbl` source file. The compiler resolves imports relative to
the importing file, then the repository root and `NIBLICK_PATH` entries.

## Output

| Option | Effect |
|---|---|
| `-o DIR`, `--output-dir DIR` | Write `.asm` and `.hex` into `DIR` |
| `--no-assemble` | Emit `.asm` only |
| `--keep-runtime` | Link the complete runtime instead of reachable routines |
| `--no-optimize` | Disable peephole and branch-relaxation passes |

The default output paths are the source path with `.asm` and `.hex`
extensions. `--no-assemble` cannot be combined with `--run`.

## Emulator

| Option | Effect |
|---|---|
| `--run` | Assemble, load, and execute the program |
| `--max-steps N` | Emulator step limit; default `100000` |
| `--trace` | Print each executed instruction |
| `--trace-limit N` | Maximum traced instructions; default `200` |
| `--trace-io` | Record OUT, OUTB, IN, and INB accesses |
| `--io-trace-limit N` | Maximum stored I/O events; `0` means unlimited |
| `--dump-ram` | Print data RAM after execution |
| `--dump-uart` | Print UART TX, RX, and error state |
| `--dump-sfr` | Print the page-15 SFRs |

`--trace`, `--trace-io`, `--dump-ram`, `--dump-uart`, and `--dump-sfr`
imply `--run`.

## Reports

| Option | Effect |
|---|---|
| `--map` | Print global addresses and flash labels |
| `--map-json PATH` | Write the symbol map as JSON |
| `--debug-map PATH` | Write the PC-to-source map as JSON |
| `--symbols` | Print function, runtime, flash, startup, and total word counts |
| `--callgraph` | Print user call edges with call type and source location |
| `--stack` | Print call depth, runtime stack costs, and depth warnings |

## Diagnostics

| Option | Effect |
|---|---|
| `--diagnostics-json` | Print compiler errors as a JSON array |

The schema is documented in {doc}`../toolchain/diagnostics`.

## Exit status

| Status | Meaning |
|---:|---|
| `0` | Compilation succeeded |
| `1` | Compilation or assembly failed |

Errors are written to standard error as a single `file:line:column` line unless
`--diagnostics-json` is set.

## Examples

```bash
python3 -m niblick examples/hello.nbl --run --dump-uart
python3 -m niblick examples/tetris.nbl --symbols --stack
python3 -m niblick examples/hello.nbl --map-json build/hello.map.json
python3 -m niblick examples/hello.nbl --debug-map build/hello.debug.json
python3 -m niblick examples/hello.nbl --no-assemble
```
