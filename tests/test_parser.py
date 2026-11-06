"""Parser and lexer tests."""

from __future__ import annotations

import pytest

from badgec import ast_nodes as ast
from badgec.errors import BadgeSyntaxError
from badgec.lexer import tokenize
from badgec.parser import parse


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


def test_parser_handles_for_update_assignment() -> None:
    program = parse(
        """
        fn main() {
            nibble i;
            for (i = 0; i < 10; i = i + 1) {
            }
        }
        """,
        "test.badge",
    )
    body = program.functions[0].body.statements
    loop = body[1]
    assert isinstance(loop, ast.For)
    assert isinstance(loop.init, ast.Assign)
    assert isinstance(loop.update, ast.Assign)


def test_parser_reports_unknown_syntax() -> None:
    with pytest.raises(BadgeSyntaxError):
        parse("fn main() { nibble x = ; }", "bad.badge")


def test_parser_accepts_c_style_function_definition() -> None:
    program = parse("nibble add(nibble a, nibble b) { return a + b; }", "test.badge")
    assert program.functions[0].name == "add"
    assert program.functions[0].return_type.name == "nibble"
