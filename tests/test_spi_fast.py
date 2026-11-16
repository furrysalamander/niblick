"""Tests for the W5500 driver's hand-written fast SPI helpers."""

from __future__ import annotations

from pathlib import Path

from niblick.assembler import assemble_file
from niblick.compiler import Compiler
from niblick.emulator import Emulator
from niblick.loader import load_program


def build(tmp_path: Path, source: str, stem: str):
    path = tmp_path / f"{stem}.nbl"
    path.write_text(source)
    compiler = Compiler(load_program(path), str(path))
    asm = compiler.compile()
    asm_path = tmp_path / f"{stem}.asm"
    asm_path.write_text(asm)
    hex_path = tmp_path / f"{stem}.hex"
    assemble_file(asm_path, hex_path)
    return compiler, hex_path


def run_and_sample_bits(
    cpu: Emulator, steps: int = 400
) -> list[int]:
    """Run *steps* instructions and return MOSI at each SCLK rising edge."""
    bits: list[int] = []
    previous = cpu.ram[0x0A]
    for _ in range(steps):
        cpu.step()
        current = cpu.ram[0x0A]
        if (previous & 0x04) == 0 and (current & 0x04) != 0:
            bits.append(1 if (current & 0x08) else 0)
        previous = current
    return bits


def test_spi_tx_fast_bit_order(tmp_path: Path) -> None:
    _, hex_path = build(
        tmp_path,
        "fn main() { w5500_spi_tx_fast(0xA5); while (1) { } }",
        "spi_tx_fast",
    )
    cpu = Emulator()
    cpu.load_hex(hex_path)
    bits = run_and_sample_bits(cpu)
    assert bits[:8] == [1, 0, 1, 0, 0, 1, 0, 1]


def test_spi_xfer_fast_reads_miso(tmp_path: Path) -> None:
    compiler, hex_path = build(
        tmp_path,
        "char result; fn main() { result = w5500_spi_xfer_fast(0); while (1) { } }",
        "spi_xfer_fast",
    )
    address = compiler.globals["result"].address
    assert address is not None

    for input_value, expected in ((0, 0x00), (1, 0xFF)):
        cpu = Emulator()
        cpu.load_hex(hex_path)
        cpu.set_input(input_value)
        cpu.run(max_steps=2000)
        assert cpu.ram[address] == (expected & 0x0F)
        assert cpu.ram[address + 1] == (expected >> 4)
