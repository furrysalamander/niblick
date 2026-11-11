"""Per-function size and stack-cost reporting."""

from __future__ import annotations

import json
from pathlib import Path

from badgec.assembler import assemble_file, code_words
from badgec.cli import main
from badgec.compiler import Compiler
from badgec.loader import load_program
from badgec.parser import parse
from badgec.runtime_linker import runtime_stack_costs

ROOT = Path(__file__).resolve().parent.parent


def build(tmp_path: Path, source: str, name: str = "report"):
    path = tmp_path / f"{name}.badge"
    path.write_text(source)
    compiler = Compiler(load_program(path), str(path))
    asm_path = tmp_path / f"{name}.asm"
    asm_path.write_text(compiler.compile())
    hex_path = tmp_path / f"{name}.hex"
    assemble_file(asm_path, hex_path)
    return compiler, hex_path


def test_runtime_stack_costs_match_documented_values() -> None:
    text = (ROOT / "badgec" / "runtime" / "runtime.asm").read_text()
    costs = runtime_stack_costs(text)
    assert costs["__bc_uart_putc"] == 1
    assert costs["__bc_flash_read_char_ptr"] == 2
    assert costs["__bc_flash_read_char"] == 3
    assert costs["__bc_gpio_set"] == 2
    assert costs["__bc_mul16"] == 1


def test_per_function_sizes_sum_to_total(tmp_path: Path) -> None:
    compiler, hex_path = build(
        tmp_path,
        """
        nibble a;
        nibble b;
        fn nibble add(nibble x, nibble y) {
            nibble r;
            r = x + y;
            return r;
        }
        fn main() {
            a = 1;
            b = add(a, 2);
        }
        """,
    )
    total = code_words(hex_path)
    sizes = compiler.code_sizes(total)
    assert sizes["total"] == total
    assert 1 <= sizes["startup"] <= 2  # reset-vector GOTO/JR fn_main
    assert sizes["functions"]["add"] > 0
    assert sizes["functions"]["main"] > 0
    assert (
        sum(sizes["functions"].values())
        + sum(sizes["runtime"].values())
        + sizes["flash"]
        + sizes["startup"]
        == total
    )


def test_map_json_includes_sizes_and_stack(tmp_path: Path) -> None:
    source = tmp_path / "report.badge"
    source.write_text(
        """
        import "lib/uart.badge";
        nibble x;
        fn main() {
            uart_init(3);
            uart_puts("hi");
            x = 1;
        }
        """
    )
    map_path = tmp_path / "report.map.json"
    assert main([str(source), "--map-json", str(map_path)]) == 0
    data = json.loads(map_path.read_text())
    assert data["code_words"] > 0
    assert data["asm_words"] == data["code_words"]
    assert data["functions"][0]["words"] > 0
    assert data["runtime_words"]["__bc_uart_putc"] > 0
    assert data["stack"]["max_call_depth"] == 1
    assert data["stack"]["runtime_costs"]["__bc_uart_putc"] == 1


def test_stack_report_and_warning_for_deep_runtime_call(tmp_path: Path) -> None:
    source = tmp_path / "deep.badge"
    source.write_text(
        """
        nibble x;
        fn void leaf() { x = gpio_test(3); }
        fn void a() { leaf(); x = x; }
        fn void b() { a(); x = x; }
        fn void c() { b(); x = x; }
        fn main() { c(); }
        """
    )
    compiler = Compiler(load_program(source), str(source))
    asm = compiler.compile()
    assert compiler.max_call_depth == 4
    assert compiler.deepest_path == ["main", "c", "b", "a", "leaf"]
    assert compiler.runtime_costs["__bc_gpio_test"] == 2
    assert compiler.stack_warnings
    assert "6 stack levels" in compiler.stack_warnings[0]

    asm_path = tmp_path / "deep.asm"
    asm_path.write_text(asm)
    assert main([str(source), "--stack"]) == 0


def test_symbols_prints_function_words(tmp_path: Path, capsys) -> None:
    source = tmp_path / "size.badge"
    source.write_text(
        """
        nibble x;
        fn nibble twice(nibble v) {
            nibble r;
            r = v + v;
            return r;
        }
        fn main() { x = twice(3); }
        """
    )
    assert main([str(source), "--symbols"]) == 0
    out = capsys.readouterr().out
    assert "twice -> nibble" in out
    assert "words" in out
    assert "total:" in out


def test_example_sizes_stay_consistent(tmp_path: Path) -> None:
    example = ROOT / "examples" / "dword_math.badge"
    compiler = Compiler(load_program(example), str(example))
    asm_path = tmp_path / "dword_math.asm"
    asm_path.write_text(compiler.compile())
    hex_path = tmp_path / "dword_math.hex"
    assemble_file(asm_path, hex_path)
    total = code_words(hex_path)
    sizes = compiler.code_sizes(total)
    assert (
        sum(sizes["functions"].values())
        + sum(sizes["runtime"].values())
        + sizes["flash"]
        + sizes["startup"]
        == total
    )
