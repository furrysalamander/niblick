"""Constant-mask GPIO lowering and runtime fallback tests."""

from __future__ import annotations

from pathlib import Path

import pytest

from badgec.assembler import assemble_file, code_words
from badgec.compiler import Compiler
from badgec.emulator import Emulator
from badgec.parser import parse

MASKS = (0, 1, 2, 3, 4, 5, 8, 15)


def build(tmp_path: Path, source: str, name: str):
    path = tmp_path / f"{name}.badge"
    path.write_text(source)
    compiler = Compiler(parse(source, str(path)), str(path))
    asm_path = tmp_path / f"{name}.asm"
    asm_path.write_text(compiler.compile())
    hex_path = tmp_path / f"{name}.hex"
    assemble_file(asm_path, hex_path)
    return compiler, asm_path, hex_path


def run(hex_path: Path, iopos: int = 0, input_value: int = 0):
    emu = Emulator()
    emu.load_hex(hex_path)
    emu.ram[0xF3] = 2 if iopos else 0
    emu.ram[0x0B] = input_value
    emu.ram[0xFB] = input_value
    emu.run(10000)
    return emu


def program(mask_expr: str, init_expr: str) -> str:
    return f"""
    nibble result;
    nibble mask;
    fn main() {{
        mask = {init_expr};
        gpio_write(5);
        gpio_set({mask_expr});
        gpio_clear({mask_expr});
        gpio_toggle({mask_expr});
        result = gpio_test({mask_expr});
    }}
    """


def test_constant_gpio_lowering_shape(tmp_path: Path) -> None:
    compiler, asm_path, _ = build(
        tmp_path,
        """
        fn main() {
            gpio_set(0b0001);
            gpio_clear(0b0010);
            gpio_toggle(0b0100);
            gpio_test(0b1000);
        }
        """,
        "gpio_shape",
    )
    asm = asm_path.read_text()
    assert "BSET R3, 0" in asm
    assert "BCLR R3, 1" in asm
    assert "BTG R3, 2" in asm
    assert "BIT R3, 3" in asm
    assert "GOSUB __bc_gpio_" not in asm
    assert not any(name.startswith("__bc_gpio_") for name in compiler.used_runtime)


@pytest.mark.parametrize("iopos", [0, 1])
@pytest.mark.parametrize("mask", MASKS)
def test_constant_masks_match_runtime(
    tmp_path: Path, mask: int, iopos: int
) -> None:
    input_value = 0b1010
    fast_compiler, _, fast_hex = build(
        tmp_path, program(str(mask), str(mask)), f"fast_{mask}_{iopos}"
    )
    slow_compiler, _, slow_hex = build(
        tmp_path,
        program("mask", str(mask)),
        f"slow_{mask}_{iopos}",
    )

    fast = run(fast_hex, iopos=iopos, input_value=input_value)
    slow = run(slow_hex, iopos=iopos, input_value=input_value)

    out_addr = 0x0A if iopos == 0 else 0xFA
    assert fast.ram[out_addr] == slow.ram[out_addr]
    assert fast.ram[out_addr] == ((((5 | mask) & (~mask & 0xF)) ^ mask) & 0xF)
    assert fast.ram[fast_compiler.globals["result"].address] == slow.ram[
        slow_compiler.globals["result"].address
    ]


def test_single_bit_test_values(tmp_path: Path) -> None:
    compiler0, _, hex_zero = build(
        tmp_path,
        "nibble r; fn main(){ r = gpio_test(4); }",
        "gpio_zero",
    )
    assert run(hex_zero, input_value=0).ram[compiler0.globals["r"].address] == 0

    compiler1, _, hex_one = build(
        tmp_path,
        "nibble r; fn main(){ r = gpio_test(4); }",
        "gpio_one",
    )
    assert run(hex_one, input_value=4).ram[compiler1.globals["r"].address] == 1


def test_multi_bit_test_falls_back(tmp_path: Path) -> None:
    compiler, asm_path, hex_path = build(
        tmp_path,
        "nibble r; fn main(){ r = gpio_test(0b0101); }",
        "gpio_multi",
    )
    assert "__bc_gpio_test" in compiler.used_runtime
    assert "GOSUB __bc_gpio_test" in asm_path.read_text()
    emu = run(hex_path, input_value=0b0100)
    assert emu.ram[compiler.globals["r"].address] == 1


def test_variable_mask_links_runtime(tmp_path: Path) -> None:
    compiler, _, _ = build(
        tmp_path,
        "nibble m; fn main(){ m = 3; gpio_set(m); }",
        "gpio_variable",
    )
    assert "__bc_gpio_set" in compiler.used_runtime


def test_constant_gpio_is_smaller(tmp_path: Path) -> None:
    _, _, fast_hex = build(
        tmp_path,
        "fn main(){ while(1){ gpio_toggle(1); } }",
        "gpio_loop_fast",
    )
    _, _, slow_hex = build(
        tmp_path,
        "nibble m; fn main(){ m = 1; while(1){ gpio_toggle(m); } }",
        "gpio_loop_slow",
    )
    assert code_words(fast_hex) + 20 < code_words(slow_hex)


def test_zero_mask_emits_no_operations(tmp_path: Path) -> None:
    compiler, asm_path, hex_path = build(
        tmp_path,
        """
        nibble r;
        fn main() {
            gpio_set(0);
            gpio_clear(0);
            gpio_toggle(0);
            r = gpio_test(0);
        }
        """,
        "gpio_zero_mask",
    )
    asm = asm_path.read_text()
    assert "BSET R3" not in asm
    assert "BCLR R3" not in asm
    assert "BTG R3" not in asm
    assert "BIT R3" not in asm
    assert not any(name.startswith("__bc_gpio_") for name in compiler.used_runtime)
    emu = run(hex_path, input_value=0b1111)
    assert emu.ram[compiler.globals["r"].address] == 0
