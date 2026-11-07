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


def decode_screen(emu: Emulator) -> tuple[tuple[int, ...], ...]:
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


def decode_vfb(emu: Emulator, address: int) -> tuple[tuple[int, ...], ...]:
    """Decode the 16x16 virtual framebuffer."""
    rows = []
    for y in range(16):
        row = []
        for group in range(4):
            value = emu.ram[address + y * 4 + group]
            for bit in range(4):
                row.append((value >> (3 - bit)) & 1)
        rows.append(tuple(row))
    return tuple(rows)


def collect_frames(
    emu: Emulator, angle_address: int, vfb_address: int, count: int = 18
):
    frames = []
    marks = []
    last_angle = None
    changes = 0
    steps = 0
    while steps < 2_000_000 and len(frames) < count:
        emu.step()
        steps += 1
        angle = emu.ram[angle_address] | (emu.ram[angle_address + 1] << 4)
        if angle != last_angle:
            last_angle = angle
            changes += 1
            # The first two changes are startup and the first rendered frame.
            if changes > 2:
                frames.append((decode_screen(emu), decode_vfb(emu, vfb_address)))
                marks.append(emu.instruction_count)
    return frames, marks


def test_cube_virtual_framebuffer_and_clipping(tmp_path: Path) -> None:
    compiler, emu, hex_path = build(tmp_path)

    screen = compiler.globals["screen"]
    vfb = compiler.globals["vfb"]
    assert screen.address == 0x40
    assert screen.array_len == 32
    assert vfb.address == 0x60
    assert vfb.array_len == 64
    assert compiler.mem.used() <= 176
    assert code_words(hex_path) <= 2100

    angle_address = compiler.globals["angle"].address
    frames, marks = collect_frames(emu, angle_address, vfb.address)
    assert len(frames) >= 14
    assert emu.ram[0xF0] == 4

    screens = [screen for screen, _ in frames]
    virtual = [vfb for _, vfb in frames]

    assert all(any(any(row) for row in bitmap) for bitmap in screens)
    assert len(set(screens)) >= 10

    # Every visible pixel must come from virtual columns 4..11.
    for visible, full in zip(screens, virtual):
        for y in range(16):
            assert visible[y] == full[y][4:12]

    # The cube must actually extend into the off-screen margin: those pixels
    # are drawn in the virtual buffer but never blitted.
    assert any(
        full[y][x]
        for full in virtual
        for y in range(16)
        for x in list(range(0, 4)) + list(range(12, 16))
    )

    for bitmap in screens:
        lit = sum(sum(row) for row in bitmap)
        assert 10 < lit <= 128

    # Guard against a large code-generation or drawing regression.
    diffs = [marks[i] - marks[i - 1] for i in range(1, len(marks))]
    assert diffs
    assert max(diffs) < 26_000
