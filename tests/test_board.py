"""Board pin-map tests."""

from __future__ import annotations

from pathlib import Path

from badgec.assembler import assemble_file
from badgec.compiler import Compiler
from badgec.emulator import Emulator
from badgec.loader import load_source


def compile_source(tmp_path: Path, source: str) -> tuple[Compiler, Emulator]:
    filename = tmp_path / "board.badge"
    program = load_source(source, filename=str(filename))
    compiler = Compiler(program, str(filename))
    asm = compiler.compile()
    asm_path = tmp_path / "board.asm"
    asm_path.write_text(asm)
    hex_path = tmp_path / "board.hex"
    assemble_file(asm_path, hex_path)

    emu = Emulator()
    emu.load_hex(hex_path)
    emu.run(10000)
    return compiler, emu


def test_voja4_pin_masks(tmp_path: Path) -> None:
    compiler, emu = compile_source(
        tmp_path,
        """
        import "lib/boards/voja4.badge";

        nibble values[15];

        fn main() {
            values[0] = OUT0;
            values[1] = OUT1;
            values[2] = OUT2;
            values[3] = OUT3;
            values[4] = IN0;
            values[5] = IN1;
            values[6] = IN2;
            values[7] = IN3;
            values[8] = SPI_SCLK;
            values[9] = SPI_MOSI;
            values[10] = SPI_MISO;
            values[11] = W5500_CS;
            values[12] = W5500_RST;
            values[13] = SPI_CS;
        }
        """,
    )
    base = compiler.globals["values"].address
    assert base is not None
    assert [emu.ram[base + index] for index in range(14)] == [
        1,
        2,
        4,
        8,
        1,
        2,
        4,
        8,
        4,
        8,
        1,
        2,
        1,
        2,
    ]
