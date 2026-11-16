"""Floating-point front-end and native assembly-helper tests."""

from __future__ import annotations

import random
import struct
from fractions import Fraction
from pathlib import Path

import pytest

from niblick.assembler import assemble_file
from niblick.compiler import Compiler
from niblick.emulator import Emulator
from niblick.loader import load_source


def build(tmp_path: Path, source: str, *, steps: int = 500_000):
    filename = str(tmp_path / "float.nbl")
    compiler = Compiler(load_source(source, filename=filename), filename)
    asm_path = tmp_path / "float.asm"
    asm_path.write_text(compiler.compile())
    hex_path = tmp_path / "float.hex"
    assemble_file(asm_path, hex_path)
    emu = Emulator()
    emu.load_hex(hex_path)
    emu.run(steps)
    return compiler, emu


def value(compiler: Compiler, emu: Emulator, name: str) -> int:
    symbol = compiler.globals[name]
    assert symbol.address is not None
    return sum(emu.ram[symbol.address + i] << (4 * i) for i in range(symbol.type.ram_size))


def f32_bits(number: float) -> int:
    try:
        data = struct.pack(">f", number)
    except OverflowError:
        data = struct.pack(">f", float("inf") if number > 0 else float("-inf"))
    return int.from_bytes(data, "big")


def run_f32(tmp_path: Path, left: float, right: float, op: str) -> int:
    source = f"""
        float a;
        float b;
        float c;
        fn main() {{
            a = {left!r};
            b = {right!r};
            c = a {op} b;
        }}
    """
    compiler, emu = build(tmp_path, source)
    return value(compiler, emu, "c")


@pytest.mark.parametrize(
    ("left", "right", "op", "expected"),
    [
        (1.5, 1.5, "+", 3.0),
        (1.5, 2.25, "+", 3.75),
        (3.0, 1.5, "-", 1.5),
        (1.5, 2.5, "-", -1.0),
        (-1.5, 0.5, "+", -1.0),
        (1.5, 1.5, "-", 0.0),
        (2.0, 1.0, "+", 3.0),
        (1.0, 2.0, "+", 3.0),
        (0.0, 1.5, "+", 1.5),
        (1.5, 0.0, "+", 1.5),
        (0.0, 1.5, "-", -1.5),
        (1.0, 2.0**-24, "+", 1.0),
        (1.0, 3 * 2.0**-24, "+", 1.0 + 2.0**-22),
        (2.0**-149, 2.0**-149, "+", 2.0**-148),
        (1e39, 1e39, "+", float("inf")),
    ],
)
def test_f32_assembly_add_sub(
    tmp_path: Path, left: float, right: float, op: str, expected: float
) -> None:
    assert run_f32(tmp_path, left, right, op) == f32_bits(expected)


def test_f32_signed_zero(tmp_path: Path) -> None:
    compiler, emu = build(
        tmp_path,
        """
        float a;
        float b;
        float c;
        fn main() {
            a = -0.0;
            b = -0.0;
            c = a + b;
        }
        """,
    )
    assert value(compiler, emu, "c") == 0x80000000


def test_f32_assembly_comparisons(tmp_path: Path) -> None:
    compiler, emu = build(
        tmp_path,
        """
        float a;
        float b;
        bool lt;
        bool gt;
        bool eq;
        bool neg_lt;
        bool neg_gt;
        bool zero_eq;
        fn main() {
            a = 1.5;
            b = 2.5;
            lt = a < b;
            gt = a > b;
            eq = a == b;
            a = -2.5;
            b = -1.5;
            neg_lt = a < b;
            neg_gt = a > b;
            a = -0.0;
            b = 0.0;
            zero_eq = a == b;
        }
        """,
    )
    assert value(compiler, emu, "lt") == 1
    assert value(compiler, emu, "gt") == 0
    assert value(compiler, emu, "eq") == 0
    assert value(compiler, emu, "neg_lt") == 1
    assert value(compiler, emu, "neg_gt") == 0
    assert value(compiler, emu, "zero_eq") == 1


def test_double_is_not_a_type(tmp_path: Path) -> None:
    from niblick.errors import NiblickError

    with pytest.raises(NiblickError):
        build(
            tmp_path,
            """
            double x;
            fn main() {
                x = 1.5;
            }
            """,
        )


@pytest.mark.parametrize(
    ("left", "right", "expected"),
    [
        (1.5, 2.25, 3.375),
        (1.5, 1.5, 2.25),
        (2.0, 2.0, 4.0),
        (-1.5, 2.0, -3.0),
        (-1.5, -2.0, 3.0),
        (0.0, 1.5, 0.0),
        (-0.0, 1.5, -0.0),
        (2.0**-149, 0.5, 2.0**-150),
        (2.0**-149, 1.5, 2.0**-148),
        (2.0**-149, 2.0**-149, 0.0),
        (1e39, 1e39, float("inf")),
        (1e39, 0.0, float("nan")),
    ],
)
def test_f32_assembly_mul(
    tmp_path: Path, left: float, right: float, expected: float
) -> None:
    assert run_f32(tmp_path, left, right, "*") == f32_bits(expected)


@pytest.mark.parametrize(
    ("left", "right", "expected"),
    [
        (3.0, 1.5, 2.0),
        (1.0, 3.0, 1.0 / 3.0),
        (1.0, 2.0, 0.5),
        (-3.0, 1.5, -2.0),
        (-3.0, -1.5, 2.0),
        (0.0, 1.5, 0.0),
        (1.5, 0.0, float("inf")),
        (-1.5, 0.0, float("-inf")),
        (0.0, 0.0, float("nan")),
        (2.0**-149, 2.0, 2.0**-150),
        (2.0**-149, 0.5, 2.0**-148),
        (1e38, 2.0**-149, float("inf")),
    ],
)
def test_f32_assembly_div(
    tmp_path: Path, left: float, right: float, expected: float
) -> None:
    assert run_f32(tmp_path, left, right, "/") == f32_bits(expected)


def test_f32_mul_and_div_together(tmp_path: Path) -> None:
    compiler, emu = build(
        tmp_path,
        """
        float a;
        float b;
        float product;
        float quotient;
        fn main() {
            a = 1.5;
            b = 2.25;
            product = a * b;
            quotient = a / b;
        }
        """,
    )
    assert value(compiler, emu, "product") == f32_bits(3.375)
    assert value(compiler, emu, "quotient") == f32_bits(1.5 / 2.25)


def _is_nan_bits(value: int) -> bool:
    return (value & 0x7F800000) == 0x7F800000 and (value & 0x7FFFFF) != 0


def _f32_value(value: int) -> float:
    return struct.unpack(">f", struct.pack(">I", value))[0]


def _round_half_even(value: Fraction) -> int:
    floor = value.numerator // value.denominator
    remainder = value - floor
    if remainder > Fraction(1, 2) or (
        remainder == Fraction(1, 2) and (floor & 1) != 0
    ):
        return floor + 1
    return floor


def _f32_from_fraction(value: Fraction, negative: bool) -> int:
    sign = 0x80000000 if negative else 0
    if value == 0:
        return sign
    exponent = value.numerator.bit_length() - value.denominator.bit_length()
    while Fraction(2) ** exponent > value:
        exponent -= 1
    while Fraction(2) ** (exponent + 1) <= value:
        exponent += 1
    if exponent < -126:
        scaled = value / Fraction(2) ** -149
        mantissa = _round_half_even(scaled)
        if mantissa == 0:
            return sign
        if mantissa >= 1 << 23:
            return sign | (1 << 23)
        return sign | mantissa
    if exponent > 127:
        return sign | 0x7F800000
    mantissa = _round_half_even(value / Fraction(2) ** (exponent - 23))
    if mantissa >= 1 << 24:
        mantissa >>= 1
        exponent += 1
        if exponent > 127:
            return sign | 0x7F800000
    return sign | ((exponent + 127) << 23) | (mantissa - (1 << 23))


def _mul_reference(left: int, right: int) -> int | None:
    if _is_nan_bits(left) or _is_nan_bits(right):
        return None
    if (left & 0x7FFFFFFF) == 0x7F800000 or (right & 0x7FFFFFFF) == 0x7F800000:
        if (left & 0x7FFFFFFF) == 0 or (right & 0x7FFFFFFF) == 0:
            return None
        return ((left ^ right) & 0x80000000) | 0x7F800000
    if (left & 0x7FFFFFFF) == 0 or (right & 0x7FFFFFFF) == 0:
        return (left ^ right) & 0x80000000
    product = Fraction(_f32_value(left)) * Fraction(_f32_value(right))
    return _f32_from_fraction(abs(product), product < 0)


def _div_reference(left: int, right: int) -> int | None:
    if _is_nan_bits(left) or _is_nan_bits(right):
        return None
    if (right & 0x7FFFFFFF) == 0:
        if (left & 0x7FFFFFFF) == 0:
            return None
        return ((left ^ right) & 0x80000000) | 0x7F800000
    if (left & 0x7FFFFFFF) == 0:
        return (left ^ right) & 0x80000000
    if (left & 0x7FFFFFFF) == 0x7F800000:
        if (right & 0x7FFFFFFF) == 0x7F800000:
            return None
        return ((left ^ right) & 0x80000000) | 0x7F800000
    if (right & 0x7FFFFFFF) == 0x7F800000:
        return (left ^ right) & 0x80000000
    quotient = Fraction(_f32_value(left)) / Fraction(_f32_value(right))
    return _f32_from_fraction(abs(quotient), quotient < 0)


def test_f32_mul_div_randomized(tmp_path: Path) -> None:
    compiler, emu = build(
        tmp_path,
        """
        float a;
        float b;
        float c;
        float d;
        fn main() {
            a = 1.5;
            b = 2.25;
            c = a * b;
            d = a / b;
        }
        """,
    )
    from niblick.disasm import decode

    pattern = [
        "MOV R0, [0x27]",
        "AND R0, 8",
        "MOV R8, R0",
        "MOV R0, [0x2F]",
        "AND R0, 8",
        "MOV R9, R0",
    ]
    core = None
    for index in range(len(emu.program) - len(pattern)):
        if [decode(emu.program[index + i]) for i in range(len(pattern))] == pattern:
            core = index
            break
    assert core is not None
    return_address = 0xFFF

    def call(left: int, right: int, mode: int) -> int:
        emu.sp = 1
        emu.ram[0x10] = return_address & 0xF
        emu.ram[0x11] = (return_address >> 4) & 0xF
        emu.ram[0x12] = (return_address >> 8) & 0xF
        for i in range(8):
            emu.ram[0x20 + i] = (left >> (4 * i)) & 0xF
            emu.ram[0x28 + i] = (right >> (4 * i)) & 0xF
        emu.ram[0x3F] = mode
        emu.pc = core
        for _ in range(200_000):
            if emu.pc == return_address:
                return sum(emu.ram[1 + i] << (4 * i) for i in range(8))
            emu.step()
        raise AssertionError("f32 core did not return")

    rng = random.Random(20261113)
    specials = [
        0x00000000,
        0x80000000,
        0x7F800000,
        0xFF800000,
        0x7FC00000,
        0x00000001,
        0x007FFFFF,
        0x00800000,
        0x3F800000,
        0xBF800000,
        0x40000000,
        0x7F7FFFFF,
    ]
    cases = [(left, right) for left in specials for right in specials]
    for _ in range(120):
        left = rng.getrandbits(32)
        right = rng.getrandbits(32)
        cases.append((left, right))
    for _ in range(120):
        left = (rng.getrandbits(1) << 31) | (
            rng.choice([1, 2, 3, 126, 127, 128, 253, 254, 255]) << 23
        ) | rng.getrandbits(23)
        right = (rng.getrandbits(1) << 31) | (
            rng.choice([1, 2, 3, 126, 127, 128, 253, 254, 255]) << 23
        ) | rng.getrandbits(23)
        cases.append((left, right))

    for left, right in cases:
        for mode, reference in ((1, _mul_reference), (2, _div_reference)):
            result = call(left, right, mode)
            expected = reference(left, right)
            if expected is None:
                assert _is_nan_bits(result), (
                    hex(left),
                    hex(right),
                    mode,
                    hex(result),
                )
            else:
                assert result == expected, (
                    hex(left),
                    hex(right),
                    mode,
                    hex(result),
                    hex(expected),
                )


def test_f32_integer_conversions_32(tmp_path: Path) -> None:
    compiler, emu = build(
        tmp_path,
        """
        float f1;
        float f2;
        uint32_t au;
        int32_t ai;
        uint32_t ru;
        int32_t ri;
        fn main() {
            au = 123456789;
            f1 = (float)au;
            ru = (uint32_t)f1;
            ai = -123456789;
            f2 = (float)ai;
            ri = (int32_t)f2;
        }
        """,
    )
    assert value(compiler, emu, "f1") == f32_bits(123456789.0)
    assert value(compiler, emu, "f2") == f32_bits(-123456789.0)
    assert value(compiler, emu, "ru") == 123456792
    assert value(compiler, emu, "ri") == (-123456792) & 0xFFFFFFFF


def test_f32_integer_conversions_64(tmp_path: Path) -> None:
    compiler, emu = build(
        tmp_path,
        """
        float f3;
        float f4;
        uint64_t bu;
        int64_t bi;
        uint64_t rbu;
        int64_t rbi;
        fn main() {
            bu = 1099511627776;
            f3 = (float)bu;
            rbu = (uint64_t)f3;
            bi = -1234567890123;
            f4 = (float)bi;
            rbi = (int64_t)f4;
        }
        """,
    )
    assert value(compiler, emu, "f3") == f32_bits(2.0**40)
    assert value(compiler, emu, "f4") == f32_bits(-1234567890123.0)
    assert value(compiler, emu, "rbu") == 1099511627776


def test_f32_integer_saturation(tmp_path: Path) -> None:
    compiler, emu = build(
        tmp_path,
        """
        float f;
        int32_t ai;
        uint32_t au;
        int64_t bi;
        uint64_t bu;
        fn main() {
            f = __nib_f32_from_bits(0x4F000000);
            ai = (int32_t)f;
            f = __nib_f32_from_bits(0xCF000000);
            ai = (int32_t)f;
            f = __nib_f32_from_bits(0x7FC00000);
            ai = (int32_t)f;
            f = __nib_f32_from_bits(0x4F000000);
            bu = (uint64_t)f;
            f = __nib_f32_from_bits(0xDF000000);
            bi = (int64_t)f;
            f = __nib_f32_from_bits(0x7F800000);
            au = (uint32_t)f;
        }
        """,
    )
    assert value(compiler, emu, "bu") == 0x80000000
    assert value(compiler, emu, "bi") == 0x8000000000000000
    assert value(compiler, emu, "au") == 0
