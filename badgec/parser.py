"""Recursive-descent parser for BadgeC."""

from __future__ import annotations

import dataclasses
from typing import Optional

from . import ast_nodes as ast
from .errors import BadgeSyntaxError, location
from .lexer import Token, tokenize
from .types import Type, type_from_name


TYPE_NAMES = {"nibble", "char", "word", "dword", "flashptr", "void"}

# Binding powers.  Assignment is handled at statement level, not here.
BINARY_PRECEDENCE = {
    "||": 1,
    "&&": 2,
    "|": 3,
    "^": 4,
    "&": 5,
    "==": 6,
    "!=": 6,
    "<": 7,
    "<=": 7,
    ">": 7,
    ">=": 7,
    "<<": 8,
    ">>": 8,
    "+": 9,
    "-": 9,
    "*": 10,
    "/": 10,
    "%": 10,
}


class Parser:
    def __init__(self, tokens: list[Token], filename: str = "<input>") -> None:
        self.tokens = tokens
        self.filename = filename
        self.pos = 0

    # ------------------------------------------------------------------
    # Token helpers
    # ------------------------------------------------------------------

    def current(self) -> Token:
        return self.tokens[self.pos]

    def peek(self, offset: int = 1) -> Token:
        index = min(self.pos + offset, len(self.tokens) - 1)
        return self.tokens[index]

    def at_end(self) -> bool:
        return self.current().kind == "eof"

    def error(self, message: str, token: Optional[Token] = None) -> BadgeSyntaxError:
        token = token or self.current()
        return BadgeSyntaxError(location(self.filename, token.line, token.column) + f": {message}")

    def advance(self) -> Token:
        token = self.current()
        if not self.at_end():
            self.pos += 1
        return token

    def check(self, value: object, kind: str | None = None) -> bool:
        token = self.current()
        if kind is not None and token.kind != kind:
            return False
        return token.value == value

    def match(self, value: object, kind: str | None = None) -> bool:
        if self.check(value, kind):
            self.advance()
            return True
        return False

    def expect(self, value: object, kind: str | None = None) -> Token:
        if not self.check(value, kind):
            raise self.error(f"expected {value!r}, got {self.current().value!r}")
        return self.advance()

    def expect_ident(self) -> str:
        return str(self.expect_ident_token().value)

    def expect_ident_token(self) -> Token:
        token = self.current()
        if token.kind not in ("ident", "keyword"):
            raise self.error(f"expected identifier, got {token.value!r}")
        self.advance()
        return token

    def expect_type(self) -> Type:
        token = self.current()
        if token.kind != "keyword" or token.value not in TYPE_NAMES:
            raise self.error(f"expected a type, got {token.value!r}")
        self.advance()
        return type_from_name(str(token.value))

    def at_type(self) -> bool:
        return self.current().kind == "keyword" and self.current().value in TYPE_NAMES

    # ------------------------------------------------------------------
    # Program
    # ------------------------------------------------------------------

    def parse_program(self) -> ast.Program:
        program = ast.Program()
        while not self.at_end():
            if self.check("import", "keyword"):
                self.advance()
                path = self.current()
                if path.kind != "string":
                    raise self.error(f"expected a quoted import path, got {path.value!r}")
                self.advance()
                self.expect(";")
                program.imports.append(
                    ast.ImportDecl(str(path.value), line=path.line, column=path.column)
                )
            elif self.check("fn", "keyword"):
                program.functions.append(self.parse_function())
            elif self.check("extern", "keyword"):
                program.functions.append(self.parse_extern_function())
            elif self.check("const", "keyword"):
                program.globals.append(self.parse_const_global())
            elif self.at_type():
                # Either a global declaration or a C-style function definition.
                if self.peek().kind in ("ident", "keyword") and self.peek(2).value == "(":
                    program.functions.append(self.parse_function())
                else:
                    program.globals.append(self.parse_global())
            else:
                raise self.error(f"unexpected top-level token {self.current().value!r}")
        _annotate_program(program, self.filename)
        return program

    def parse_function(self) -> ast.FunctionDecl:
        start = self.current()
        line = start.line
        column = start.column
        if self.match("fn", "keyword"):
            if self.at_type():
                return_type = self.expect_type()
            else:
                return_type = type_from_name("void")
            name_token = self.expect_ident_token()
        else:
            return_type = self.expect_type()
            name_token = self.expect_ident_token()

        params = self.parse_params()
        body = self.parse_block()
        return ast.FunctionDecl(
            str(name_token.value),
            return_type,
            params,
            body,
            line=line,
            column=column,
            name_line=name_token.line,
            name_column=name_token.column,
        )

    def parse_extern_function(self) -> ast.FunctionDecl:
        """Parse ``extern fn [type] name(params);``.

        The implementation lives in an imported .asm file and must define a
        ``fn_name:`` entry point.
        """

        start = self.expect("extern", "keyword")
        line = start.line
        column = start.column
        if self.match("fn", "keyword"):
            if self.at_type():
                return_type = self.expect_type()
            else:
                return_type = type_from_name("void")
            name_token = self.expect_ident_token()
        else:
            return_type = self.expect_type()
            name_token = self.expect_ident_token()

        params = self.parse_params()
        self.expect(";")
        return ast.FunctionDecl(
            str(name_token.value),
            return_type,
            params,
            ast.Block(line=line, column=column),
            line=line,
            column=column,
            name_line=name_token.line,
            name_column=name_token.column,
            is_extern=True,
        )

    def parse_params(self) -> list[ast.Param]:
        self.expect("(")
        params: list[ast.Param] = []
        if not self.check(")"):
            while True:
                param_type = self.expect_type()
                param_token = self.expect_ident_token()
                params.append(
                    ast.Param(
                        str(param_token.value),
                        param_type,
                        line=param_token.line,
                        column=param_token.column,
                    )
                )
                if not self.match(","):
                    break
        self.expect(")")
        return params

    def parse_const_global(self) -> ast.GlobalDecl:
        self.expect("const", "keyword")
        type_ = self.expect_type()
        name_token = self.expect_ident_token()
        name = str(name_token.value)
        line = name_token.line
        column = name_token.column

        if not self.check("["):
            # Scalar constant, e.g. ``const nibble PIN = 1;``.
            self.expect("=")
            init = self.parse_expression()
            self.expect(";")
            return ast.GlobalDecl(
                name=name,
                type=type_,
                init=init,
                is_const=True,
                line=line,
                column=column,
            )

        self.expect("[")
        array_len: Optional[int] = None
        if not self.check("]"):
            array_len = self.parse_const_int()
        self.expect("]")
        self.expect("=")

        init_string: Optional[str] = None
        init_list: Optional[list[ast.Expr]] = None
        init: Optional[ast.Expr] = None

        if self.current().kind == "string":
            init_string = str(self.advance().value)
            if type_.name != "char":
                raise self.error("string literals can only initialize const char arrays")
        elif self.match("{"):
            init_list = []
            if not self.check("}"):
                while True:
                    init_list.append(self.parse_expression())
                    if not self.match(","):
                        break
            self.expect("}")
        else:
            init = self.parse_expression()
        self.expect(";")

        if array_len is None:
            if init_string is not None:
                array_len = len(init_string) + 1
            elif init_list is not None:
                array_len = len(init_list)
            else:
                raise self.error("const array requires an explicit length or initializer")

        return ast.GlobalDecl(
            name=name,
            type=type_,
            array_len=array_len,
            init=init,
            init_list=init_list,
            init_string=init_string,
            is_const=True,
            line=line,
            column=column,
        )

    def parse_global(self) -> ast.GlobalDecl:
        type_ = self.expect_type()
        name_token = self.expect_ident_token()
        name = str(name_token.value)
        array_len: Optional[int] = None
        if self.match("["):
            if not self.check("]"):
                array_len = self.parse_const_int()
            self.expect("]")
        init: Optional[ast.Expr] = None
        if self.match("="):
            init = self.parse_expression()
        self.expect(";")
        return ast.GlobalDecl(
            name,
            type_,
            array_len,
            init=init,
            line=name_token.line,
            column=name_token.column,
        )

    def parse_const_int(self) -> int:
        token = self.current()
        if token.kind != "number":
            raise self.error("expected an integer literal")
        self.advance()
        return int(token.value)

    # ------------------------------------------------------------------
    # Statements
    # ------------------------------------------------------------------

    def parse_block(self) -> ast.Block:
        start = self.current()
        line = start.line
        column = start.column
        self.expect("{")
        statements: list[ast.Stmt] = []
        while not self.check("}"):
            if self.at_end():
                raise self.error("unterminated block")
            statements.append(self.parse_statement())
        self.expect("}")
        return ast.Block(statements, line=line, column=column)

    def parse_statement(self) -> ast.Stmt:
        token = self.current()

        if self.check("{"):
            return self.parse_block()

        if self.check("if", "keyword"):
            return self.parse_if()

        if self.check("while", "keyword"):
            return self.parse_while()

        if self.check("for", "keyword"):
            return self.parse_for()

        if self.check("return", "keyword"):
            token = self.advance()
            value = None
            if not self.check(";"):
                value = self.parse_expression()
            self.expect(";")
            return ast.Return(value, line=token.line, column=token.column)

        if self.check("break", "keyword"):
            token = self.advance()
            self.expect(";")
            return ast.Break(line=token.line, column=token.column)

        if self.check("continue", "keyword"):
            token = self.advance()
            self.expect(";")
            return ast.Continue(line=token.line, column=token.column)

        if self.check("const", "keyword"):
            return self.parse_local_const()

        if self.at_type():
            return self.parse_local_decl()

        # Assignment or expression statement.
        line = token.line
        column = token.column
        expr = self.parse_expression()
        if self.match("="):
            if not isinstance(expr, (ast.Var, ast.Index)):
                raise self.error("left side of assignment must be a variable or array element")
            value = self.parse_expression()
            self.expect(";")
            return ast.Assign(expr, value, line=line, column=column)
        self.expect(";")
        return ast.ExprStmt(expr, line=line, column=column)

    def parse_local_decl(self) -> ast.VarDecl:
        type_ = self.expect_type()
        name_token = self.expect_ident_token()
        name = str(name_token.value)
        array_len: Optional[int] = None
        if self.match("["):
            if not self.check("]"):
                array_len = self.parse_const_int()
            self.expect("]")
        init: Optional[ast.Expr] = None
        if self.match("="):
            init = self.parse_expression()
        self.expect(";")
        return ast.VarDecl(
            name,
            type_,
            array_len,
            init,
            line=name_token.line,
            column=name_token.column,
        )

    def parse_local_const(self) -> ast.VarDecl:
        self.expect("const", "keyword")
        type_ = self.expect_type()
        name_token = self.expect_ident_token()
        name = str(name_token.value)
        array_len: Optional[int] = None
        if self.match("["):
            if not self.check("]"):
                array_len = self.parse_const_int()
            self.expect("]")
        init: Optional[ast.Expr] = None
        if self.match("="):
            init = self.parse_expression()
        self.expect(";")
        return ast.VarDecl(
            name,
            type_,
            array_len,
            init,
            is_const=True,
            line=name_token.line,
            column=name_token.column,
        )

    def parse_if(self) -> ast.If:
        token = self.expect("if", "keyword")
        self.expect("(")
        condition = self.parse_expression()
        self.expect(")")
        then_block = self.parse_statement_as_block()
        else_block = None
        if self.match("else", "keyword"):
            else_block = self.parse_statement_as_block()
        return ast.If(
            condition,
            then_block,
            else_block,
            line=token.line,
            column=token.column,
        )

    def parse_while(self) -> ast.While:
        token = self.expect("while", "keyword")
        self.expect("(")
        condition = self.parse_expression()
        self.expect(")")
        body = self.parse_statement_as_block()
        return ast.While(
            condition, body, line=token.line, column=token.column
        )

    def parse_for(self) -> ast.For:
        token = self.expect("for", "keyword")
        line = token.line
        column = token.column
        self.expect("(")
        init: Optional[ast.Stmt] = None
        if not self.check(";"):
            if self.at_type():
                init = self.parse_local_decl()
            else:
                init_expr = self.parse_expression()
                if self.match("="):
                    if not isinstance(init_expr, (ast.Var, ast.Index)):
                        raise self.error("left side of for-init must be a variable or array element")
                    init = ast.Assign(
                        init_expr,
                        self.parse_expression(),
                        line=init_expr.line,
                        column=init_expr.column,
                    )
                else:
                    init = ast.ExprStmt(
                        init_expr, line=init_expr.line, column=init_expr.column
                    )
                self.expect(";")
        else:
            self.expect(";")

        condition = None
        if not self.check(";"):
            condition = self.parse_expression()
        self.expect(";")

        update: Optional[ast.Stmt] = None
        if not self.check(")"):
            update_expr = self.parse_expression()
            if self.match("="):
                if not isinstance(update_expr, (ast.Var, ast.Index)):
                    raise self.error("left side of for-update must be a variable or array element")
                update = ast.Assign(
                    update_expr,
                    self.parse_expression(),
                    line=update_expr.line,
                    column=update_expr.column,
                )
            else:
                update = ast.ExprStmt(
                    update_expr, line=update_expr.line, column=update_expr.column
                )
        self.expect(")")
        body = self.parse_statement_as_block()
        return ast.For(init, condition, update, body, line=line, column=column)

    def parse_statement_as_block(self) -> ast.Block:
        if self.check("{"):
            return self.parse_block()
        stmt = self.parse_statement()
        return ast.Block([stmt], line=stmt.line, column=stmt.column)

    # ------------------------------------------------------------------
    # Expressions
    # ------------------------------------------------------------------

    def parse_expression(self, min_precedence: int = 1) -> ast.Expr:
        left = self.parse_unary()
        while True:
            token = self.current()
            if token.kind != "op" or token.value not in BINARY_PRECEDENCE:
                break
            precedence = BINARY_PRECEDENCE[str(token.value)]
            if precedence < min_precedence:
                break
            op = str(self.advance().value)
            right = self.parse_expression(precedence + 1)
            left = ast.Binary(
                op, left, right, line=token.line, column=token.column
            )
        return left

    def parse_unary(self) -> ast.Expr:
        token = self.current()
        if token.kind == "op" and token.value in ("-", "~", "!", "&"):
            self.advance()
            operand = self.parse_unary()
            if token.value == "&":
                return ast.AddressOf(
                    operand, line=token.line, column=token.column
                )
            return ast.Unary(
                str(token.value), operand, line=token.line, column=token.column
            )

        # (type) expr cast.  A type keyword after '(' cannot start any other
        # expression, so it is unambiguous.
        if (
            token.kind == "punct"
            and token.value == "("
            and self.peek(1).kind == "keyword"
            and self.peek(1).value in TYPE_NAMES
        ):
            self.advance()
            target = self.expect_type()
            self.expect(")")
            return ast.Cast(
                target, self.parse_unary(), line=token.line, column=token.column
            )

        return self.parse_postfix()

    def parse_postfix(self) -> ast.Expr:
        expr = self.parse_primary()
        while True:
            if self.check("["):
                bracket = self.advance()
                index = self.parse_expression()
                self.expect("]")
                expr = ast.Index(
                    expr,
                    index,
                    line=bracket.line,
                    column=bracket.column,
                )
            elif self.check("("):
                self.advance()
                if not isinstance(expr, ast.Var):
                    raise self.error("only named functions can be called")
                args: list[ast.Expr] = []
                if not self.check(")"):
                    while True:
                        args.append(self.parse_expression())
                        if not self.match(","):
                            break
                self.expect(")")
                expr = ast.Call(
                    expr.name,
                    args,
                    line=expr.line,
                    column=expr.column,
                )
            else:
                break
        return expr

    def parse_primary(self) -> ast.Expr:
        token = self.current()

        if token.kind == "number":
            self.advance()
            return ast.Number(
                int(token.value), line=token.line, column=token.column
            )

        if token.kind == "string":
            self.advance()
            return ast.StringLiteral(
                str(token.value), line=token.line, column=token.column
            )

        if token.kind in ("ident", "keyword"):
            self.advance()
            return ast.Var(
                str(token.value), line=token.line, column=token.column
            )

        if self.match("("):
            expr = self.parse_expression()
            self.expect(")")
            return expr

        raise self.error(f"unexpected token {token.value!r} in expression")


_AST_NODE_TYPES = (
    ast.Expr,
    ast.Stmt,
    ast.GlobalDecl,
    ast.Param,
    ast.FunctionDecl,
    ast.ImportDecl,
)


def _annotate_file(node, filename: str) -> None:
    if isinstance(node, _AST_NODE_TYPES):
        node.file = filename
    for field in dataclasses.fields(node):
        value = getattr(node, field.name)
        if isinstance(value, _AST_NODE_TYPES):
            _annotate_file(value, filename)
        elif isinstance(value, list):
            for item in value:
                if isinstance(item, _AST_NODE_TYPES):
                    _annotate_file(item, filename)


def _annotate_program(program: ast.Program, filename: str) -> None:
    for node in program.globals:
        _annotate_file(node, filename)
    for node in program.functions:
        _annotate_file(node, filename)
    for node in program.imports:
        _annotate_file(node, filename)


def parse(source: str, filename: str = "<input>") -> ast.Program:
    tokens = tokenize(source, filename)
    return Parser(tokens, filename).parse_program()
