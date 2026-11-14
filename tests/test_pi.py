"""The pi example computes the expected digits over UART."""

from __future__ import annotations

from pathlib import Path

from badgec.assembler import assemble_file
from badgec.compiler import Compiler
from badgec.emulator import Emulator
from badgec.loader import load_program

EXPECTED = b"pi = 3.14159265358979323846264338327950288419716939\r\n"


def test_pi_example(tmp_path: Path) -> None:
    example = Path(__file__).resolve().parent.parent / "examples" / "pi.badge"
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
