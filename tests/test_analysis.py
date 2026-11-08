"""Tests for AST source positions, loader overrides, and editor analysis."""

from __future__ import annotations

from pathlib import Path

from badgec import ast_nodes as ast
from badgec.analysis import Analysis
from badgec.loader import load_program
from badgec.parser import parse


def test_parser_records_positions_and_files() -> None:
    program = parse(
        "const nibble PIN = 1;\n"
        "nibble x;\n"
        "fn main() {\n"
        "    x = PIN + 1;\n"
        "}\n",
        "test.badge",
    )
    pin, x = program.globals
    main = program.functions[0]

    assert pin.file == "test.badge"
    assert pin.line == 1
    assert pin.column == 14
    assert x.file == "test.badge"
    assert x.line == 2
    assert x.column == 8
    assert main.file == "test.badge"
    assert main.line == 3
    assert main.name_line == 3
    assert main.name_column == 4

    assign = main.body.statements[0]
    assert isinstance(assign, ast.Assign)
    assert assign.file == "test.badge"
    assert assign.line == 4
    assert isinstance(assign.target, ast.Var)
    assert assign.target.column == 5
    assert isinstance(assign.value, ast.Binary)
    assert assign.value.column == 13
    assert isinstance(assign.value.left, ast.Var)
    assert assign.value.left.column == 9


def test_load_program_honours_source_overrides(tmp_path: Path) -> None:
    entry = tmp_path / "main.badge"
    entry.write_text("fn main() { this is not valid }\n")
    program = load_program(
        entry,
        source_overrides={
            entry: "fn main() { while (1) { } }\n",
        },
    )
    assert program.functions[0].name == "main"


def test_analysis_reports_syntax_error_with_position(tmp_path: Path) -> None:
    entry = tmp_path / "bad.badge"
    entry.write_text("fn main() { nibble x = ; }\n")
    diagnostics = Analysis(entry).diagnostics()
    assert len(diagnostics) == 1
    assert diagnostics[0].file == str(entry.resolve())
    assert diagnostics[0].line == 1
    assert diagnostics[0].column > 1
    assert "expected" in diagnostics[0].message


def test_analysis_reports_type_error(tmp_path: Path) -> None:
    entry = tmp_path / "types.badge"
    entry.write_text("nibble x;\nfn main() { x = 300; }\n")
    diagnostics = Analysis(entry).diagnostics()
    assert len(diagnostics) == 1
    assert diagnostics[0].line == 2
    assert "cannot convert" in diagnostics[0].message


def test_analysis_checks_library_without_main(tmp_path: Path) -> None:
    entry = tmp_path / "lib.badge"
    entry.write_text(
        "fn nibble add(nibble a, nibble b) { return a + b; }\n"
    )
    assert Analysis(entry).diagnostics() == []


def test_analysis_reports_imported_asm_error(tmp_path: Path) -> None:
    entry = tmp_path / "main.badge"
    entry.write_text(
        'import "bad.asm";\n'
        "extern fn void bad();\n"
        "fn main() { bad(); }\n"
    )
    bad = tmp_path / "bad.asm"
    bad.write_text("fn_bad:\n    MOV JSR, R1\n    RET R0, 0\n")
    diagnostics = Analysis(entry).diagnostics()
    assert len(diagnostics) == 1
    assert diagnostics[0].file == str(bad.resolve())
    assert diagnostics[0].line == 2
    assert "raw MOV JSR" in diagnostics[0].message


def test_analysis_reports_missing_asm_entry_point(tmp_path: Path) -> None:
    entry = tmp_path / "main.badge"
    entry.write_text(
        'import "empty.asm";\n'
        "extern fn void missing();\n"
        "fn main() { missing(); }\n"
    )
    (tmp_path / "empty.asm").write_text("; no entry points\n")
    diagnostics = Analysis(entry).diagnostics()
    assert len(diagnostics) == 1
    assert diagnostics[0].line == 2
    assert "has no fn_missing" in diagnostics[0].message


def test_document_symbols_filters_by_file(tmp_path: Path) -> None:
    lib = tmp_path / "lib.badge"
    lib.write_text(
        "const nibble ANSWER = 7;\n"
        "fn nibble twice(nibble n) { return n + n; }\n"
    )
    entry = tmp_path / "main.badge"
    entry.write_text(
        'import "lib.badge";\n'
        "nibble result;\n"
        "fn main() { result = twice(ANSWER); }\n"
    )
    analysis = Analysis(entry)
    entry_symbols = analysis.document_symbols(entry)
    assert [symbol.name for symbol in entry_symbols] == ["result", "main"]
    assert entry_symbols[1].line == 3
    assert entry_symbols[1].detail == "void main()"

    lib_symbols = analysis.document_symbols(lib)
    assert [symbol.name for symbol in lib_symbols] == ["ANSWER", "twice"]
    assert lib_symbols[1].detail == "nibble twice(nibble n)"
    assert lib_symbols[1].children[0].name == "n"


def test_document_symbols_for_asm_file(tmp_path: Path) -> None:
    asm = tmp_path / "driver.asm"
    asm.write_text(
        "fn_driver:\n"
        "    RET R0, 0\n"
        "table:\n"
        "    NIBBLE 1\n"
    )
    entry = tmp_path / "main.badge"
    entry.write_text("fn main() { while (1) { } }\n")
    symbols = Analysis(entry).document_symbols(asm)
    assert [(symbol.name, symbol.kind) for symbol in symbols] == [
        ("fn_driver", "function"),
        ("table", "variable"),
    ]
