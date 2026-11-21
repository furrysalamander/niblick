# Expressions

## Precedence

From lowest to highest:

| Precedence | Operators | Associativity |
|---:|---|---|
| 1 | `?:` | right |
| 2 | `\|\|` | left |
| 3 | `&&` | left |
| 4 | `\|` | left |
| 5 | `^` | left |
| 6 | `&` | left |
| 7 | `==` `!=` | left |
| 8 | `<` `<=` `>` `>=` | left |
| 9 | `<<` `>>` | left |
| 10 | `+` `-` | left |
| 11 | `*` `/` `%` | left |
| 12 | unary `+` `-` `~` `!` `&`, cast | right |
| 13 | postfix `[]` `.` `()` | left |

## Expression typing

There are no implicit integer promotions. The result type of an expression is
determined by its operands, its expected destination type, and explicit casts.

### Result width

| Expression | Result |
|---|---|
| Binary arithmetic and bitwise | Wider operand width |
| Shift | Left operand width |
| Comparison | Common operand type |
| Logical `&&`, `\|\|`, `!` | `bool` |
| Unary `+`, `-`, `~` | Operand width |

### Expected-type width floor

An expected destination type sets a minimum evaluation width.

| Context | Effect |
|---|---|
| Assignment, initializer, argument, return, array element, struct field | Destination type sets the minimum width |
| Comparison | Common operand type sets the minimum width |
| Arithmetic, bitwise, shift, unary node | Minimum width propagates through the expression |
| Condition without a comparison | No expected type |
| Explicit cast | Sets the evaluation width and overrides the destination floor |
| Narrowing | Requires an explicit cast |
| Signedness | Unchanged by the width floor |

```c
uint16_t n = 1 << 8;              // 0x100
uint32_t m = 1 << 20;             // 0x100000
int16_t r = -200;                 // sign-extends the literal
bool ok = x + y < 200;            // comparison uses a 16-bit common type
uint16_t narrow = (uint8_t)(1 << 8);  // 0
```

### Common type

| Operand signedness | Common type |
|---|---|
| Both signed | Signed at the wider width |
| Both unsigned | Unsigned at the wider width |
| Mixed, unsigned operand narrower | Signed at the wider width |
| Mixed, unsigned operand equal or wider | Unsigned at the wider width |

### Multiplication result

| Operand type | Unsigned result | Signed result |
|---|---|---|
| `nibble` / `i4` | `char` | `i8` |
| `char` / `i8` | `uint16_t` | `i16` |
| `uint16_t` / `i16` | `uint16_t` | `i16` |
| `uint32_t` / `i32` | `uint32_t` | `i32` |
| `uint64_t` / `i64` | `uint64_t` | `i64` |

## Operators

### Binary and ternary

| Operators | Result | Meaning |
|---|---|---|
| `+` `-` `*` `/` `%` | Integer | Arithmetic |
| `&` `\|` `^` | Integer | Bitwise |
| `<<` `>>` | Left operand type | Shift |
| `==` `!=` `<` `<=` `>` `>=` | `bool` | Comparison |
| `&&` `\|\|` | `bool` | Logical; short-circuit |
| `?:` | Common branch type | Conditional |
| `[]` | Element type | Array index |
| `.` | Field type | Struct field |
| `()` | Function return type | Named function call |

### Unary

| Operator | Result | Meaning |
|---|---|---|
| `+x` | Operand type | No-op |
| `-x` | Operand type | Two's-complement negation |
| `~x` | Operand type | Bitwise complement |
| `!x` | `bool` | Logical negation |
| `&x` | Nibble address or `flashptr` | Address of an array |

Integer overflow, division, modulo, and shift behavior are in
{doc}`semantics`.

## Assignments

| Form | Requirement | Behavior |
|---|---|---|
| `target = expr` | Variable, array element, or struct field | Convert and store |
| `target op= expr` | Variable, array element, or struct field | Read, combine, store |
| `target++`, `target--` | Statement | Increment or decrement |
| `++target`, `--target` | Statement | Same effect as postfix |

| Constraint | Rule |
|---|---|
| Index or member base with a call | Rejected |
| Lvalue evaluation | Once for the read and once for the write |
| Expression result | None; these forms are statements |

```c
x += 2;
x <<= 1;
a[i] += 3;
p.field -= 1;
x++;
--x;
```

## Conditional expressions

| Rule | Value |
|---|---|
| Condition evaluation | Once |
| Branch execution | Selected branch only |
| Branch checking | Both branches type-checked |
| Result type | Common branch type with the destination width floor |
| `bool` result | Normalized to 0 or 1 |
| Mixed `half` / `float` branches | Explicit cast required |
| `void` or struct branches | Rejected |
| Constant condition | Folded at compile time |
| Constant condition contexts | Scalar `const` initializer, array length, inline-assembly `${...}` expression |

```c
value = cond ? a : b;
value = a ? b : c ? d : e;   // a ? b : (c ? d : e)
```

## Address-of

| Form | Result |
|---|---|
| `&array` for a RAM array | Nibble address |
| `&array` for a `const` flash array | `flashptr` |
| `&scalar` | Rejected |
| Pointer arithmetic | Rejected |

## Related

- {doc}`semantics` for evaluation order, overflow, division, shifts, and conversion behavior.
- {doc}`declarations` for literals, strings, and initializers.
- {doc}`types` for type widths and aliases.
