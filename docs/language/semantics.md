# Semantics

## Evaluation order

- Binary operands evaluate left to right.
- Function arguments evaluate left to right.
- Array indices and struct field bases evaluate once per access.
- The condition of `?:` evaluates once. Only the selected branch executes.
- `&&` and `||` short-circuit.
- Global initializers run at the start of `main`, in declaration order.

## Initialization and lifetime

Global variables occupy static RAM. The badge clears data RAM on RUN, so a
global without an initializer starts at zero. Initializers run in `main`
before the first statement.

Local variables are allocated in the current function frame. A local without an
initializer is not cleared. Frame overlay reuses slots between functions that
cannot be active at the same time, so an uninitialized local may contain a value
left by another function.

Scalar `const` declarations are folded at compile time and occupy no RAM.
`const` arrays live in flash.

## Overflow and arithmetic

- Signed and unsigned arithmetic wrap at the type width.
- Overflow is not undefined behavior.
- `/` truncates toward zero.
- `%` takes the dividend's sign.
- Division by zero returns 0.
- The most-negative value divided by `-1` wraps to itself.
- `>>` is arithmetic for signed values and logical for unsigned values.
- A shift count at or above the width produces 0, or sign fill for an
  arithmetic right shift.

## Conversions

- Widening a signed value sign-extends.
- Widening an unsigned value zero-extends.
- Narrowing requires an explicit cast.
- Assigning an integer to `bool` normalizes it to 0 or 1.
- Assigning `bool` to an integer yields 0 or 1.
- Float-to-integer conversion truncates toward zero and saturates.
- NaN converts to 0.
- Negative values converted to unsigned types become 0.

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
