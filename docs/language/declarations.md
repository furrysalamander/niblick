# Declarations and literals

## Variables

```c
nibble n;
char buffer[16];
uint32_t total = 0;
bool ready = false;
```

A declaration has a type, a name, an optional array suffix, and an optional
initializer. Global declarations appear at file scope. Local declarations
appear inside a function or block.

Local declarations are scoped to the enclosing block. A name may not be
redeclared in the same scope.

## `const`

A scalar `const` has a compile-time constant value and occupies no RAM.

```c
const nibble LED = 1;
const nibble MASK = LED | 2;
```

The initializer may contain literals, other scalar consts, casts, unary
`- ~ !`, arithmetic, shifts, bitwise operators, and comparisons. Width and
wrapping rules match runtime expressions.

A scalar `const` with a dynamic initializer is rejected. Taking `&CONST` is
rejected. Local scalar consts follow the same rules.

A `const` array is stored in flash and is read-only.

```c
const char message[] = "ready\n";
const nibble digits[] = { 0, 1, 2, 3, 4, 5, 6, 7, 8, 9 };
```

Local `const` arrays and `const` structs are rejected. See {doc}`limitations`.

## Array lengths

An array length is a constant expression. It may use integer literals and
file-scope scalar `const` declarations.

```c
const nibble N = 3;
nibble values[N + 1];
```

An array without an explicit length requires an initializer.

## Initializers

RAM arrays and structs accept brace initializers in declaration order. Missing
scalar elements are zero-initialized.

```c
nibble values[4] = { 1, 2 };
Point origin = { 3, 4 };
char text[] = "hi";
char buffer[4] = "ab";
```

A string initializer includes its NUL terminator and must fit in the array.
Initializers do not nest. See {doc}`limitations`.

## Literals

Integer literals accept decimal, `0x` hexadecimal, `0b` binary, and `0o` octal
forms. `_` separates digits. A decimal literal with a leading zero is rejected.

```c
15
0xF
0b1111
0o17
1_000
```

Floating-point literals accept `1.5`, `1.`, `.5`, and exponent forms such as
`1e3` and `1.5e-3`.

Character literals contain one byte:

```c
'A'
'\n'
'\x41'
```

## Strings

Text strings are terminated by `0x00`. `0xFF` is reserved for binary sentinel
tables such as audio and PDM data.

Adjacent string literals concatenate:

```c
const char message[] = "abc" "def";
```

Escapes are `\a \b \f \n \r \t \v \\ \' \" \?`, `\x` with one or two hex
digits, and octal `\ooo` with one to three digits. Raw newlines and `\0` are
rejected in string literals. `0xFF` is allowed in text strings and in
`const char[]` data.

## Struct declarations

```c
struct Point {
    nibble x;
    nibble y;
};
```

Struct declarations are file-local and must appear before use. See
{doc}`structs`.
