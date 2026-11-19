# Limitations

## Unsupported syntax

| Construct | Status |
|---|---|
| `switch` | Rejected |
| `do` / `while` | Rejected |
| `enum` | Rejected |
| `typedef` | Rejected |
| `sizeof` | Rejected |
| `static` | Rejected |
| `volatile` | Rejected |
| `goto` | Rejected |
| Preprocessor directives | Not implemented |
| C-style function definitions | Rejected; use `fn` |
| Variadic functions | Not supported |
| Multiple return values | Not supported |
| Default or named arguments | Not supported |
| Compound literals | Not supported |
| Designated initializers | Not supported |

## Types and data

| Construct | Status |
|---|---|
| General pointers | Not supported |
| Pointer arithmetic | Not supported |
| `char *` parameters | Not supported |
| `double`, `f64`, `_Float64` | Not supported |
| `intptr_t`, `uintptr_t` | Not defined |
| Variable-length arrays | Not supported |
| Dynamic allocation | Not supported |
| Runtime code modification | Not possible |
| Array bounds checking | Not performed |

## Aggregates

| Construct | Status |
|---|---|
| Struct fields that are arrays | Not supported |
| Nested struct fields | Not supported |
| Whole-struct comparison | Not supported |
| Nested aggregate initializers | Not supported |
| `const` structs | Not supported |
| Structs in flash tables | Not supported |
| Struct names shared across files | Not supported |
| Local `const` arrays | Not supported |

## Control flow and storage

| Construct | Status |
|---|---|
| General recursion | Rejected |
| Non-tail recursion | Rejected |
| More than four non-tail user call levels | Rejected |
| Uninitialized local values | Indeterminate |
| Out-of-range array indices | Unchecked |

Tail-call cycles are permitted. See {doc}`functions` and {doc}`semantics`.

## Library scope

The standard library does not provide:

- dynamic `print()` format strings
- non-UART formatting targets
- Q8.8 fixed point
- interrupt-driven UART
- I2C or 1-Wire helpers
- display circles, sprites, or right/up/down scrolling
- key repeat and multi-key combinations
- a calibrated millisecond or audio timing model

See {doc}`../standard-library/index` for the available modules.
