# Statements

## Blocks

```c
{
    nibble n;
    n = 1;
}
```

A block introduces a scope. Declarations inside a block are not visible after
the closing brace.

## `if` and `else`

```c
if (condition) {
    statement;
} else {
    statement;
}
```

The condition may be any testable value. An integer is false when zero. `bool`
uses its logical value. `flashptr` and floats are testable. A single statement
may replace a braced block.

## `while`

```c
while (condition) {
    statement;
}
```

The condition is evaluated before each iteration.

## `for`

```c
for (i = 0; i < 10; i++) {
    statement;
}
```

The initializer may be a local declaration or an assignment. The condition and
update are optional. The update may be an assignment, compound assignment, or
`++`/`--` statement.

The initializer, condition, and update share the loop scope.

## `break` and `continue`

`break` exits the innermost `while` or `for` loop. `continue` jumps to the loop
condition for `while`, or to the update for `for`.

```c
while (1) {
    if (ready()) {
        break;
    }
    continue;
}
```

## `return`

```c
return;
return value;
```

A non-`void` function must return a value on every reachable path. A `return`
from `main` enters the badge idle loop. A `return` from any other function
pops the hardware stack.

A `return` whose value is a function call may compile as a tail call.

## Expression and assignment statements

```c
value = 1;
buffer[0] = 'A';
point.x += 2;
i++;
```

Assignments, compound assignments, and `++`/`--` are statements. A bare
expression statement is permitted but has no effect unless it contains a call.

The left side must be a variable, array element, or struct field. Calls in the
index of a compound assignment are rejected.

## Inline assembly

```c
asm {
    MOV R1, 3
    NOP
}
```

An `asm` block emits its text at the current statement position. See
{doc}`inline-asm`.

## Related

- {doc}`expressions` for operators and lvalues.
- {doc}`functions` for parameters, returns, and tail calls.
- {doc}`limitations` for unsupported control-flow constructs.
