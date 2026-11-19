# Diagnostics and reports

## Text errors

The CLI prints one line to standard error:

```text
error: file.nbl:12:5: message
```

Exit status is 1.

## JSON errors

```bash
python3 -m niblick source.nbl --diagnostics-json
```

The CLI prints a JSON array with one object:

```json
[
  {
    "file": "source.nbl",
    "line": 12,
    "column": 5,
    "severity": "error",
    "message": "unknown function 'foo'"
  }
]
```

| Field | Type | Meaning |
|---|---|---|
| `file` | string | Source path, or empty when unavailable |
| `line` | integer | 1-based line |
| `column` | integer | 1-based column |
| `severity` | string | `error` |
| `message` | string | Diagnostic text |
| `end_line` | integer | Optional end line |
| `end_column` | integer | End column |
| `code` | string | Optional diagnostic code |

`end_line`, `end_column`, and `code` appear only when set.

## Symbol maps

```bash
python3 -m niblick source.nbl --map-json build/source.map.json
python3 -m niblick source.nbl --debug-map build/source.debug.json
```

`--map-json` contains globals, functions, runtime routines, flash data, and
code-size buckets. `--debug-map` contains PC-to-source mappings for the
debugger.

## Size report

```bash
python3 -m niblick source.nbl --symbols
```

The report lists per-function word counts, runtime routines, flash data,
startup overhead, and the total.

## Stack report

```bash
python3 -m niblick source.nbl --stack
```

The report lists maximum non-tail user depth, the deepest path, per-function
entry depth, runtime call sites with stack cost, and linked runtime costs. A
call that would exceed the five hardware stack entries produces a warning.

## Execution trace

```bash
python3 -m niblick source.nbl --run --trace --trace-limit 20
```

Each line contains the PC, raw word, decoded instruction, selected registers,
stack pointer, and flags. `--trace-limit` caps printed instructions.

## I/O trace

```bash
python3 -m niblick source.nbl --run --trace-io --io-trace-limit 200
```

The trace lists step, PC, event kind, address, bit, and before/after values.
`--io-trace-limit 0` stores unlimited events.

## Dumps

| Option | Output |
|---|---|
| `--dump-ram` | 16 rows of 16 nibbles |
| `--dump-uart` | UART TX and RX bytes, error state |
| `--dump-sfr` | Page-15 SFR values |
