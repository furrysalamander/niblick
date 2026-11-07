"""Behavioral checks for the spinning-cube demo."""

from __future__ import annotations

from pathlib import Path

from badgec.assembler import assemble_file, code_words
from badgec.compiler import Compiler
from badgec.emulator import Emulator
from badgec.loader import load_program

ROOT = Path(__file__).resolve().parent.parent
EXAMPLE = ROOT / "examples" / "cube.badge"


def build(tmp_path: Path):
    compiler = Compiler(load_program(EXAMPLE), str(EXAMPLE))
    asm_path = tmp_path / "cube.asm"
    asm_path.write_text(compiler.compile())
    hex_path = tmp_path / "cube.hex"
    assemble_file(asm_path, hex_path)
    emu = Emulator()
    emu.load_hex(hex_path)
    return compiler, emu, hex_path


def decode(emu: Emulator) -> tuple[tuple[int, ...], ...]:
    """Decode the two visible pages into an 8x16 bitmap."""
    left, right = emu.display_pages()
    rows = []
    for y in range(16):
        row = []
        for x in range(4):
            row.append((left[y] >> (3 - x)) & 1)
        for x in range(4):
            row.append((right[y] >> (3 - x)) & 1)
        rows.append(tuple(row))
    return tuple(rows)


def collect_frames(emu: Emulator, count: int = 24):
    frames = []
    marks = []
    last_page = None
    steps = 0
    while steps < 2_000_000 and len(frames) < count:
        emu.step()
        steps += 1
        page = emu.ram[0xF0]
        if page in (4, 6) and page != last_page:
            frames.append((page, decode(emu)))
            marks.append(emu.instruction_count)
            last_page = page
    return frames, marks


def test_cube_buffers_geometry_and_timing(tmp_path: Path) -> None:
    compiler, emu, hex_path = build(tmp_path)

    # The first global must sit at page 4 so pages 4/5 and 6/7 are usable
    # as two page-aligned framebuffers.
    assert compiler.globals["screen"].address == 0x40
    assert compiler.mem.used() <= 176
    assert code_words(hex_path) <= 2100

    frames, marks = collect_frames(emu)
    assert len(frames) >= 20

    nonblank = [(page, bitmap) for page, bitmap in frames if any(any(row) for row in bitmap)]
    assert len(nonblank) >= 18
    assert {page for page, _ in nonblank} == {4, 6}

    bitmaps = {bitmap for _, bitmap in nonblank}
    assert len(bitmaps) >= 10

    for _, bitmap in nonblank:
        lit = sum(sum(row) for row in bitmap)
        assert 10 < lit <= 128

    # The cube is scaled to clip at the left and right edges.
    assert any(bitmap[y][0] for _, bitmap in nonblank for y in range(16))
    assert any(bitmap[y][7] for _, bitmap in nonblank for y in range(16))

    # Guard against a large code-generation or drawing regression.
    diffs = [marks[i] - marks[i - 1] for i in range(1, len(marks))]
    assert diffs
    assert max(diffs) < 22_000
