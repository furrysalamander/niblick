"""Smoke test for the signed-nibble wave-field demo."""

from __future__ import annotations

from pathlib import Path

from badgec.assembler import assemble_file, code_words
from badgec.compiler import Compiler
from badgec.emulator import Emulator
from badgec.loader import load_program

ROOT = Path(__file__).resolve().parent.parent


def test_wave_demo_runs_and_draws(tmp_path: Path) -> None:
    example = ROOT / "examples" / "wave.badge"
    compiler = Compiler(load_program(example), str(example))
    asm_path = tmp_path / "wave.asm"
    asm_path.write_text(compiler.compile())
    hex_path = tmp_path / "wave.hex"
    assemble_file(asm_path, hex_path)

    assert code_words(hex_path) <= 1100
    assert compiler.mem.used() <= 176

    emu = Emulator()
    emu.load_hex(hex_path)
    screen = compiler.globals["screen"].address
    assert screen == 0x40  # page 4: the right half of the matrix

    for _ in range(12):
        emu.run(25_000)
        if any(emu.ram[screen + index] for index in range(32)):
            break

    assert any(emu.ram[screen + index] for index in range(32))
