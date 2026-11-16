"""Tests for peephole and branch-relaxation passes."""

from __future__ import annotations

from niblick.asm_opt import (
    asm_word_count,
    copy_propagate,
    dead_register_writes,
    optimize_asm,
    peephole,
    relax_branches,
)


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


def test_dead_register_writes_remove_overwritten_move() -> None:
    source = """\
MOV R1, 3
MOV R2, 4
MOV R1, 5
MOV [10], R1
"""
    result = dead_register_writes(source.splitlines())
    assert result == ["MOV R2, 4", "MOV R1, 5", "MOV [10], R1"]


def test_dead_register_writes_keep_live_move() -> None:
    source = """\
MOV R1, 3
ADD R0, R1
MOV R1, 5
"""
    result = dead_register_writes(source.splitlines())
    assert result == ["MOV R1, 3", "ADD R0, R1", "MOV R1, 5"]


def test_dead_register_writes_keep_memory_loads() -> None:
    # Reading KeyStatus clears JustPress, so loads are not dead code.
    source = """\
MOV R0, [253]
MOV R0, 1
MOV [10], R0
"""
    result = dead_register_writes(source.splitlines())
    assert result == ["MOV R0, [253]", "MOV R0, 1", "MOV [10], R0"]


def test_dead_register_writes_skip_window_is_protected() -> None:
    source = """\
SKIP NZ, 1
MOV R1, 3
MOV R1, 4
MOV [10], R1
"""
    result = dead_register_writes(source.splitlines())
    # Dropping the first move would make SKIP jump into the second one.
    assert result == source.splitlines()


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


def test_word_size_counts_two_word_pseudo_ops() -> None:
    source = """\
CPL R0
CPL R1, R0
NEG R1, R0
SL R1, R0
RLC R1, R0
LSR R1
GOTO target
EQU_VALUE EQU 3
target:
"""
    assert asm_word_count(source) == 13


def test_no_optimize_region_is_opaque() -> None:
    source = """\
; @niblick: no-optimize-begin
MOV R1, R1
GOTO target
; @niblick: no-optimize-end
MOV R2, R2
target:
JR -1
"""
    result = optimize_asm(source)
    assert "MOV R1, R1" in result
    assert "GOTO target" in result
    assert "MOV R2, R2" not in result


def test_file_no_optimize_marker_is_opaque() -> None:
    source = """\
; @niblick: no-optimize
MOV R1, R1
GOTO target
target:
JR -1
"""
    result = optimize_asm(source)
    assert "MOV R1, R1" in result
    assert "GOTO target" in result
