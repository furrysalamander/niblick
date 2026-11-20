"""Optional cross-checks against the upstream headless emulator.

These tests run only when the optional fidelity dependency is installed::

    python3 -m pip install -r requirements-fidelity.txt
    python3 -m pytest tests/test_upstream_emulator.py
"""

from __future__ import annotations

import contextlib
import io
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path

import pytest

try:
    version("supercon6-emulator")
except PackageNotFoundError:
    pytest.skip("supercon6-emulator is not installed", allow_module_level=True)

pytest.importorskip("badge")
pytest.importorskip("bvmCPU")
pytest.importorskip("bvmParser")

from badge import Badge  # noqa: E402
from niblick.assembler import assemble_file  # noqa: E402
from niblick.emulator import Emulator  # noqa: E402

PROGRAM = """\
; Exercise arithmetic, logic, and register-move paths.
; SUB/SBB are omitted: the upstream CPU clears C on no-borrow, while the
; hardware manuals specify inverse borrow (C=1 for no borrow).
MOV R0,5
MOV R1,3
ADD R0,R1
XOR R0,R1
MOV R2,R0
MOV R3,1
loop:
JR -1
"""


def _upstream_state(badge: Badge) -> tuple[int, int, int, int, int, list[int]]:
    cpu = badge.cpu
    return (cpu.pc, cpu.sp, cpu.C, cpu.Z, cpu.V, list(cpu.ram[:10]))


def _our_state(emulator: Emulator) -> tuple[int, int, int, int, int, list[int]]:
    return (
        emulator.pc,
        emulator.sp,
        emulator.C,
        emulator.Z,
        emulator.V,
        list(emulator.ram[:10]),
    )


def test_upstream_core_matches_niblick_on_arithmetic(tmp_path: Path) -> None:
    asm_path = tmp_path / "arith.asm"
    asm_path.write_text(PROGRAM)
    hex_path = tmp_path / "arith.hex"
    assemble_file(asm_path, hex_path)

    upstream = Badge()
    upstream.load(str(hex_path))
    upstream.cpu.ram[0xFF] = 0

    ours = Emulator()
    ours.load_hex(hex_path)
    ours.ram[0xFF] = 0

    with contextlib.redirect_stdout(io.StringIO()):
        for _ in range(12):
            upstream.step()
            ours.step()
            assert _upstream_state(upstream) == _our_state(ours)
