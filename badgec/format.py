"""Compile-time expansion for ``print("...", ...)``.

The formatter is deliberately a compile-time construct.  The format string
must be a literal, every placeholder is checked against the argument type, and
the call is replaced with ordinary calls to the UART formatting helpers.  This
keeps the language free of a varargs ABI and lets the dead-declaration pass
remove formatters that are not used.
"""

from __future__ import annotations

import dataclasses
from dataclasses import dataclass
from typing import Optional

from . import ast_nodes as ast
from .errors import BadgeCompileError, BadgeTypeError, location
from .types import (
    CHAR,
    DWORD,
    FLASHPTR,
    NIBBLE,
    WORD,
    Type,
    promoted_mul_type,
    wider,
)


@dataclass(frozen=True)
class TextPart:
    text: str


@dataclass(frozen=True)
class PlaceholderPart:
    spec: str
    column: int


FormatPart = TextPart | PlaceholderPart


def parse_format(text: str, filename: str, line: int, column: int = 1) -> list[FormatPart]:
    """Split a literal format string into text and placeholder parts."""

    parts: list[FormatPart] = []
    literal: list[str] = []
    index = 0

    def flush() -> None:
        if literal:
            parts.append(TextPart("".join(literal)))
            literal.clear()

    while index < len(text):
        char = text[index]
        if char == "{":
            if index + 1 < len(text) and text[index + 1] == "{":
                literal.append("{")
                index += 2
                continue
            flush()
            closing = text.find("}", index + 1)
            if closing < 0:
                raise BadgeCompileError(
                    f"{location(filename, line, column + index)}: unclosed '{{' in format string"
                )
            spec = text[index + 1 : closing]
            if spec.startswith(":"):
                spec = spec[1:]
            elif spec:
                spec = f":{spec}"
            if spec not in ("", "d", "x", "b", "c", "s"):
                raise BadgeCompileError(
                    f"{location(filename, line, column + index)}: unsupported print "
                    f"format specifier {spec!r}"
                )
            parts.append(PlaceholderPart(spec, column + index))
            index = closing + 1
        elif char == "}":
            if index + 1 < len(text) and text[index + 1] == "}":
                literal.append("}")
                index += 2
                continue
            raise BadgeCompileError(
                f"{location(filename, line, column + index)}: unmatched '}}' in format string"
            )
        else:
            literal.append(char)
            index += 1

    flush()
    return parts


def _builtin_types() -> dict:
    # Imported lazily to avoid a module cycle: compiler imports this module.
    from .compiler import BUILTINS

    return BUILTINS


class PrintExpander:
    def __init__(self, program: ast.Program, filename: str) -> None:
        self.program = program
        self.filename = filename
        self.globals = {decl.name: decl for decl in program.globals}
        self.functions = {decl.name: decl for decl in program.functions}
        self.scopes: list[dict[str, object]] = []
        self.used_helpers: dict[str, tuple[str, int]] = {}

    # ------------------------------------------------------------------
    # Entry point
    # ------------------------------------------------------------------

    def expand(self) -> None:
        for function in self.program.functions:
            if function.is_extern:
                continue
            self.scopes = [
                {param.name: param for param in function.params}
            ]
            self.expand_block(function.body)

        for decl in self.program.globals:
            if decl.init is not None:
                self.reject_dynamic_print(decl.init)
            if decl.init_list is not None:
                for expr in decl.init_list:
                    self.reject_dynamic_print(expr)

        available = set(self.functions) | set(_builtin_types())
        for helper, (helper_file, line) in sorted(
            self.used_helpers.items(), key=lambda item: item[1][1]
        ):
            if helper not in available:
                raise BadgeCompileError(
                    f"{location(helper_file, line)}: print() needs {helper!r}; "
                    'add import "lib/uart.badge"'
                )

    # ------------------------------------------------------------------
    # Statements
    # ------------------------------------------------------------------

    def expand_block(self, block: ast.Block) -> None:
        self.scopes.append({})
        try:
            statements: list[ast.Stmt] = []
            for stmt in block.statements:
                statements.extend(self.expand_stmt(stmt))
            block.statements = statements
        finally:
            self.scopes.pop()

    def expand_stmt(self, stmt: ast.Stmt) -> list[ast.Stmt]:
        if isinstance(stmt, ast.Block):
            self.expand_block(stmt)
            return [stmt]

        if isinstance(stmt, ast.VarDecl):
            if stmt.init is not None:
                self.reject_dynamic_print(stmt.init)
            init_list = getattr(stmt, "init_list", None)
            if init_list is not None:
                for expr in init_list:
                    self.reject_dynamic_print(expr)
            self.scopes[-1][stmt.name] = stmt
            return [stmt]

        if isinstance(stmt, ast.Assign):
            self.reject_dynamic_print(stmt.target)
            self.reject_dynamic_print(stmt.value)
            return [stmt]

        if isinstance(stmt, ast.ExprStmt):
            call = stmt.expr
            if isinstance(call, ast.Call) and call.name == "print":
                return self.expand_print(call)
            self.reject_dynamic_print(call)
            return [stmt]

        if isinstance(stmt, ast.If):
            self.reject_dynamic_print(stmt.condition)
            self.expand_block(stmt.then_block)
            if stmt.else_block is not None:
                self.expand_block(stmt.else_block)
            return [stmt]

        if isinstance(stmt, ast.While):
            self.reject_dynamic_print(stmt.condition)
            self.expand_block(stmt.body)
            return [stmt]

        if isinstance(stmt, ast.For):
            self.scopes.append({})
            try:
                if stmt.init is not None:
                    if isinstance(stmt.init, ast.VarDecl):
                        if stmt.init.init is not None:
                            self.reject_dynamic_print(stmt.init.init)
                        self.scopes[-1][stmt.init.name] = stmt.init
                    else:
                        self.reject_dynamic_print(stmt.init)
                if stmt.condition is not None:
                    self.reject_dynamic_print(stmt.condition)
                if stmt.update is not None:
                    self.reject_dynamic_print(stmt.update)
                self.expand_block(stmt.body)
            finally:
                self.scopes.pop()
            return [stmt]

        if isinstance(stmt, ast.Return):
            if stmt.value is not None:
                self.reject_dynamic_print(stmt.value)
            return [stmt]

        if isinstance(stmt, ast.InlineAsm):
            return [stmt]

        return [stmt]

    # ------------------------------------------------------------------
    # print expansion
    # ------------------------------------------------------------------

    def expand_print(self, call: ast.Call) -> list[ast.Stmt]:
        if not call.args:
            raise BadgeCompileError(
                f"{location(self.filename, call.line)}: print() requires a format string"
            )
        fmt = call.args[0]
        if not isinstance(fmt, ast.StringLiteral):
            raise BadgeCompileError(
                f"{location(self.filename, fmt.line)}: print() format string must be a literal"
            )
        source = fmt.file or call.file or self.filename
        parts = parse_format(fmt.value, source, fmt.line, fmt.column or 1)
        values = call.args[1:]
        placeholders = sum(isinstance(part, PlaceholderPart) for part in parts)
        if placeholders != len(values):
            raise BadgeTypeError(
                f"{location(self.filename, call.line)}: print() format has "
                f"{placeholders} placeholder(s) but {len(values)} value(s) were supplied"
            )

        statements: list[ast.Stmt] = []
        value_index = 0
        for part in parts:
            if isinstance(part, TextPart):
                statements.append(
                    ast.ExprStmt(
                        expr=ast.Call(
                            name="uart_puts",
                            args=[
                                ast.StringLiteral(
                                    value=part.text,
                                    line=fmt.line,
                                    column=fmt.column,
                                    file=fmt.file,
                                )
                            ],
                            line=call.line,
                            column=call.column,
                            file=call.file,
                        ),
                        line=call.line,
                        column=call.column,
                        file=call.file,
                    )
                )
                self.used_helpers.setdefault(
                    "uart_puts", (call.file or self.filename, call.line)
                )
                continue

            arg = values[value_index]
            value_index += 1
            arg_type = self.infer_type(arg)
            helper, cast_type = self.choose_helper(
                part.spec, arg_type, call.file or self.filename, call.line
            )
            if cast_type is not None:
                arg = ast.Cast(
                    type=cast_type,
                    operand=arg,
                    line=arg.line,
                    column=arg.column,
                    file=arg.file,
                )
            self.used_helpers.setdefault(helper, (call.file or self.filename, call.line))
            statements.append(
                ast.ExprStmt(
                    expr=ast.Call(
                        name=helper,
                        args=[arg],
                        line=call.line,
                        column=call.column,
                        file=call.file,
                    ),
                    line=call.line,
                    column=call.column,
                    file=call.file,
                )
            )
        return statements

    def choose_helper(
        self, spec: str, arg_type: Type, filename: str, line: int
    ) -> tuple[str, Optional[Type]]:
        if spec in ("", "d"):
            table = {
                NIBBLE: ("uart_print_dec8", CHAR),
                CHAR: ("uart_print_dec8", None),
                WORD: ("uart_print_dec16", None),
                DWORD: ("uart_print_dec32", None),
            }
            if arg_type is FLASHPTR:
                return "uart_puts", None
        elif spec == "x":
            table = {
                NIBBLE: ("uart_print_nibble", None),
                CHAR: ("uart_print_hex8", None),
                WORD: ("uart_print_hex16", None),
                DWORD: ("uart_print_hex32", None),
            }
        elif spec == "b":
            table = {
                NIBBLE: ("uart_print_bin4", None),
                CHAR: ("uart_print_bin8", None),
                WORD: ("uart_print_bin16", None),
                DWORD: ("uart_print_bin32", None),
            }
        elif spec == "c":
            if arg_type is NIBBLE:
                return "uart_putc", CHAR
            if arg_type is CHAR:
                return "uart_putc", None
            table = {}
        elif spec == "s":
            if arg_type is FLASHPTR:
                return "uart_puts", None
            if arg_type is CHAR:
                return "uart_print_str", None
            table = {}
        else:  # pragma: no cover - parse_format rejects these
            table = {}

        if arg_type not in table:
            raise BadgeTypeError(
                f"{location(filename, line)}: cannot format {arg_type} "
                f"with print specifier {{{':' + spec if spec else ''}}}"
            )
        return table[arg_type]

    # ------------------------------------------------------------------
    # Type inference
    # ------------------------------------------------------------------

    def lookup(self, name: str):
        for scope in reversed(self.scopes):
            if name in scope:
                return scope[name]
        return self.globals.get(name)

    def infer_type(self, expr: ast.Expr):
        if isinstance(expr, ast.Number):
            if expr.value <= 15:
                return NIBBLE
            if expr.value <= 255:
                return CHAR
            if expr.value <= 0xFFFF:
                return WORD
            return DWORD
        if isinstance(expr, ast.StringLiteral):
            return FLASHPTR
        if isinstance(expr, ast.Var):
            decl = self.lookup(expr.name)
            if decl is None:
                raise BadgeCompileError(
                    f"{location(self.filename, expr.line)}: unknown identifier {expr.name!r}"
                )
            if getattr(decl, "array_len", None) is not None:
                if self.globals.get(expr.name) is decl and getattr(decl, "is_const", False):
                    return FLASHPTR
                raise BadgeTypeError(
                    f"{location(self.filename, expr.line)}: array {expr.name!r} used without an index"
                )
            return decl.type
        if isinstance(expr, ast.Index):
            if not isinstance(expr.base, ast.Var):
                raise BadgeTypeError(
                    f"{location(self.filename, expr.line)}: only named arrays can be indexed"
                )
            decl = self.lookup(expr.base.name)
            if decl is None:
                raise BadgeCompileError(
                    f"{location(self.filename, expr.base.line)}: unknown identifier "
                    f"{expr.base.name!r}"
                )
            if getattr(decl, "array_len", None) is None:
                raise BadgeTypeError(
                    f"{location(self.filename, expr.line)}: {expr.base.name!r} is not an array"
                )
            return decl.type
        if isinstance(expr, ast.Unary):
            if expr.op == "!":
                return NIBBLE
            return self.infer_type(expr.operand)
        if isinstance(expr, ast.AddressOf):
            return CHAR
        if isinstance(expr, ast.Binary):
            if expr.op in ("==", "!=", "<", "<=", ">", ">=", "&&", "||"):
                return NIBBLE
            if expr.op in ("<<", ">>"):
                return self.infer_type(expr.left)
            left = self.infer_type(expr.left)
            right = self.infer_type(expr.right)
            if expr.op == "*":
                return promoted_mul_type(wider(left, right))
            return wider(left, right)
        if isinstance(expr, ast.Call):
            if expr.name == "print":
                raise BadgeCompileError(
                    f"{location(self.filename, expr.line)}: print() can only be used as a statement"
                )
            builtin = _builtin_types().get(expr.name)
            if builtin is not None:
                return builtin
            decl = self.functions.get(expr.name)
            if decl is None:
                raise BadgeCompileError(
                    f"{location(self.filename, expr.line)}: unknown function {expr.name!r}"
                )
            return decl.return_type
        if isinstance(expr, (ast.Cast, ast.ToType)):
            return expr.type
        raise BadgeCompileError(
            f"{location(self.filename, expr.line)}: cannot infer type of "
            f"{type(expr).__name__}"
        )

    # ------------------------------------------------------------------
    # Validation walkers
    # ------------------------------------------------------------------

    def reject_dynamic_print(self, expr: ast.Expr) -> None:
        if isinstance(expr, ast.Call):
            if expr.name == "print":
                raise BadgeCompileError(
                    f"{location(self.filename, expr.line)}: print() can only be used as a statement"
                )
            for arg in expr.args:
                self.reject_dynamic_print(arg)
            return
        for data_field in dataclasses.fields(expr):
            value = getattr(expr, data_field.name)
            if isinstance(value, ast.Expr):
                self.reject_dynamic_print(value)
            elif isinstance(value, list):
                for item in value:
                    if isinstance(item, ast.Expr):
                        self.reject_dynamic_print(item)


def expand_print(program: ast.Program, filename: str) -> None:
    PrintExpander(program, filename).expand()
