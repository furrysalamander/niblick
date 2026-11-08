"""Tests for AST source positions, loader overrides, and editor analysis."""

from __future__ import annotations

from pathlib import Path

from badgec import ast_nodes as ast
from badgec.analysis import Analysis
from badgec.loader import load_program
from badgec.parser import parse


def position(source: str, needle: str, occurrence: int = 1) -> tuple[int, int]:
    index = -1
    start = 0
    for _ in range(occurrence):
        index = source.index(needle, start)
        start = index + len(needle)
    line = source.count("\n", 0, index) + 1
    column = index - source.rfind("\n", 0, index)
    return line, column


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


def test_navigation_and_hover_for_badgec_symbols(tmp_path: Path) -> None:
    source_text = (
        "nibble g;\n"
        "fn nibble add(nibble a, nibble b) {\n"
        "    nibble c;\n"
        "    c = a + b;\n"
        "    return c;\n"
        "}\n"
        "fn main() {\n"
        "    nibble x;\n"
        "    x = add(g, 2);\n"
        "}\n"
    )
    entry = tmp_path / "nav.badge"
    entry.write_text(source_text)
    analysis = Analysis(entry)

    # Local assignment target resolves to its declaration.
    line, column = position(source_text, "c = a")
    target = analysis.definition(entry, line, column)
    assert target is not None
    assert target.name == "c"
    assert target.line == 3

    # Parameter reference.
    line, column = position(source_text, "a + b")
    target = analysis.definition(entry, line, column)
    assert target is not None
    assert target.kind == "param"
    assert target.name == "a"

    # Global reference in a call argument.
    line, column = position(source_text, "g, 2")
    target = analysis.definition(entry, line, column)
    assert target is not None
    assert target.kind == "global"

    # Function call and hover signature.
    line, column = position(source_text, "add(g")
    target = analysis.definition(entry, line, column)
    assert target is not None
    assert target.name == "add"
    hover = analysis.hover(entry, line, column)
    assert hover is not None
    assert "nibble add(nibble a, nibble b)" in hover

    # Completion includes visible params, locals, globals, and functions.
    line, column = position(source_text, "a + b")
    names = {item.name for item in analysis.completions(entry, line, column)}
    assert {"a", "b", "c", "g", "add"}.issubset(names)


def test_navigation_into_imported_asm(tmp_path: Path) -> None:
    source_text = (
        'import "impl.asm";\n'
        "extern fn nibble add3(nibble x);\n"
        "nibble result;\n"
        "fn main() {\n"
        "    result = add3(4);\n"
        "}\n"
    )
    entry = tmp_path / "main.badge"
    entry.write_text(source_text)
    asm_text = (
        "fn_add3:\n"
        "    MOV R0, [${x}]\n"
        "    ADD R0, 3\n"
        "    MOV R1, R0\n"
        "    RET R0, 0\n"
    )
    asm = tmp_path / "impl.asm"
    asm.write_text(asm_text)

    analysis = Analysis(entry)

    # A call to an extern function goes to its assembly entry point.
    line, column = position(source_text, "add3(4)")
    target = analysis.definition(entry, line, column)
    assert target is not None
    assert target.file == str(asm.resolve())
    assert target.line == 1

    # A placeholder in assembly resolves to the C parameter.
    line, column = position(asm_text, "${x}")
    target = analysis.definition(asm, line, column + 2)
    assert target is not None
    assert target.name == "x"
    assert target.file == str(entry.resolve())
    assert target.line == 2

    # Hover on the asm label shows the entry point.
    line, column = position(asm_text, "fn_add3")
    hover = analysis.hover(asm, line, column)
    assert hover is not None
    assert "assembly entry point" in hover


def test_asm_completions_include_instructions_and_labels(tmp_path: Path) -> None:
    entry = tmp_path / "main.badge"
    entry.write_text("fn main() { while (1) { } }\n")
    asm = tmp_path / "impl.asm"
    asm.write_text("fn_impl:\n    RET R0, 0\n")
    analysis = Analysis(entry, extra_asm={asm: asm.read_text()})
    labels = {item.name for item in analysis.asm_labels(asm)}
    assert "fn_impl" in labels
