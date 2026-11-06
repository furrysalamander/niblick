"""Conservative whole-program inliner and dead-function elimination.

Only tiny functions whose body is a single ``return <expr>`` are considered.
That covers the common accessor/wrapper case and keeps the transformation
predictable.  Calls to a parameter are allowed multiple times only when the
corresponding argument is pure (a literal, a variable, or ``&variable``), so
inlining cannot duplicate side effects.
"""

from __future__ import annotations

import copy
import dataclasses
from typing import Iterable

from . import ast_nodes as ast


def _is_pure(expr: ast.Expr) -> bool:
    if isinstance(expr, (ast.Number, ast.StringLiteral, ast.Var, ast.AddressOf)):
        return True
    return False


def _count_var(expr: ast.Expr, name: str) -> int:
    count = 0
    if isinstance(expr, ast.Var) and expr.name == name:
        return 1
    for field in dataclasses.fields(expr):
        value = getattr(expr, field.name)
        if isinstance(value, ast.Expr):
            count += _count_var(value, name)
        elif isinstance(value, list):
            count += sum(_count_var(item, name) for item in value if isinstance(item, ast.Expr))
    return count


def _substitute(node, mapping: dict[str, ast.Expr]):
    if isinstance(node, ast.Var) and node.name in mapping:
        return copy.deepcopy(mapping[node.name])

    for field in dataclasses.fields(node):
        value = getattr(node, field.name)
        if isinstance(value, ast.Expr):
            setattr(node, field.name, _substitute(value, mapping))
        elif isinstance(value, list):
            setattr(
                node,
                field.name,
                [
                    _substitute(item, mapping) if isinstance(item, ast.Expr) else item
                    for item in value
                ],
            )
    return node


def _inline_expr(
    expr: ast.Expr,
    candidates: dict[str, ast.FunctionDecl],
    active: set[str],
) -> ast.Expr:
    if isinstance(expr, ast.Call) and expr.name in candidates and expr.name not in active:
        fn = candidates[expr.name]
        return_stmt = fn.body.statements[0]
        assert isinstance(return_stmt, ast.Return) and return_stmt.value is not None

        mapping: dict[str, ast.Expr] = {}
        allowed = True
        for param, arg in zip(fn.params, expr.args):
            uses = _count_var(return_stmt.value, param.name)
            if uses == 0:
                # Dropping a pure argument is fine; dropping a side-effecting
                # argument would change program behavior.
                if not _is_pure(arg):
                    allowed = False
                    break
            elif uses > 1 and not _is_pure(arg):
                allowed = False
                break
            mapping[param.name] = arg

        if allowed and len(fn.params) == len(expr.args):
            body = copy.deepcopy(return_stmt.value)
            substituted = _substitute(body, mapping)
            return _inline_expr(substituted, candidates, active | {fn.name})

    for field in dataclasses.fields(expr):
        value = getattr(expr, field.name)
        if isinstance(value, ast.Expr):
            setattr(expr, field.name, _inline_expr(value, candidates, active))
        elif isinstance(value, list):
            setattr(
                expr,
                field.name,
                [
                    _inline_expr(item, candidates, active) if isinstance(item, ast.Expr) else item
                    for item in value
                ],
            )
    return expr


def _inline_stmt(stmt: ast.Stmt, candidates: dict[str, ast.FunctionDecl], active: set[str]) -> None:
    for field in dataclasses.fields(stmt):
        value = getattr(stmt, field.name)
        if isinstance(value, ast.Expr):
            setattr(stmt, field.name, _inline_expr(value, candidates, active))
        elif isinstance(value, ast.Block):
            _inline_block(value, candidates, active)
        elif isinstance(value, ast.Stmt):
            _inline_stmt(value, candidates, active)
        elif isinstance(value, list):
            for item in value:
                if isinstance(item, ast.Expr):
                    _inline_expr(item, candidates, active)
                elif isinstance(item, ast.Stmt):
                    _inline_stmt(item, candidates, active)


def _inline_block(block: ast.Block, candidates: dict[str, ast.FunctionDecl], active: set[str]) -> None:
    for stmt in block.statements:
        _inline_stmt(stmt, candidates, active)


def _collect_calls_expr(expr: ast.Expr, calls: set[str]) -> None:
    if isinstance(expr, ast.Call):
        calls.add(expr.name)
    for field in dataclasses.fields(expr):
        value = getattr(expr, field.name)
        if isinstance(value, ast.Expr):
            _collect_calls_expr(value, calls)
        elif isinstance(value, list):
            for item in value:
                if isinstance(item, ast.Expr):
                    _collect_calls_expr(item, calls)


def _collect_calls_stmt(stmt: ast.Stmt, calls: set[str]) -> None:
    for field in dataclasses.fields(stmt):
        value = getattr(stmt, field.name)
        if isinstance(value, ast.Expr):
            _collect_calls_expr(value, calls)
        elif isinstance(value, ast.Block):
            for child in value.statements:
                _collect_calls_stmt(child, calls)
        elif isinstance(value, ast.Stmt):
            _collect_calls_stmt(value, calls)
        elif isinstance(value, list):
            for item in value:
                if isinstance(item, ast.Expr):
                    _collect_calls_expr(item, calls)
                elif isinstance(item, ast.Stmt):
                    _collect_calls_stmt(item, calls)


def optimize(program: ast.Program) -> None:
    """Inline tiny return-only functions and remove unreachable functions."""
    candidates: dict[str, ast.FunctionDecl] = {}
    for fn in program.functions:
        if fn.name == "main":
            continue
        if len(fn.body.statements) != 1:
            continue
        stmt = fn.body.statements[0]
        if isinstance(stmt, ast.Return) and stmt.value is not None:
            candidates[fn.name] = fn

    if not candidates:
        return

    for fn in program.functions:
        _inline_block(fn.body, candidates, set())
    for decl in program.globals:
        if decl.init is not None:
            decl.init = _inline_expr(decl.init, candidates, set())
        if decl.init_list is not None:
            decl.init_list = [_inline_expr(item, candidates, set()) for item in decl.init_list]

    # Remove functions that are no longer reachable from main or a global
    # initializer (global initialization code is emitted at the start of main).
    by_name = {fn.name: fn for fn in program.functions}
    reachable: set[str] = set()
    worklist = ["main"] if "main" in by_name else []
    for decl in program.globals:
        exprs = []
        if decl.init is not None:
            exprs.append(decl.init)
        if decl.init_list:
            exprs.extend(decl.init_list)
        for expr in exprs:
            calls: set[str] = set()
            _collect_calls_expr(expr, calls)
            worklist.extend(calls)
    while worklist:
        name = worklist.pop()
        if name in reachable or name not in by_name:
            continue
        reachable.add(name)
        calls: set[str] = set()
        for stmt in by_name[name].body.statements:
            _collect_calls_stmt(stmt, calls)
        worklist.extend(calls - reachable)

    program.functions = [fn for fn in program.functions if fn.name in reachable]
