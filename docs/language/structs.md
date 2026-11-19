# Structs

Niblick supports RAM-resident structs with scalar fields.

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
through a field:

```c
make_point().x
```

Scalar fields can be initialized in declaration order. Missing fields are
zero-initialized.

```c
Point origin = { 3, 4 };
```

## Layout

Fields are laid out in declaration order, low nibble first. Each field starts
immediately after the previous field. The total size is padded to the next power
of two.

```c
struct Mixed {
    char a;       // offset 0, two nibbles
    nibble b;     // offset 2
    uint16_t c;   // offset 3, four nibbles
};
```

`Mixed` uses seven nibbles of fields and is padded to eight nibbles. Padding
nibbles are unused.

## Operations

- struct declarations with scalar fields
- global and local struct variables
- arrays of structs
- field reads and writes
- `arr[index].field`
- whole-struct assignment, including array elements
- struct parameters, copied by value
- struct return values
- direct field access on a returned struct, such as `make_point().x`
- struct fields in `print()` placeholders

## Limits

Struct fields are scalar. Struct declarations are file-local and must appear
before use in the same source file. Functions in imported modules can use their
own structs internally.

See {doc}`limitations` for unsupported aggregate forms.

## Memory

A struct occupies its padded size in RAM, whether it is a single variable or an
array element. Struct parameters are copied into the callee's frame. Struct
returns use a shared result buffer sized to the largest struct in the program.
Struct size is limited by the 176 usable nibbles of data RAM after globals and
function frames.
