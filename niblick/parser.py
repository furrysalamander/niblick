"""Recursive-descent parser for Niblick."""

from __future__ import annotations

import dataclasses
from typing import Optional

from . import ast_nodes as ast
from .errors import NiblickSyntaxError, location
from .lexer import Token, tokenize
from .types import SCALAR_TYPES, U8, StructField, StructType, Type, type_from_name


TYPE_NAMES = set(SCALAR_TYPES)

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

UNSUPPORTED_KEYWORDS = {
    "switch",
    "do",
    "enum",
    "typedef",
    "sizeof",
    "static",
    "volatile",
    "goto",
}

COMPOUND_OPS = {
    "+=": "+",
    "-=": "-",
    "*=": "*",
    "/=": "/",
    "%=": "%",
    "&=": "&",
    "|=": "|",
    "^=": "^",
    "<<=": "<<",
    ">>=": ">>",
}


class Parser:
    def __init__(
        self,
        tokens: list[Token],
        filename: str = "<input>",
        struct_types: dict[str, StructType] | None = None,
    ) -> None:
        self.tokens = tokens
        self.filename = filename
        self.pos = 0
        self.struct_types: dict[str, StructType] = (
            struct_types if struct_types is not None else {}
        )

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

    def error(self, message: str, token: Optional[Token] = None) -> NiblickSyntaxError:
        token = token or self.current()
        return NiblickSyntaxError(location(self.filename, token.line, token.column) + f": {message}")

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
        if token.kind != "ident":
            raise self.error(f"expected identifier, got {token.value!r}")
        self.advance()
        return token

    def expect_type(self) -> Type:
        token = self.current()
        if token.kind == "keyword" and token.value in TYPE_NAMES:
            self.advance()
            return type_from_name(str(token.value))
        if token.kind == "ident" and token.value in self.struct_types:
            self.advance()
            return self.struct_types[str(token.value)]
        raise self.error(f"expected a type, got {token.value!r}")

    def at_type(self) -> bool:
        token = self.current()
        return (
            token.kind == "keyword" and token.value in TYPE_NAMES
        ) or (token.kind == "ident" and token.value in self.struct_types)

    # ------------------------------------------------------------------
    # Program
    # ------------------------------------------------------------------

    def parse_program(self) -> ast.Program:
        program = ast.Program()
        while not self.at_end():
            if (
                self.current().kind == "keyword"
                and self.current().value in UNSUPPORTED_KEYWORDS
            ):
                raise self.error(f"{self.current().value} is not supported")
            if self.check("struct", "keyword"):
                self.parse_struct()
            elif self.check("import", "keyword"):
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
                if self.peek().kind == "ident" and self.peek(2).value == "(":
                    raise self.error(
                        "C-style function definitions are not supported; "
                        "use 'fn [type] name(...)'"
                    )
                program.globals.append(self.parse_global())
            else:
                raise self.error(f"unexpected top-level token {self.current().value!r}")
        _annotate_program(program, self.filename)
        return program

    def parse_struct(self) -> None:
        self.expect("struct", "keyword")
        name_token = self.expect_ident_token()
        if name_token.kind != "ident":
            raise self.error("struct name must be an identifier", name_token)
        name = str(name_token.value)
        if name in self.struct_types:
            raise self.error(f"duplicate struct {name!r}", name_token)
        if name in SCALAR_TYPES or name in TYPE_NAMES:
            raise self.error(f"struct name {name!r} conflicts with a builtin type", name_token)
        self.expect("{")
        fields: list[StructField] = []
        offset = 0
        while not self.check("}"):
            field_type = self.expect_type()
            if field_type.name == "void":
                raise self.error("struct fields cannot have type void")
            field_token = self.expect_ident_token()
            array_len = 0
            if self.check("["):
                self.expect("[")
                length = self.current()
                if length.kind != "number":
                    raise self.error("struct field array length must be an integer literal")
                array_len = int(length.value)
                self.advance()
                self.expect("]")
                if array_len <= 0:
                    raise self.error("struct field array length must be positive")
                if isinstance(field_type, StructType):
                    raise self.error("struct fields cannot be arrays of structs")
            if any(item.name == field_token.value for item in fields):
                raise self.error(
                    f"duplicate field {field_token.value!r} in struct {name!r}",
                    field_token,
                )
            self.expect(";")
            fields.append(
                StructField(
                    name=str(field_token.value),
                    type=field_type,
                    offset=offset,
                    array_len=array_len,
                )
            )
            offset += field_type.ram_size * (array_len or 1)
        self.expect("}")
        self.expect(";")
        if not fields:
            raise self.error(f"struct {name!r} must have at least one field", name_token)
        self.struct_types[name] = StructType(
            name=name,
            ram_size=offset,
            flash_size=1,
            is_scalar=False,
            fields=tuple(fields),
        )

    def parse_function(self) -> ast.FunctionDecl:
        start = self.expect("fn", "keyword")
        line = start.line
        column = start.column
        if self.at_type():
            return_type = self.expect_type()
        else:
            return_type = type_from_name("void")
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
        self.expect("fn", "keyword")
        if self.at_type():
            return_type = self.expect_type()
        else:
            return_type = type_from_name("void")
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
                if self.check(")"):
                    break
        self.expect(")")
        return params

    def parse_array_suffix(self) -> tuple[Optional[int], Optional[ast.Expr]]:
        if not self.match("["):
            return None, None
        if self.check("]"):
            self.expect("]")
            return None, None
        expr = self.parse_expression()
        self.expect("]")
        if isinstance(expr, ast.Number):
            return int(expr.value), None
        return None, expr

    def parse_string_value(self) -> str:
        if self.current().kind != "string":
            raise self.error(f"expected a string literal, got {self.current().value!r}")
        parts = [str(self.advance().value)]
        while self.current().kind == "string":
            parts.append(str(self.advance().value))
        return "".join(parts)

    def parse_init_list(self) -> list[ast.Expr]:
        self.expect("{")
        values: list[ast.Expr] = []
        if not self.check("}"):
            while True:
                if self.check("{"):
                    values.append(
                        ast.InitList(
                            self.parse_init_list(),
                            line=self.current().line,
                            column=self.current().column,
                        )
                    )
                else:
                    values.append(self.parse_expression())
                if not self.match(","):
                    break
                if self.check("}"):
                    break
        self.expect("}")
        return values

    def parse_initializer(
        self, type_: Type
    ) -> tuple[Optional[ast.Expr], Optional[list[ast.Expr]], Optional[str]]:
        if self.check("{"):
            init_list = self.parse_init_list()
            return None, init_list, None
        if self.current().kind == "string":
            value = self.parse_string_value()
            if type_ is not U8:
                raise self.error("string literals can only initialize char arrays")
            return None, None, value
        return self.parse_expression(), None, None

    def parse_const_global(self) -> ast.GlobalDecl:
        self.expect("const", "keyword")
        type_ = self.expect_type()
        name_token = self.expect_ident_token()
        name = str(name_token.value)
        line = name_token.line
        column = name_token.column

        if not self.check("[") and not isinstance(type_, StructType):
            # Scalar constant, e.g. ``const nibble PIN = 1;``.
            self.expect("=")
            scalar_init = self.parse_expression()
            self.expect(";")
            return ast.GlobalDecl(
                name=name,
                type=type_,
                init=scalar_init,
                is_const=True,
                line=line,
                column=column,
            )

        if not self.check("["):
            self.expect("=")
            init, init_list, init_string = self.parse_initializer(type_)
            self.expect(";")
            return ast.GlobalDecl(
                name=name,
                type=type_,
                init=init,
                init_list=init_list,
                init_string=init_string,
                is_const=True,
                line=line,
                column=column,
            )

        array_len, array_len_expr = self.parse_array_suffix()
        self.expect("=")
        init, init_list, init_string = self.parse_initializer(type_)
        self.expect(";")

        if array_len is None and array_len_expr is None:
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
            array_len_expr=array_len_expr,
            init=init,
            init_list=init_list,
            init_string=init_string,
            is_const=True,
            is_array=True,
            line=line,
            column=column,
        )

    def parse_global(self) -> ast.GlobalDecl:
        type_ = self.expect_type()
        name_token = self.expect_ident_token()
        name = str(name_token.value)
        has_array = self.check("[")
        array_len, array_len_expr = self.parse_array_suffix()
        init: Optional[ast.Expr] = None
        init_list: Optional[list[ast.Expr]] = None
        init_string: Optional[str] = None
        if self.match("="):
            init, init_list, init_string = self.parse_initializer(type_)
        self.expect(";")
        if has_array and array_len is None and array_len_expr is None:
            if init_list is not None:
                array_len = len(init_list)
            elif init_string is not None:
                array_len = len(init_string) + 1
            else:
                raise self.error("array requires a length or initializer")
        return ast.GlobalDecl(
            name,
            type_,
            array_len,
            array_len_expr=array_len_expr,
            init=init,
            init_list=init_list,
            init_string=init_string,
            is_array=has_array,
            line=name_token.line,
            column=name_token.column,
        )

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

        if token.kind == "keyword" and token.value in UNSUPPORTED_KEYWORDS:
            raise self.error(f"{token.value} is not supported")

        if token.kind == "asm_block":
            self.advance()
            return ast.InlineAsm(
                str(token.value), line=token.line, column=token.column
            )

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
        expr = self.parse_expression()
        stmt = self.parse_assignment_tail(expr, "assignment")
        self.expect(";")
        return stmt

    def parse_assignment_tail(self, expr: ast.Expr, context: str) -> ast.Stmt:
        line = expr.line
        column = expr.column
        if self.match("="):
            if not isinstance(expr, (ast.Var, ast.Index, ast.Member)):
                raise self.error(
                    f"left side of {context} must be a variable or array element"
                )
            value = self.parse_expression()
            return ast.Assign(expr, value, line=line, column=column)
        token = self.current()
        if token.kind == "op" and token.value in COMPOUND_OPS:
            if not isinstance(expr, (ast.Var, ast.Index, ast.Member)):
                raise self.error(
                    f"left side of {context} must be a variable or array element"
                )
            self.advance()
            value = self.parse_expression()
            return ast.CompoundAssign(
                expr,
                COMPOUND_OPS[str(token.value)],
                value,
                line=line,
                column=column,
            )
        return ast.ExprStmt(expr, line=line, column=column)

    def parse_local_decl(self) -> ast.VarDecl:
        type_ = self.expect_type()
        name_token = self.expect_ident_token()
        name = str(name_token.value)
        has_array = self.check("[")
        array_len, array_len_expr = self.parse_array_suffix()
        init: Optional[ast.Expr] = None
        init_list: Optional[list[ast.Expr]] = None
        init_string: Optional[str] = None
        if self.match("="):
            init, init_list, init_string = self.parse_initializer(type_)
        self.expect(";")
        if has_array and array_len is None and array_len_expr is None:
            if init_list is not None:
                array_len = len(init_list)
            elif init_string is not None:
                array_len = len(init_string) + 1
            else:
                raise self.error("array requires a length or initializer")
        return ast.VarDecl(
            name,
            type_,
            array_len,
            array_len_expr=array_len_expr,
            init=init,
            init_list=init_list,
            init_string=init_string,
            is_array=has_array,
            line=name_token.line,
            column=name_token.column,
        )

    def parse_local_const(self) -> ast.VarDecl:
        self.expect("const", "keyword")
        type_ = self.expect_type()
        name_token = self.expect_ident_token()
        name = str(name_token.value)
        has_array = self.check("[")
        array_len, array_len_expr = self.parse_array_suffix()
        init: Optional[ast.Expr] = None
        init_list: Optional[list[ast.Expr]] = None
        init_string: Optional[str] = None
        if self.match("="):
            init, init_list, init_string = self.parse_initializer(type_)
        self.expect(";")
        if has_array and array_len is None and array_len_expr is None:
            if init_list is not None:
                array_len = len(init_list)
            elif init_string is not None:
                array_len = len(init_string) + 1
            else:
                raise self.error("array requires a length or initializer")
        return ast.VarDecl(
            name,
            type_,
            array_len,
            array_len_expr=array_len_expr,
            init=init,
            init_list=init_list,
            init_string=init_string,
            is_const=True,
            is_array=has_array,
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
                init = self.parse_assignment_tail(init_expr, "for-init")
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
            update = self.parse_assignment_tail(update_expr, "for-update")
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

    def parse_expression(self) -> ast.Expr:
        return self.parse_conditional()

    def parse_conditional(self) -> ast.Expr:
        condition = self.parse_binary(1)
        if self.check("?"):
            token = self.advance()
            then_expr = self.parse_expression()
            self.expect(":")
            else_expr = self.parse_conditional()
            return ast.Conditional(
                condition,
                then_expr,
                else_expr,
                line=token.line,
                column=token.column,
            )
        return condition

    def parse_binary(self, min_precedence: int = 1) -> ast.Expr:
        left = self.parse_unary()
        while True:
            token = self.current()
            if token.kind != "op" or token.value not in BINARY_PRECEDENCE:
                break
            precedence = BINARY_PRECEDENCE[str(token.value)]
            if precedence < min_precedence:
                break
            op = str(self.advance().value)
            right = self.parse_binary(precedence + 1)
            left = ast.Binary(
                op, left, right, line=token.line, column=token.column
            )
        return left

    def parse_unary(self) -> ast.Expr:
        token = self.current()
        if token.kind == "op" and token.value in ("++", "--"):
            self.advance()
            operand = self.parse_unary()
            return ast.IncDec(
                operand,
                str(token.value),
                prefix=True,
                line=token.line,
                column=token.column,
            )
        if token.kind == "op" and token.value in ("-", "+", "~", "!", "&"):
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
            elif self.check("."):
                dot = self.advance()
                field_token = self.expect_ident_token()
                expr = ast.Member(
                    expr,
                    str(field_token.value),
                    line=dot.line,
                    column=dot.column,
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
                        if self.check(")"):
                            break
                self.expect(")")
                expr = ast.Call(
                    expr.name,
                    args,
                    line=expr.line,
                    column=expr.column,
                )
            elif self.check("++") or self.check("--"):
                op = self.advance()
                expr = ast.IncDec(
                    expr,
                    str(op.value),
                    prefix=False,
                    line=op.line,
                    column=op.column,
                )
            else:
                break
        return expr

    def parse_primary(self) -> ast.Expr:
        token = self.current()

        if token.kind == "keyword" and token.value in UNSUPPORTED_KEYWORDS:
            raise self.error(f"{token.value} is not supported")

        if token.kind == "number":
            self.advance()
            return ast.Number(
                int(token.value), line=token.line, column=token.column
            )

        if token.kind == "float":
            self.advance()
            return ast.FloatLiteral(
                float(token.value), line=token.line, column=token.column
            )

        if token.kind == "string":
            return ast.StringLiteral(
                self.parse_string_value(), line=token.line, column=token.column
            )

        if token.kind == "keyword" and token.value in ("true", "false"):
            self.advance()
            return ast.Number(
                1 if token.value == "true" else 0,
                line=token.line,
                column=token.column,
            )

        if token.kind == "ident":
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


def parse(
    source: str,
    filename: str = "<input>",
    struct_types: dict[str, StructType] | None = None,
) -> ast.Program:
    tokens = tokenize(source, filename)
    return Parser(tokens, filename, struct_types).parse_program()
