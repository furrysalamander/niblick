"""Tests for inline asm blocks in Niblick functions."""

from __future__ import annotations

from pathlib import Path

import pytest

from niblick.assembler import assemble_file
from niblick.compiler import Compiler
from niblick.emulator import Emulator
from niblick.errors import NiblickCompileError
from niblick.loader import load_program


def build(tmp_path: Path, source: str):
    entry = tmp_path / "main.nbl"
    entry.write_text(source)
    compiler = Compiler(load_program(entry), str(entry))
    asm = compiler.compile()
    asm_path = tmp_path / "main.asm"
    asm_path.write_text(asm)
    hex_path = tmp_path / "main.hex"
    assemble_file(asm_path, hex_path)
    return compiler, asm, hex_path


def run(hex_path: Path, steps: int = 10000) -> Emulator:
    emu = Emulator()
    emu.load_hex(hex_path)
    emu.run(max_steps=steps)
    return emu


def test_inline_asm_reads_and_writes_globals(tmp_path: Path) -> None:
    compiler, asm, hex_path = build(
        tmp_path,
        """
        nibble source;
        nibble target;
        fn main() {
            source = 3;
            asm {
                MOV R0, [${source}]
                ADD R0, 2
                MOV [${target}], R0
            }
            while (1) { }
        }
        """,
    )
    assert "; inline assembly" in asm
    assert target_defined(compiler) is not None
    emu = run(hex_path)
    assert emu.ram[compiler.globals["target"].address] == 5


def target_defined(compiler: Compiler) -> int | None:
    return compiler.globals["target"].address


def test_inline_asm_reads_locals(tmp_path: Path) -> None:
    compiler, _, hex_path = build(
        tmp_path,
        """
        nibble result;
        fn main() {
            nibble local;
            local = 9;
            asm {
                MOV R0, [${local}]
                MOV [${result}], R0
            }
            while (1) { }
        }
        """,
    )
    emu = run(hex_path)
    assert emu.ram[compiler.globals["result"].address] == 9


def test_inline_asm_calls_runtime(tmp_path: Path) -> None:
    _, _, hex_path = build(
        tmp_path,
        """
        import "lib/uart.nbl";
        fn main() {
            uart_init(3);
            asm {
                MOV R1, 1
                MOV R2, 4
                GOSUB __nib_uart_putc
            }
            while (1) { }
        }
        """,
    )
    emu = run(hex_path)
    assert b"A" in bytes(emu.uart_tx)


def test_inline_asm_keeps_global_alive_in_dce(tmp_path: Path) -> None:
    compiler, _, hex_path = build(
        tmp_path,
        """
        nibble only_in_asm;
        fn main() {
            asm {
                MOV R0, 7
                MOV [${only_in_asm}], R0
            }
            while (1) { }
        }
        """,
    )
    assert "only_in_asm" in compiler.globals
    emu = run(hex_path)
    assert emu.ram[compiler.globals["only_in_asm"].address] == 7


def test_inline_asm_local_label_loop(tmp_path: Path) -> None:
    compiler, _, hex_path = build(
        tmp_path,
        """
        nibble count;
        fn main() {
            asm {
                MOV R1, 3
                MOV R0, 0
            .loop:
                INC R0
                DEC R1
                SKIP Z, 1
                JR .loop
                MOV [${count}], R0
            }
            while (1) { }
        }
        """,
    )
    emu = run(hex_path)
    assert emu.ram[compiler.globals["count"].address] == 3


def test_inline_asm_is_opaque_to_optimizer(tmp_path: Path) -> None:
    _, asm, _ = build(
        tmp_path,
        """
        fn main() {
            asm {
                MOV R1, R1
            }
            while (1) { }
        }
        """,
    )
    assert "MOV R1, R1" in asm


def test_inline_asm_rejects_ret(tmp_path: Path) -> None:
    entry = tmp_path / "main.nbl"
    entry.write_text(
        """
        fn main() {
            asm {
                RET R0, 0
            }
        }
        """
    )
    compiler = Compiler(load_program(entry), str(entry))
    with pytest.raises(NiblickCompileError, match="RET is not allowed"):
        compiler.compile()


def test_inline_asm_rejects_global_labels(tmp_path: Path) -> None:
    entry = tmp_path / "main.nbl"
    entry.write_text(
        """
        fn main() {
            asm {
            .ok:
                GOTO .ok
            bad_label:
                GOTO bad_label
            }
        }
        """
    )
    compiler = Compiler(load_program(entry), str(entry))
    with pytest.raises(NiblickCompileError, match="labels must start with"):
        compiler.compile()
