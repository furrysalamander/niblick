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


@dataclass
class Number(Expr):
    value: int = 0


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


# ---------------------------------------------------------------------------
# Statements
# ---------------------------------------------------------------------------


@dataclass(kw_only=True)
class Stmt:
    line: int = 0


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


@dataclass
class Param:
    name: str
    type: Type
    line: int = 0


@dataclass
class FunctionDecl:
    name: str
    return_type: Type
    params: list[Param]
    body: Block
    line: int = 0


@dataclass
class Program:
    globals: list[GlobalDecl] = field(default_factory=list)
    functions: list[FunctionDecl] = field(default_factory=list)
