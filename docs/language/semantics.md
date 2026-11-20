# Semantics

## Evaluation order

| Construct | Order |
|---|---|
| Binary operands | Left to right |
| Function arguments | Left to right |
| Array index and struct field base | Once per access |
| `?:` condition | Once; selected branch only |
| `&&`, `\|\|` | Short-circuit |
| Global initializers | Start of `main`, declaration order |

## Initialization and lifetime

| Storage | Initialization |
|---|---|
| Global variable | Zero on RUN; initializer runs at the start of `main` |
| Local variable | Not cleared; frame overlay may reuse the slot |
| Scalar `const` | Folded at compile time; no RAM |
| `const` array | Flash |

Frame overlay reuses local slots between functions that cannot be active at the
same time. An uninitialized local may contain a value left by another function.

## Arithmetic behavior

| Operation | Rule |
|---|---|
| Signed and unsigned arithmetic | Wraps at the type width |
| Overflow | Not undefined behavior |
| `/` | Truncates toward zero |
| `%` | Takes the dividend's sign |
| Division by zero | Returns 0 |
| Most-negative value divided by `-1` | Wraps to itself |
| `>>` | Arithmetic for signed values, logical for unsigned values |
| Shift count at or above the width | Produces 0, or sign fill for an arithmetic right shift |

## Conversions

| Conversion | Rule |
|---|---|
| Widening a signed value | Sign-extends |
| Widening an unsigned value | Zero-extends |
| Narrowing | Requires an explicit cast |
| Integer to `bool` | Normalizes to 0 or 1 |
| `bool` to integer | Yields 0 or 1 |
| Float to integer | Truncates toward zero and saturates |
| NaN to integer | Yields 0 |
| Negative value to unsigned type | Yields 0 |

## Arrays

Arrays have a fixed length known at compile time. Index expressions are not
range-checked. An out-of-range index reads or writes another data-memory
location.

`&array` yields the base nibble address. A `char` element occupies two nibbles,
so byte arrays advance by two addresses per element.

## Calls and recursion

Non-tail calls use the five-entry hardware stack. Tail calls compile to `GOTO`
and consume no stack entry. Recursion is permitted only when every edge in the
cycle is a tail call. The compiler rejects deeper than four non-tail user call
levels from `main`, leaving one stack entry for runtime helpers.

## Unsupported operations

General pointers, pointer arithmetic, dynamic allocation, and runtime code
modification are not available. See {doc}`limitations`.
