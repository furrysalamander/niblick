"""The pi example computes the expected digits over UART."""

from __future__ import annotations

from pathlib import Path

from niblick.assembler import assemble_file
from niblick.compiler import Compiler
from niblick.emulator import Emulator
from niblick.loader import load_program

EXPECTED = b"pi = 3.14159265358979323846264338327950288419716939\r\n"


def test_pi_example(tmp_path: Path) -> None:
    example = Path(__file__).resolve().parent.parent / "examples" / "pi.nbl"
    compiler = Compiler(load_program(example), str(example))
    asm_path = tmp_path / "pi.asm"
    asm_path.write_text(compiler.compile())
    hex_path = tmp_path / "pi.hex"
    assemble_file(asm_path, hex_path)

    emulator = Emulator()
    emulator.load_hex(hex_path)
    for _ in range(200):
        emulator.run(100_000)
        if emulator.uart_tx and emulator.uart_tx[-1] == 10:
            break

    assert bytes(emulator.uart_tx) == EXPECTED
    assert compiler.mem.used() <= 208


def test_pi_matrix_banner(tmp_path: Path) -> None:
    """After the UART line, the result scrolls on the LED matrix."""
    example = Path(__file__).resolve().parent.parent / "examples" / "pi.nbl"
    compiler = Compiler(load_program(example), str(example))
    asm_path = tmp_path / "pi.asm"
    asm_path.write_text(compiler.compile())
    hex_path = tmp_path / "pi.hex"
    assemble_file(asm_path, hex_path)

    emulator = Emulator()
    emulator.load_hex(hex_path)
    for _ in range(200):
        emulator.run(100_000)
        if emulator.uart_tx and emulator.uart_tx[-1] == 10:
            break

    # Let the banner draw a couple of dozen columns.
    for _ in range(10):
        emulator.run(100_000)

    # The scroll routine selects pages 7/8 as the framebuffer and sets a
    # mid-brightness dimmer.
    assert emulator._read_memory(0xF0) == 7
    assert emulator._read_memory(0xFE) == 8

    # Glyph bits must occupy the top eight rows of both halves.  Rows 8..15
    # stay clear because the banner only draws 5x8 text.
    left, right = emulator.display_pages()
    assert any(left[y] or right[y] for y in range(8))
    assert any(left[y] for y in range(8))
    assert not any(left[y] or right[y] for y in range(8, 16))
