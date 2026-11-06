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


NIBBLE = Type("nibble", ram_size=1, flash_size=1)
CHAR = Type("char", ram_size=2, flash_size=2)
FLASHPTR = Type("flashptr", ram_size=3, flash_size=0)
VOID = Type("void", ram_size=0, flash_size=0, is_scalar=False)

SCALAR_TYPES = {
    "nibble": NIBBLE,
    "char": CHAR,
    "flashptr": FLASHPTR,
    "void": VOID,
}


def type_from_name(name: str) -> Type:
    try:
        return SCALAR_TYPES[name]
    except KeyError as exc:
        raise ValueError(f"unknown type {name!r}") from exc


def is_integer(t: Type) -> bool:
    return t in (NIBBLE, CHAR)


def is_comparable(t: Type) -> bool:
    return t in (NIBBLE, CHAR)
