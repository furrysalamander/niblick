"""Falling-water cellular automaton smoke test."""

from __future__ import annotations

from pathlib import Path

from badgec.assembler import assemble_file, code_words
from badgec.compiler import Compiler
from badgec.emulator import Emulator
from badgec.loader import load_program

ROOT = Path(__file__).resolve().parent.parent


def _bits(emu: Emulator, address: int, count: int = 32) -> int:
    return sum(bin(emu.ram[address + index]).count("1") for index in range(count))


def test_water_conserves_cells_and_changes_gravity(tmp_path: Path) -> None:
    example = ROOT / "examples" / "water.badge"
    compiler = Compiler(load_program(example), str(example))
    asm_path = tmp_path / "water.asm"
    asm_path.write_text(compiler.compile())
    hex_path = tmp_path / "water.hex"
    assemble_file(asm_path, hex_path)

    assert code_words(hex_path) <= 1900
    assert compiler.mem.used() <= 176

    emu = Emulator()
    emu.load_hex(hex_path)

    grid = compiler.globals["grid"].address
    screen = compiler.globals["screen"].address
    direction = compiler.globals["dir"].address
    assert screen == 0x40

    emu.run(50_000)
    assert _bits(emu, grid) == 40  # five full rows

    directions = set()
    max_screen = 0
    for _ in range(70):
        emu.run(50_000)
        assert _bits(emu, grid) == 40
        directions.add(emu.ram[direction])
        max_screen = max(max_screen, _bits(emu, screen))
        if len(directions) >= 2 and max_screen == 40:
            break

    assert len(directions) >= 2
    assert max_screen == 40
