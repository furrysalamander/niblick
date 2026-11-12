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

Fields are accessed with `.`. A struct variable or struct array element can be
used anywhere a scalar field is expected; the struct value itself cannot be
copied, passed, returned, or printed.

## Layout

Fields are laid out in declaration order, low nibble first. Each field starts
immediately after the previous field. The struct's total RAM size is padded to
the next power of two so the existing array-address code can index arrays of
structs with a shift.

Example:

```c
struct Mixed {
    char a;     // offset 0, two nibbles
    nibble b;   // offset 2
    word c;     // offset 3, four nibbles
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
- struct fields in `print()` placeholders

## Not supported yet

- struct fields that are arrays
- nested struct fields
- struct parameters and return values
- whole-struct assignment or comparison
- aggregate initializers such as `Point p = { 1, 2 };`
- `const` structs
- structs in flash tables
- struct names declared in one file and used in another

Struct declarations are currently file-local: a struct must be declared before
it is used in the same source file. Functions in imported modules can use their
own structs internally.

## Memory cost

A struct occupies its padded size in RAM, whether it is a single variable or
an array element. Keep structs small; the badge has only about 176 usable
nibbles of data RAM after globals and function frames.

For a one-off group of values that is never indexed, separate variables may be
cheaper because they avoid padding.
