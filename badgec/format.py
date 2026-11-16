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
    BOOL,
    FLASHPTR,
    I8,
    U4,
    U8,
    VOID,
    StructType,
    Type,
    common_type,
    fits_value,
    is_integer,
    promoted_mul_type,
    smallest_type_for,
    type_for,
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
            if arg_type is FLASHPTR:
                return "uart_puts", None
            if arg_type is BOOL:
                return "uart_print_dec8", U8
            if is_integer(arg_type):
                width = arg_type.ram_size
                if width == 1:
                    return (
                        ("uart_print_dec8_signed", I8)
                        if arg_type.signed
                        else ("uart_print_dec8", U8)
                    )
                if width == 2:
                    return (
                        ("uart_print_dec8_signed", None)
                        if arg_type.signed
                        else ("uart_print_dec8", None)
                    )
                if width == 4:
                    return (
                        ("uart_print_dec16_signed", None)
                        if arg_type.signed
                        else ("uart_print_dec16", None)
                    )
                if width == 8:
                    return (
                        ("uart_print_dec32_signed", None)
                        if arg_type.signed
                        else ("uart_print_dec32", None)
                    )
                if width == 16:
                    return (
                        ("uart_print_dec64_signed", None)
                        if arg_type.signed
                        else ("uart_print_dec64", None)
                    )
        elif spec == "x":
            if arg_type is BOOL:
                return "uart_print_nibble", U4
            if is_integer(arg_type):
                unsigned = type_for(arg_type.ram_size, False)
                helper = {
                    1: "uart_print_nibble",
                    2: "uart_print_hex8",
                    4: "uart_print_hex16",
                    8: "uart_print_hex32",
                    16: "uart_print_hex64",
                }.get(arg_type.ram_size)
                if helper is not None:
                    return helper, (unsigned if arg_type is not unsigned else None)
        elif spec == "b":
            if arg_type is BOOL:
                return "uart_print_bin4", U4
            if is_integer(arg_type):
                unsigned = type_for(arg_type.ram_size, False)
                helper = {
                    1: "uart_print_bin4",
                    2: "uart_print_bin8",
                    4: "uart_print_bin16",
                    8: "uart_print_bin32",
                    16: "uart_print_bin64",
                }.get(arg_type.ram_size)
                if helper is not None:
                    return helper, (unsigned if arg_type is not unsigned else None)
        elif spec == "c":
            if arg_type is BOOL or (is_integer(arg_type) and arg_type.ram_size in (1, 2)):
                return "uart_putc", U8
        elif spec == "s":
            if arg_type is FLASHPTR:
                return "uart_puts", None
            if arg_type is U8:
                return "uart_print_str", None

        raise BadgeTypeError(
            f"{location(filename, line)}: cannot format {arg_type} "
            f"with print specifier {{{':' + spec if spec else ''}}}"
        )

    # ------------------------------------------------------------------
    # Type inference
    # ------------------------------------------------------------------

    def lookup(self, name: str):
        for scope in reversed(self.scopes):
            if name in scope:
                return scope[name]
        return self.globals.get(name)

    @staticmethod
    def _literal_value(expr: ast.Expr):
        if isinstance(expr, ast.Number):
            return int(expr.value)
        if (
            isinstance(expr, ast.Unary)
            and expr.op == "-"
            and isinstance(expr.operand, ast.Number)
        ):
            return -int(expr.operand.value)
        return None

    def _literal_type_for(self, value: int, context: Type) -> Type:
        if is_integer(context):
            if fits_value(context, value):
                return context
            if context.signed:
                for width in (1, 2, 4, 8):
                    if width >= context.ram_size:
                        candidate = type_for(width, True)
                        if fits_value(candidate, value):
                            return candidate
                return context
            if value < 0:
                return context
            for width in (2, 4, 8):
                if width >= context.ram_size:
                    candidate = type_for(width, False)
                    if fits_value(candidate, value):
                        return candidate
            return context
        return smallest_type_for(value, signed_hint=False)

    def _common_expr_type(self, left: ast.Expr, right: ast.Expr) -> Type:
        left_value = self._literal_value(left)
        right_value = self._literal_value(right)
        if left_value is not None and right_value is not None:
            signed = left_value < 0 or right_value < 0
            for width in (1, 2, 4, 8):
                candidate = type_for(width, signed)
                if fits_value(candidate, left_value) and fits_value(candidate, right_value):
                    return candidate
            return type_for(8, signed)
        if left_value is not None:
            right_type = self.infer_type(right)
            if right_type is BOOL:
                right_type = U4
            if not is_integer(right_type):
                return right_type
            return common_type(self._literal_type_for(left_value, right_type), right_type)
        if right_value is not None:
            left_type = self.infer_type(left)
            if left_type is BOOL:
                left_type = U4
            if not is_integer(left_type):
                return left_type
            return common_type(left_type, self._literal_type_for(right_value, left_type))
        left_type = self.infer_type(left)
        right_type = self.infer_type(right)
        if left_type is BOOL:
            left_type = U4
        if right_type is BOOL:
            right_type = U4
        return common_type(left_type, right_type)

    def infer_type(self, expr: ast.Expr):
        if isinstance(expr, ast.Number):
            return smallest_type_for(int(expr.value), signed_hint=False)
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
        if isinstance(expr, ast.Member):
            base_type = self.infer_type(expr.base)
            if not isinstance(base_type, StructType):
                raise BadgeTypeError(
                    f"{location(self.filename, expr.line)}: {base_type} has no field "
                    f"{expr.field!r}"
                )
            field = base_type.field(expr.field)
            if field is None:
                raise BadgeTypeError(
                    f"{location(self.filename, expr.line)}: struct {base_type.name} "
                    f"has no field {expr.field!r}"
                )
            return field.type
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
                return BOOL
            if expr.op == "-":
                literal = self._literal_value(expr)
                if literal is not None:
                    return smallest_type_for(literal, signed_hint=True)
                operand = self.infer_type(expr.operand)
                if operand is BOOL:
                    operand = U4
                if not is_integer(operand):
                    raise BadgeTypeError(
                        f"{location(self.filename, expr.line)}: unary - requires an integer operand"
                    )
                return type_for(operand.ram_size, True)
            operand = self.infer_type(expr.operand)
            return U4 if operand is BOOL else operand
        if isinstance(expr, ast.Conditional):
            then_type = self.infer_type(expr.then_expr)
            else_type = self.infer_type(expr.else_expr)
            if then_type is VOID or else_type is VOID:
                raise BadgeTypeError(
                    f"{location(self.filename, expr.line)}: ternary branches "
                    "must produce a value"
                )
            if isinstance(then_type, StructType) or isinstance(else_type, StructType):
                raise BadgeTypeError(
                    f"{location(self.filename, expr.line)}: ternary branches "
                    "cannot be struct values"
                )
            if then_type.is_float or else_type.is_float:
                if (
                    then_type.is_float
                    and else_type.is_float
                    and then_type is not else_type
                ):
                    raise BadgeTypeError(
                        f"{location(self.filename, expr.line)}: mixed float types "
                        f"{then_type} and {else_type}; use an explicit cast"
                    )
                return then_type if then_type.is_float else else_type
            if then_type is FLASHPTR or else_type is FLASHPTR:
                if then_type is FLASHPTR and else_type is FLASHPTR:
                    return FLASHPTR
                raise BadgeTypeError(
                    f"{location(self.filename, expr.line)}: ternary branches "
                    "must both be flash pointers"
                )
            return self._common_expr_type(expr.then_expr, expr.else_expr)
        if isinstance(expr, ast.AddressOf):
            return U8
        if isinstance(expr, ast.Binary):
            if expr.op in ("==", "!=", "<", "<=", ">", ">=", "&&", "||"):
                return BOOL
            if expr.op in ("<<", ">>"):
                return self.infer_type(expr.left)
            if expr.op == "*":
                return promoted_mul_type(
                    self._common_expr_type(expr.left, expr.right)
                )
            return self._common_expr_type(expr.left, expr.right)
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
