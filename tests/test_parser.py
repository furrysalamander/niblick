"""Parser and lexer tests."""

from __future__ import annotations

import pytest

from niblick import ast_nodes as ast
from niblick.errors import NiblickSyntaxError
from niblick.lexer import tokenize
from niblick.parser import parse


def test_lexer_handles_comments_strings_and_literals() -> None:
    tokens = tokenize(
        """
        // line comment
        const char msg[] = "Hi\\n";
        nibble x = 0x0A;
        nibble y = 0b0011;
        nibble z = 'A';
        """
    )
    values = [token.value for token in tokens]
    assert "Hi\n" in values
    assert 10 in values
    assert 3 in values
    assert 65 in values


def test_const_array_allows_trailing_comma() -> None:
    program = parse(
        "const char values[] = { 1, 2, 3, };\nfn main() { }\n",
        "test.nbl",
    )
    assert len(program.globals[0].init_list or []) == 3


def test_parser_handles_for_update_assignment() -> None:
    program = parse(
        """
        fn main() {
            nibble i;
            for (i = 0; i < 10; i = i + 1) {
            }
        }
        """,
        "test.nbl",
    )
    body = program.functions[0].body.statements
    loop = body[1]
    assert isinstance(loop, ast.For)
    assert isinstance(loop.init, ast.Assign)
    assert isinstance(loop.update, ast.Assign)


def test_parser_reports_unknown_syntax() -> None:
    with pytest.raises(NiblickSyntaxError):
        parse("fn main() { nibble x = ; }", "bad.nbl")


def test_parser_rejects_c_style_function_definition() -> None:
    with pytest.raises(NiblickSyntaxError, match="C-style function definitions"):
        parse("nibble add(nibble a, nibble b) { return a + b; }", "test.nbl")


def test_parser_accepts_extern_function_declarations() -> None:
    program = parse(
        """
        extern fn char convert(char value);
        extern fn uint16_t read16(nibble addr);
        fn main() { }
        """,
        "test.nbl",
    )
    convert, read16, main = program.functions
    assert convert.name == "convert"
    assert convert.is_extern
    assert convert.body.statements == []
    assert convert.params[0].name == "value"
    assert convert.return_type.name == "char"
    assert read16.is_extern
    assert read16.return_type.name == "uint16_t"
    assert not main.is_extern


def test_parser_accepts_inline_asm_block() -> None:
    program = parse(
        """
        fn main() {
            nibble x;
            asm {
                ; raw text with a placeholder
                MOV R0, [${x}]
                MOV R1, R0
            }
        }
        """,
        "test.nbl",
    )
    statements = program.functions[0].body.statements
    inline = statements[1]
    assert isinstance(inline, ast.InlineAsm)
    assert "MOV R0, [${x}]" in inline.text
    assert inline.file == "test.nbl"


def test_parser_rejects_unterminated_inline_asm_block() -> None:
    with pytest.raises(NiblickSyntaxError, match="unterminated asm block"):
        parse("fn main() { asm { MOV R1, 1", "bad.nbl")
