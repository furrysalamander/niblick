"""Code-size regression and runtime-stripping tests."""

from __future__ import annotations

from pathlib import Path

from badgec.assembler import assemble_file, code_words
from badgec.compiler import Compiler
from badgec.loader import load_program

ROOT = Path(__file__).resolve().parent.parent
BUDGETS = {
    "hello.badge": 120,
    "serial_echo.badge": 200,
    "flash_walk.badge": 180,
    "gpio_blink.badge": 70,
    "tetris.badge": 2600,
    "stdlib_demo.badge": 1900,
    "word_math.badge": 1300,
    "dword_math.badge": 2300,
    "math32_test.badge": 2800,
    "cube.badge": 2100,
    "wave.badge": 1200,
    "water.badge": 2800,
}


def compile_example(example: Path, tmp_path: Path, strip_runtime: bool = True):
    compiler = Compiler(
        load_program(example), str(example), strip_runtime=strip_runtime
    )
    asm = compiler.compile()
    asm_path = tmp_path / (example.stem + ".asm")
    asm_path.write_text(asm)
    hex_path = tmp_path / (example.stem + ".hex")
    assemble_file(asm_path, hex_path)
    return compiler, asm, hex_path


def test_example_size_budgets(tmp_path: Path) -> None:
    for name, budget in BUDGETS.items():
        example = ROOT / "examples" / name
        _, _, hex_path = compile_example(example, tmp_path)
        words = code_words(hex_path)
        assert words <= budget, f"{name} grew to {words} words (budget {budget})"


def test_runtime_stripping_removes_unused_helpers(tmp_path: Path) -> None:
    example = ROOT / "examples" / "hello.badge"
    stripped_dir = tmp_path / "stripped"
    full_dir = tmp_path / "full"
    stripped_dir.mkdir()
    full_dir.mkdir()

    _, stripped_asm, stripped_hex = compile_example(example, stripped_dir, True)
    _, full_asm, full_hex = compile_example(example, full_dir, False)

    assert "__bc_uart_puts" in stripped_asm
    assert "__bc_gpio_set" not in stripped_asm
    assert "__bc_gpio_set" in full_asm
    assert code_words(stripped_hex) < code_words(full_hex)
