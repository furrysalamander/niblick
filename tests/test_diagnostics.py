"""Structured diagnostic and assembler-mapping tests."""

from __future__ import annotations

import json
from pathlib import Path

from niblick.analysis import Analysis
from niblick.cli import main
from niblick.compiler import Compiler
from niblick.errors import NiblickSyntaxError
from niblick.loader import load_program
from niblick.parser import parse


def test_parser_error_exposes_structured_fields() -> None:
    try:
        parse("fn main() { nibble x = ; }", "bad.nbl")
    except NiblickSyntaxError as exc:
        assert exc.file == "bad.nbl"
        assert exc.line == 1
        assert exc.column > 1
        assert "expected" in exc.message
    else:
        raise AssertionError("expected a syntax error")


def test_compiler_error_exposes_structured_fields(tmp_path: Path) -> None:
    entry = tmp_path / "bad.nbl"
    entry.write_text("nibble x;\nfn main() { x = 300; }\n")
    compiler = Compiler(load_program(entry), str(entry))
    try:
        compiler.compile()
    except Exception as exc:  # NiblickTypeError
        assert exc.file == str(entry)
        assert exc.line == 2
        assert "cannot convert" in exc.message
    else:
        raise AssertionError("expected a compiler error")


def test_cli_diagnostics_json(tmp_path: Path, capsys) -> None:
    entry = tmp_path / "bad.nbl"
    entry.write_text("nibble x;\nfn main() { x = 300; }\n")
    code = main([str(entry), "--no-assemble", "--diagnostics-json"])
    captured = capsys.readouterr()
    assert code == 1
    data = json.loads(captured.out)
    assert data[0]["file"] == str(entry)
    assert data[0]["line"] == 2
    assert data[0]["severity"] == "error"
    assert "cannot convert" in data[0]["message"]


def test_assembler_error_maps_to_imported_asm_line(tmp_path: Path) -> None:
    entry = tmp_path / "main.nbl"
    entry.write_text(
        'import "bad.asm";\n'
        "extern fn void bad();\n"
        "fn main() { bad(); }\n"
    )
    asm = tmp_path / "bad.asm"
    asm.write_text(
        "fn_bad:\n"
        "    MOV R99, R0\n"
        "    RET R0, 0\n"
    )
    diagnostics = Analysis(entry).diagnostics()
    assert len(diagnostics) == 1
    assert diagnostics[0].file == str(asm.resolve())
    assert diagnostics[0].line == 2


def test_assembler_error_maps_to_inline_asm_line(tmp_path: Path) -> None:
    entry = tmp_path / "main.nbl"
    entry.write_text(
        "fn main() {\n"
        "    asm {\n"
        "        MOV R99, R0\n"
        "    }\n"
        "}\n"
    )
    diagnostics = Analysis(entry).diagnostics()
    assert len(diagnostics) == 1
    assert diagnostics[0].file == str(entry.resolve())
    assert diagnostics[0].line == 3
