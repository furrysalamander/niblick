"""Property-based compiler/emulator checks for nibble arithmetic."""

from __future__ import annotations

from pathlib import Path

import pytest

hypothesis = pytest.importorskip("hypothesis")
from hypothesis import HealthCheck, given, settings, strategies as st  # noqa: E402

from niblick.assembler import assemble_file  # noqa: E402
from niblick.compiler import Compiler  # noqa: E402
from niblick.emulator import Emulator  # noqa: E402
from niblick.loader import load_source  # noqa: E402


@st.composite
def nibble_expressions(draw):
    start = draw(st.integers(min_value=0, max_value=15))
    steps = draw(
        st.lists(
            st.tuples(
                st.sampled_from(["+", "-", "&", "|", "^"]),
                st.integers(min_value=0, max_value=15),
            ),
            min_size=1,
            max_size=5,
        )
    )
    return start, steps


def reference(start: int, steps: list[tuple[str, int]]) -> int:
    value = start
    for op, operand in steps:
        if op == "+":
            value = (value + operand) & 0xF
        elif op == "-":
            value = (value - operand) & 0xF
        elif op == "&":
            value &= operand
        elif op == "|":
            value |= operand
        else:
            value ^= operand
    return value & 0xF


def compile_and_run(tmp_path: Path, source: str) -> int:
    path = tmp_path / "property.nbl"
    path.write_text(source)
    compiler = Compiler(load_source(source, filename=str(path)), str(path))
    asm = compiler.compile()
    asm_path = tmp_path / "property.asm"
    asm_path.write_text(asm)
    hex_path = tmp_path / "property.hex"
    assemble_file(asm_path, hex_path)

    emu = Emulator()
    emu.load_hex(hex_path)
    emu.run(50000)
    address = compiler.globals["result"].address
    assert address is not None
    return emu.ram[address]


@settings(max_examples=30, deadline=None, suppress_health_check=[HealthCheck.function_scoped_fixture])
@given(nibble_expressions())
def test_nibble_expression_matches_reference(tmp_path: Path, expression) -> None:
    start, steps = expression
    expr = str(start)
    for op, operand in steps:
        expr = f"({expr} {op} {operand})"
    source = f"nibble result;\nfn main() {{ result = {expr}; }}\n"
    assert compile_and_run(tmp_path, source) == reference(start, steps)
