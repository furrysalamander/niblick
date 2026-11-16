# Structs

BadgeC supports small RAM-resident structs with scalar fields:

```c
struct Point {
    nibble x;
    nibble y;
};

Point origin;
Point points[3];

fn main() {
    origin.x = 3;
    origin.y = 4;
    points[1].x = 7;
    points[1].y = 8;
}
```

Fields are accessed with `.`. Struct values can be assigned, passed to
functions by value, and returned from functions. A returned struct can be used
directly through a field, for example `make_point().x`.

Scalar fields can be initialized in declaration order. Missing fields are
zero-initialized:

```c
Point origin = { 3, 4 };
```

## Layout

Fields are laid out in declaration order, low nibble first. Each field starts
immediately after the previous field. The struct's total RAM size is padded to
the next power of two so the existing array-address code can index arrays of
structs with a shift.

Example:

```c
struct Mixed {
    char a;       // offset 0, two nibbles
    nibble b;     // offset 2
    uint16_t c;   // offset 3, four nibbles
};
```

`Mixed` uses 7 nibbles of fields and is padded to 8 nibbles. The padding bytes
are unused.

## Supported

- struct declarations with scalar fields
- global and local struct variables
- arrays of structs
- field reads and writes
- `arr[index].field`
- whole-struct assignment, including array elements
- struct parameters, copied by value
- struct return values
- direct field access on a returned struct, e.g. `make_point().x`
- struct fields in `print()` placeholders

## Not supported

- struct fields that are arrays
- nested struct fields
- whole-struct comparison
- nested aggregate initializers
- `const` structs
- structs in flash tables
- struct names declared in one file and used in another

Struct declarations are currently file-local: a struct must be declared before
it is used in the same source file. Functions in imported modules can use their
own structs internally.

## Memory cost

A struct occupies its padded size in RAM, whether it is a single variable or
an array element. Struct parameters are copied into the called function's
frame, and struct returns use a shared result buffer sized to the largest
struct in the program. Keep structs small; the badge has only about 176 usable
nibbles of data RAM after globals and function frames.

For a one-off group of values that is never indexed, separate variables may be
cheaper because they avoid padding.
