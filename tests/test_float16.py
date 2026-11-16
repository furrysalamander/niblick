"""Native binary16 add/sub and comparison tests."""

from __future__ import annotations

import struct
from pathlib import Path

import pytest

from badgec.assembler import assemble_file
from badgec.compiler import Compiler
from badgec.emulator import Emulator
from badgec.loader import load_source


def build(tmp_path: Path, source: str):
    filename = str(tmp_path / "float16.badge")
    compiler = Compiler(load_source(source, filename=filename), filename)
    asm_path = tmp_path / "float16.asm"
    asm_path.write_text(compiler.compile())
    hex_path = tmp_path / "float16.hex"
    assemble_file(asm_path, hex_path)
    emu = Emulator()
    emu.load_hex(hex_path)
    emu.run(2_000_000)
    return compiler, emu


def value(compiler: Compiler, emu: Emulator, name: str) -> int:
    symbol = compiler.globals[name]
    assert symbol.address is not None
    return sum(emu.ram[symbol.address + i] << (4 * i) for i in range(symbol.type.ram_size))


def h16_bits(number: float) -> int:
    try:
        data = struct.pack(">e", number)
    except OverflowError:
        data = struct.pack(">e", float("inf") if number > 0 else float("-inf"))
    return int.from_bytes(data, "big")


def run_f16(tmp_path: Path, left: float, right: float, op: str) -> int:
    source = f"""
        half a;
        half b;
        half c;
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
        (0.0, 1.5, "+", 1.5),
        (1.5, 0.0, "+", 1.5),
        (0.0, 1.5, "-", -1.5),
        (2.0**-24, 2.0**-24, "+", 2.0**-23),
        (1.0, 2.0**-11, "+", 1.0),
        (60000.0, 60000.0, "+", float("inf")),
    ],
)
def test_f16_assembly_add_sub(
    tmp_path: Path, left: float, right: float, op: str, expected: float
) -> None:
    assert run_f16(tmp_path, left, right, op) == h16_bits(expected)


def test_f16_assembly_comparisons(tmp_path: Path) -> None:
    compiler, emu = build(
        tmp_path,
        """
        half a;
        half b;
        bool lt;
        bool gt;
        bool eq;
        bool neg_lt;
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
    assert value(compiler, emu, "zero_eq") == 1


@pytest.mark.parametrize(
    ("left", "right", "expected"),
    [
        (1.5, 1.5, 2.25),
        (2.0, 2.0, 4.0),
        (-1.5, 2.0, -3.0),
        (0.0, 1.5, 0.0),
        (1.5, 2.0, 3.0),
        (60000.0, 2.0, float("inf")),
    ],
)
def test_f16_assembly_mul(
    tmp_path: Path, left: float, right: float, expected: float
) -> None:
    assert run_f16(tmp_path, left, right, "*") == h16_bits(expected)


@pytest.mark.parametrize(
    ("left", "right", "expected"),
    [
        (1.0, 1.0, 1.0),
        (3.0, 2.0, 1.5),
        (1.0, 2.0, 0.5),
        (1.0, 3.0, 1.0 / 3.0),
        (0.0, 1.5, 0.0),
        (1.5, 0.0, float("inf")),
        (0.0, 0.0, float("nan")),
    ],
)
def test_f16_assembly_div(
    tmp_path: Path, left: float, right: float, expected: float
) -> None:
    assert run_f16(tmp_path, left, right, "/") == h16_bits(expected)


def test_f16_f32_conversions(tmp_path: Path) -> None:
    compiler, emu = build(
        tmp_path,
        """
        half h_norm;
        half h_sub;
        half h_inf;
        float f_norm;
        float f_sub;
        fn main() {
            h_norm = __bc_f16_from_bits(0x3C00);
            f_norm = __bc_f16_to_f32(h_norm);
            h_sub = __bc_f16_from_bits(0x0001);
            f_sub = __bc_f16_to_f32(h_sub);
            h_sub = __bc_f32_to_f16(__bc_f32_from_bits(0x33800000));
            h_inf = __bc_f32_to_f16(__bc_f32_from_bits(0x477FF000));
        }
        """,
    )
    assert value(compiler, emu, "f_norm") == 0x3F800000
    assert value(compiler, emu, "f_sub") == 0x33800000
    assert value(compiler, emu, "h_sub") == 0x0001
    assert value(compiler, emu, "h_inf") == 0x7C00


def test_f16_integer_conversions(tmp_path: Path) -> None:
    compiler, emu = build(
        tmp_path,
        """
        half h;
        int32_t i;
        int32_t round_trip;
        fn main() {
            i = -1000;
            h = (half)i;
            round_trip = (int32_t)h;
        }
        """,
    )
    assert value(compiler, emu, "h") == h16_bits(-1000.0)
    assert value(compiler, emu, "round_trip") == (-1000) & 0xFFFFFFFF


def test_f16_saturation(tmp_path: Path) -> None:
    compiler, emu = build(
        tmp_path,
        """
        half h;
        int32_t from_inf;
        int32_t from_max;
        int32_t from_neg_inf;
        fn main() {
            h = __bc_f16_from_bits(0x7C00);
            from_inf = (int32_t)h;
            h = __bc_f16_from_bits(0x7BFF);
            from_max = (int32_t)h;
            h = __bc_f16_from_bits(0xFC00);
            from_neg_inf = (int32_t)h;
        }
        """,
    )
    assert value(compiler, emu, "from_inf") == 0
    assert value(compiler, emu, "from_max") == 65504
    assert value(compiler, emu, "from_neg_inf") == 0
