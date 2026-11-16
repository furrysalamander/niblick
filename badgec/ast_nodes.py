"""AST nodes for BadgeC.

The tree is intentionally small: expressions, statements, functions and
top-level declarations.  Semantic decisions (allocation, code generation)
live in badgec/compiler.py.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from .types import Type


# ---------------------------------------------------------------------------
# Expressions
# ---------------------------------------------------------------------------


@dataclass(kw_only=True)
class Expr:
    line: int = 0
    column: int = 0
    file: str = ""


@dataclass
class Number(Expr):
    value: int = 0


@dataclass
class FloatLiteral(Expr):
    value: float = 0.0


@dataclass
class StringLiteral(Expr):
    value: str = ""


@dataclass
class Var(Expr):
    name: str = ""


@dataclass
class Index(Expr):
    base: Expr = field(default_factory=Expr)
    index: Expr = field(default_factory=Expr)


@dataclass
class Member(Expr):
    base: Expr = field(default_factory=Expr)
    field: str = ""


@dataclass
class Unary(Expr):
    op: str = ""
    operand: Expr = field(default_factory=Expr)


@dataclass
class Binary(Expr):
    op: str = ""
    left: Expr = field(default_factory=Expr)
    right: Expr = field(default_factory=Expr)


@dataclass
class Call(Expr):
    name: str = ""
    args: list[Expr] = field(default_factory=list)


@dataclass
class AddressOf(Expr):
    operand: Expr = field(default_factory=Expr)


@dataclass
class ToType(Expr):
    """Internal width-preserving cast inserted by the inliner."""

    type: Type = None  # type: ignore[assignment]
    operand: Expr = field(default_factory=Expr)


@dataclass
class Cast(Expr):
    """Explicit ``(uint16_t)expr`` style conversion."""

    type: Type = None  # type: ignore[assignment]
    operand: Expr = field(default_factory=Expr)


# ---------------------------------------------------------------------------
# Statements
# ---------------------------------------------------------------------------


@dataclass(kw_only=True)
class Stmt:
    line: int = 0
    column: int = 0
    file: str = ""


@dataclass
class Block(Stmt):
    statements: list[Stmt] = field(default_factory=list)


@dataclass
class VarDecl(Stmt):
    name: str = ""
    type: Type = None  # type: ignore[assignment]
    array_len: Optional[int] = None
    init: Optional[Expr] = None
    is_const: bool = False


@dataclass
class Assign(Stmt):
    target: Expr = field(default_factory=Expr)
    value: Expr = field(default_factory=Expr)


@dataclass
class ExprStmt(Stmt):
    expr: Expr = field(default_factory=Expr)


@dataclass
class If(Stmt):
    condition: Expr = field(default_factory=Expr)
    then_block: Block = field(default_factory=Block)
    else_block: Optional[Block] = None


@dataclass
class While(Stmt):
    condition: Expr = field(default_factory=Expr)
    body: Block = field(default_factory=Block)


@dataclass
class For(Stmt):
    init: Optional[Stmt] = None
    condition: Optional[Expr] = None
    update: Optional[Stmt] = None
    body: Block = field(default_factory=Block)


@dataclass
class Return(Stmt):
    value: Optional[Expr] = None


@dataclass
class Break(Stmt):
    pass


@dataclass
class Continue(Stmt):
    pass


@dataclass
class InlineAsm(Stmt):
    text: str = ""


# ---------------------------------------------------------------------------
# Top-level declarations
# ---------------------------------------------------------------------------


@dataclass
class GlobalDecl:
    name: str
    type: Type
    array_len: Optional[int] = None
    init: Optional[Expr] = None
    init_list: Optional[list[Expr]] = None
    init_string: Optional[str] = None
    is_const: bool = False
    line: int = 0
    column: int = 0
    file: str = ""


@dataclass
class Param:
    name: str
    type: Type
    line: int = 0
    column: int = 0
    file: str = ""


@dataclass
class FunctionDecl:
    name: str
    return_type: Type
    params: list[Param]
    body: Block
    line: int = 0
    column: int = 0
    file: str = ""
    name_line: int = 0
    name_column: int = 0
    # ``extern`` functions have no BadgeC body.  Their implementation is
    # expected to appear as a ``fn_name:`` entry point in an imported .asm
    # file.
    is_extern: bool = False


@dataclass
class ImportDecl:
    path: str
    line: int = 0
    column: int = 0
    file: str = ""


@dataclass
class AsmSource:
    """An imported .asm file, kept as text until code generation."""

    path: str
    text: str


@dataclass
class Program:
    globals: list[GlobalDecl] = field(default_factory=list)
    functions: list[FunctionDecl] = field(default_factory=list)
    imports: list[ImportDecl] = field(default_factory=list)
    asm_sources: list[AsmSource] = field(default_factory=list)
