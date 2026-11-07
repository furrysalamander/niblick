"""Falling-water cellular automaton smoke test."""

from __future__ import annotations

from pathlib import Path

from badgec.assembler import assemble_file, code_words
from badgec.compiler import Compiler
from badgec.emulator import Emulator
from badgec.loader import load_program

ROOT = Path(__file__).resolve().parent.parent


def _water_count(emu: Emulator, grid: int) -> int:
    total = 0
    for index in range(128):
        cell = emu.ram[grid + (index >> 1)]
        total += (cell >> ((index & 1) << 1)) & 1
    return total


def _screen_bits(emu: Emulator, screen: int) -> int:
    first = sum(bin(emu.ram[screen + index]).count("1") for index in range(32))
    second = sum(
        bin(emu.ram[screen + 32 + index]).count("1") for index in range(32)
    )
    return max(first, second)


def test_water_conserves_cells_and_changes_gravity(tmp_path: Path) -> None:
    example = ROOT / "examples" / "water.badge"
    compiler = Compiler(load_program(example), str(example))
    asm_path = tmp_path / "water.asm"
    asm_path.write_text(compiler.compile())
    hex_path = tmp_path / "water.hex"
    assemble_file(asm_path, hex_path)

    assert code_words(hex_path) <= 2100
    assert compiler.mem.used() <= 176

    emu = Emulator()
    emu.load_hex(hex_path)

    grid = compiler.globals["grid"].address
    screen = compiler.globals["screen"].address
    direction = compiler.globals["dir"].address
    assert screen == 0x40

    emu.run(100_000)
    counts = {_water_count(emu, grid)}
    assert counts & {39, 40}

    directions = set()
    max_screen = 0
    for _ in range(70):
        emu.run(50_000)
        counts.add(_water_count(emu, grid))
        directions.add(emu.ram[direction])
        max_screen = max(max_screen, _screen_bits(emu, screen))
        if len(directions) >= 2 and max_screen == 40:
            break

    assert counts <= {39, 40}
    assert 40 in counts
    assert len(directions) >= 2
    assert max_screen == 40
