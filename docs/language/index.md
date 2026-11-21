# Language

The Niblick language is statically typed, with explicit-width integer types
and no pointer type.

## Source file

A source file contains, in any order:

- `import` declarations
- global variable declarations
- `struct` declarations
- function declarations
- `extern fn` declarations

Statements appear only inside functions.

```c
import "lib/uart.nbl";

struct Point {
    nibble x;
    nibble y;
};

const nibble LED = 1;
Point origin;

fn nibble add(nibble a, nibble b) {
    return a + b;
}

fn main() {
    origin.x = add(1, 2);
    origin.y = 0;
}
```

## Entry point

Every program requires one `fn main()` with no parameters and no `extern`
marker. The generated startup sequence jumps to `main` with `GOTO`. A `return`
from `main`, or reaching its closing brace, enters the badge idle loop.

## Case and identifiers

Identifiers begin with an ASCII letter or `_` and continue with ASCII letters,
digits, or `_`. Keywords are lowercase and case-sensitive.

## Comments

```c
// Line comment

/* Block comment */
```

Block comments do not nest.

## Compilation unit

`import` merges declarations from other files into one program. Imports are
resolved relative to the importing file, then the repository root and
`NIBLICK_PATH` entries. Each file is parsed once. Import cycles are rejected.

Struct names share one namespace across imported files. A struct must be
declared before use.

See {doc}`syntax`, {doc}`types`, {doc}`expressions`, {doc}`semantics`,
{doc}`declarations`, {doc}`statements`, {doc}`functions`, {doc}`structs`,
{doc}`imports`, {doc}`inline-asm`, {doc}`asm-modules`, and {doc}`limitations`.
