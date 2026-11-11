"""Tests for the PC-to-source debug map."""

from __future__ import annotations

from pathlib import Path

from badgec.assembler import assemble_file
from badgec.compiler import Compiler
from badgec.loader import load_program


def build(tmp_path: Path, source: str):
    entry = tmp_path / "main.badge"
    entry.write_text(source)
    compiler = Compiler(load_program(entry), str(entry))
    asm = compiler.compile()
    asm_path = tmp_path / "main.asm"
    asm_path.write_text(asm)
    assemble_file(asm_path, tmp_path / "main.hex")
    return compiler, entry, compiler.debug_map()


def test_debug_map_contains_functions_and_lines(tmp_path: Path) -> None:
    compiler, entry, debug = build(
        tmp_path,
        "nibble x;\n"
        "fn main() {\n"
        "    x = 1;\n"
        "    while (1) { }\n"
        "}\n",
    )
    main = debug["functions"]["main"]
    assert main["start_pc"] == debug["labels"]["fn_main"]
    assert main["end_pc"] > main["start_pc"]
    source_lines = debug["source"][str(entry.resolve())]
    assert "3" in source_lines
    assert "4" in source_lines
    assert source_lines["3"][0] < source_lines["4"][0]
    assert str(main["start_pc"]) in debug["pc_source"]


def test_debug_map_covers_inline_asm_lines(tmp_path: Path) -> None:
    _, entry, debug = build(
        tmp_path,
        "fn main() {\n"
        "    nibble x;\n"
        "    asm {\n"
        "        MOV R0, 1\n"
        "        MOV [${x}], R0\n"
        "    }\n"
        "    while (1) { }\n"
        "}\n",
    )
    source_lines = debug["source"][str(entry.resolve())]
    assert "4" in source_lines
    assert "5" in source_lines


def test_debug_map_does_not_map_runtime_after_source_end(tmp_path: Path) -> None:
    _, _, debug = build(
        tmp_path,
        "fn main() { uart_putc(65); while (1) { } }\n",
    )
    # The runtime follows a source-end marker; only the entry source should
    # appear in the source map.
    assert len(debug["source"]) == 1
