# Structs

A struct declares an aggregate of scalar, array, or nested-struct fields.

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
functions by value, and returned from functions. A returned struct allows
direct field access:

```c
make_point().x
```

Fields can be initialized in declaration order. Missing fields and array
elements are zero-initialized.

```c
Point origin = { 3, 4 };
```

Nested structs and array fields use nested braces:

```c
struct Packet {
    nibble header;
    char payload[4];
    Point point;
};

Packet packet = { 1, { 'A', 'B' }, { 3, 4 } };
```

## Layout

Fields are laid out in declaration order, low nibble first. Each field starts
immediately after the previous field. Struct size is the exact sum of the field
sizes; there is no trailing padding.

```c
struct Mixed {
    char a;       // offset 0, two nibbles
    nibble b;     // offset 2
    uint16_t c;   // offset 3, four nibbles
};
```

`Mixed` occupies seven nibbles.

Array fields occupy `length * element size` nibbles. Nested struct fields
occupy the nested struct's exact size.

```c
struct Packet {
    nibble header;
    char payload[4];
    Point point;
};
```

## Operations

- scalar fields and nested struct fields
- global and local struct variables
- arrays of structs
- field reads and writes
- `arr[index].field`
- `obj.array[index]`
- `obj.inner.field`
- whole-struct assignment, including array elements
- struct parameters, copied by value
- struct return values
- whole-struct `==` and `!=`
- `const` structs and const struct arrays stored in flash
- struct fields in `print()` placeholders

## Limits

Struct names share one namespace across imported files. A struct must be
declared before it is used.

Array fields have scalar elements. Arrays of structs inside a struct are
rejected. Local `const` structs are rejected.

See {doc}`limitations` for remaining constraints.

## Memory

A struct occupies its exact size in RAM, whether it is a single variable or an
array element. Struct parameters are copied into the callee's frame. Struct
returns use a shared result buffer sized to the largest struct in the program.
Struct size is limited by the 176 usable nibbles of data RAM after globals and
function frames.

A `const` struct is stored in flash and occupies no RAM. A const struct array
uses `array_len * struct_size` nibbles of flash. Passing or returning a const
struct copies the value into RAM.
