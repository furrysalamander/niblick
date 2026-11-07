"""BadgeC type system.

The badge CPU is nibble-oriented.  BadgeC deliberately exposes only a few
types so that every value has an obvious, compact lowering:

    nibble     one 4-bit value
    char       one 8-bit value (two nibbles, low first)
    flashptr   one 12-bit program-memory address (three nibbles)
    void       no value

`char` is unsigned, 0..255, because the UART is byte-oriented.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Type:
    name: str
    ram_size: int = 0          # nibbles occupied in data RAM
    flash_size: int = 0        # words per element when stored in flash
    is_scalar: bool = True

    def __str__(self) -> str:
        return self.name

    def __copy__(self) -> "Type":
        return self

    def __deepcopy__(self, memo: object) -> "Type":
        # Types are immutable singletons; copying them would break the
        # identity checks used throughout code generation.
        return self


NIBBLE = Type("nibble", ram_size=1, flash_size=1)
CHAR = Type("char", ram_size=2, flash_size=2)
WORD = Type("word", ram_size=4, flash_size=4)
FLASHPTR = Type("flashptr", ram_size=3, flash_size=0)
VOID = Type("void", ram_size=0, flash_size=0, is_scalar=False)

SCALAR_TYPES = {
    "nibble": NIBBLE,
    "char": CHAR,
    "word": WORD,
    "flashptr": FLASHPTR,
    "void": VOID,
}

# Widening order for integer types.  ram_size is also the register width in
# nibbles, so the index is a convenient width code.
INTEGER_TYPES = (NIBBLE, CHAR, WORD)


def type_from_name(name: str) -> Type:
    try:
        return SCALAR_TYPES[name]
    except KeyError as exc:
        raise ValueError(f"unknown type {name!r}") from exc


def is_integer(t: Type) -> bool:
    return t in INTEGER_TYPES


def is_comparable(t: Type) -> bool:
    return t in INTEGER_TYPES


def wider(a: Type, b: Type) -> Type:
    """Return the wider of two integer types (or *a* when one is not integer)."""

    if a not in INTEGER_TYPES:
        return b
    if b not in INTEGER_TYPES:
        return a
    return a if a.ram_size >= b.ram_size else b


def promoted_mul_type(t: Type) -> Type:
    """Result type of ``a * b`` after both operands are promoted to *t*."""

    if t is NIBBLE:
        return CHAR
    return WORD
