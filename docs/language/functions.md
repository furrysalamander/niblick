# Functions

## Declaration

```c
fn nibble add(nibble a, nibble b) {
    return a + b;
}

fn void reset() {
}
```

A function has a return type, a name, a parameter list, and a block.

- Parameters are passed by value.
- Struct parameters are copied into the callee's parameter slot.
- A `void` function returns no value.
- A non-`void` function returns a value of its declared type.
- Parameters are visible throughout the function body.
- A local declaration may shadow a parameter or an outer local in a nested
  block.
- Function names are unique within the program.

A function that reaches its closing brace emits `RET R0,0` or, for `main`,
`JR -1`. Do not rely on the return value of a non-`void` function that falls
through.

## `main`

```c
fn main() {
}
```

`main` takes no parameters and cannot be `extern`. The startup sequence is:

```asm
GOTO fn_main
```

`main` runs at call depth 0. A `return` from `main`, or reaching its closing
brace, enters the badge idle loop.

## Calls

```c
result = add(1, 2);
```

Arguments evaluate left to right. Each argument is converted to the parameter
type before the call. A call to an unknown function or a call with the wrong
argument count is rejected.

Struct arguments and return values use the shared struct result buffer. See
{doc}`structs`.

## Tail calls

A `return` whose value is a call compiles as a tail call when the caller and
callee signatures permit it.

```c
fn nibble count(nibble n, nibble acc) {
    if (n == 0) {
        return acc;
    }
    return count(n - 1, acc + 1);
}
```

A tail call uses `GOTO` and consumes no hardware stack entry. Tail recursion
therefore runs in constant stack depth.

## Recursion

The hardware stack has five entries. The compiler permits recursion only when
every edge in the cycle is a tail call. A non-tail cycle is rejected. The
maximum non-tail user call depth from `main` is four, leaving one entry for
runtime helpers.

## `extern fn`

```c
extern fn void display_init();
```

An `extern fn` declares a function implemented in an imported `.asm` module.
The module must define `fn_<name>:`. See {doc}`asm-modules`.

## Inlining

The compiler inlines whole-program single-statement functions and void wrappers
where the call graph and side-effect checks permit it. This is an optimization;
it does not change language semantics.

## Related

- {doc}`../internals/runtime-abi` for register and frame conventions.
- {doc}`statements` for `return` and control flow.
- {doc}`limitations` for recursion and stack limits.
