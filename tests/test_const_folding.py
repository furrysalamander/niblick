"""Scalar ``const`` declarations and compile-time constant folding."""

from __future__ import annotations

from pathlib import Path

import pytest

from badgec.assembler import assemble_file
from badgec.compiler import Compiler
from badgec.emulator import Emulator
from badgec.errors import BadgeTypeError
from badgec.parser import parse


def build(tmp_path: Path, source: str, name: str = "const"):
    path = tmp_path / f"{name}.badge"
    path.write_text(source)
    compiler = Compiler(parse(source, str(path)), str(path))
    asm_path = tmp_path / f"{name}.asm"
    asm = compiler.compile()
    asm_path.write_text(asm)
    hex_path = tmp_path / f"{name}.hex"
    assemble_file(asm_path, hex_path)
    emu = Emulator()
    emu.load_hex(hex_path)
    emu.run(100000)
    return compiler, asm, emu


def test_scalar_const_globals_have_no_ram_storage(tmp_path: Path) -> None:
    compiler, asm, emu = build(
        tmp_path,
        """
        const nibble SER = 1;
        const nibble SRCLK = 2;
        const nibble MASK = SER | SRCLK;
        const char HIGH = (char)0x1FF;
        const uint16_t W = 0x1234;
        const uint32_t D = 0x12345678;
        nibble out;
        char h;
        uint16_t w;
        uint32_t d;
        fn main() {
            gpio_set(SER);
            gpio_set(MASK);
            out = MASK;
            h = HIGH;
            w = W;
            d = D;
        }
        """,
    )

    for name, value in (
        ("SER", 1),
        ("SRCLK", 2),
        ("MASK", 3),
        ("HIGH", 0xFF),
        ("W", 0x1234),
        ("D", 0x12345678),
    ):
        symbol = compiler.globals[name]
        assert symbol.address is None
        assert symbol.const_value == value

    assert "BSET R3, 0" in asm
    assert "BSET R3, 1" in asm
    assert "GOSUB __bc_gpio_set" not in asm
    assert not any(entry.startswith("__bc_gpio_") for entry in compiler.used_runtime)

    out = compiler.globals["out"].address
    assert out is not None
    assert emu.ram[out] == 3
    h = compiler.globals["h"].address
    assert emu.ram[h] | (emu.ram[h + 1] << 4) == 0xFF
    w = compiler.globals["w"].address
    assert sum(emu.ram[w + i] << (4 * i) for i in range(4)) == 0x1234
    d = compiler.globals["d"].address
    assert sum(emu.ram[d + i] << (4 * i) for i in range(8)) == 0x12345678


def test_const_folding_matches_runtime_width_rules(tmp_path: Path) -> None:
    compiler, _, emu = build(
        tmp_path,
        """
        const uint16_t W = 0x100;
        const uint16_t M = W * W;
        const nibble N = (nibble)0x1FF;
        const nibble NEG = -1;
        const char C = 0xFF;
        const uint32_t D = 0xFFFFFFFF;
        uint16_t w;
        nibble n;
        nibble neg;
        char c;
        uint32_t d;
        fn main() {
            w = M;
            n = N;
            neg = NEG;
            c = C;
            d = D;
        }
        """,
    )

    assert compiler.globals["M"].const_value == 0
    assert compiler.globals["N"].const_value == 15
    assert compiler.globals["NEG"].const_value == 15
    assert compiler.globals["C"].const_value == 0xFF
    assert compiler.globals["D"].const_value == 0xFFFFFFFF

    w = compiler.globals["w"].address
    assert sum(emu.ram[w + i] << (4 * i) for i in range(4)) == 0
    assert emu.ram[compiler.globals["n"].address] == 15
    assert emu.ram[compiler.globals["neg"].address] == 15
    c = compiler.globals["c"].address
    assert emu.ram[c] | (emu.ram[c + 1] << 4) == 0xFF


def test_forward_references_and_local_const(tmp_path: Path) -> None:
    compiler, asm, emu = build(
        tmp_path,
        """
        const nibble A = B + 1;
        const nibble B = 2;
        nibble out;
        fn main() {
            const nibble LOCAL = A + 4;
            gpio_set(LOCAL);
            out = LOCAL;
        }
        """,
    )

    assert compiler.globals["A"].const_value == 3
    assert compiler.globals["B"].const_value == 2
    assert "BSET R3, 0" in asm
    assert "BSET R3, 1" in asm
    assert "BSET R3, 2" in asm
    assert compiler.mem.used() == 1  # only ``out`` is in RAM
    out = compiler.globals["out"].address
    assert emu.ram[out] == 7


def test_const_folding_matches_runtime_expressions(tmp_path: Path) -> None:
    compiler, _, emu = build(
        tmp_path,
        """
        const nibble A = 13;
        const nibble B = 5;
        const char C = 200;
        const char D = 7;
        const uint16_t W = 0x1234;
        const uint32_t X = 0x12345678;
        nibble a;
        nibble b;
        char c;
        char d;
        uint16_t w;
        uint32_t x;
        nibble nd;
        nibble nc;
        char rd;
        char rc;
        uint16_t md;
        uint16_t mc;
        uint16_t sd;
        uint16_t sc;
        uint32_t ad;
        uint32_t ac;
        fn main() {
            a = 13;
            b = 5;
            c = 200;
            d = 7;
            w = 0x1234;
            x = 0x12345678;

            nd = a / b;
            nc = A / B;
            rd = c % d;
            rc = C % D;
            md = c * d;
            mc = C * D;
            sd = w << a;
            sc = W << A;
            ad = x + w;
            ac = X + W;
        }
        """,
    )

    def value(name: str) -> int:
        symbol = compiler.globals[name]
        width = {"nibble": 1, "char": 2, "uint16_t": 4, "uint32_t": 8}[symbol.type.name]
        return sum(
            emu.ram[symbol.address + index] << (4 * index)
            for index in range(width)
        )

    for dynamic, folded in (
        ("nd", "nc"),
        ("rd", "rc"),
        ("md", "mc"),
        ("sd", "sc"),
        ("ad", "ac"),
    ):
        assert value(dynamic) == value(folded), (dynamic, folded)

    assert value("nc") == 13 // 5
    assert value("rc") == 200 % 7
    assert value("mc") == 200 * 7
    assert value("ac") == 0x12345678 + 0x1234


def test_dynamic_scalar_const_is_rejected(tmp_path: Path) -> None:
    path = tmp_path / "dynamic.badge"
    source = """
    nibble x;
    nibble r;
    const nibble A = x + 1;
    fn main() { x = 1; r = A; }
    """
    path.write_text(source)
    with pytest.raises(BadgeTypeError, match="compile-time constant"):
        Compiler(parse(source, str(path)), str(path)).compile()


def test_const_address_and_assignment_are_rejected(tmp_path: Path) -> None:
    address_source = "const nibble A = 1; nibble x; fn main() { x = &A; }"
    path = tmp_path / "address.badge"
    path.write_text(address_source)
    with pytest.raises(BadgeTypeError, match="address of const"):
        Compiler(parse(address_source, str(path)), str(path)).compile()

    assign_source = "const nibble A = 1; fn main() { A = 2; }"
    path = tmp_path / "assign.badge"
    path.write_text(assign_source)
    with pytest.raises(BadgeTypeError, match="cannot assign to const"):
        Compiler(parse(assign_source, str(path)), str(path)).compile()


def test_map_reports_const_values(tmp_path: Path) -> None:
    compiler, _, _ = build(
        tmp_path,
        """
        const nibble PIN = 3;
        nibble out;
        fn main() { out = PIN; }
        """,
    )
    data = compiler.map_data()
    entry = next(item for item in data["globals"] if item["name"] == "PIN")
    assert entry["address"] is None
    assert entry["value"] == 3
    assert entry["const"] is True
