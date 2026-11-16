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

from . import ast_nodes as ast
from .asm_link import scan_asm
from .asm_text import IDENT_RE, asm_function_references, placeholder_names
from .types import BOOL, F32, VOID, is_integer


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
        if isinstance(value, (ast.Expr, ast.Stmt, ast.Block)):
            setattr(node, field.name, _substitute(value, mapping))
        elif isinstance(value, list):
            setattr(
                node,
                field.name,
                [
                    _substitute(item, mapping)
                    if isinstance(item, (ast.Expr, ast.Stmt, ast.Block))
                    else item
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
            # Preserve parameter width when a literal or narrower argument is
            # substituted, so char/word arithmetic does not become nibble
            # arithmetic after inlining.
            mapping[param.name] = (
                ast.ToType(param.type, arg, line=getattr(arg, "line", 0))
                if (is_integer(param.type) and param.type.ram_size >= 2) or param.type is BOOL
                else arg
            )

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
    if isinstance(stmt, ast.InlineAsm):
        calls.update(asm_function_references(stmt.text))
        return
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


def _collect_vars_expr(expr: ast.Expr, names: set[str]) -> None:
    if isinstance(expr, ast.Var):
        names.add(expr.name)
    for field in dataclasses.fields(expr):
        value = getattr(expr, field.name)
        if isinstance(value, ast.Expr):
            _collect_vars_expr(value, names)
        elif isinstance(value, list):
            for item in value:
                if isinstance(item, ast.Expr):
                    _collect_vars_expr(item, names)


def _collect_vars_stmt(stmt: ast.Stmt, names: set[str]) -> None:
    if isinstance(stmt, ast.InlineAsm):
        names.update(placeholder_names(stmt.text))
        return
    for field in dataclasses.fields(stmt):
        value = getattr(stmt, field.name)
        if isinstance(value, ast.Expr):
            _collect_vars_expr(value, names)
        elif isinstance(value, ast.Block):
            for child in value.statements:
                _collect_vars_stmt(child, names)
        elif isinstance(value, ast.Stmt):
            _collect_vars_stmt(value, names)
        elif isinstance(value, list):
            for item in value:
                if isinstance(item, ast.Expr):
                    _collect_vars_expr(item, names)
                elif isinstance(item, ast.Stmt):
                    _collect_vars_stmt(item, names)


def _initializers(decl: ast.GlobalDecl) -> list[ast.Expr]:
    exprs: list[ast.Expr] = []
    if decl.init is not None:
        exprs.append(decl.init)
    if decl.init_list is not None:
        exprs.extend(decl.init_list)
    return exprs


def _global_has_side_effects(decl: ast.GlobalDecl) -> bool:
    for expr in _initializers(decl):
        calls: set[str] = set()
        _collect_calls_expr(expr, calls)
        if calls:
            return True
    return False


QW_FUNCTION_NAMES = {
    "__bc_mul64",
    "__bc_div64",
    "__bc_mod64",
    "__bc_smul64",
    "__bc_sdiv64",
    "__bc_smod64",
    "uart_print_dec32_digits",
    "uart_print_dec64",
    "uart_print_dec64_signed",
    "uart_print_hex64",
    "uart_print_bin64",
}
QW_GLOBAL_NAMES = {
    "__bc_w_q",
    "__bc_w_r",
    "__bc_conv64_f32",
}

FLOAT32_FUNCTIONS = {
    "__bc_f32_add", "__bc_f32_sub", "__bc_f32_mul", "__bc_f32_div",
    "__bc_f32_cmp", "__bc_f32_eq", "__bc_f32_ne", "__bc_f32_lt",
    "__bc_f32_le", "__bc_f32_gt", "__bc_f32_ge", "__bc_f32_is_zero",
    "__bc_u32_to_f32", "__bc_i32_to_f32",
    "__bc_u64_to_f32", "__bc_i64_to_f32",
    "__bc_f32_to_i32", "__bc_f32_to_u32",
    "__bc_f32_to_i64", "__bc_f32_to_u64",
    "__bc_f32_to_u64_asm", "__bc_f32_to_i64_asm",
    "__bc_f32_int32_core", "__bc_f32_int64_core", "__bc_f32_core",
}

FLOAT16_FUNCTIONS = {
    "__bc_f16_add", "__bc_f16_sub", "__bc_f16_mul", "__bc_f16_div",
    "__bc_f16_cmp", "__bc_f16_eq", "__bc_f16_ne", "__bc_f16_lt",
    "__bc_f16_le", "__bc_f16_gt", "__bc_f16_ge", "__bc_f16_is_zero",
    "__bc_u32_to_f16", "__bc_i32_to_f16",
    "__bc_u64_to_f16", "__bc_i64_to_f16",
    "__bc_f16_to_i32", "__bc_f16_to_u32",
    "__bc_f16_to_i64", "__bc_f16_to_u64",
    "__bc_f16_to_f32", "__bc_f32_to_f16", "__bc_f16_core",
}



def _walk_ast(node) -> None:
    if not dataclasses.is_dataclass(node):
        return
    yield_node[0](node)
    for data_field in dataclasses.fields(node):
        value = getattr(node, data_field.name)
        if dataclasses.is_dataclass(value):
            _walk_ast(value)
        elif isinstance(value, list):
            for item in value:
                if dataclasses.is_dataclass(item):
                    _walk_ast(item)


yield_node: list = [lambda node: None]


def _uses_qword(program: ast.Program) -> bool:
    """True when a program mentions a 64-bit type or literal."""

    found = [False]

    def visit(node) -> None:
        if found[0]:
            return
        if isinstance(node, ast.Number):
            if int(node.value) > 0xFFFFFFFF:
                found[0] = True
        elif isinstance(node, ast.Unary) and node.op == "-" and isinstance(node.operand, ast.Number):
            if -int(node.operand.value) < -(1 << 31):
                found[0] = True
        elif isinstance(node, (ast.Cast, ast.ToType)):
            if getattr(node.type, "ram_size", 0) == 16:
                found[0] = True
        else:
            typ = getattr(node, "type", None)
            if typ is not None and getattr(typ, "ram_size", 0) == 16:
                found[0] = True
            if isinstance(node, ast.FunctionDecl) and getattr(node.return_type, "ram_size", 0) == 16:
                found[0] = True

    yield_node[0] = visit
    for decl in program.globals:
        if decl.name in QW_GLOBAL_NAMES:
            continue
        _walk_ast(decl)
        if found[0]:
            return True
    excluded = QW_FUNCTION_NAMES | FLOAT32_FUNCTIONS | FLOAT16_FUNCTIONS
    for fn in program.functions:
        if fn.name in excluded:
            continue
        _walk_ast(fn)
        if found[0]:
            return True
    return False


def _collect_binary_ops(program: ast.Program) -> set[str]:
    ops: set[str] = set()

    def visit(node) -> None:
        if isinstance(node, ast.Binary):
            ops.add(node.op)

    yield_node[0] = visit
    for decl in program.globals:
        if decl.name in QW_GLOBAL_NAMES:
            continue
        _walk_ast(decl)
    for fn in program.functions:
        if fn.name in QW_FUNCTION_NAMES:
            continue
        _walk_ast(fn)
    return ops


def _uses_signed_qword(program: ast.Program) -> bool:
    found = [False]

    def visit(node) -> None:
        if found[0]:
            return
        typ = getattr(node, "type", None)
        if typ is not None and getattr(typ, "ram_size", 0) == 16 and getattr(typ, "signed", False):
            found[0] = True
            return
        if isinstance(node, ast.FunctionDecl) and getattr(node.return_type, "ram_size", 0) == 16 and getattr(node.return_type, "signed", False):
            found[0] = True
        elif isinstance(node, ast.Unary) and node.op == "-" and isinstance(node.operand, ast.Number):
            if -int(node.operand.value) < -(1 << 31):
                found[0] = True

    yield_node[0] = visit
    for decl in program.globals:
        if decl.name in QW_GLOBAL_NAMES:
            continue
        _walk_ast(decl)
        if found[0]:
            return True
    for fn in program.functions:
        if fn.name in QW_FUNCTION_NAMES:
            continue
        _walk_ast(fn)
        if found[0]:
            return True
    return False


def _qword_helpers_needed(program: ast.Program) -> set[str]:
    if not _uses_qword(program):
        return set()
    ops = _collect_binary_ops(program)
    signed = _uses_signed_qword(program)
    needed: set[str] = set()
    if "*" in ops:
        needed.add("__bc_mul64")
        if signed:
            needed.add("__bc_smul64")
    if "/" in ops:
        needed.add("__bc_div64")
        if signed:
            needed.add("__bc_sdiv64")
    if "%" in ops:
        needed.add("__bc_mod64")
        if signed:
            needed.add("__bc_smod64")
    return needed


def _uses_float(program: ast.Program, bits: int) -> bool:
    found = [False]
    excluded = FLOAT32_FUNCTIONS | FLOAT16_FUNCTIONS

    def visit(node) -> None:
        if found[0]:
            return
        typ = getattr(node, "type", None)
        if typ is not None and getattr(typ, "is_float", False) and getattr(typ, "float_bits", 0) == bits:
            found[0] = True
            return
        if isinstance(node, ast.FunctionDecl):
            rt = node.return_type
            if getattr(rt, "is_float", False) and getattr(rt, "float_bits", 0) == bits:
                found[0] = True

    yield_node[0] = visit
    for decl in program.globals:
        _walk_ast(decl)
        if found[0]:
            return True
    for fn in program.functions:
        if fn.name in excluded:
            continue
        _walk_ast(fn)
        if found[0]:
            return True
    return False


def _float_ops_by_width(program: ast.Program) -> dict[int, set[str]]:
    """Best-effort type-aware float operation discovery.

    The AST has no type annotations at this stage, so this walks declarations
    to build a simple name-to-type map and uses it to decide whether an
    arithmetic or comparison operation belongs to binary16 or binary32.
    """

    global_types = {decl.name: decl.type for decl in program.globals}
    returns = {fn.name: fn.return_type for fn in program.functions}
    result: dict[int, set[str]] = {16: set(), 32: set()}

    def infer(expr: ast.Expr, scope: dict[str, object]):
        if isinstance(expr, ast.Var):
            return scope.get(expr.name, global_types.get(expr.name))
        if isinstance(expr, ast.FloatLiteral):
            return F32
        if isinstance(expr, ast.Number):
            return None
        if isinstance(expr, (ast.Cast, ast.ToType)):
            return expr.type if getattr(expr.type, "is_float", False) else None
        if isinstance(expr, ast.Call):
            return returns.get(expr.name)
        if isinstance(expr, ast.Unary):
            return infer(expr.operand, scope)
        if isinstance(expr, ast.Binary):
            left = infer(expr.left, scope)
            if left is not None and getattr(left, "is_float", False):
                return left
            right = infer(expr.right, scope)
            if right is not None and getattr(right, "is_float", False):
                return right
            return None
        return None

    def walk_expr(expr: ast.Expr, scope: dict[str, object]) -> None:
        if isinstance(expr, ast.Binary):
            typ = infer(expr.left, scope) or infer(expr.right, scope)
            if typ is not None and getattr(typ, "is_float", False):
                if expr.op in ("+", "-", "*", "/"):
                    result.setdefault(typ.float_bits, set()).add(expr.op)
                elif expr.op in ("==", "!=", "<", "<=", ">", ">="):
                    result.setdefault(typ.float_bits, set()).add(expr.op)
            walk_expr(expr.left, scope)
            walk_expr(expr.right, scope)
            return
        if isinstance(expr, ast.Unary):
            walk_expr(expr.operand, scope)
            return
        if isinstance(expr, (ast.Cast, ast.ToType)):
            walk_expr(expr.operand, scope)
            return
        for data_field in dataclasses.fields(expr):
            value = getattr(expr, data_field.name)
            if isinstance(value, ast.Expr):
                walk_expr(value, scope)
            elif isinstance(value, list):
                for item in value:
                    if isinstance(item, ast.Expr):
                        walk_expr(item, scope)

    def walk_stmt(stmt: ast.Stmt, scope: dict[str, object]) -> None:
        if isinstance(stmt, ast.VarDecl):
            scope[stmt.name] = stmt.type
        if isinstance(stmt, ast.Block):
            for child in stmt.statements:
                walk_stmt(child, scope)
            return
        if isinstance(stmt, ast.If):
            walk_expr(stmt.condition, scope)
            walk_stmt(stmt.then_block, scope)
            if stmt.else_block is not None:
                walk_stmt(stmt.else_block, scope)
            return
        if isinstance(stmt, ast.While):
            walk_expr(stmt.condition, scope)
            walk_stmt(stmt.body, scope)
            return
        if isinstance(stmt, ast.For):
            if stmt.init is not None:
                walk_stmt(stmt.init, scope)
            if stmt.condition is not None:
                walk_expr(stmt.condition, scope)
            if stmt.update is not None:
                walk_stmt(stmt.update, scope)
            walk_stmt(stmt.body, scope)
            return
        for data_field in dataclasses.fields(stmt):
            value = getattr(stmt, data_field.name)
            if isinstance(value, ast.Expr):
                walk_expr(value, scope)
            elif isinstance(value, list):
                for item in value:
                    if isinstance(item, ast.Expr):
                        walk_expr(item, scope)

    for decl in program.globals:
        for expr in _initializers(decl):
            walk_expr(expr, {})
    for fn in program.functions:
        scope = {param.name: param.type for param in fn.params}
        walk_stmt(fn.body, scope)
    return result


def _float_helpers_needed(program: ast.Program, bits: int) -> set[str]:
    if not _uses_float(program, bits):
        return set()
    prefix = f"__bc_f{bits}"
    excluded = FLOAT32_FUNCTIONS | FLOAT16_FUNCTIONS
    ops = _float_ops_by_width(program).get(bits, set())
    cast_float = [False]
    cast_int = [False]
    int_targets: set[str] = set()

    def visit(node) -> None:
        if isinstance(node, (ast.Cast, ast.ToType)):
            target = node.type
            if getattr(target, "is_float", False):
                cast_float[0] = True
            elif target is BOOL:
                cast_int[0] = True
                int_targets.add("zero")
            elif is_integer(target):
                cast_int[0] = True
                int_targets.add(
                    ("i" if target.signed else "u")
                    + ("64" if target.ram_size == 16 else "32")
                )

    yield_node[0] = visit
    for decl in program.globals:
        if decl.name in QW_GLOBAL_NAMES:
            continue
        _walk_ast(decl)
    for fn in program.functions:
        if fn.name in excluded or fn.name in QW_FUNCTION_NAMES:
            continue
        _walk_ast(fn)

    needed: set[str] = set()
    if "+" in ops:
        needed.add(prefix + "_add")
    if "-" in ops:
        needed.add(prefix + "_add")
        needed.add(prefix + "_sub")
    if "*" in ops:
        needed.add(prefix + "_mul")
    if "/" in ops:
        needed.add(prefix + "_div")
    if ops & {"==", "!=", "<", "<=", ">", ">="}:
        needed.add(prefix + "_cmp")
    if cast_float[0] or cast_int[0]:
        use64 = _uses_qword(program)
        other = 16 if bits == 32 else 32
        both_floats = _uses_float(program, other)
        if bits == 32:
            if cast_float[0]:
                needed.update({"__bc_u32_to_f32", "__bc_i32_to_f32"})
                if use64:
                    needed.update({"__bc_u64_to_f32", "__bc_i64_to_f32"})
            if cast_int[0]:
                for key in int_targets:
                    if key == "zero":
                        needed.add("__bc_f32_is_zero")
                    else:
                        needed.add(f"__bc_f32_to_{key}")
            if cast_float[0] and both_floats:
                needed.update({"__bc_f32_to_f16", "__bc_f16_to_f32"})
        elif bits == 16:
            if cast_float[0]:
                needed.update({"__bc_u32_to_f16", "__bc_i32_to_f16"})
                if use64:
                    needed.update({"__bc_u64_to_f16", "__bc_i64_to_f16"})
            if cast_int[0]:
                for key in int_targets:
                    if key == "zero":
                        needed.add("__bc_f16_is_zero")
                    else:
                        needed.add(f"__bc_f16_to_{key}")
            if cast_float[0] and both_floats:
                needed.update({"__bc_f16_to_f32", "__bc_f32_to_f16"})
    return needed


def _eliminate_dead(
    program: ast.Program, extra_functions: set[str] | None = None
) -> None:
    """Remove unreachable functions and unreferenced pure globals.

    Functions and globals are analysed together: a kept global's initializer
    can keep a function alive, and a reachable function can keep a global
    alive.  Globals with side-effecting initializers are always kept.
    """

    by_function = {fn.name: fn for fn in program.functions}
    by_global = {decl.name: decl for decl in program.globals}

    asm_calls: dict[str, set[str]] = {}
    asm_globals: dict[str, set[str]] = {}
    asm_function_refs: dict[str, set[str]] = {}
    module_globals: set[str] = set()
    module_functions: set[str] = set()
    for source in program.asm_sources:
        scan = scan_asm(source.text, source.path)
        for call in scan.calls:
            caller = (
                call.caller_label[3:]
                if call.caller_label.startswith("fn_")
                else call.caller_label
            )
            callee = call.target_label[3:]
            if caller in by_function and callee in by_function:
                asm_calls.setdefault(caller, set()).add(callee)

        for function_label, placeholder in scan.placeholders:
            token_names = set(IDENT_RE.findall(placeholder.text))
            globals_here = {name for name in token_names if name in by_global}
            functions_here = {name for name in token_names if name in by_function}
            if function_label is None:
                module_globals.update(globals_here)
                module_functions.update(functions_here)
            else:
                name = function_label[3:]
                if globals_here:
                    asm_globals.setdefault(name, set()).update(globals_here)
                if functions_here:
                    asm_function_refs.setdefault(name, set()).update(functions_here)

    kept_globals: set[str] = {
        decl.name for decl in program.globals if _global_has_side_effects(decl)
    }
    kept_globals.update(module_globals)
    reachable: set[str] = set()
    function_worklist: list[str] = (
        (["main"] if "main" in by_function else [])
        + sorted(module_functions)
        + sorted((extra_functions or set()) & set(by_function))
    )
    global_worklist: list[str] = list(kept_globals)

    while function_worklist or global_worklist:
        while function_worklist:
            name = function_worklist.pop()
            if name in reachable or name not in by_function:
                continue
            reachable.add(name)

            calls: set[str] = set()
            names: set[str] = set()
            for stmt in by_function[name].body.statements:
                _collect_calls_stmt(stmt, calls)
                _collect_vars_stmt(stmt, names)
            function_worklist.extend(calls - reachable)
            global_worklist.extend(names - kept_globals)
            function_worklist.extend(asm_calls.get(name, set()) - reachable)
            function_worklist.extend(asm_function_refs.get(name, set()) - reachable)
            global_worklist.extend(asm_globals.get(name, set()) - kept_globals)

        while global_worklist:
            name = global_worklist.pop()
            if name in kept_globals:
                continue
            kept_globals.add(name)
            decl = by_global.get(name)
            if decl is None:
                continue
            for expr in _initializers(decl):
                init_calls: set[str] = set()
                init_names: set[str] = set()
                _collect_calls_expr(expr, init_calls)
                _collect_vars_expr(expr, init_names)
                function_worklist.extend(init_calls - reachable)
                global_worklist.extend(init_names - kept_globals)

    program.functions = [fn for fn in program.functions if fn.name in reachable]
    program.globals = [decl for decl in program.globals if decl.name in kept_globals]




def _count_calls(program: ast.Program) -> dict[str, int]:
    counts: dict[str, int] = {}

    def count_expr(expr: ast.Expr) -> None:
        if isinstance(expr, ast.Call):
            counts[expr.name] = counts.get(expr.name, 0) + 1
        for field in dataclasses.fields(expr):
            value = getattr(expr, field.name)
            if isinstance(value, ast.Expr):
                count_expr(value)
            elif isinstance(value, list):
                for item in value:
                    if isinstance(item, ast.Expr):
                        count_expr(item)

    def count_stmt(stmt: ast.Stmt) -> None:
        if isinstance(stmt, ast.InlineAsm):
            return
        for field in dataclasses.fields(stmt):
            value = getattr(stmt, field.name)
            if isinstance(value, ast.Expr):
                count_expr(value)
            elif isinstance(value, ast.Block):
                for child in value.statements:
                    count_stmt(child)
            elif isinstance(value, ast.Stmt):
                count_stmt(value)
            elif isinstance(value, list):
                for item in value:
                    if isinstance(item, ast.Expr):
                        count_expr(item)
                    elif isinstance(item, ast.Stmt):
                        count_stmt(item)

    for fn in program.functions:
        count_stmt(fn.body)
    return counts


def _safe_void_stmt(stmt: ast.Stmt) -> bool:
    """True when a statement can be inlined into a caller without control-flow surgery."""
    if isinstance(stmt, (ast.Return, ast.Break, ast.Continue, ast.VarDecl, ast.While, ast.For, ast.InlineAsm)):
        return False
    if isinstance(stmt, ast.If):
        if not all(_safe_void_stmt(child) for child in stmt.then_block.statements):
            return False
        if stmt.else_block is not None:
            if not all(_safe_void_stmt(child) for child in stmt.else_block.statements):
                return False
    return True


def _inlineable_void(fn: ast.FunctionDecl, call_count: int) -> bool:
    if fn.name == "main" or fn.is_extern or fn.return_type is not VOID:
        return False
    if len(fn.body.statements) != 1:
        return False
    stmt = fn.body.statements[0]
    if not isinstance(stmt, (ast.ExprStmt, ast.If)):
        return False
    if not _safe_void_stmt(stmt):
        return False
    # Single call sites are always worth inlining.  Multi-call bodies are
    # only inlined when they are one simple statement and the duplication is
    # small; large/branchy wrappers stay shared.
    if call_count <= 1:
        return True
    return isinstance(stmt, ast.ExprStmt) and call_count <= 3


def _inline_void_stmt(
    stmt: ast.Stmt,
    candidates: dict[str, ast.FunctionDecl],
    active: set[str],
) -> list[ast.Stmt]:
    if isinstance(stmt, ast.ExprStmt) and isinstance(stmt.expr, ast.Call):
        call = stmt.expr
        fn = candidates.get(call.name)
        if (
            fn is not None
            and fn.name not in active
            and len(fn.params) == len(call.args)
            and all(_is_pure(arg) for arg in call.args)
        ):
            mapping: dict[str, ast.Expr] = {}
            for param, arg in zip(fn.params, call.args):
                mapping[param.name] = (
                    ast.ToType(param.type, arg, line=getattr(arg, "line", 0))
                    if (is_integer(param.type) and param.type.ram_size >= 2) or param.type is BOOL
                    else arg
                )
            body = copy.deepcopy(fn.body)
            _substitute(body, mapping)
            out: list[ast.Stmt] = []
            for child in body.statements:
                out.extend(_inline_void_stmt(child, candidates, active | {fn.name}))
            return out

    if isinstance(stmt, ast.If):
        _inline_void_block(stmt.then_block, candidates, active)
        if stmt.else_block is not None:
            _inline_void_block(stmt.else_block, candidates, active)
    return [stmt]


def _inline_void_block(
    block: ast.Block,
    candidates: dict[str, ast.FunctionDecl],
    active: set[str],
) -> None:
    statements: list[ast.Stmt] = []
    for stmt in block.statements:
        statements.extend(_inline_void_stmt(stmt, candidates, active))
    block.statements = statements


def optimize(program: ast.Program) -> None:
    """Inline tiny return-only functions and remove dead declarations."""
    candidates: dict[str, ast.FunctionDecl] = {}
    for fn in program.functions:
        if fn.name == "main" or fn.is_extern:
            continue
        if len(fn.body.statements) != 1:
            continue
        stmt = fn.body.statements[0]
        if isinstance(stmt, ast.Return) and stmt.value is not None:
            candidates[fn.name] = fn

    if candidates:
        for fn in program.functions:
            _inline_block(fn.body, candidates, set())
        for decl in program.globals:
            if decl.init is not None:
                decl.init = _inline_expr(decl.init, candidates, set())
            if decl.init_list is not None:
                decl.init_list = [
                    _inline_expr(item, candidates, set()) for item in decl.init_list
                ]

    counts = _count_calls(program)
    void_candidates: dict[str, ast.FunctionDecl] = {
        fn.name: fn
        for fn in program.functions
        if _inlineable_void(fn, counts.get(fn.name, 0))
    }
    if void_candidates:
        for fn in program.functions:
            _inline_void_block(fn.body, void_candidates, set())
        # Inlining a void body can expose tiny return-only helpers.
        if candidates:
            for fn in program.functions:
                _inline_block(fn.body, candidates, set())

    # This must run even when there was nothing to inline: imported library
    # modules rely on unused functions and tables disappearing.
    extra = set(_qword_helpers_needed(program))
    extra.update(_float_helpers_needed(program, 32))
    extra.update(_float_helpers_needed(program, 16))
    _eliminate_dead(program, extra)
