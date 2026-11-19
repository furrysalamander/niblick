# Expressions

## Precedence

From lowest to highest:

| Precedence | Operators | Associativity |
|---:|---|---|
| 1 | `?:` | right |
| 2 | `||` | left |
| 3 | `&&` | left |
| 4 | `|` | left |
| 5 | `^` | left |
| 6 | `&` | left |
| 7 | `==` `!=` | left |
| 8 | `<` `<=` `>` `>=` | left |
| 9 | `<<` `>>` | left |
| 10 | `+` `-` | left |
| 11 | `*` `/` `%` | left |
| 12 | unary `+` `-` `~` `!` `&` `++` `--`, cast | right |
| 13 | postfix `[]` `.` `()` `++` `--` | left |

`?:` binds below `||`.

## No implicit promotions

Expression width comes from the operands and the expected destination type.
There are no C integer promotions.

Arithmetic keeps the wider operand's width. Multiplication widens one step.

```c
uint8_t a = 200;
uint8_t b = 200;
uint8_t c = a + b;              // 144: 8-bit addition
uint16_t d = a + b;             // 400: destination widens the expression
uint16_t e = (uint8_t)(a + b);  // 144: explicit cast forces 8-bit

int8_t x = 100;
int8_t y = 100;
int8_t p = x + y;               // -56: 8-bit addition
int16_t q = x + y;              // 200: destination widens
```

Multiplication results:

| Operand type | Result |
|---|---|
| `nibble` | `char` |
| `char` | `uint16_t` |
| `uint16_t` | `uint16_t` |
| `uint32_t` | `uint32_t` |

Signed multiplication follows the same width rule: `i4*i4 -> i8`,
`i8*i8 -> i16`, `i16*i16 -> i16`, `i32*i32 -> i32`.

## Expected-type width floor

An expression is evaluated at least at the width of its destination. This is a
width floor, not a promotion.

- It applies to assignments, initializers, function arguments, returns, array
  elements, and struct fields.
- Comparison operands use their common type as the floor.
- The floor propagates through arithmetic, bitwise, shift, and unary nodes.
- It never narrows an expression and never changes signedness.
- An explicit cast overrides it.

```c
uint16_t n = 1 << 8;      // 0x100
uint32_t m = 1 << 20;     // 0x100000
int16_t r = -200;         // negative literal sign-extends
bool ok = x + y < 200;    // comparison uses a 16-bit common type
```

Use an explicit cast for narrow evaluation:

```c
uint16_t n = (uint8_t)(1 << 8);  // 0
```

A condition without a comparison has no expected type.

## Signedness mixing

| Operands | Common type |
|---|---|
| Both signed | Signed at the wider width |
| Both unsigned | Unsigned at the wider width |
| Mixed | Signed if the unsigned operand is strictly narrower, otherwise unsigned |

At equal width, unsigned wins.

## Arithmetic

| Operator | Meaning |
|---|---|
| `+` `-` `*` `/` `%` | Integer arithmetic |
| `&` `|` `^` `~` | Bitwise operations |
| `<<` `>>` | Shifts |
| `==` `!=` `<` `<=` `>` `>=` | Comparisons, result `bool` |
| `&&` `||` `!` | Logical operations, result `bool` |
| `+` unary | Type-preserving no-op |
| `-` unary | Two's-complement negation |

`/` truncates toward zero. `%` takes the dividend's sign. Division by zero
returns 0. The most-negative value divided by `-1` wraps to itself.

`>>` is arithmetic for signed left operands and logical for unsigned operands.
A shift count at or above the width produces 0, or sign fill for an arithmetic
right shift.

## Assignments

Compound assignment is statement-level:

```c
x += 2;
x <<= 1;
x |= 1;
a[i] += 3;
p.field -= 1;
```

`++` and `--` are statements. Prefix and postfix forms have the same effect.

```c
x++;
--x;
for (i = 0; i < 10; i++) {
}
```

Compound assignment and `++`/`--` require an lvalue with a side-effect-free
index or member base. The lvalue is evaluated once for the read and once for
the write. Calls in the index are rejected.

## Conditional expressions

```c
value = cond ? a : b;
value = a ? b : c ? d : e;   // a ? b : (c ? d : e)
```

The condition is evaluated once. Only the selected branch executes. Both
branches are type-checked. The result type is the common type of the branches,
with the destination width floor applied. `bool` results normalize to 0 or 1.
Mixed `half`/`float` branches require an explicit cast. Branches cannot be
`void` or struct values.

A constant condition is folded at compile time. This permits `?:` in scalar
`const` initializers, array lengths, and inline-assembly `${...}` expressions.

## Address-of

`&array` yields the nibble address of a RAM array, or a `flashptr` for a
`const` flash array. `&scalar` and pointer arithmetic are not supported.

## Related

- {doc}`semantics` for evaluation order, overflow, and conversion behavior.
- {doc}`declarations` for literals, strings, and initializers.
- {doc}`types` for type widths and aliases.
