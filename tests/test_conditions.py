"""End-to-end checks for direct condition lowering.

Every condition is written as ``if (cond) { results[i] = 1; }`` so the
compiler can branch straight from flags instead of materialising a value.
Expected results are computed in Python with BadgeC's unsigned semantics.
Cases are split across a few small programs to stay inside code and RAM.
"""

from __future__ import annotations

from pathlib import Path

from badgec.assembler import assemble_file
from badgec.compiler import Compiler
from badgec.emulator import Emulator
from badgec.parser import parse

OPS = {
    "==": lambda a, b: a == b,
    "!=": lambda a, b: a != b,
    "<": lambda a, b: a < b,
    "<=": lambda a, b: a <= b,
    ">": lambda a, b: a > b,
    ">=": lambda a, b: a >= b,
}


def _run_cases(
    tmp_path: Path,
    name: str,
    declarations: list[str],
    setup: list[str],
    cases: list[tuple[str | None, str, bool]],
) -> None:
    lines = declarations + [f"nibble results[{len(cases)}];", "fn main() {"] + setup
    for index, (assignment, condition, _) in enumerate(cases):
        if assignment:
            lines.append(f"    {assignment};")
        lines.append(f"    if ({condition}) {{ results[{index}] = 1; }}")
    lines.append("}")
    source = "\n".join(lines) + "\n"

    source_path = tmp_path / f"{name}.badge"
    source_path.write_text(source)
    compiler = Compiler(parse(source, str(source_path)), str(source_path))
    asm_path = tmp_path / f"{name}.asm"
    asm_path.write_text(compiler.compile())
    hex_path = tmp_path / f"{name}.hex"
    assemble_file(asm_path, hex_path)

    emu = Emulator()
    emu.load_hex(hex_path)
    emu.run(300000)

    base = compiler.globals["results"].address
    assert base is not None
    for index, (_, condition, expected) in enumerate(cases):
        actual = emu.ram[base + index]
        assert actual == int(expected), f"{name}: condition {condition!r}: got {actual}"


def _run_chunked(
    tmp_path: Path,
    name: str,
    declarations: list[str],
    setup: list[str],
    cases: list[tuple[str | None, str, bool]],
    chunk: int = 50,
) -> None:
    for index in range(0, len(cases), chunk):
        _run_cases(
            tmp_path,
            f"{name}{index // chunk}",
            declarations,
            setup,
            cases[index : index + chunk],
        )


def test_nibble_against_literal(tmp_path: Path) -> None:
    cases = [
        (f"a = {a}", f"a {op} {constant}", fn(a, constant))
        for a in (0, 5, 15)
        for op, fn in OPS.items()
        for constant in (0, 1, 5, 15, 16, 255)
    ]
    _run_chunked(tmp_path, "nibble_literal", ["nibble a;"], [], cases)


def test_nibble_against_nibble(tmp_path: Path) -> None:
    cases = [
        (f"a = {a}; b = {b}", f"a {op} b", fn(a, b))
        for a in (0, 1, 5, 15)
        for b in (0, 5, 9, 15)
        for op, fn in OPS.items()
    ]
    _run_chunked(
        tmp_path,
        "nibble_var",
        ["nibble a;", "nibble b;"],
        [],
        cases,
    )


def test_char_against_literal(tmp_path: Path) -> None:
    cases = [
        (f"c = {c}", f"c {op} {constant}", fn(c, constant))
        for c in (0, 15, 16, 100, 255)
        for op, fn in OPS.items()
        for constant in (0, 1, 15, 16, 255)
    ]
    _run_chunked(tmp_path, "char_literal", ["char c;"], [], cases)


def test_char_against_char(tmp_path: Path) -> None:
    cases = [
        (f"c = {c}; d = {d}", f"c {op} d", fn(c, d))
        for c in (0, 15, 16, 255)
        for d in (0, 15, 16, 255)
        for op, fn in OPS.items()
    ]
    _run_chunked(
        tmp_path,
        "char_var",
        ["char c;", "char d;"],
        [],
        cases,
    )


def test_logical_and_not_conditions(tmp_path: Path) -> None:
    cases = [
        (None, "!(a < 6)", not (5 < 6)),
        (None, "!(c == 15)", not (100 == 15)),
        (None, "(a < 6) && (b > 2)", (5 < 6) and (9 > 2)),
        (None, "(a < 6) && (b > 9)", (5 < 6) and (9 > 9)),
        (None, "(a == 9) || (b == 9)", (5 == 9) or (9 == 9)),
        (None, "(a == 9) || (b == 4)", (5 == 9) or (9 == 4)),
        (None, "(c < 16) && (d == 15)", (100 < 16) and (15 == 15)),
        (None, "(c >= 16) || (d == 15)", (100 >= 16) or (15 == 15)),
        (None, "1", True),
        (None, "0", False),
    ]
    _run_chunked(
        tmp_path,
        "logic",
        ["nibble a;", "nibble b;", "char c;", "char d;"],
        ["    a = 5;", "    b = 9;", "    c = 100;", "    d = 15;"],
        cases,
    )
