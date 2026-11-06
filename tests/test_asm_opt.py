"""Tests for peephole and branch-relaxation passes."""

from __future__ import annotations

from badgec.asm_opt import copy_propagate, optimize_asm, peephole, relax_branches


def test_peephole_removes_redundant_moves() -> None:
    source = """\
MOV R1, R1
MOV R0, R1
MOV R1, R0
MOV R2, 3
MOV R2, 4
MOV R3, R3
"""
    result = peephole(source.splitlines())
    assert result == ["MOV R0, R1", "MOV R2, 4"]


def test_copy_propagation_removes_round_trip_move() -> None:
    source = """\
MOV R0, [142]
MOV R1, R0
MOV R2, 0
MOV R0, R1
MOV [181], R0
"""
    result = copy_propagate(source.splitlines())
    assert result == ["MOV R0, [142]", "MOV R1, R0", "MOV R2, 0", "MOV [181], R0"]


def test_copy_propagation_stops_at_control_flow() -> None:
    source = """\
MOV R0, [142]
MOV R1, R0
GOTO next
MOV R0, R1
next:
MOV R0, R1
"""
    result = copy_propagate(source.splitlines())
    assert result.count("MOV R0, R1") == 2


def test_copy_propagation_tracks_clobbers() -> None:
    source = """\
MOV R0, [142]
MOV R1, R0
ADD R1, R0
MOV R0, R1
"""
    result = copy_propagate(source.splitlines())
    # ADD changes R1, so the final copy back into R0 is required.
    assert result == [
        "MOV R0, [142]",
        "MOV R1, R0",
        "ADD R1, R0",
        "MOV R0, R1",
    ]


def test_branch_relaxation_uses_jr_and_adjusts_skip() -> None:
    source = """\
start:
CP R0, 0
SKIP NZ, 2
GOTO end
MOV R1, 1
end:
JR -1
"""
    result = optimize_asm(source)
    assert "JR end" in result
    assert "SKIP NZ, 1" in result
    assert "GOTO end" not in result


def test_branch_relaxation_keeps_long_goto() -> None:
    filler = "\n".join(["MOV R1, 1"] * 400)
    source = f"""\
start:
GOTO far
{filler}
far:
JR -1
"""
    result = "\n".join(relax_branches(source.splitlines()))
    assert "GOTO far" in result
