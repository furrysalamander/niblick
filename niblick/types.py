"""Niblick type system.

The badge CPU is nibble-oriented, so Niblick exposes explicit-width integer
types rather than pretending to be a normal C target:

    u4 / i4     one nibble (4 bits)
    u8 / i8     two nibbles (8 bits)
    u16 / i16   four nibbles (16 bits)
    u32 / i32   eight nibbles (32 bits)
    bool        one nibble, 0 or 1
    flashptr    a 12-bit code-memory address
    void        no value

``char`` and ``byte`` are aliases for ``u8`` and are unsigned, because the
UART is byte-oriented.  ``int`` is signed 16-bit, ``long`` is signed 32-bit,
and ``short`` is signed 16-bit, matching the usual choice for 16-bit targets.

There are deliberately no implicit integer promotions: the width of an
expression comes from its operands and its expected (destination) type.  See
``common_type`` and the compiler's expected-type handling.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Type:
    name: str
    ram_size: int = 0          # nibbles occupied in data RAM
    flash_size: int = 0        # words per element when stored in flash
    is_scalar: bool = True
    signed: bool = False
    is_bool: bool = False
    is_float: bool = False
    float_bits: int = 0

    def __str__(self) -> str:
        return self.name

    def __copy__(self) -> "Type":
        return self

    def __deepcopy__(self, memo: object) -> "Type":
        # Types are immutable singletons; copying them would break the
        # identity checks used throughout code generation.
        return self


U4 = Type("nibble", ram_size=1, flash_size=1)
I4 = Type("i4", ram_size=1, flash_size=1, signed=True)
U8 = Type("char", ram_size=2, flash_size=2)
I8 = Type("i8", ram_size=2, flash_size=2, signed=True)
U16 = Type("uint16_t", ram_size=4, flash_size=4)
I16 = Type("i16", ram_size=4, flash_size=4, signed=True)
U32 = Type("uint32_t", ram_size=8, flash_size=8)
I32 = Type("i32", ram_size=8, flash_size=8, signed=True)
U64 = Type("uint64_t", ram_size=16, flash_size=16)
I64 = Type("i64", ram_size=16, flash_size=16, signed=True)
F16 = Type("f16", ram_size=4, flash_size=4, is_float=True, float_bits=16)
F32 = Type("f32", ram_size=8, flash_size=8, is_float=True, float_bits=32)
BOOL = Type("bool", ram_size=1, flash_size=1, is_bool=True)
FLASHPTR = Type("flashptr", ram_size=3, flash_size=0)
VOID = Type("void", ram_size=0, flash_size=0, is_scalar=False)


@dataclass(frozen=True)
class StructField:
    name: str
    type: Type
    offset: int
    # Zero for a scalar field; the declared length otherwise.
    array_len: int = 0


@dataclass(frozen=True)
class StructType(Type):
    """An aggregate of scalar, array, and nested-struct fields.

    ``ram_size`` is the exact sum of the field sizes. Array indexing uses a
    shift for power-of-two sizes and a constant multiply otherwise.
    """

    fields: tuple[StructField, ...] = ()

    def field(self, name: str) -> StructField | None:
        for item in self.fields:
            if item.name == name:
                return item
        return None


# Canonical spellings and their aliases.  Aliases must point at the same
# immutable ``Type`` object so the compiler can keep using identity checks for
# the special types (bool, flashptr, void, structs).
SCALAR_TYPES = {
    "u4": U4,
    "nibble": U4,
    "i4": I4,
    "u8": U8,
    "char": U8,
    "byte": U8,
    "uint8_t": U8,
    "i8": I8,
    "int8_t": I8,
    "int_least8_t": I8,
    "int_fast8_t": I8,
    "uint_least8_t": U8,
    "uint_fast8_t": U8,
    "u16": U16,
    "uint16_t": U16,
    "i16": I16,
    "int16_t": I16,
    "int_least16_t": I16,
    "int_fast16_t": I16,
    "uint_least16_t": U16,
    "uint_fast16_t": U16,
    "short": I16,
    "int": I16,
    "u32": U32,
    "uint32_t": U32,
    "i32": I32,
    "int32_t": I32,
    "int_least32_t": I32,
    "int_fast32_t": I32,
    "uint_least32_t": U32,
    "uint_fast32_t": U32,
    "long": I32,
    "u64": U64,
    "uint64_t": U64,
    "uint_least64_t": U64,
    "uint_fast64_t": U64,
    "i64": I64,
    "int64_t": I64,
    "int_least64_t": I64,
    "int_fast64_t": I64,
    "intmax_t": I64,
    "uintmax_t": U64,
    "half": F16,
    "f16": F16,
    "_Float16": F16,
    "float": F32,
    "f32": F32,
    "_Float32": F32,
    "bool": BOOL,
    "flashptr": FLASHPTR,
    "void": VOID,
}

# Integer types in width order.  ``bool`` is intentionally separate: it is a
# logical type and does not participate in arithmetic without a cast.
INTEGER_TYPES = (U4, I4, U8, I8, U16, I16, U32, I32, U64, I64)

_BY_WIDTH = {
    (1, False): U4,
    (1, True): I4,
    (2, False): U8,
    (2, True): I8,
    (4, False): U16,
    (4, True): I16,
    (8, False): U32,
    (8, True): I32,
    (16, False): U64,
    (16, True): I64,
}


def type_from_name(name: str) -> Type:
    try:
        return SCALAR_TYPES[name]
    except KeyError as exc:
        raise ValueError(f"unknown type {name!r}") from exc


def is_integer(t: Type) -> bool:
    return t in INTEGER_TYPES


def is_signed(t: Type) -> bool:
    return is_integer(t) and t.signed


def is_float_type(t: Type) -> bool:
    return t.is_float


def is_comparable(t: Type) -> bool:
    return t in INTEGER_TYPES or t is BOOL or t.is_float


def is_testable(t: Type) -> bool:
    return t in INTEGER_TYPES or t is BOOL or t is FLASHPTR or t.is_float


def type_for(width: int, signed: bool) -> Type:
    return _BY_WIDTH[(width, signed)]


def widen_type(t: Type, expected: Type | None) -> Type:
    """Apply an expected-type *width floor*.

    The expected type may make an expression wider, but it never narrows it and
    never changes its signedness.  Non-integer expectations are ignored.
    """

    if expected is None or not is_integer(t) or not is_integer(expected):
        return t
    if expected.ram_size <= t.ram_size:
        return t
    return type_for(expected.ram_size, t.signed)


def common_type(a: Type, b: Type) -> Type:
    """Return the common type for two integer operands.

    No C-style promotions are applied.  The width is the wider operand, except
    that a strictly narrower unsigned operand is widened into the signed
    operand's type (a simplified value-preserving rule).  At equal width,
    unsigned wins, matching C's same-rank rule.
    """

    if a not in INTEGER_TYPES:
        return b
    if b not in INTEGER_TYPES:
        return a

    width = max(a.ram_size, b.ram_size)
    if a.signed == b.signed:
        return type_for(width, a.signed)

    signed_t, unsigned_t = (a, b) if a.signed else (b, a)
    if unsigned_t.ram_size < signed_t.ram_size:
        return type_for(signed_t.ram_size, True)
    return type_for(width, False)


def promoted_mul_type(t: Type) -> Type:
    """Result type of ``a * b`` after both operands are promoted to *t*.

    Multiplication widens one step so that 4x4 produces 8 bits and 8x8
    produces 16 bits.  Wider types keep their width (and therefore their low
    bits) and signedness.
    """

    if t is BOOL:
        return U4
    if t.ram_size == 1:
        return type_for(2, t.signed)
    if t.ram_size == 2:
        return type_for(4, t.signed)
    return t


def integer_range(t: Type) -> tuple[int, int]:
    bits = 4 * max(t.ram_size, 1)
    if t.signed:
        return -(1 << (bits - 1)), (1 << (bits - 1)) - 1
    return 0, (1 << bits) - 1


def fits_value(t: Type, value: int) -> bool:
    if not is_integer(t):
        return False
    low, high = integer_range(t)
    return low <= value <= high


def smallest_type_for(value: int, signed_hint: bool | None = None) -> Type:
    """Smallest integer type that can represent *value*.

    ``signed_hint`` chooses signed vs unsigned for non-negative values.  A
    negative value always produces a signed type.
    """

    signed = value < 0 or bool(signed_hint)
    for width in (1, 2, 4, 8, 16):
        candidate = type_for(width, signed)
        if fits_value(candidate, value):
            return candidate
    return I64 if signed else U64


def unsigned_type_like(t: Type) -> Type:
    return type_for(t.ram_size, False)


def signed_type_like(t: Type) -> Type:
    return type_for(t.ram_size, True)
