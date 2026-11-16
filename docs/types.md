# Types and arithmetic

Niblick uses explicit-width integer types. There are no implicit C integer
promotions: the width of an expression comes from its operands and from the
type it is being assigned to.

## Type spellings

| Canonical | Width | Signed | Aliases |
|---|---:|---|---|
| `nibble` | 4 | no | `u4` |
| `i4` | 4 | yes | — |
| `char` | 8 | no | `u8`, `byte`, `uint8_t` |
| `i8` | 8 | yes | `int8_t` |
| `uint16_t` | 16 | no | `u16` |
| `i16` | 16 | yes | `int16_t`, `short`, `int` |
| `uint32_t` | 32 | no | `u32` |
| `i32` | 32 | yes | `int32_t`, `long` |
| `uint64_t` | 64 | no | `u64`, `uint_least64_t`, `uint_fast64_t`, `uintmax_t` |
| `i64` | 64 | yes | `int64_t`, `int_least64_t`, `int_fast64_t`, `intmax_t` |
| `bool` | 1 | logical | — |
| `flashptr` | 12 | — | code-memory address |
| `void` | 0 | — | no value |

`char` is unsigned, because the UART is byte-oriented. Use `int8_t` for a
signed byte. `int` is signed 16-bit and `long` is signed 32-bit; this matches
the usual choice for 16-bit C targets. The `int_least*_t`, `int_fast*_t`,
`intmax_t`, and `uintmax_t` spellings are aliases for the same fixed-width
types. `intptr_t`/`uintptr_t` are not defined because Niblick has no general
pointers.

The old `word` and `dword` type spellings have been removed. The ISA
uses "word" for a 12-bit instruction word and describes the data word as 4
bits; neither is a 16-bit data type. Use `uint16_t`/`int16_t` (or `u16`/`i16`)
and `uint32_t`/`int32_t` (or `u32`/`i32`) instead.

## No implicit promotions

Arithmetic keeps the wider operand's width, with one exception:
multiplication widens one step.

```c
uint8_t a = 200;
uint8_t b = 200;
uint8_t c = a + b;      // 144: 8-bit addition
uint16_t d = a + b;     // 400: destination widens the expression
uint16_t e = (uint8_t)(a + b);  // 144: explicit cast forces 8-bit

int8_t x = 100;
int8_t y = 100;
int8_t p = x + y;       // -56: 8-bit addition
int16_t q = x + y;      // 200: destination widens
```

Multiplication results:

| Common operand type | Result |
|---|---|
| `nibble` | `char` |
| `char` | `uint16_t` |
| `uint16_t` | `uint16_t` |
| `uint32_t` | `uint32_t` |

Signedness follows the same rule (`i4*i4 -> i8`, `i8*i8 -> i16`,
`i16*i16 -> i16`, `i32*i32 -> i32`).

## Expected-type width floor

An expression is evaluated at least at the width of its destination. This is
a *width floor*, not a promotion:

- it applies to assignments, initializers, function arguments, returns, array
  elements, and struct fields;
- comparison operands use their common type as the floor;
- the floor propagates recursively through arithmetic, bitwise, shift, and
  unary nodes;
- it never narrows an expression and never changes its signedness;
- an explicit cast overrides it.

```c
uint16_t n = 1 << 8;     // 0x100: the shift is evaluated at 16 bits
uint32_t m = 1 << 20;    // 0x100000
int16_t r = -200;        // negative literal sign-extends
bool ok = x + y < 200;   // comparison uses a 16-bit common type
```

Use an explicit cast when you want narrow evaluation:

```c
uint16_t n = (uint8_t)(1 << 8);  // 0
```

Conditions without a comparison have no expected type. Use an explicit cast
if a condition needs a wider computation.

## Signedness mixing

When the operands have different signedness, the common type is chosen as
follows:

- both signed -> signed at the wider width;
- both unsigned -> unsigned at the wider width;
- mixed -> signed if the unsigned operand is strictly narrower, otherwise
  unsigned.

At equal width, unsigned wins, matching C's same-rank rule. Use an explicit
cast when you want a different interpretation.

## Signed semantics

Signed values use two's complement in the same registers and RAM layout as
their unsigned counterparts.

- Arithmetic overflow wraps; it is not undefined behavior.
- `/` truncates toward zero, matching C.
- `%` takes the dividend's sign.
- The most-negative value divided by `-1` wraps to itself.
- Division by zero returns 0.
- `>>` is arithmetic for signed left operands and logical for unsigned ones.
- Left shift wraps; a shift count at or above the width produces 0 (or sign
  fill for an arithmetic right shift).
- Widening a signed value sign-extends; widening an unsigned value
  zero-extends. Narrowing requires an explicit cast.

```c
int16_t a = -7;
int16_t b = 2;
a / b;   // -3
a % b;   // -1
a >> 1;  // -4
a < b;   // true
```

## Operators

Compound assignment is statement-level:

```c
x += 2;
x <<= 1;
x |= 1;
a[i] += 3;
p.field -= 1;
```

`++` and `--` are statements. Prefix and postfix forms have the same effect:

```c
x++;
--x;
for (i = 0; i < 10; i++) {
}
```

Compound assignment and `++`/`--` require an lvalue with a side-effect-free
index or member base. The lvalue is evaluated once for the read and once for
the write; expressions with calls in the index are rejected.

Unary `+` is a type-preserving no-op.

## Conditional expressions

`?:` is right-associative and binds below `||`:

```c
value = cond ? a : b;
value = a ? b : c ? d : e;   // a ? b : (c ? d : e)
```

The condition is evaluated once. Only the selected branch executes. Both
branches are type-checked. The result type is the common type of the branches,
with the expected destination width applied as a width floor. `bool` results
normalize to 0/1. Mixed `half`/`float` branches require an explicit cast.
Branches cannot be `void` or struct values.

A constant condition is folded at compile time. This permits `?:` in scalar
`const` initializers, array lengths, and inline-assembly `${...}` expressions.

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
`1e3` and `1.5e-3`. There are no integer or float suffixes.

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

## Array lengths and initializers

Array lengths are constant expressions. They may use integer literals and
file-scope scalar `const` declarations:

```c
const nibble N = 3;
nibble values[N + 1];
```

RAM arrays and structs accept brace initializers in declaration order. Missing
scalar elements are zero-initialized:

```c
nibble values[4] = { 1, 2 };
Point origin = { 3, 4 };
char text[] = "hi";
char buffer[4] = "ab";
```

A string initializer includes its NUL terminator. The initializer must fit in
the declared array. Nested aggregate initializers are not supported. Local
`const` arrays are not supported.

## `bool`

`bool` is a distinct logical type with one nibble of storage:

- comparisons, `!`, `&&`, and `||` produce `bool`;
- assigning an integer to `bool` normalizes it to 0 or 1;
- converting `bool` to an integer yields 0 or 1;
- `true` and `false` are `bool`-compatible literals;
- arithmetic promotes `bool` to a 4-bit integer, so `true + true` is 2;
- printed with `{}` or `{:d}`, a `bool` prints as 0 or 1.

## Floating point

`float`/`f32` has a native binary32 soft-float implementation:

- add, subtract, multiply, divide, comparison, and zero tests are hand-written
  assembly;
- arithmetic uses round-to-nearest-even, including guard, round, and sticky
  bits, so results match IEEE-754 binary32;
- subnormal inputs and results are handled normally;
- signed zero is preserved where IEEE-754 requires it;
- infinities propagate, and NaN inputs produce a canonical quiet NaN.

`half`/`f16` has a separate native addition/subtraction, multiplication,
division, and comparison engine. It does not call the binary32 arithmetic
helpers. Integer and 64-bit integer values convert to and from both float
types, and `half`/`f16` converts directly to and from `float`/`f32`.

Float-to-integer conversion truncates toward zero and saturates on overflow:
NaN becomes 0, too-negative values become the type's minimum, and too-positive
values become its maximum. Negative values converted to an unsigned type
become 0. Narrower integer casts use the saturated 32-bit integer result and
then truncate it.

`double`, `f64`, and `_Float64` are intentionally not supported: there is no
64-bit floating-point type on this target.

64-bit integers use a memory-based result buffer because a 64-bit value needs
sixteen nibbles and cannot fit in the register result convention. Each 64-bit variable costs
sixteen nibbles of RAM, and the compiler also reserves a result buffer plus
temporary slots while a 64-bit expression is evaluated. Programs with many
64-bit globals may not fit in the badge's data RAM. 64-bit multiply and
divide are implemented by `lib/wide.nbl`; they are correct but size- and RAM-constrained, so they are best used sparingly. The 64-bit print
helpers live in `lib/wide.nbl` as well; the current UART helper call chain
can exceed the five-entry hardware call stack for some 64-bit formats, and a
64-bit print program may not have enough RAM for the full formatter set.
