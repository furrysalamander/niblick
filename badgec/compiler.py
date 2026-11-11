"""BadgeC semantic analysis and code generation.

Values are kept in fixed registers at expression boundaries:

    nibble    R1
    char      R1 (low), R2 (high)
    flashptr  R1 (low), R2 (mid), R3 (high)

Temporaries for nested expressions live in a small static scratch area
(0x20..0x3F).  Variables and arrays live from 0x40 upward.  The hardware
call stack is used for GOSUB/RET; tail calls become GOTO.
"""

from __future__ import annotations

import dataclasses
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from . import ast_nodes as ast
from .asm_link import AsmScan, scan_asm
from .asm_opt import asm_word_count, optimize_asm, word_sizes
from .asm_text import (
    NO_OPTIMIZE,
    NO_OPTIMIZE_BEGIN,
    NO_OPTIMIZE_END,
    PLACEHOLDER_RE,
    asm_function_references,
    code_part,
    has_file_marker,
    label_name,
    label_span,
)
from .inline import optimize as optimize_program
from .runtime_linker import (
    ROUTINE_LABELS,
    link_runtime,
    reachable_labels,
    routine_labels,
    runtime_stack_costs,
)
from .errors import BadgeCompileError, BadgeError, BadgeTypeError, location
from .types import (
    CHAR,
    DWORD,
    FLASHPTR,
    NIBBLE,
    VOID,
    WORD,
    Type,
    is_comparable,
    is_integer,
    promoted_mul_type,
    wider,
)


RAM_START = 0x40
RAM_END = 0xF0
TEMP_START = 0x20
# 0x38..0x3F is reserved for the 16-bit multiply/divide runtime scratch.
TEMP_END = 0x38

BUILTINS = {
    "uart_putc": VOID,
    "uart_getc": CHAR,
    "flash_read_char": CHAR,
    "flash_read_nibble": NIBBLE,
    "flash_next": CHAR,
    "out": VOID,
    "in": NIBBLE,
    "peek": NIBBLE,
    "poke": VOID,
    "gpio_set": VOID,
    "gpio_clear": VOID,
    "gpio_toggle": VOID,
    "gpio_test": NIBBLE,
    "peek8": CHAR,
    "poke8": VOID,
    "high_nibble": NIBBLE,
    "low_nibble": NIBBLE,
    "w5500_spi_tx_fast": VOID,
    "w5500_spi_xfer_fast": CHAR,
    "delay": VOID,
}


# Builtins that are implemented by a runtime label.
RUNTIME_ENTRY = {
    "uart_putc": "__bc_uart_putc",
    "uart_getc": "__bc_uart_getc",
    "flash_read_char": "__bc_flash_read_char",
    "flash_read_nibble": "__bc_flash_read_nibble",
    "flash_next": "__bc_flash_read_char_ptr",
    "gpio_set": "__bc_gpio_set",
    "gpio_clear": "__bc_gpio_clear",
    "gpio_toggle": "__bc_gpio_toggle",
    "gpio_test": "__bc_gpio_test",
    "delay": "__bc_delay",
    "w5500_spi_tx_fast": "__bc_w5500_spi_tx_fast",
    "w5500_spi_xfer_fast": "__bc_w5500_spi_xfer_fast",
}

_COMPARE_OPS = {"==", "!=", "<", "<=", ">", ">="}
_FLAG_INVERSE = {"C": "NC", "NC": "C", "Z": "NZ", "NZ": "Z"}
_FLAG_SWAP = {"<": ">", "<=": ">=", ">": "<", ">=": "<=", "==": "==", "!=": "!="}
_NIBBLE_BINARY = {"+": "ADD", "-": "SUB", "&": "AND", "|": "OR", "^": "XOR"}
_REGS = {
    1: ("R1",),
    2: ("R1", "R2"),
    4: ("R1", "R2", "R3", "R4"),
    8: ("R1", "R2", "R3", "R4", "R5", "R6", "R7", "R8"),
}
_SAVED_REGS = {1: ("R3",), 2: ("R3", "R4"), 4: ("R5", "R6", "R7", "R8")}


@dataclass
class VarSymbol:
    name: str
    type: Type
    address: Optional[int] = None
    array_len: Optional[int] = None
    is_const: bool = False
    flash_label: Optional[str] = None
    is_global: bool = False
    is_param: bool = False
    line: int = 0
    # Scalar ``const`` values are folded to immediates and have no RAM
    # storage.  ``address`` stays None for these symbols.
    const_value: Optional[int] = None


@dataclass
class FrameBlock:
    size: int
    members: set[str] = field(default_factory=set)


@dataclass
class FunctionSymbol:
    name: str
    decl: ast.FunctionDecl
    label: str
    params: list[VarSymbol] = field(default_factory=list)
    locals: list[VarSymbol] = field(default_factory=list)
    labels_seen: set[str] = field(default_factory=set)
    ram_base: int = 0
    block_end: int = 0
    local_next: int = 0
    param_size: int = 0
    overlay_depth: int = 0


class Scope:
    def __init__(self, parent: Optional["Scope"] = None) -> None:
        self.parent = parent
        self.symbols: dict[str, VarSymbol] = {}

    def define(self, symbol: VarSymbol, filename: str = "<input>") -> None:
        if symbol.name in self.symbols:
            raise BadgeCompileError(
                f"{location(filename, symbol.line)}: duplicate declaration of {symbol.name!r}"
            )
        self.symbols[symbol.name] = symbol

    def lookup(self, name: str) -> Optional[VarSymbol]:
        scope: Optional[Scope] = self
        while scope is not None:
            if name in scope.symbols:
                return scope.symbols[name]
            scope = scope.parent
        return None


class MemoryAllocator:
    def __init__(self, start: int = RAM_START, end: int = RAM_END) -> None:
        self.start = start
        self.end = end
        self.next = start

    def alloc(self, size: int, what: str, filename: str, line: int) -> int:
        if size <= 0:
            raise BadgeCompileError(f"{location(filename, line)}: cannot allocate zero-sized {what}")
        if self.next + size > self.end:
            raise BadgeCompileError(
                f"{location(filename, line)}: out of data RAM allocating {what} "
                f"({size} nibbles; {self.used()} of {self.end - self.start} already used)"
            )
        address = self.next
        self.next += size
        return address

    def used(self) -> int:
        return self.next - self.start


class TempAllocator:
    def __init__(self, start: int = TEMP_START, end: int = TEMP_END) -> None:
        self.start = start
        self.end = end
        self.top = start

    def mark(self) -> int:
        return self.top

    def reset(self, mark: int) -> None:
        self.top = mark

    def alloc(self, size: int, what: str, filename: str, line: int) -> int:
        if self.top + size > self.end:
            raise BadgeCompileError(
                f"{location(filename, line)}: expression is too complex for the temporary area "
                f"({size} nibbles needed, {self.end - self.top} free)"
            )
        address = self.top
        self.top += size
        return address


@dataclass
class FlashItem:
    label: str
    type: Type
    values: list[int]
    string_value: Optional[str] = None


class Compiler:
    def __init__(
        self,
        program: ast.Program,
        filename: str = "<input>",
        strip_runtime: bool = True,
        asm_optimize: bool = True,
    ) -> None:
        self.program = program
        self.filename = filename
        self.declared_functions = {fn.name: fn for fn in program.functions}
        self.strip_runtime = strip_runtime
        self.asm_optimize = asm_optimize
        self.used_runtime: set[str] = set()
        self.mem = MemoryAllocator()
        self.temp = TempAllocator()
        self.lines: list[str] = []
        self.globals: dict[str, VarSymbol] = {}
        self.functions: dict[str, FunctionSymbol] = {}
        self.global_inits: list[tuple[VarSymbol, ast.Expr]] = []
        self.flash: list[FlashItem] = []
        self.flash_counter = 0
        self.label_counter = 0
        self.asm_counter = 0
        self.current_source: tuple[str, int] | None = None
        self.last_emitted_source: tuple[str, int] | None = None
        self.current_function: Optional[FunctionSymbol] = None
        self.loop_stack: list[tuple[str, str]] = []  # (break label, continue label)
        self.calls: list[tuple[str, str, bool, int, str]] = []  # caller, callee, tail, line, file
        self.runtime_calls: list[tuple[str, str, int, str]] = []  # caller, runtime entry, line, file
        self.function_depths: dict[str, int] = {}
        self.deepest_path: list[str] = []
        self.stack_call_sites: list[dict] = []
        self.stack_warnings: list[str] = []
        self.runtime_costs: dict[str, int] = {}
        self.const_globals: dict[str, tuple[int, Type]] = {}
        self.max_call_depth = 0
        self.d32_scratch_addr: Optional[int] = None
        self.asm_text = ""
        self.runtime_text = ""
        self.linked_runtime: set[str] = set()
        self.asm_scans: list[AsmScan] = []
        self.all_asm_scans: list[AsmScan] = []
        self.emitted_asm_sources: list[ast.AsmSource] = []

    # ------------------------------------------------------------------
    # Entry point
    # ------------------------------------------------------------------

    def compile(self) -> str:
        if self.program.imports:
            raise BadgeCompileError(
                f"{self.filename}: imports must be resolved first; "
                "load the program with badgec.loader.load_program()"
            )
        optimize_program(self.program)
        self.prepare_globals()
        self.prepare_functions()
        if "main" not in self.functions:
            raise BadgeCompileError(f"{self.filename}: no main() function found")
        self.current_source = None
        self.emit("; BadgeC generated assembly")
        self.emit("GOTO fn_main")
        for fn in self.program.functions:
            self.compile_function(self.functions[fn.name])
        self.emit("")
        self.current_source = None
        self.all_asm_scans = self.scan_asm_sources(self.program.asm_sources)
        self.emitted_asm_sources = self.kept_asm_sources()
        self.asm_scans = self.scan_asm_sources(self.emitted_asm_sources)
        self.apply_asm_scans()
        self.validate_extern_labels()
        self.emit_asm_sources(self.emitted_asm_sources)
        self.emit("")
        runtime_full = Path(__file__).with_name("runtime").joinpath("runtime.asm").read_text()
        self.runtime_text = runtime_full
        if self.strip_runtime:
            self.linked_runtime = reachable_labels(runtime_full, self.used_runtime)
            runtime_text = link_runtime(runtime_full, self.used_runtime)
        else:
            self.linked_runtime = set(routine_labels(runtime_full))
            runtime_text = runtime_full
        base = self.d32_scratch_addr if self.d32_scratch_addr is not None else 0
        for index in range(24):
            token = f"__D32_{index:02d}"
            runtime_text = runtime_text.replace(token, f"0x{(base + index) & 0xFF:02X}")
        self.current_source = None
        self.emit("; @badgec-src-end")
        self.emit(runtime_text)
        self.emit_flash_data()
        self.validate_call_graph()
        asm = "\n".join(self.lines) + "\n"
        if self.asm_optimize:
            asm = optimize_asm(asm)
        self.asm_text = asm
        return asm

    def check(self, prune: bool = False) -> None:
        """Run semantic checks without requiring ``main`` or emitting output.

        This is the analysis entry point used by the editor.  When ``prune``
        is true and the program has a ``main`` function, dead-declaration
        elimination runs first so the check matches a real build.  Library
        analysis can leave it disabled to inspect every declaration.

        The caller should pass a copy of the program when pruning, because
        dead-declaration elimination mutates the AST.
        """

        if self.program.imports:
            raise BadgeCompileError(
                f"{self.filename}: imports must be resolved first; "
                "load the program with badgec.loader.load_program()"
            )
        if prune and "main" in {fn.name for fn in self.program.functions}:
            optimize_program(self.program)
        self.prepare_globals()
        self.prepare_functions()
        for fn in self.program.functions:
            self.compile_function(self.functions[fn.name])

    # ------------------------------------------------------------------
    # Declarations and allocation
    # ------------------------------------------------------------------

    def new_flash_label(self) -> str:
        label = f"F{self.flash_counter}"
        self.flash_counter += 1
        return label

    def new_label(self, hint: str = "L") -> str:
        self.label_counter += 1
        return f"{hint}{self.label_counter}"

    def new_asm_label(self) -> str:
        self.asm_counter += 1
        return f"__asm_{self.asm_counter}"

    def use_runtime(
        self,
        entry: str,
        line: int,
        caller: Optional[str] = None,
        filename: Optional[str] = None,
    ) -> None:
        """Record a runtime helper call for linking and stack reporting."""

        self.used_runtime.add(entry)
        caller_name = caller
        if caller_name is None and self.current_function is not None:
            caller_name = self.current_function.name
        if caller_name is not None:
            self.runtime_calls.append(
                (caller_name, entry, line, filename or self.filename)
            )

    @staticmethod
    def _width_mask(typ: Type) -> int:
        return (1 << (4 * max(typ.ram_size, 1))) - 1

    def fold_const_decl(
        self,
        target: Type,
        init: ast.Expr,
        scope: Optional[Scope],
        line: int,
    ) -> Optional[int]:
        """Fold a scalar const initializer, or return None if it is dynamic."""

        folded = self.eval_const(init, scope)
        if folded is None:
            return None
        value, typ = folded
        if typ.ram_size > target.ram_size:
            raise BadgeTypeError(
                f"{location(self.filename, line)}: cannot convert {typ} value {value} "
                f"to {target}"
            )
        return value & self._width_mask(target)

    def eval_const(
        self, expr: ast.Expr, scope: Optional[Scope]
    ) -> Optional[tuple[int, Type]]:
        """Return ``(value, type)`` when *expr* is a compile-time integer.

        The rules mirror :meth:`infer_type` and the runtime arithmetic, so a
        folded expression produces exactly the same bits as the generated
        code would.  Anything with a side effect or unknown value returns
        ``None`` and is compiled normally.
        """

        if isinstance(expr, ast.Number):
            value = int(expr.value)
            if value < 0 or value > 0xFFFFFFFF:
                raise BadgeCompileError(
                    f"{location(self.filename, expr.line)}: integer {value} does not fit in a dword"
                )
            if value <= 15:
                return value, NIBBLE
            if value <= 255:
                return value, CHAR
            if value <= 0xFFFF:
                return value, WORD
            return value, DWORD

        if isinstance(expr, ast.Var):
            symbol = scope.lookup(expr.name) if scope is not None else None
            if symbol is not None:
                if symbol.const_value is None:
                    return None
                return symbol.const_value & self._width_mask(symbol.type), symbol.type
            if expr.name in self.const_globals:
                value, typ = self.const_globals[expr.name]
                return value & self._width_mask(typ), typ
            symbol = self.globals.get(expr.name)
            if symbol is not None and symbol.const_value is not None:
                return symbol.const_value & self._width_mask(symbol.type), symbol.type
            return None

        if isinstance(expr, (ast.ToType, ast.Cast)):
            target = expr.type
            if not is_integer(target):
                return None
            folded = self.eval_const(expr.operand, scope)
            if folded is None:
                return None
            value, _ = folded
            return value & self._width_mask(target), target

        if isinstance(expr, ast.Unary):
            if expr.op == "&":
                return None
            folded = self.eval_const(expr.operand, scope)
            if folded is None:
                return None
            value, typ = folded
            if expr.op == "!":
                return (0 if value else 1), NIBBLE
            if expr.op == "~":
                return (~value) & self._width_mask(typ), typ
            if expr.op == "-":
                return (-value) & self._width_mask(typ), typ
            return None

        if isinstance(expr, ast.Binary):
            left = self.eval_const(expr.left, scope)
            right = self.eval_const(expr.right, scope)
            if left is None or right is None:
                return None
            left_value, left_type = left
            right_value, right_type = right

            if expr.op in ("==", "!=", "<", "<=", ">", ">="):
                result = {
                    "==": left_value == right_value,
                    "!=": left_value != right_value,
                    "<": left_value < right_value,
                    "<=": left_value <= right_value,
                    ">": left_value > right_value,
                    ">=": left_value >= right_value,
                }[expr.op]
                return (1 if result else 0), NIBBLE

            if expr.op in ("&&", "||"):
                result = (
                    bool(left_value) and bool(right_value)
                    if expr.op == "&&"
                    else bool(left_value) or bool(right_value)
                )
                return (1 if result else 0), NIBBLE

            if expr.op in ("<<", ">>"):
                width = 4 * left_type.ram_size
                if right_value >= width:
                    return 0, left_type
                value = (
                    (left_value << right_value)
                    if expr.op == "<<"
                    else (left_value >> right_value)
                )
                return value & self._width_mask(left_type), left_type

            if expr.op == "*":
                result_type = promoted_mul_type(wider(left_type, right_type))
                return (
                    (left_value * right_value) & self._width_mask(result_type),
                    result_type,
                )

            if expr.op in ("/", "%"):
                result_type = wider(left_type, right_type)
                if right_value == 0:
                    value = 0
                elif expr.op == "/":
                    value = left_value // right_value
                else:
                    value = left_value % right_value
                return value & self._width_mask(result_type), result_type

            if expr.op in ("+", "-", "&", "|", "^"):
                result_type = wider(left_type, right_type)
                value = {
                    "+": left_value + right_value,
                    "-": left_value - right_value,
                    "&": left_value & right_value,
                    "|": left_value | right_value,
                    "^": left_value ^ right_value,
                }[expr.op]
                return value & self._width_mask(result_type), result_type

        return None

    def prepare_const_globals(self) -> None:
        """Resolve scalar const globals before allocating any RAM.

        The fixpoint lets a const refer to another const declared later.
        Scalars that cannot be resolved are rejected by :meth:`prepare_globals`
        with a clear error rather than becoming silently mutable storage.
        """

        pending = [
            decl
            for decl in self.program.globals
            if decl.is_const
            and decl.array_len is None
            and decl.init is not None
            and is_integer(decl.type)
        ]
        if not pending:
            return

        while True:
            progress = False
            for decl in pending:
                if decl.name in self.const_globals:
                    continue
                assert decl.init is not None
                value = self.fold_const_decl(decl.type, decl.init, None, decl.line)
                if value is None:
                    continue
                self.const_globals[decl.name] = (value, decl.type)
                progress = True
            if not progress:
                break

    def prepare_globals(self) -> None:
        self.prepare_const_globals()
        for decl in self.program.globals:
            if decl.name in self.globals:
                raise BadgeCompileError(
                    f"{location(self.filename, decl.line)}: duplicate global {decl.name!r}"
                )

            if decl.is_const and decl.array_len is None:
                if not is_integer(decl.type):
                    raise BadgeTypeError(
                        f"{location(self.filename, decl.line)}: scalar const "
                        f"{decl.name!r} must have an integer type"
                    )
                if decl.name not in self.const_globals:
                    raise BadgeTypeError(
                        f"{location(self.filename, decl.line)}: initializer for const "
                        f"{decl.name!r} must be a compile-time constant"
                    )
                value, _ = self.const_globals[decl.name]
                self.globals[decl.name] = VarSymbol(
                    name=decl.name,
                    type=decl.type,
                    is_const=True,
                    is_global=True,
                    line=decl.line,
                    const_value=value,
                )
                continue

            if decl.is_const and decl.array_len is not None:
                label = self.new_flash_label()
                values = self.constant_flash_values(decl)
                self.flash.append(
                    FlashItem(label, decl.type, values, string_value=decl.init_string)
                )
                self.globals[decl.name] = VarSymbol(
                    name=decl.name,
                    type=decl.type,
                    array_len=decl.array_len,
                    is_const=True,
                    flash_label=label,
                    is_global=True,
                    line=decl.line,
                )
                continue

            size = (decl.array_len or 1) * decl.type.ram_size
            address = self.mem.alloc(size, decl.name, self.filename, decl.line)
            symbol = VarSymbol(
                name=decl.name,
                type=decl.type,
                address=address,
                array_len=decl.array_len,
                is_const=decl.is_const,
                is_global=True,
                line=decl.line,
            )
            self.globals[decl.name] = symbol
            if decl.init is not None:
                if decl.array_len is not None:
                    raise BadgeCompileError(
                        f"{location(self.filename, decl.line)}: array initializers are not supported yet"
                    )
                self.global_inits.append((symbol, decl.init))
            elif decl.init_list is not None:
                raise BadgeCompileError(
                    f"{location(self.filename, decl.line)}: array initializers are not supported yet"
                )

    def constant_flash_values(self, decl: ast.GlobalDecl) -> list[int]:
        mask = (1 << (4 * max(decl.type.ram_size, 1))) - 1
        values: list[int] = []
        if decl.init_string is not None:
            values = [ord(ch) & 0xFF for ch in decl.init_string]
            values.append(0xFF)
        elif decl.init_list is not None:
            for expr in decl.init_list:
                if not isinstance(expr, ast.Number):
                    raise BadgeCompileError(
                        f"{location(self.filename, expr.line)}: flash array initializers must be integer literals"
                    )
                values.append(int(expr.value) & mask)
        else:
            values = [0] * (decl.array_len or 0)

        if decl.array_len is not None:
            if len(values) > decl.array_len:
                raise BadgeCompileError(
                    f"{location(self.filename, decl.line)}: too many initializers for {decl.name!r}"
                )
            values.extend([0] * (decl.array_len - len(values)))
        return values

    def prepare_functions(self) -> None:
        for decl in self.program.functions:
            if decl.name in self.functions:
                raise BadgeCompileError(
                    f"{location(self.filename, decl.line)}: duplicate function {decl.name!r}"
                )
            if decl.name in BUILTINS:
                raise BadgeCompileError(
                    f"{location(self.filename, decl.line)}: cannot redefine builtin {decl.name!r}"
                )
            if decl.name == "main" and decl.params:
                raise BadgeCompileError(
                    f"{location(self.filename, decl.line)}: main() must not take parameters"
                )
            if decl.name == "main" and decl.is_extern:
                raise BadgeCompileError(
                    f"{location(self.filename, decl.line)}: main() cannot be extern"
                )
            fn = FunctionSymbol(
                name=decl.name,
                decl=decl,
                label=f"fn_{decl.name}",
            )
            for param in decl.params:
                fn.params.append(
                    VarSymbol(
                        name=param.name,
                        type=param.type,
                        address=None,
                        is_param=True,
                        line=param.line,
                    )
                )
            self.functions[decl.name] = fn
        self.allocate_function_slots()

    # ------------------------------------------------------------------
    # Function-slot overlay
    # ------------------------------------------------------------------

    def _function_footprint(self, decl: ast.FunctionDecl) -> int:
        size = sum(param.type.ram_size for param in decl.params)

        def walk_stmt(stmt: ast.Stmt) -> None:
            nonlocal size
            if isinstance(stmt, ast.VarDecl):
                if not (stmt.is_const and stmt.array_len is None):
                    size += (stmt.array_len or 1) * stmt.type.ram_size
            elif isinstance(stmt, ast.Block):
                for child in stmt.statements:
                    walk_stmt(child)
            elif isinstance(stmt, ast.If):
                walk_stmt(stmt.then_block)
                if stmt.else_block is not None:
                    walk_stmt(stmt.else_block)
            elif isinstance(stmt, ast.While):
                walk_stmt(stmt.body)
            elif isinstance(stmt, ast.For):
                if stmt.init is not None:
                    walk_stmt(stmt.init)
                walk_stmt(stmt.body)

        walk_stmt(decl.body)
        return size

    def _collect_expr_callees(
        self, expr: ast.Expr, known: set[str], callees: set[str]
    ) -> None:
        if isinstance(expr, ast.Call):
            if expr.name in known:
                callees.add(expr.name)
            for arg in expr.args:
                self._collect_expr_callees(arg, known, callees)
            return
        for data_field in dataclasses.fields(expr):
            value = getattr(expr, data_field.name)
            if isinstance(value, ast.Expr):
                self._collect_expr_callees(value, known, callees)
            elif isinstance(value, list):
                for item in value:
                    if isinstance(item, ast.Expr):
                        self._collect_expr_callees(item, known, callees)

    def _collect_shallow_stmt_callees(
        self, stmt: ast.Stmt, known: set[str], callees: set[str]
    ) -> None:
        """Collect callees evaluated directly by *stmt*, not by nested blocks."""
        if isinstance(stmt, ast.InlineAsm):
            callees.update(asm_function_references(stmt.text) & known)
            return
        for data_field in dataclasses.fields(stmt):
            value = getattr(stmt, data_field.name)
            if isinstance(value, ast.Expr):
                self._collect_expr_callees(value, known, callees)
            elif isinstance(value, ast.Block):
                continue
            elif isinstance(value, ast.Stmt):
                self._collect_shallow_stmt_callees(value, known, callees)
            elif isinstance(value, list):
                for item in value:
                    if isinstance(item, ast.Expr):
                        self._collect_expr_callees(item, known, callees)
                    elif isinstance(item, ast.Stmt):
                        self._collect_shallow_stmt_callees(item, known, callees)

    def _function_interference(self) -> dict[str, set[str]]:
        """Build a conservative frame-interference graph.

        A caller and its callee interfere.  Callees evaluated within the same
        statement also interfere: one callee's parameter slots can be live
        while another is called from an argument expression.  Sequential
        statements can share a frame.
        """
        from .inline import _collect_calls_expr

        known = set(self.functions)
        edges: dict[str, set[str]] = {name: set() for name in self.functions}
        calls: dict[str, set[str]] = {name: set() for name in self.functions}

        def add_edge(a: str, b: str) -> None:
            if a != b and a in edges and b in edges:
                edges[a].add(b)
                edges[b].add(a)

        def add_clique(caller: str, callees: set[str]) -> None:
            calls[caller].update(callees)
            for callee in callees:
                add_edge(caller, callee)
            items = sorted(callees)
            for index, left in enumerate(items):
                for right in items[index + 1 :]:
                    add_edge(left, right)

        def process_block(caller: str, block: ast.Block) -> None:
            for stmt in block.statements:
                callees: set[str] = set()
                self._collect_shallow_stmt_callees(stmt, known, callees)
                add_clique(caller, callees)
                if isinstance(stmt, ast.If):
                    process_block(caller, stmt.then_block)
                    if stmt.else_block is not None:
                        process_block(caller, stmt.else_block)
                elif isinstance(stmt, ast.While):
                    process_block(caller, stmt.body)
                elif isinstance(stmt, ast.For):
                    process_block(caller, stmt.body)

        for name, fn in self.functions.items():
            process_block(name, fn.decl.body)

        # Global initializers run in main.
        for _symbol, expr in self.global_inits:
            callees: set[str] = set()
            _collect_calls_expr(expr, callees)
            add_clique("main", callees & known)

        # Imported assembly routines can call BadgeC functions directly.
        for source in self.program.asm_sources:
            scan = scan_asm(source.text, source.path)
            for call in scan.calls:
                if call.caller_label.startswith("fn_") and call.target_label.startswith("fn_"):
                    caller = call.caller_label[3:]
                    target = call.target_label[3:]
                    if caller in known and target in known:
                        calls[caller].add(target)
                        add_edge(caller, target)

        # A function's frame is live for its entire subtree, so it cannot
        # share slots with any transitive callee.
        for name in self.functions:
            stack = list(calls.get(name, ()))
            seen: set[str] = set()
            while stack:
                callee = stack.pop()
                if callee in seen:
                    continue
                seen.add(callee)
                stack.extend(calls.get(callee, ()))
            for callee in seen:
                add_edge(name, callee)
        return edges

    def allocate_function_slots(self) -> None:
        footprints = {
            name: self._function_footprint(fn.decl)
            for name, fn in self.functions.items()
        }
        interference = self._function_interference()

        # Greedy weighted coloring, largest frame first.
        blocks: list[FrameBlock] = []
        assignment: dict[str, int] = {}
        order = sorted(
            self.functions,
            key=lambda name: (-footprints[name], name),
        )
        for name in order:
            size = footprints[name]
            placed = False
            for index, block in enumerate(blocks):
                if block.size < size:
                    continue
                if any(other in interference[name] for other in block.members):
                    continue
                block.members.add(name)
                assignment[name] = index
                placed = True
                break
            if not placed:
                assignment[name] = len(blocks)
                blocks.append(FrameBlock(size=size, members={name}))

        total = sum(block.size for block in blocks)
        if total:
            overlay_base = self.mem.alloc(
                total, "function slots", self.filename, 0
            )
        else:
            overlay_base = self.mem.next

        offsets: list[int] = []
        cursor = overlay_base
        for block in blocks:
            offsets.append(cursor)
            cursor += block.size

        for name, fn in self.functions.items():
            index = assignment[name]
            size = blocks[index].size
            fn.ram_base = offsets[index]
            fn.block_end = fn.ram_base + size
            fn.overlay_depth = index
            fn.param_size = sum(param.type.ram_size for param in fn.decl.params)
            if fn.param_size > size:
                raise BadgeCompileError(
                    f"{self.filename}: parameter footprint for {name!r} exceeds its function slot"
                )
            fn.local_next = fn.ram_base + fn.param_size
            address = fn.ram_base
            for param in fn.params:
                param.address = address
                address += param.type.ram_size

    # ------------------------------------------------------------------
    # Imported assembly
    # ------------------------------------------------------------------

    def scan_asm_sources(self, sources: list[ast.AsmSource]) -> list[AsmScan]:
        return [scan_asm(source.text, source.path) for source in sources]

    def kept_asm_sources(self) -> list[ast.AsmSource]:
        """Drop sections for asm entry points that are no longer reachable.

        A source file without any ``fn_*`` label (for example, a table-only
        module) is kept whole.  Otherwise the preamble before the first
        entry point is kept, and each ``fn_*`` section is kept only when its
        function survived dead-declaration elimination.  Dropped sections
        become blank lines so diagnostics keep the original file line
        numbers.
        """

        reachable = set(self.functions)
        kept: list[ast.AsmSource] = []

        for source in self.program.asm_sources:
            lines = source.text.splitlines()
            keep = [True] * len(lines)
            first_section: int | None = None
            current_keep = True
            kept_sections = False

            for index, line in enumerate(lines):
                label = label_name(line)
                if label is not None and label.startswith("fn_"):
                    if first_section is None:
                        first_section = index
                    current_keep = label[3:] in reachable
                    kept_sections = kept_sections or current_keep
                keep[index] = current_keep

            preamble_end = first_section if first_section is not None else len(lines)
            has_preamble_code = any(
                line.strip() and not line.lstrip().startswith(";")
                for line in lines[:preamble_end]
            )
            if first_section is not None and not kept_sections and not has_preamble_code:
                continue

            kept.append(
                ast.AsmSource(
                    source.path,
                    "\n".join(
                        line if keep[index] else ""
                        for index, line in enumerate(lines)
                    ),
                )
            )

        return kept

    def apply_asm_scans(self) -> None:
        """Turn assembly calls into linker and call-graph information."""

        for scan in self.asm_scans:
            for runtime_call in scan.runtime_calls:
                if runtime_call.target_label not in ROUTINE_LABELS:
                    raise BadgeCompileError(
                        f"{location(scan.path, runtime_call.line)}: unknown runtime routine "
                        f"{runtime_call.target_label!r}"
                    )
                caller = (
                    runtime_call.caller_label[3:]
                    if runtime_call.caller_label.startswith("fn_")
                    else runtime_call.caller_label
                )
                self.use_runtime(
                    runtime_call.target_label,
                    runtime_call.line,
                    caller=caller,
                    filename=scan.path,
                )

            for call in scan.calls:
                caller = (
                    call.caller_label[3:]
                    if call.caller_label.startswith("fn_")
                    else call.caller_label
                )
                callee = (
                    call.target_label[3:]
                    if call.target_label.startswith("fn_")
                    else call.target_label
                )
                if caller not in self.functions:
                    raise BadgeCompileError(
                        f"{location(scan.path, call.line)}: call from undeclared "
                        f"assembly routine {call.caller_label!r}"
                    )
                if callee not in self.functions:
                    raise BadgeCompileError(
                        f"{location(scan.path, call.line)}: call to undeclared "
                        f"function {call.target_label!r}; add an extern fn declaration"
                    )
                self.calls.append(
                    (caller, callee, call.tail, call.line, scan.path)
                )

    def validate_extern_labels(self) -> None:
        """Check that every asm entry point has a declaration, and vice versa."""

        locations: dict[str, tuple[str, int]] = {}
        for scan in self.all_asm_scans:
            for label, line in scan.labels.items():
                if label in locations:
                    path, first_line = locations[label]
                    raise BadgeCompileError(
                        f"{location(scan.path, line)}: duplicate assembly label "
                        f"{label!r} (already defined at {location(path, first_line)})"
                    )
                locations[label] = (scan.path, line)

        for label, (path, line) in locations.items():
            if label in {"__bc_flash_data"} or any(
                item.label == label for item in self.flash
            ):
                raise BadgeCompileError(
                    f"{location(path, line)}: assembly label {label!r} collides with "
                    "compiler-generated flash data"
                )
            if not label.startswith("fn_"):
                continue
            name = label[3:]
            declaration = self.declared_functions.get(name)
            if declaration is None:
                raise BadgeCompileError(
                    f"{location(path, line)}: assembly defines {label!r} but there is "
                    f"no extern fn {name}() declaration"
                )
            if not declaration.is_extern:
                raise BadgeCompileError(
                    f"{location(path, line)}: assembly redefines BadgeC function "
                    f"{name!r}"
                )

        for name, fn in self.functions.items():
            if fn.decl.is_extern and fn.label not in locations:
                raise BadgeCompileError(
                    f"{location(self.filename, fn.decl.line)}: extern function "
                    f"{name!r} has no {fn.label}: definition in imported assembly"
                )

    def _asm_scope(self, function_label: str) -> Scope:
        scope = Scope()
        fn = self.functions.get(function_label[3:])
        if fn is not None:
            for param in fn.params:
                if param.name not in scope.symbols:
                    scope.define(param, self.filename)
        return scope

    def _asm_symbol(
        self, name: str, scope: Scope, path: str, line: int
    ) -> VarSymbol:
        if "." in name:
            function_name, param_name = name.split(".", 1)
            fn = self.functions.get(function_name)
            if fn is None:
                raise BadgeCompileError(
                    f"{location(path, line)}: unknown function {function_name!r} "
                    f"in asm placeholder"
                )
            for param in fn.params:
                if param.name == param_name:
                    return param
            raise BadgeCompileError(
                f"{location(path, line)}: function {function_name!r} has no parameter "
                f"{param_name!r}"
            )

        symbol = scope.lookup(name)
        if symbol is None:
            symbol = self.globals.get(name)
        if symbol is None:
            raise BadgeCompileError(
                f"{location(path, line)}: unknown asm placeholder {name!r}"
            )
        return symbol

    def _asm_symbol_value(
        self, symbol: VarSymbol, path: str, line: int
    ) -> int | str:
        if symbol.const_value is not None:
            return symbol.const_value & self._width_mask(symbol.type)
        if symbol.flash_label is not None:
            return symbol.flash_label
        if symbol.address is not None:
            return symbol.address
        raise BadgeCompileError(
            f"{location(path, line)}: {symbol.name!r} has no address for inline assembly"
        )

    _ASM_OFFSET_RE = re.compile(
        r"^([A-Za-z_][A-Za-z0-9_]*(?:\.[A-Za-z_][A-Za-z0-9_]*)?)"
        r"\s*([+-])\s*(0[xX][0-9A-Fa-f]+|\d+)$"
    )
    _ASM_QUALIFIED_RE = re.compile(
        r"^([A-Za-z_][A-Za-z0-9_]*)\.([A-Za-z_][A-Za-z0-9_]*)$"
    )

    def resolve_asm_placeholder(
        self, text: str, scope: Scope, path: str, line: int
    ) -> str:
        text = text.strip()
        address_of = text.startswith("&")
        if address_of:
            text = text[1:].strip()

        if address_of:
            if not (
                re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", text)
                or self._ASM_QUALIFIED_RE.fullmatch(text)
            ):
                raise BadgeCompileError(
                    f"{location(path, line)}: '&' in an asm placeholder requires "
                    "a variable name"
                )
            symbol = self._asm_symbol(text, scope, path, line)
            if symbol.const_value is not None and symbol.address is None and symbol.flash_label is None:
                raise BadgeCompileError(
                    f"{location(path, line)}: cannot take the address of const "
                    f"{symbol.name!r}"
                )
            value = self._asm_symbol_value(symbol, path, line)
            return value if isinstance(value, str) else f"0x{value:X}"

        offset_match = self._ASM_OFFSET_RE.match(text)
        if offset_match is not None:
            base_name, operator, amount_text = offset_match.groups()
            symbol = self._asm_symbol(base_name, scope, path, line)
            base = self._asm_symbol_value(symbol, path, line)
            amount = int(amount_text, 0)
            if operator == "-":
                amount = -amount
            if isinstance(base, int):
                value = base + amount
                if value < 0:
                    raise BadgeCompileError(
                        f"{location(path, line)}: asm address expression "
                        f"{text!r} is negative"
                    )
                return f"0x{value:X}"
            if amount:
                raise BadgeCompileError(
                    f"{location(path, line)}: cannot add an offset to flash label "
                    f"{base!r} in an asm placeholder"
                )
            return base

        if re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", text) or self._ASM_QUALIFIED_RE.fullmatch(text):
            symbol = self._asm_symbol(text, scope, path, line)
            value = self._asm_symbol_value(symbol, path, line)
            return value if isinstance(value, str) else f"0x{value:X}"

        try:
            number = int(text, 0)
        except ValueError:
            number = None
        if number is not None:
            if number < 0:
                return str(number)
            return f"0x{number:X}"

        # Fall back to the normal constant-expression evaluator for things
        # like ``CONST << 2`` or ``(char)0x123``.
        from .lexer import tokenize
        from .parser import Parser

        try:
            parser = Parser(tokenize(text, path), path)
            expr = parser.parse_expression()
            if not parser.at_end():
                raise ValueError("trailing tokens")
        except Exception as exc:
            raise BadgeCompileError(
                f"{location(path, line)}: invalid asm placeholder {text!r}: {exc}"
            ) from exc

        folded = self.eval_const(expr, scope)
        if folded is None:
            raise BadgeCompileError(
                f"{location(path, line)}: asm placeholder {text!r} is not a "
                "compile-time constant or variable address"
            )
        value, _ = folded
        return f"0x{value:X}"

    def _substitute_placeholders(
        self, line: str, scope: Scope, path: str, line_number: int
    ) -> str:
        comment_index = line.find(";")
        if comment_index < 0:
            code = line
            comment = ""
        else:
            code = line[:comment_index]
            comment = line[comment_index:]

        if "${" not in code:
            return line

        def replace(match: re.Match[str]) -> str:
            return self.resolve_asm_placeholder(
                match.group(1), scope, path, line_number
            )

        return PLACEHOLDER_RE.sub(replace, code) + comment

    def emit_asm_sources(self, sources: list[ast.AsmSource]) -> None:
        self.current_source = None
        for source in sources:
            file_opaque = has_file_marker(source.text, NO_OPTIMIZE)
            self.emit(f"; imported assembly: {source.path}")
            if file_opaque:
                self.emit(NO_OPTIMIZE_BEGIN)

            scope = Scope()
            for line_number, line in enumerate(source.text.splitlines(), 1):
                if file_opaque and line.strip().lower() == NO_OPTIMIZE.lower():
                    continue

                label = label_name(line)
                if label is not None:
                    if label.startswith("fn_"):
                        scope = self._asm_scope(label)
                    elif not label.startswith("."):
                        scope = Scope()

                substituted = self._substitute_placeholders(
                    line, scope, source.path, line_number
                )
                stripped = line.strip().lower()
                if stripped in {
                    NO_OPTIMIZE.lower(),
                    NO_OPTIMIZE_BEGIN.lower(),
                    NO_OPTIMIZE_END.lower(),
                }:
                    self.emit(substituted)
                else:
                    self.emit(
                        f"{substituted} ; @badgec-src "
                        f"{source.path}:{line_number}"
                    )

            if file_opaque:
                self.emit(NO_OPTIMIZE_END)
            self.emit("")
        self.current_source = None
        self.emit("; @badgec-src-end")

    # ------------------------------------------------------------------
    # Function code generation
    # ------------------------------------------------------------------

    def compile_function(self, fn: FunctionSymbol) -> None:
        if fn.decl.is_extern:
            # The body and fn_* label come from an imported .asm file.
            return
        self.current_function = fn
        self.loop_stack = []
        scope = Scope()
        for param in fn.params:
            scope.define(param, self.filename)

        self.current_source = (
            fn.decl.file or self.filename,
            max(1, fn.decl.line),
        )
        self.emit(f"; function {fn.name}")
        self.emit(f"{fn.label}:")
        if fn.name == "main":
            for symbol, expr in self.global_inits:
                self.current_source = (
                    expr.file or self.filename,
                    max(1, expr.line),
                )
                typ = self.compile_expr(expr, scope)
                self.coerce(typ, symbol.type, expr.line)
                self.store_symbol(symbol, expr.line)

        self.compile_block(fn.decl.body, scope, tail=False)

        self.current_source = (
            fn.decl.file or self.filename,
            max(1, fn.decl.line),
        )
        if fn.name == "main":
            self.emit("JR -1")
        else:
            self.emit("RET R0, 0")
        self.emit("")
        self.current_function = None

    def compile_block(self, block: ast.Block, scope: Scope, tail: bool = False) -> None:
        child = Scope(scope)
        if not block.statements:
            return
        for index, stmt in enumerate(block.statements):
            is_tail = tail and index == len(block.statements) - 1
            self.compile_stmt(stmt, child, is_tail)

    def compile_stmt(self, stmt: ast.Stmt, scope: Scope, tail: bool = False) -> None:
        self.current_source = (
            stmt.file or self.filename,
            max(1, stmt.line),
        )
        if isinstance(stmt, ast.Block):
            self.compile_block(stmt, scope, tail=tail)

        elif isinstance(stmt, ast.VarDecl):
            self.compile_var_decl(stmt, scope)

        elif isinstance(stmt, ast.Assign):
            target_type = self.lvalue_type(stmt.target, scope)
            if target_type in (NIBBLE, CHAR, WORD, DWORD):
                limit = {NIBBLE: 15, CHAR: 255, WORD: 0xFFFF, DWORD: 0xFFFFFFFF}[target_type]
                if isinstance(stmt.value, ast.Number):
                    value = int(stmt.value.value)
                    if value > limit:
                        raise BadgeTypeError(
                            f"{location(self.filename, stmt.line)}: cannot convert value {value} to {target_type}"
                        )
                    if 0 <= value <= limit and self.store_constant(
                        stmt.target, scope, target_type, value, stmt.line
                    ):
                        return
                else:
                    folded = self.eval_const(stmt.value, scope)
                    if folded is not None:
                        value, value_type = folded
                        if value_type.ram_size > target_type.ram_size:
                            raise BadgeTypeError(
                                f"{location(self.filename, stmt.line)}: cannot convert {value_type} "
                                f"value {value} to {target_type}"
                            )
                        if value > limit:
                            raise BadgeTypeError(
                                f"{location(self.filename, stmt.line)}: cannot convert value {value} "
                                f"to {target_type}"
                            )
                        if self.store_constant(
                            stmt.target, scope, target_type, value, stmt.line
                        ):
                            return
            typ = self.compile_expr(stmt.value, scope)
            self.coerce(typ, target_type, stmt.line)

            if isinstance(stmt.target, ast.Index):
                # The index expression may clobber R1/R2, so park the value
                # while the address is computed.
                mark = self.temp.mark()
                temp_addr = self.temp.alloc(
                    target_type.ram_size, "assignment", self.filename, stmt.line
                )
                self.store_temp(target_type, temp_addr)
                self.store_index_from_temp(stmt.target, scope, target_type, temp_addr, stmt.line)
                self.temp.reset(mark)
            else:
                self.store_lvalue(stmt.target, scope, stmt.line)

        elif isinstance(stmt, ast.ExprStmt):
            if isinstance(stmt.expr, ast.Call):
                fn = self.current_function
                if (
                    tail
                    and fn is not None
                    and fn.decl.return_type is VOID
                    and stmt.expr.name in self.functions
                ):
                    self.compile_tail_call(stmt.expr, scope)
                    return
            self.compile_expr(stmt.expr, scope)

        elif isinstance(stmt, ast.InlineAsm):
            self.compile_inline_asm(stmt, scope)

        elif isinstance(stmt, ast.If):
            self.compile_if(stmt, scope, tail)

        elif isinstance(stmt, ast.While):
            self.compile_while(stmt, scope)

        elif isinstance(stmt, ast.For):
            self.compile_for(stmt, scope)

        elif isinstance(stmt, ast.Return):
            self.compile_return(stmt, scope)

        elif isinstance(stmt, ast.Break):
            if not self.loop_stack:
                raise BadgeCompileError(
                    f"{location(self.filename, stmt.line)}: break outside a loop"
                )
            self.emit(f"GOTO {self.loop_stack[-1][0]}")

        elif isinstance(stmt, ast.Continue):
            if not self.loop_stack:
                raise BadgeCompileError(
                    f"{location(self.filename, stmt.line)}: continue outside a loop"
                )
            self.emit(f"GOTO {self.loop_stack[-1][1]}")

        else:
            raise BadgeCompileError(
                f"{location(self.filename, getattr(stmt, 'line', 0))}: unsupported statement {type(stmt).__name__}"
            )

    def compile_inline_asm(self, stmt: ast.InlineAsm, scope: Scope) -> None:
        path = stmt.file or self.filename
        text = stmt.text
        base_line = stmt.line
        self._validate_inline_asm(stmt, path, base_line)

        wrapper = f"fn___inline_asm:\n{text}\n"
        try:
            scan = scan_asm(wrapper, path)
        except BadgeError as exc:
            raise self._shifted_asm_error(exc, base_line - 2) from exc

        caller = (
            self.current_function.name
            if self.current_function is not None
            else "main"
        )
        for call in scan.calls:
            source_line = call.line + base_line - 2
            callee = call.target_label[3:]
            if callee not in self.functions:
                raise BadgeCompileError(
                    f"{location(path, source_line)}: call to undeclared function "
                    f"{call.target_label!r}; add an extern fn declaration"
                )
            self.calls.append(
                (caller, callee, call.tail, source_line, path)
            )

        for runtime_call in scan.runtime_calls:
            source_line = runtime_call.line + base_line - 2
            if runtime_call.target_label not in ROUTINE_LABELS:
                raise BadgeCompileError(
                    f"{location(path, source_line)}: unknown runtime routine "
                    f"{runtime_call.target_label!r}"
                )
            self.use_runtime(
                runtime_call.target_label,
                source_line,
                caller=caller,
                filename=path,
            )

        self.emit(NO_OPTIMIZE_BEGIN)
        self.emit(f"; inline assembly (source line {stmt.line})")
        self.emit(f"{self.new_asm_label()}:")
        self.current_source = None
        for index, line in enumerate(text.splitlines(), 1):
            source_line = base_line + index - 1
            self.emit(
                self._substitute_placeholders(
                    line, scope, path, source_line
                )
                + f" ; @badgec-src {path}:{source_line}"
            )
        self.emit(NO_OPTIMIZE_END)

    def _validate_inline_asm(
        self, stmt: ast.InlineAsm, path: str, base_line: int
    ) -> None:
        for index, line in enumerate(stmt.text.splitlines(), 1):
            code = code_part(line).strip()
            if not code:
                continue
            source_line = base_line + index - 1
            label = label_span(line)
            if label is not None:
                if not label[0].startswith("."):
                    raise BadgeCompileError(
                        f"{location(path, source_line)}: inline asm labels must "
                        "start with '.'"
                    )
                continue
            op = code.split(None, 1)[0].upper()
            if op == "RET":
                raise BadgeCompileError(
                    f"{location(path, source_line)}: RET is not allowed in "
                    "inline asm; let the BadgeC function return normally"
                )

    def _shifted_asm_error(self, exc: BadgeError, delta: int) -> BadgeError:
        message = str(exc)
        match = re.match(
            r"^(?P<file>.+?):(?P<line>\d+)(?::(?P<column>\d+))?:\s*(?P<msg>.*)$",
            message,
        )
        if match is None:
            return exc
        line = max(1, int(match.group("line")) + delta)
        column = match.group("column")
        prefix = location(
            match.group("file"),
            line,
            int(column) if column is not None else None,
        )
        return BadgeCompileError(f"{prefix}: {match.group('msg')}")

    def alloc_local(self, size: int, what: str, filename: str, line: int) -> int:
        fn = self.current_function
        if fn is None:
            raise BadgeCompileError(
                f"{location(filename, line)}: local allocation outside a function"
            )
        if fn.local_next + size > fn.block_end:
            raise BadgeCompileError(
                f"{location(filename, line)}: function slot overflow allocating {what} "
                f"({size} nibbles; {fn.block_end - fn.local_next} free)"
            )
        address = fn.local_next
        fn.local_next += size
        return address

    def compile_var_decl(self, stmt: ast.VarDecl, scope: Scope) -> None:
        if stmt.name in scope.symbols:
            raise BadgeCompileError(
                f"{location(self.filename, stmt.line)}: duplicate local {stmt.name!r}"
            )
        if stmt.is_const and stmt.array_len is None:
            if not is_integer(stmt.type):
                raise BadgeTypeError(
                    f"{location(self.filename, stmt.line)}: scalar const "
                    f"{stmt.name!r} must have an integer type"
                )
            if stmt.init is None:
                raise BadgeTypeError(
                    f"{location(self.filename, stmt.line)}: const {stmt.name!r} "
                    f"requires an initializer"
                )
            value = self.fold_const_decl(stmt.type, stmt.init, scope, stmt.line)
            if value is None:
                raise BadgeTypeError(
                    f"{location(self.filename, stmt.line)}: initializer for const "
                    f"{stmt.name!r} must be a compile-time constant"
                )
            symbol = VarSymbol(
                name=stmt.name,
                type=stmt.type,
                is_const=True,
                line=stmt.line,
                const_value=value,
            )
            scope.define(symbol, self.filename)
            if self.current_function is not None:
                self.current_function.locals.append(symbol)
            return
        size = (stmt.array_len or 1) * stmt.type.ram_size
        address = self.alloc_local(size, stmt.name, self.filename, stmt.line)
        symbol = VarSymbol(
            name=stmt.name,
            type=stmt.type,
            address=address,
            array_len=stmt.array_len,
            is_const=stmt.is_const,
            line=stmt.line,
        )
        scope.define(symbol, self.filename)
        if self.current_function is not None:
            self.current_function.locals.append(symbol)
        if stmt.init is not None:
            if stmt.array_len is not None:
                raise BadgeCompileError(
                    f"{location(self.filename, stmt.line)}: local array initializers are not supported yet"
                )
            typ = self.compile_expr(stmt.init, scope)
            self.coerce(typ, stmt.type, stmt.line)
            self.store_symbol(symbol, stmt.line)

    def compile_if(self, stmt: ast.If, scope: Scope, tail: bool) -> None:
        end_label = self.new_label("endif")
        if stmt.else_block is not None:
            else_label = self.new_label("else")
            self.emit_jump_if_false(stmt.condition, else_label, scope)
            self.compile_block(stmt.then_block, scope, tail=tail)
            self.emit(f"GOTO {end_label}")
            self.emit(f"{else_label}:")
            self.compile_block(stmt.else_block, scope, tail=tail)
            self.emit(f"{end_label}:")
        else:
            self.emit_jump_if_false(stmt.condition, end_label, scope)
            self.compile_block(stmt.then_block, scope, tail=tail)
            self.emit(f"{end_label}:")

    def compile_while(self, stmt: ast.While, scope: Scope) -> None:
        start_label = self.new_label("while")
        end_label = self.new_label("endwhile")
        self.loop_stack.append((end_label, start_label))
        self.emit(f"{start_label}:")
        self.emit_jump_if_false(stmt.condition, end_label, scope)
        self.compile_block(stmt.body, scope)
        self.emit(f"GOTO {start_label}")
        self.emit(f"{end_label}:")
        self.loop_stack.pop()

    def compile_for(self, stmt: ast.For, scope: Scope) -> None:
        loop_scope = Scope(scope)
        if stmt.init is not None:
            self.compile_stmt(stmt.init, loop_scope)

        start_label = self.new_label("for")
        end_label = self.new_label("endfor")
        continue_label = self.new_label("continuefor")
        self.loop_stack.append((end_label, continue_label))

        self.emit(f"{start_label}:")
        if stmt.condition is not None:
            self.emit_jump_if_false(stmt.condition, end_label, loop_scope)
        self.compile_block(stmt.body, loop_scope)
        self.emit(f"{continue_label}:")
        if stmt.update is not None:
            self.compile_stmt(stmt.update, loop_scope)
        self.emit(f"GOTO {start_label}")
        self.emit(f"{end_label}:")
        self.loop_stack.pop()

    def compile_return(self, stmt: ast.Return, scope: Scope) -> None:
        fn = self.current_function
        assert fn is not None
        if stmt.value is not None and isinstance(stmt.value, ast.Call):
            if stmt.value.name in self.functions and fn.name != "main":
                self.compile_tail_call(stmt.value, scope)
                return

        if stmt.value is not None:
            typ = self.compile_expr(stmt.value, scope)
            if fn.decl.return_type is not VOID:
                self.coerce(typ, fn.decl.return_type, stmt.line)

        if fn.name == "main":
            self.emit("JR -1")
        else:
            self.emit("RET R0, 0")

    # ------------------------------------------------------------------
    # Expressions
    # ------------------------------------------------------------------

    def compile_expr(self, expr: ast.Expr, scope: Scope) -> Type:
        if not isinstance(expr, ast.Number):
            folded = self.eval_const(expr, scope)
            if folded is not None:
                value, typ = folded
                self._emit_immediate(value, _REGS[typ.ram_size])
                return typ

        if isinstance(expr, ast.Number):
            if expr.value < 0 or expr.value > 0xFFFFFFFF:
                raise BadgeCompileError(
                    f"{location(self.filename, expr.line)}: integer {expr.value} does not fit in a dword"
                )
            if expr.value <= 15:
                self.emit(f"MOV R1, {expr.value}")
                return NIBBLE
            if expr.value <= 255:
                self.emit(f"MOV R1, {expr.value & 0xF}")
                self.emit(f"MOV R2, {(expr.value >> 4) & 0xF}")
                return CHAR
            if expr.value <= 0xFFFF:
                for index in range(4):
                    self.emit(f"MOV R{index + 1}, {(expr.value >> (4 * index)) & 0xF}")
                return WORD
            for index in range(8):
                self.emit(f"MOV R{index + 1}, {(expr.value >> (4 * index)) & 0xF}")
            return DWORD

        if isinstance(expr, ast.StringLiteral):
            label = self.new_flash_string(expr.value)
            self.emit_flashptr(label)
            return FLASHPTR

        if isinstance(expr, ast.Var):
            symbol = self.lookup(expr.name, scope, expr.line)
            if symbol.array_len is not None:
                if symbol.flash_label is not None:
                    self.emit_flashptr(symbol.flash_label)
                    return FLASHPTR
                raise BadgeTypeError(
                    f"{location(self.filename, expr.line)}: array {expr.name!r} used without an index"
                )
            self.load_symbol(symbol, expr.line)
            return symbol.type

        if isinstance(expr, ast.Index):
            return self.compile_index(expr, scope)

        if isinstance(expr, ast.Unary):
            return self.compile_unary(expr, scope)

        if isinstance(expr, ast.Binary):
            return self.compile_binary(expr, scope)

        if isinstance(expr, ast.Call):
            return self.compile_call(expr, scope)

        if isinstance(expr, ast.AddressOf):
            return self.compile_address_of(expr, scope)

        if isinstance(expr, (ast.ToType, ast.Cast)):
            target = expr.type
            if not is_integer(target):
                raise BadgeTypeError(
                    f"{location(self.filename, expr.line)}: casts are only supported between integer types"
                )
            typ = self.compile_expr(expr.operand, scope)
            if not is_integer(typ):
                raise BadgeTypeError(
                    f"{location(self.filename, expr.line)}: cannot cast {typ} to {target}"
                )
            if typ.ram_size < target.ram_size:
                self.coerce(typ, target, expr.line)
            return target

        raise BadgeCompileError(
            f"{location(self.filename, getattr(expr, 'line', 0))}: unsupported expression {type(expr).__name__}"
        )

    def compile_unary(self, expr: ast.Unary, scope: Scope) -> Type:
        if expr.op == "&":
            return self.compile_address_of(ast.AddressOf(expr.operand, line=expr.line), scope)

        typ = self.compile_expr(expr.operand, scope)
        if expr.op == "!":
            if not is_integer(typ):
                raise BadgeTypeError(
                    f"{location(self.filename, expr.line)}: ! requires an integer operand"
                )
            self.emit_truth_value(typ)
            self.emit("MOV R0, R1")
            self.emit("CP R0, 0")
            self.emit("MOV R1, 0")
            self.emit("SKIP NZ, 1")
            self.emit("INC R1")
            self.emit("MOV R2, 0")
            return NIBBLE

        if expr.op == "~":
            if typ is NIBBLE:
                self._emit_complement(("R1",))
                return NIBBLE
            if typ is CHAR:
                self._emit_complement(("R1", "R2"))
                return CHAR
            if typ is WORD:
                self._emit_complement(("R1", "R2", "R3", "R4"))
                return WORD
            if typ is DWORD:
                self._emit_complement(("R1", "R2", "R3", "R4", "R5", "R6", "R7", "R8"))
                return DWORD
            raise BadgeTypeError(
                f"{location(self.filename, expr.line)}: ~ requires an integer operand"
            )

        if expr.op == "-":
            if typ is NIBBLE:
                self._emit_complement(("R1",))
                self.emit("INC R1")
                return NIBBLE
            if typ is CHAR:
                self._emit_complement(("R1", "R2"))
                self.emit("MOV R0, 1")
                self.emit("ADD R1, R0")
                self.emit("MOV R0, 0")
                self.emit("ADC R2, R0")
                return CHAR
            if typ is WORD:
                self._emit_complement(("R1", "R2", "R3", "R4"))
                self.emit("MOV R0, 1")
                self.emit("ADD R1, R0")
                self.emit("MOV R0, 0")
                self.emit("ADC R2, R0")
                self.emit("ADC R3, R0")
                self.emit("ADC R4, R0")
                return WORD
            if typ is DWORD:
                self._emit_complement(("R1", "R2", "R3", "R4", "R5", "R6", "R7", "R8"))
                self.emit("MOV R0, 1")
                self.emit("ADD R1, R0")
                self.emit("MOV R0, 0")
                for reg in ("R2", "R3", "R4", "R5", "R6", "R7", "R8"):
                    self.emit(f"ADC {reg}, R0")
                return DWORD
            raise BadgeTypeError(
                f"{location(self.filename, expr.line)}: unary - requires an integer operand"
            )

        raise BadgeCompileError(
            f"{location(self.filename, expr.line)}: unsupported unary operator {expr.op!r}"
        )

    def _emit_complement(self, regs: tuple[str, ...]) -> None:
        # CPL RX,RY = MOV RX,#15; SUB RX,RY.  RX must differ from RY, so
        # park the original in R0 first.
        for reg in regs:
            self.emit(f"MOV R0, {reg}")
            self.emit(f"CPL {reg}, R0")

    def compile_address_of(self, expr: ast.AddressOf, scope: Scope) -> Type:
        if not isinstance(expr.operand, ast.Var):
            raise BadgeTypeError(
                f"{location(self.filename, expr.line)}: & is only supported on simple variables"
            )
        symbol = self.lookup(expr.operand.name, scope, expr.line)
        if symbol.const_value is not None:
            raise BadgeTypeError(
                f"{location(self.filename, expr.line)}: cannot take the address of const "
                f"{symbol.name!r}"
            )
        if symbol.address is None:
            raise BadgeTypeError(
                f"{location(self.filename, expr.line)}: cannot take the address of {symbol.name!r}"
            )
        self.emit(f"MOV R1, {symbol.address & 0xF}")
        self.emit(f"MOV R2, {(symbol.address >> 4) & 0xF}")
        return CHAR

    def compile_binary(self, expr: ast.Binary, scope: Scope) -> Type:
        op = expr.op
        if op in ("&&", "||"):
            return self.compile_logical(expr, scope)
        if op in ("==", "!=", "<", "<=", ">", ">="):
            return self.compile_comparison(expr, scope)
        if op in ("+", "-", "&", "|", "^"):
            return self.compile_arithmetic(expr, scope)
        if op in ("<<", ">>"):
            return self.compile_shift(expr, scope)
        if op == "*":
            return self.compile_mul(expr, scope)
        if op in ("/", "%"):
            return self.compile_divmod(expr, scope)
        raise BadgeCompileError(
            f"{location(self.filename, expr.line)}: unsupported binary operator {op!r}"
        )

    def compile_logical(self, expr: ast.Binary, scope: Scope) -> Type:
        end_label = self.new_label("logicend")
        if expr.op == "&&":
            false_label = self.new_label("andfalse")
            self._emit_cond_branch(expr.left, false_label, when_true=False, scope=scope)
            self._emit_cond_branch(expr.right, false_label, when_true=False, scope=scope)
            self.emit("MOV R1, 1")
            self.emit(f"GOTO {end_label}")
            self.emit(f"{false_label}:")
            self.emit("MOV R1, 0")
            self.emit(f"{end_label}:")
            self.emit("MOV R2, 0")
            return NIBBLE

        true_label = self.new_label("ortrue")
        self._emit_cond_branch(expr.left, true_label, when_true=True, scope=scope)
        self._emit_cond_branch(expr.right, true_label, when_true=True, scope=scope)
        self.emit("MOV R1, 0")
        self.emit(f"GOTO {end_label}")
        self.emit(f"{true_label}:")
        self.emit("MOV R1, 1")
        self.emit(f"{end_label}:")
        self.emit("MOV R2, 0")
        return NIBBLE

    def compile_comparison(self, expr: ast.Binary, scope: Scope) -> Type:
        op = expr.op
        left = expr.left
        right = expr.right

        if isinstance(left, ast.Number) and isinstance(right, ast.Number):
            a, b = int(left.value), int(right.value)
            result = {
                "==": a == b,
                "!=": a != b,
                "<": a < b,
                "<=": a <= b,
                ">": a > b,
                ">=": a >= b,
            }[op]
            self.emit(f"MOV R1, {1 if result else 0}")
            self.emit("MOV R2, 0")
            return NIBBLE
        left_type = self.infer_type(left, scope)
        right_type = self.infer_type(right, scope)
        if not is_comparable(left_type) or not is_comparable(right_type):
            raise BadgeTypeError(
                f"{location(self.filename, expr.line)}: comparisons require integer operands"
            )
        common = wider(left_type, right_type)
        if common is DWORD:
            return self._compile_dword_comparison(left, right, op, scope, expr.line)
        if common is WORD:
            return self._compile_word_comparison(left, right, op, scope, expr.line)

        materialize = op
        if op == "<=":
            left, right = right, left
            materialize = ">="
        elif op == ">":
            left, right = right, left
            materialize = "<"

        mark = self.temp.mark()
        temp_addr = self.temp.alloc(common.ram_size, "comparison", self.filename, expr.line)

        typ = self.compile_expr(left, scope)
        self.coerce(typ, common, expr.line)
        self.store_temp(common, temp_addr)

        typ = self.compile_expr(right, scope)
        self.coerce(typ, common, expr.line)
        if common is NIBBLE:
            self.emit("MOV R2, R1")
        else:
            self.emit("MOV R3, R1")
            self.emit("MOV R4, R2")

        self.load_temp(common, temp_addr)
        if common is NIBBLE:
            self.emit("MOV R0, R1")
            self.emit("SUB R0, R2")
        else:
            self.emit("MOV R0, R2")
            self.emit("SUB R0, R4")
            self.emit("SKIP NZ, 2")
            self.emit("MOV R0, R1")
            self.emit("SUB R0, R3")

        self.emit("MOV R1, 0")
        inverse = {
            "==": "NZ",
            "!=": "Z",
            "<": "C",
            ">=": "NC",
        }[materialize]
        self.emit(f"SKIP {inverse}, 1")
        self.emit("INC R1")
        self.emit("MOV R2, 0")
        self.temp.reset(mark)
        return NIBBLE

    def compile_arithmetic(self, expr: ast.Binary, scope: Scope) -> Type:
        left_type = self.infer_type(expr.left, scope)
        right_type = self.infer_type(expr.right, scope)
        if not is_integer(left_type) or not is_integer(right_type):
            raise BadgeTypeError(
                f"{location(self.filename, expr.line)}: arithmetic requires integer operands"
            )

        common = wider(left_type, right_type)
        if common is DWORD:
            return self._compile_dword_arithmetic(expr, scope)

        width = common.ram_size
        mask = (1 << (4 * width)) - 1
        dest = _REGS[width]
        saved = _SAVED_REGS[width]

        if isinstance(expr.left, ast.Number) and isinstance(expr.right, ast.Number):
            a, b = int(expr.left.value), int(expr.right.value)
            result = {
                "+": a + b,
                "-": a - b,
                "&": a & b,
                "|": a | b,
                "^": a ^ b,
            }[expr.op]
            self._emit_immediate(result & mask, dest)
            return common

        if (
            expr.op in ("+", "-")
            and isinstance(expr.right, ast.Number)
            and int(expr.right.value) == 1
        ):
            typ = self.compile_expr(expr.left, scope)
            self.coerce(typ, common, expr.line)
            if common is NIBBLE:
                self.emit("INC R1" if expr.op == "+" else "DEC R1")
            elif common is CHAR:
                self.emit("MOV R0, 1")
                self.emit("ADD R1, R0" if expr.op == "+" else "SUB R1, R0")
                self.emit("MOV R0, 0")
                self.emit("ADC R2, R0" if expr.op == "+" else "SBB R2, R0")
            else:
                self.emit("MOV R0, 1")
                self.emit("ADD R1, R0" if expr.op == "+" else "SUB R1, R0")
                self.emit("MOV R0, 0")
                self.emit("ADC R2, R0" if expr.op == "+" else "SBB R2, R0")
                self.emit("ADC R3, R0" if expr.op == "+" else "SBB R3, R0")
                self.emit("ADC R4, R0" if expr.op == "+" else "SBB R4, R0")
            return common

        if isinstance(expr.right, ast.Number):
            typ = self.compile_expr(expr.left, scope)
            self.coerce(typ, common, expr.line)
            self._emit_immediate(int(expr.right.value) & mask, saved)
            self._emit_binary(expr.op, dest, saved)
            return common

        if self._is_leaf(expr.right):
            typ = self.compile_expr(expr.left, scope)
            self.coerce(typ, common, expr.line)
            self._move(dest, saved)
            typ = self.compile_expr(expr.right, scope)
            self.coerce(typ, common, expr.line)
            if expr.op == "-":
                # Left is in the saved registers and right in the result
                # registers; subtract in place and move the result back.
                self._emit_binary("-", saved, dest)
                self._move(saved, dest)
            else:
                self._emit_binary(expr.op, dest, saved)
            return common

        mark = self.temp.mark()
        temp_addr = self.temp.alloc(common.ram_size, "expression", self.filename, expr.line)

        typ = self.compile_expr(expr.left, scope)
        self.coerce(typ, common, expr.line)
        self.store_temp(common, temp_addr)

        typ = self.compile_expr(expr.right, scope)
        self.coerce(typ, common, expr.line)
        self._move(dest, saved)
        self.load_temp(common, temp_addr)
        self._emit_binary(expr.op, dest, saved)
        self.temp.reset(mark)
        return common

    def _compile_dword_arithmetic(self, expr: ast.Binary, scope: Scope) -> Type:
        op = expr.op
        mask = 0xFFFFFFFF

        if isinstance(expr.left, ast.Number) and isinstance(expr.right, ast.Number):
            a, b = int(expr.left.value), int(expr.right.value)
            result = {
                "+": a + b,
                "-": a - b,
                "&": a & b,
                "|": a | b,
                "^": a ^ b,
            }[op]
            self._emit_immediate(result & mask, _REGS[8])
            return DWORD

        if isinstance(expr.right, ast.Number):
            typ = self.compile_expr(expr.left, scope)
            self.coerce(typ, DWORD, expr.line)
            value = int(expr.right.value) & mask
            for index in range(8):
                self.emit(f"MOV R0, {(value >> (4 * index)) & 0xF}")
                if op == "+":
                    self.emit(f"{'ADD' if index == 0 else 'ADC'} R{index + 1}, R0")
                elif op == "-":
                    self.emit(f"{'SUB' if index == 0 else 'SBB'} R{index + 1}, R0")
                else:
                    self.emit(f"{_NIBBLE_BINARY[op]} R{index + 1}, R0")
            return DWORD

        mark = self.temp.mark()
        left_addr = self.temp.alloc(8, "dword expression", self.filename, expr.line)
        right_addr = self.temp.alloc(8, "dword expression", self.filename, expr.line)

        typ = self.compile_expr(expr.left, scope)
        self.coerce(typ, DWORD, expr.line)
        self.store_temp(DWORD, left_addr)
        typ = self.compile_expr(expr.right, scope)
        self.coerce(typ, DWORD, expr.line)
        self.store_temp(DWORD, right_addr)
        self.load_temp(DWORD, left_addr)

        for index in range(8):
            self.emit(f"MOV R0, [{right_addr + index}]")
            if op == "+":
                self.emit(f"{'ADD' if index == 0 else 'ADC'} R{index + 1}, R0")
            elif op == "-":
                self.emit(f"{'SUB' if index == 0 else 'SBB'} R{index + 1}, R0")
            else:
                self.emit(f"{_NIBBLE_BINARY[op]} R{index + 1}, R0")
        self.temp.reset(mark)
        return DWORD

    def _emit_immediate(self, value: int, regs: tuple[str, ...]) -> None:
        for index, reg in enumerate(regs):
            self.emit(f"MOV {reg}, {(value >> (4 * index)) & 0xF}")

    def _move(self, source: tuple[str, ...], target: tuple[str, ...]) -> None:
        for src, dst in zip(source, target):
            self.emit(f"MOV {dst}, {src}")

    def _emit_binary(
        self, op: str, dest: tuple[str, ...], source: tuple[str, ...]
    ) -> None:
        if op == "+":
            self.emit(f"ADD {dest[0]}, {source[0]}")
            for index in range(1, len(dest)):
                self.emit(f"ADC {dest[index]}, {source[index]}")
        elif op == "-":
            self.emit(f"SUB {dest[0]}, {source[0]}")
            for index in range(1, len(dest)):
                self.emit(f"SBB {dest[index]}, {source[index]}")
        else:
            instruction = _NIBBLE_BINARY[op]
            for dst, src in zip(dest, source):
                self.emit(f"{instruction} {dst}, {src}")

    def _emit_shift_left(self, typ: Type, count: int) -> None:
        for _ in range(count):
            self._emit_shift_step(typ, "<<")

    def _emit_shift_right(self, typ: Type, count: int) -> None:
        for _ in range(count):
            self._emit_shift_step(typ, ">>")

    def _emit_mask(self, typ: Type, mask: int) -> None:
        if typ is DWORD:
            for index in range(8):
                self.emit(f"MOV R0, {(mask >> (4 * index)) & 0xF}")
                self.emit(f"AND R{index + 1}, R0")
            return
        dest = _REGS[typ.ram_size]
        saved = _SAVED_REGS[typ.ram_size]
        self._emit_immediate(mask, saved)
        self._emit_binary("&", dest, saved)

    def _emit_shift_step(self, typ: Type, op: str) -> None:
        regs = _REGS[typ.ram_size]
        if op == "<<":
            self.emit(f"ADD {regs[0]}, {regs[0]}")
            for reg in regs[1:]:
                self.emit(f"ADC {reg}, {reg}")
        else:
            self.emit("ADD R0, 0")           # clear carry
            for reg in reversed(regs):
                self.emit(f"RRC {reg}")

    def compile_shift(self, expr: ast.Binary, scope: Scope) -> Type:
        left_type = self.infer_type(expr.left, scope)
        if not is_integer(left_type):
            raise BadgeTypeError(
                f"{location(self.filename, expr.line)}: shifts require an integer operand"
            )
        width = 4 * left_type.ram_size
        mask = (1 << width) - 1
        regs = _REGS[left_type.ram_size]

        if isinstance(expr.right, ast.Number):
            count = int(expr.right.value)
            if isinstance(expr.left, ast.Number):
                value = int(expr.left.value)
                result = ((value << count) & mask) if expr.op == "<<" else ((value >> count) & mask)
                self._emit_immediate(result, regs)
                return left_type

            typ = self.compile_expr(expr.left, scope)
            self.coerce(typ, left_type, expr.line)
            if count == 0:
                return left_type
            if count >= width:
                self._emit_immediate(0, regs)
            else:
                for _ in range(count):
                    self._emit_shift_step(left_type, expr.op)
            return left_type

        # Variable count: loop one shift at a time.  Counts must fit in a
        # char; the count is unsigned, so a large count just shifts to zero.
        right_type = self.infer_type(expr.right, scope)
        if not is_integer(right_type) or right_type.ram_size > CHAR.ram_size:
            raise BadgeTypeError(
                f"{location(self.filename, expr.line)}: shift counts must fit in a char"
            )

        mark = self.temp.mark()
        value_addr = self.temp.alloc(
            left_type.ram_size, "shift value", self.filename, expr.line
        )
        count_addr = self.temp.alloc(CHAR.ram_size, "shift count", self.filename, expr.line)

        typ = self.compile_expr(expr.left, scope)
        self.coerce(typ, left_type, expr.line)
        self.store_temp(left_type, value_addr)
        typ = self.compile_expr(expr.right, scope)
        self.coerce(typ, CHAR, expr.line)
        self.store_temp(CHAR, count_addr)
        self.load_temp(left_type, value_addr)

        loop_label = self.new_label("shift")
        done_label = self.new_label("shiftdone")
        self.emit(f"{loop_label}:")
        self.emit(f"MOV R0, [{count_addr}]")
        self.emit("MOV R9, R0")
        self.emit(f"MOV R0, [{count_addr + 1}]")
        self.emit("OR R0, R9")
        self.emit("CP R0, 0")
        self.emit("SKIP NZ, 2")
        self.emit(f"GOTO {done_label}")

        self._emit_shift_step(left_type, expr.op)

        self.emit("MOV R9, 1")
        self.emit(f"MOV R0, [{count_addr}]")
        self.emit("SUB R0, R9")
        self.emit(f"MOV [{count_addr}], R0")
        self.emit("MOV R9, 0")
        self.emit(f"MOV R0, [{count_addr + 1}]")
        self.emit("SBB R0, R9")
        self.emit(f"MOV [{count_addr + 1}], R0")
        self.emit(f"GOTO {loop_label}")
        self.emit(f"{done_label}:")
        self.temp.reset(mark)
        return left_type

    def ensure_d32_scratch(self) -> int:
        if self.d32_scratch_addr is None:
            self.d32_scratch_addr = self.mem.alloc(
                24, "dword math scratch", self.filename, 0
            )
        return self.d32_scratch_addr

    def compile_mul(self, expr: ast.Binary, scope: Scope) -> Type:
        left_type = self.infer_type(expr.left, scope)
        right_type = self.infer_type(expr.right, scope)
        if not is_integer(left_type) or not is_integer(right_type):
            raise BadgeTypeError(
                f"{location(self.filename, expr.line)}: multiplication requires integer operands"
            )
        common = wider(left_type, right_type)
        result = promoted_mul_type(common)
        mask = (1 << (4 * result.ram_size)) - 1

        left, right = expr.left, expr.right
        if isinstance(left, ast.Number) and not isinstance(right, ast.Number):
            left, right = right, left

        if isinstance(left, ast.Number) and isinstance(right, ast.Number):
            self._emit_immediate(
                (int(left.value) * int(right.value)) & mask, _REGS[result.ram_size]
            )
            return result

        if isinstance(right, ast.Number):
            constant = int(right.value)
            if constant == 0:
                typ = self.compile_expr(left, scope)
                self.coerce(typ, common, expr.line)
                self._emit_immediate(0, _REGS[result.ram_size])
                return result
            if constant == 1:
                typ = self.compile_expr(left, scope)
                self.coerce(typ, common, expr.line)
                self.coerce(common, result, expr.line)
                return result
            if constant & (constant - 1) == 0:
                typ = self.compile_expr(left, scope)
                self.coerce(typ, common, expr.line)
                self.coerce(common, result, expr.line)
                self._emit_shift_left(result, constant.bit_length() - 1)
                return result

        if common is DWORD:
            return self._compile_dword_mul(left, right, scope, expr.line)

        mark = self.temp.mark()
        temp_addr = self.temp.alloc(common.ram_size, "multiply", self.filename, expr.line)
        typ = self.compile_expr(left, scope)
        self.coerce(typ, common, expr.line)
        self.store_temp(common, temp_addr)

        typ = self.compile_expr(right, scope)
        self.coerce(typ, common, expr.line)
        if common is NIBBLE:
            self.emit("MOV R2, R1")
            self.load_temp(NIBBLE, temp_addr)
            self.use_runtime("__bc_mul4", expr.line)
            self.emit("GOSUB __bc_mul4")
        elif common is CHAR:
            self._move(("R1", "R2"), ("R3", "R4"))
            self.load_temp(CHAR, temp_addr)
            self.use_runtime("__bc_mul8", expr.line)
            self.emit("GOSUB __bc_mul8")
        else:
            self._move(("R1", "R2", "R3", "R4"), ("R5", "R6", "R7", "R8"))
            self.load_temp(WORD, temp_addr)
            self.use_runtime("__bc_mul16", expr.line)
            self.emit("GOSUB __bc_mul16")
        self.temp.reset(mark)
        return result

    def _compile_dword_mul(
        self, left: ast.Expr, right: ast.Expr, scope: Scope, line: int
    ) -> Type:
        mark = self.temp.mark()
        left_addr = self.temp.alloc(8, "dword multiply", self.filename, line)
        right_addr = self.temp.alloc(8, "dword multiply", self.filename, line)
        typ = self.compile_expr(left, scope)
        self.coerce(typ, DWORD, line)
        self.store_temp(DWORD, left_addr)
        typ = self.compile_expr(right, scope)
        self.coerce(typ, DWORD, line)
        self.store_temp(DWORD, right_addr)

        self.ensure_d32_scratch()
        self.emit(f"MOV R4, {(left_addr >> 4) & 0xF}")
        self.emit(f"MOV R5, {left_addr & 0xF}")
        self.emit(f"MOV R6, {(right_addr >> 4) & 0xF}")
        self.emit(f"MOV R7, {right_addr & 0xF}")
        self.use_runtime("__bc_mul32", line)
        self.emit("GOSUB __bc_mul32")
        self.temp.reset(mark)
        return DWORD

    def compile_divmod(self, expr: ast.Binary, scope: Scope) -> Type:
        left_type = self.infer_type(expr.left, scope)
        right_type = self.infer_type(expr.right, scope)
        if not is_integer(left_type) or not is_integer(right_type):
            raise BadgeTypeError(
                f"{location(self.filename, expr.line)}: division requires integer operands"
            )
        common = wider(left_type, right_type)
        width = common.ram_size
        mask = (1 << (4 * width)) - 1
        is_div = expr.op == "/"

        if isinstance(expr.left, ast.Number) and isinstance(expr.right, ast.Number):
            a, b = int(expr.left.value), int(expr.right.value)
            value = 0 if b == 0 else (a // b if is_div else a % b)
            self._emit_immediate(value & mask, _REGS[width])
            return common

        if isinstance(expr.right, ast.Number):
            constant = int(expr.right.value)
            if constant == 0:
                typ = self.compile_expr(expr.left, scope)
                self.coerce(typ, common, expr.line)
                self._emit_immediate(0, _REGS[width])
                return common
            if constant == 1:
                typ = self.compile_expr(expr.left, scope)
                self.coerce(typ, common, expr.line)
                if not is_div:
                    self._emit_immediate(0, _REGS[width])
                return common
            if constant & (constant - 1) == 0:
                shift = constant.bit_length() - 1
                typ = self.compile_expr(expr.left, scope)
                self.coerce(typ, common, expr.line)
                if is_div:
                    self._emit_shift_right(common, shift)
                else:
                    self._emit_mask(common, constant - 1)
                return common

        if common is DWORD:
            return self._compile_dword_divmod(expr.left, expr.right, is_div, scope, expr.line)

        mark = self.temp.mark()
        if common is NIBBLE:
            temp_common = CHAR
        else:
            temp_common = common
        temp_addr = self.temp.alloc(
            temp_common.ram_size, "divide", self.filename, expr.line
        )

        typ = self.compile_expr(expr.left, scope)
        self.coerce(typ, common, expr.line)
        self.coerce(common, temp_common, expr.line)
        self.store_temp(temp_common, temp_addr)

        typ = self.compile_expr(expr.right, scope)
        self.coerce(typ, common, expr.line)
        self.coerce(common, temp_common, expr.line)

        if common is NIBBLE:
            self._move(("R1", "R2"), ("R3", "R4"))
            self.load_temp(CHAR, temp_addr)
            self.use_runtime("__bc_divmod8", expr.line)
            self.emit("GOSUB __bc_divmod8")
            if is_div:
                self.temp.reset(mark)
                return NIBBLE
            self.emit("MOV R1, R3")
            self.temp.reset(mark)
            return NIBBLE

        if common is CHAR:
            self._move(("R1", "R2"), ("R3", "R4"))
            self.load_temp(CHAR, temp_addr)
            self.use_runtime("__bc_divmod8", expr.line)
            self.emit("GOSUB __bc_divmod8")
            if not is_div:
                self._move(("R3", "R4"), ("R1", "R2"))
            self.temp.reset(mark)
            return CHAR

        self._move(("R1", "R2", "R3", "R4"), ("R5", "R6", "R7", "R8"))
        self.load_temp(WORD, temp_addr)
        self.use_runtime("__bc_divmod16", expr.line)
        self.emit("GOSUB __bc_divmod16")
        if not is_div:
            self._move(("R5", "R6", "R7", "R8"), ("R1", "R2", "R3", "R4"))
        self.temp.reset(mark)
        return WORD

    def _compile_dword_divmod(
        self, left: ast.Expr, right: ast.Expr, is_div: bool, scope: Scope, line: int
    ) -> Type:
        mark = self.temp.mark()
        left_addr = self.temp.alloc(8, "dword divide", self.filename, line)
        right_addr = self.temp.alloc(8, "dword divide", self.filename, line)
        typ = self.compile_expr(left, scope)
        self.coerce(typ, DWORD, line)
        self.store_temp(DWORD, left_addr)
        typ = self.compile_expr(right, scope)
        self.coerce(typ, DWORD, line)
        self.store_temp(DWORD, right_addr)

        self.ensure_d32_scratch()
        self.emit(f"MOV R4, {(left_addr >> 4) & 0xF}")
        self.emit(f"MOV R5, {left_addr & 0xF}")
        self.emit(f"MOV R6, {(right_addr >> 4) & 0xF}")
        self.emit(f"MOV R7, {right_addr & 0xF}")
        self.use_runtime("__bc_divmod32", line)
        self.emit("GOSUB __bc_divmod32")
        self.load_temp(DWORD, left_addr if is_div else right_addr)
        self.temp.reset(mark)
        return DWORD

    def compile_index(self, expr: ast.Index, scope: Scope) -> Type:
        if not isinstance(expr.base, ast.Var):
            raise BadgeTypeError(
                f"{location(self.filename, expr.line)}: only named arrays can be indexed"
            )
        symbol = self.lookup(expr.base.name, scope, expr.line)
        if symbol.array_len is None:
            raise BadgeTypeError(
                f"{location(self.filename, expr.line)}: {symbol.name!r} is not an array"
            )

        if isinstance(expr.index, ast.Number):
            if expr.index.value < 0 or expr.index.value >= symbol.array_len:
                raise BadgeCompileError(
                    f"{location(self.filename, expr.line)}: index {expr.index.value} out of bounds "
                    f"for {symbol.name}[{symbol.array_len}]"
                )

        if symbol.flash_label is not None:
            self.compile_flash_addr(symbol, expr.index, scope, expr.line)
            if symbol.type is CHAR:
                self.use_runtime("__bc_flash_read_char", expr.line)
                self.emit("GOSUB __bc_flash_read_char")
                return CHAR
            if symbol.type is WORD:
                self.use_runtime("__bc_flash_read_word", expr.line)
                self.emit("GOSUB __bc_flash_read_word")
                return WORD
            if symbol.type is DWORD:
                self.ensure_d32_scratch()
                self.use_runtime("__bc_flash_read_dword", expr.line)
                self.emit("GOSUB __bc_flash_read_dword")
                return DWORD
            self.use_runtime("__bc_flash_read_nibble", expr.line)
            self.emit("GOSUB __bc_flash_read_nibble")
            return NIBBLE

        assert symbol.address is not None
        if isinstance(expr.index, ast.Number):
            # A constant index addresses fixed nibbles, so no R4:R5 address
            # calculation and no indirect access are needed.
            address = symbol.address + int(expr.index.value) * symbol.type.ram_size
            for index in range(symbol.type.ram_size):
                self.emit(f"MOV R0, [{address + index}]")
                self.emit(f"MOV R{index + 1}, R0")
            return symbol.type

        self.compile_ram_addr(symbol, expr.index, scope, expr.line)
        if symbol.type is NIBBLE:
            self.emit("MOV R0, [R4:R5]")
            self.emit("MOV R1, R0")
            return NIBBLE
        if symbol.type is CHAR:
            self.emit("MOV R0, [R4:R5]")
            self.emit("MOV R1, R0")
            self.emit("INC R5")
            self.emit("SKIP NC, 1")
            self.emit("INC R4")
            self.emit("MOV R0, [R4:R5]")
            self.emit("MOV R2, R0")
            return CHAR
        if symbol.type is DWORD:
            # A dword value occupies R1..R8, leaving no free address pair.
            # Stage the value through a temp buffer.
            mark = self.temp.mark()
            temp_addr = self.temp.alloc(8, "dword index", self.filename, expr.line)
            for index in range(8):
                self.emit("MOV R0, [R4:R5]")
                self.emit(f"MOV [{temp_addr + index}], R0")
                if index != 7:
                    self.emit("INC R5")
                    self.emit("SKIP NC, 1")
                    self.emit("INC R4")
            self.load_temp(DWORD, temp_addr)
            self.temp.reset(mark)
            return DWORD
        if symbol.type is WORD:
            # Copy the address away from R4:R5 first: R4 is also the value's
            # high nibble.
            self.emit("MOV R6, R4")
            self.emit("MOV R7, R5")
            for index in range(4):
                self.emit("MOV R0, [R6:R7]")
                self.emit(f"MOV R{index + 1}, R0")
                if index != 3:
                    self.emit("INC R7")
                    self.emit("SKIP NC, 1")
                    self.emit("INC R6")
            return WORD
        raise BadgeTypeError(
            f"{location(self.filename, expr.line)}: cannot index {symbol.type} array {symbol.name!r}"
        )

    # ------------------------------------------------------------------
    # Address helpers
    # ------------------------------------------------------------------

    def compile_ram_addr(self, symbol: VarSymbol, index: ast.Expr, scope: Scope, line: int) -> None:
        assert symbol.address is not None
        base = symbol.address
        index_type = self.compile_expr(index, scope)
        if index_type not in (NIBBLE, CHAR):
            raise BadgeTypeError(
                f"{location(self.filename, line)}: array index must be a nibble or char"
            )

        scale = symbol.type.ram_size
        if scale & (scale - 1):
            raise BadgeCompileError(
                f"{location(self.filename, line)}: unsupported array element size {scale}"
            )

        if scale == 1 and (base & 0xF) == 0:
            # The array starts on a 16-nibble page boundary, so a nibble
            # index never carries into the high address nibble.  A char
            # index only ever adds to the high nibble.
            self.emit(f"MOV R4, {(base >> 4) & 0xF}")
            self.emit("MOV R5, R1")
            if index_type is CHAR:
                self.emit("ADD R4, R2")
            return

        # Offset = index * scale in R4:R5.  scale is a power of two.
        self.emit("MOV R5, R1")
        if index_type is CHAR:
            self.emit("MOV R4, R2")
        else:
            self.emit("MOV R4, 0")
        for _ in range(scale.bit_length() - 1):
            self.emit("ADD R4, R4")
            self.emit("ADD R5, R5")
            self.emit("SKIP NC, 1")
            self.emit("INC R4")

        self.emit(f"MOV R0, {base & 0xF}")
        self.emit("ADD R5, R0")
        self.emit("SKIP NC, 1")
        self.emit("INC R4")
        self.emit(f"MOV R0, {(base >> 4) & 0xF}")
        self.emit("ADD R4, R0")

    def compile_flash_addr(self, symbol: VarSymbol, index: ast.Expr, scope: Scope, line: int) -> None:
        assert symbol.flash_label is not None
        index_type = self.compile_expr(index, scope)
        if index_type not in (NIBBLE, CHAR):
            raise BadgeTypeError(
                f"{location(self.filename, line)}: flash array index must be a nibble or char"
            )

        scale = symbol.type.flash_size
        if scale < 1 or scale & (scale - 1):
            raise BadgeCompileError(
                f"{location(self.filename, line)}: unsupported flash element size {scale}"
            )
        self.emit("MOV R4, R1")
        if index_type is CHAR:
            self.emit("MOV R5, R2")
        else:
            self.emit("MOV R5, 0")
        for _ in range(scale.bit_length() - 1):
            self.emit("ADD R5, R5")
            self.emit("ADD R4, R4")
            self.emit("SKIP NC, 1")
            self.emit("INC R5")

        self.emit_flashptr(symbol.flash_label)
        self.emit("ADD R1, R4")
        self.emit("MOV R0, 0")
        self.emit("ADC R2, R0")
        self.emit("ADC R3, R0")
        self.emit("ADD R2, R5")
        self.emit("MOV R0, 0")
        self.emit("ADC R3, R0")

    # ------------------------------------------------------------------
    # Calls
    # ------------------------------------------------------------------

    def compile_call(self, expr: ast.Call, scope: Scope) -> Type:
        if expr.name in BUILTINS:
            return self.compile_builtin(expr, scope)
        fn = self.functions.get(expr.name)
        if fn is None:
            raise BadgeCompileError(
                f"{location(self.filename, expr.line)}: unknown function {expr.name!r}"
            )
        if len(expr.args) != len(fn.params):
            raise BadgeTypeError(
                f"{location(self.filename, expr.line)}: {expr.name} expects {len(fn.params)} "
                f"arguments, got {len(expr.args)}"
            )

        for arg, param in zip(expr.args, fn.params):
            typ = self.compile_expr(arg, scope)
            self.coerce(typ, param.type, arg.line)
            self.store_symbol(param, arg.line)

        self.emit(f"GOSUB {fn.label}")
        assert self.current_function is not None
        self.calls.append(
            (self.current_function.name, fn.name, False, expr.line, self.filename)
        )
        return fn.decl.return_type

    def compile_tail_call(self, expr: ast.Call, scope: Scope) -> Type:
        fn = self.functions.get(expr.name)
        if fn is None:
            raise BadgeCompileError(
                f"{location(self.filename, expr.line)}: cannot tail-call unknown function {expr.name!r}"
            )
        if len(expr.args) != len(fn.params):
            raise BadgeTypeError(
                f"{location(self.filename, expr.line)}: {expr.name} expects {len(fn.params)} "
                f"arguments, got {len(expr.args)}"
            )

        mark = self.temp.mark()
        temp_addresses: list[int] = []
        for arg, param in zip(expr.args, fn.params):
            typ = self.compile_expr(arg, scope)
            self.coerce(typ, param.type, arg.line)
            address = self.temp.alloc(param.type.ram_size, "tail argument", self.filename, arg.line)
            self.store_temp(param.type, address)
            temp_addresses.append(address)

        for address, param in zip(temp_addresses, fn.params):
            self.load_temp(param.type, address)
            self.store_symbol(param, expr.line)

        self.emit(f"GOTO {fn.label}")
        assert self.current_function is not None
        self.calls.append(
            (self.current_function.name, fn.name, True, expr.line, self.filename)
        )
        self.temp.reset(mark)
        return fn.decl.return_type

    def _constant_nibble(self, expr: ast.Expr, scope: Scope) -> Optional[int]:
        folded = self.eval_const(expr, scope)
        if folded is None:
            return None
        value, typ = folded
        if typ is NIBBLE and 0 <= value <= 15:
            return value
        return None

    def _constant_address(self, expr: ast.Expr, scope: Scope) -> Optional[int]:
        folded = self.eval_const(expr, scope)
        if folded is None:
            return None
        value, _typ = folded
        if 0 <= value <= 0xFF:
            return value
        return None

    def compile_builtin(self, expr: ast.Call, scope: Scope) -> Type:
        name = expr.name
        entry = RUNTIME_ENTRY.get(name)

        constant_mask = None
        if name in ("gpio_set", "gpio_clear", "gpio_toggle", "gpio_test") and len(expr.args) == 1:
            constant_mask = self._constant_nibble(expr.args[0], scope)
        fast_gpio = constant_mask is not None and (
            name != "gpio_test" or constant_mask.bit_count() <= 1
        )
        if entry is not None and not fast_gpio:
            self.use_runtime(entry, expr.line)

        if name == "uart_putc":
            self.require_args(expr, 1)
            typ = self.compile_expr(expr.args[0], scope)
            self.coerce(typ, CHAR, expr.line)
            self.emit("GOSUB __bc_uart_putc")
            return VOID

        if name == "uart_getc":
            self.require_args(expr, 0)
            self.emit("GOSUB __bc_uart_getc")
            return CHAR

        if name == "flash_read_char":
            self.require_args(expr, 1)
            typ = self.compile_expr(expr.args[0], scope)
            self.coerce(typ, FLASHPTR, expr.line)
            self.emit("GOSUB __bc_flash_read_char")
            return CHAR

        if name == "flash_read_nibble":
            self.require_args(expr, 1)
            typ = self.compile_expr(expr.args[0], scope)
            self.coerce(typ, FLASHPTR, expr.line)
            self.emit("GOSUB __bc_flash_read_nibble")
            return NIBBLE

        if name == "flash_next":
            self.require_args(expr, 1)
            arg = expr.args[0]
            if not isinstance(arg, ast.AddressOf) or not isinstance(arg.operand, ast.Var):
                raise BadgeTypeError(
                    f"{location(self.filename, expr.line)}: flash_next expects &variable"
                )
            symbol = self.lookup(arg.operand.name, scope, expr.line)
            if symbol.type is not FLASHPTR or symbol.address is None or symbol.is_const:
                raise BadgeTypeError(
                    f"{location(self.filename, expr.line)}: flash_next expects a mutable flashptr variable"
                )
            addr = symbol.address
            self.emit(f"MOV R0, [{addr}]")
            self.emit("MOV R6, R0")
            self.emit(f"MOV R0, [{addr + 1}]")
            self.emit("MOV R7, R0")
            self.emit(f"MOV R0, [{addr + 2}]")
            self.emit("MOV R8, R0")
            self.emit("GOSUB __bc_flash_read_char_ptr")
            # Store the advanced pointer without disturbing R1/R2.
            self.emit("MOV R0, R6")
            self.emit(f"MOV [{addr}], R0")
            self.emit("MOV R0, R7")
            self.emit(f"MOV [{addr + 1}], R0")
            self.emit("MOV R0, R8")
            self.emit(f"MOV [{addr + 2}], R0")
            return CHAR

        if name in ("gpio_set", "gpio_clear", "gpio_toggle", "gpio_test"):
            self.require_args(expr, 1)
            mask = self._constant_nibble(expr.args[0], scope)
            if mask is not None:
                if name == "gpio_test":
                    if mask == 0:
                        self.emit("MOV R1, 0")
                        return NIBBLE
                    if mask.bit_count() == 1:
                        bit = mask.bit_length() - 1
                        self.emit(f"BIT R3, {bit}")
                        self.emit("MOV R1, 0")
                        self.emit("SKIP Z, 1")
                        self.emit("INC R1")
                        return NIBBLE
                else:
                    instruction = {
                        "gpio_set": "BSET",
                        "gpio_clear": "BCLR",
                        "gpio_toggle": "BTG",
                    }[name]
                    for bit in range(4):
                        if mask & (1 << bit):
                            self.emit(f"{instruction} R3, {bit}")
                    return VOID

            typ = self.compile_expr(expr.args[0], scope)
            self.coerce(typ, NIBBLE, expr.line)
            self.emit(f"GOSUB __bc_{name}")
            return NIBBLE if name == "gpio_test" else VOID

        if name == "w5500_spi_tx_fast":
            self.require_args(expr, 1)
            typ = self.compile_expr(expr.args[0], scope)
            self.coerce(typ, CHAR, expr.line)
            self.emit("GOSUB __bc_w5500_spi_tx_fast")
            return VOID

        if name == "w5500_spi_xfer_fast":
            self.require_args(expr, 1)
            typ = self.compile_expr(expr.args[0], scope)
            self.coerce(typ, CHAR, expr.line)
            self.emit("GOSUB __bc_w5500_spi_xfer_fast")
            return CHAR

        if name == "delay":
            self.require_args(expr, 1)
            typ = self.compile_expr(expr.args[0], scope)
            self.coerce(typ, NIBBLE, expr.line)
            self.emit("GOSUB __bc_delay")
            return VOID

        if name == "out":
            self.require_args(expr, 1)
            typ = self.compile_expr(expr.args[0], scope)
            self.coerce(typ, NIBBLE, expr.line)
            self.emit("MOV R0, R1")
            self.emit("MOV [0x0A], R0")
            return VOID

        if name == "in":
            self.require_args(expr, 0)
            self.emit("MOV R0, [0x0B]")
            self.emit("MOV R1, R0")
            return NIBBLE

        if name == "peek":
            self.require_args(expr, 1)
            constant_addr = self._constant_address(expr.args[0], scope)
            if constant_addr is not None:
                self.emit(f"MOV R0, [0x{constant_addr:02X}]")
                self.emit("MOV R1, R0")
                return NIBBLE
            typ = self.compile_expr(expr.args[0], scope)
            self.coerce(typ, CHAR, expr.line)
            self.emit("MOV R4, R2")
            self.emit("MOV R5, R1")
            self.emit("MOV R0, [R4:R5]")
            self.emit("MOV R1, R0")
            return NIBBLE

        if name == "poke":
            self.require_args(expr, 2)
            constant_addr = self._constant_address(expr.args[0], scope)
            if constant_addr is not None:
                typ = self.compile_expr(expr.args[1], scope)
                self.coerce(typ, NIBBLE, expr.line)
                self.emit("MOV R0, R1")
                self.emit(f"MOV [0x{constant_addr:02X}], R0")
                return VOID
            mark = self.temp.mark()
            temp_addr = self.temp.alloc(1, "poke value", self.filename, expr.line)
            typ = self.compile_expr(expr.args[1], scope)
            self.coerce(typ, NIBBLE, expr.line)
            self.store_temp(NIBBLE, temp_addr)
            typ = self.compile_expr(expr.args[0], scope)
            self.coerce(typ, CHAR, expr.line)
            self.emit("MOV R4, R2")
            self.emit("MOV R5, R1")
            self.load_temp(NIBBLE, temp_addr)
            self.emit("MOV R0, R1")
            self.emit("MOV [R4:R5], R0")
            self.temp.reset(mark)
            return VOID

        if name == "peek8":
            self.require_args(expr, 1)
            constant_addr = self._constant_address(expr.args[0], scope)
            if constant_addr is not None:
                high_addr = (constant_addr + 1) & 0xFF
                self.emit(f"MOV R0, [0x{constant_addr:02X}]")
                self.emit("MOV R1, R0")
                self.emit(f"MOV R0, [0x{high_addr:02X}]")
                self.emit("MOV R2, R0")
                return CHAR
            typ = self.compile_expr(expr.args[0], scope)
            self.coerce(typ, CHAR, expr.line)
            self.emit("MOV R4, R2")
            self.emit("MOV R5, R1")
            self.emit("MOV R0, [R4:R5]")
            self.emit("MOV R1, R0")
            self.emit("INC R5")
            self.emit("SKIP NC, 1")
            self.emit("INC R4")
            self.emit("MOV R0, [R4:R5]")
            self.emit("MOV R2, R0")
            return CHAR

        if name == "poke8":
            self.require_args(expr, 2)
            constant_addr = self._constant_address(expr.args[0], scope)
            if constant_addr is not None:
                high_addr = (constant_addr + 1) & 0xFF
                typ = self.compile_expr(expr.args[1], scope)
                self.coerce(typ, CHAR, expr.line)
                self.emit("MOV R0, R1")
                self.emit(f"MOV [0x{constant_addr:02X}], R0")
                self.emit("MOV R0, R2")
                self.emit(f"MOV [0x{high_addr:02X}], R0")
                return VOID
            mark = self.temp.mark()
            temp_addr = self.temp.alloc(2, "poke8 value", self.filename, expr.line)
            typ = self.compile_expr(expr.args[1], scope)
            self.coerce(typ, CHAR, expr.line)
            self.store_temp(CHAR, temp_addr)

            typ = self.compile_expr(expr.args[0], scope)
            self.coerce(typ, CHAR, expr.line)
            self.emit("MOV R4, R2")
            self.emit("MOV R5, R1")
            self.load_temp(CHAR, temp_addr)
            self.emit("MOV R0, R1")
            self.emit("MOV [R4:R5], R0")
            self.emit("INC R5")
            self.emit("SKIP NC, 1")
            self.emit("INC R4")
            self.emit("MOV R0, R2")
            self.emit("MOV [R4:R5], R0")
            self.temp.reset(mark)
            return VOID

        if name in ("high_nibble", "low_nibble"):
            self.require_args(expr, 1)
            typ = self.compile_expr(expr.args[0], scope)
            self.coerce(typ, CHAR, expr.line)
            if name == "high_nibble":
                self.emit("MOV R1, R2")
            return NIBBLE

        raise BadgeCompileError(
            f"{location(self.filename, expr.line)}: unsupported builtin {name!r}"
        )

    def require_args(self, expr: ast.Call, count: int) -> None:
        if len(expr.args) != count:
            raise BadgeTypeError(
                f"{location(self.filename, expr.line)}: {expr.name} expects {count} "
                f"arguments, got {len(expr.args)}"
            )

    # ------------------------------------------------------------------
    # Value movement
    # ------------------------------------------------------------------

    def lookup(self, name: str, scope: Scope, line: int) -> VarSymbol:
        symbol = scope.lookup(name)
        if symbol is None:
            symbol = self.globals.get(name)
        if symbol is None:
            raise BadgeCompileError(
                f"{location(self.filename, line)}: unknown identifier {name!r}"
            )
        return symbol

    def lvalue_type(self, target: ast.Expr, scope: Scope) -> Type:
        if isinstance(target, ast.Var):
            symbol = self.lookup(target.name, scope, target.line)
            if symbol.array_len is not None:
                raise BadgeTypeError(
                    f"{location(self.filename, target.line)}: cannot assign to array {target.name!r}"
                )
            if symbol.is_const:
                raise BadgeTypeError(
                    f"{location(self.filename, target.line)}: cannot assign to const {target.name!r}"
                )
            return symbol.type
        if isinstance(target, ast.Index):
            if not isinstance(target.base, ast.Var):
                raise BadgeTypeError(
                    f"{location(self.filename, target.line)}: only named arrays can be indexed"
                )
            symbol = self.lookup(target.base.name, scope, target.line)
            if symbol.array_len is None:
                raise BadgeTypeError(
                    f"{location(self.filename, target.line)}: {symbol.name!r} is not an array"
                )
            if symbol.is_const:
                raise BadgeTypeError(
                    f"{location(self.filename, target.line)}: cannot write to const array {symbol.name!r}"
                )
            return symbol.type
        raise BadgeTypeError(
            f"{location(self.filename, target.line)}: invalid assignment target"
        )

    def store_constant(
        self, target: ast.Expr, scope: Scope, typ: Type, value: int, line: int
    ) -> bool:
        """Write a constant directly, skipping the R1/R2 staging moves."""

        address: Optional[int] = None
        if isinstance(target, ast.Var):
            symbol = self.lookup(target.name, scope, target.line)
            address = symbol.address
        elif isinstance(target, ast.Index) and isinstance(target.base, ast.Var):
            symbol = self.lookup(target.base.name, scope, target.line)
            if not isinstance(target.index, ast.Number) or symbol.address is None:
                return False
            index = int(target.index.value)
            assert symbol.array_len is not None
            if index < 0 or index >= symbol.array_len:
                raise BadgeCompileError(
                    f"{location(self.filename, line)}: index {index} out of bounds "
                    f"for {symbol.name}[{symbol.array_len}]"
                )
            address = symbol.address + index * typ.ram_size
        else:
            return False

        if address is None:
            return False
        for index in range(typ.ram_size):
            self.emit(f"MOV R0, {(value >> (4 * index)) & 0xF}")
            self.emit(f"MOV [{address + index}], R0")
        return True

    def store_lvalue(self, target: ast.Expr, scope: Scope, line: int) -> None:
        if isinstance(target, ast.Var):
            symbol = self.lookup(target.name, scope, target.line)
            self.store_symbol(symbol, line)
            return
        if isinstance(target, ast.Index):
            assert isinstance(target.base, ast.Var)
            symbol = self.lookup(target.base.name, scope, target.line)
            mark = self.temp.mark()
            temp_addr = self.temp.alloc(
                symbol.type.ram_size, "assignment", self.filename, line
            )
            self.store_temp(symbol.type, temp_addr)
            self.store_index_from_temp(target, scope, symbol.type, temp_addr, line)
            self.temp.reset(mark)
            return
        raise BadgeTypeError(
            f"{location(self.filename, line)}: invalid assignment target"
        )

    def store_index_from_temp(
        self,
        target: ast.Index,
        scope: Scope,
        typ: Type,
        temp_addr: int,
        line: int,
    ) -> None:
        assert isinstance(target.base, ast.Var)
        symbol = self.lookup(target.base.name, scope, target.line)
        if isinstance(target.index, ast.Number) and symbol.address is not None:
            address = symbol.address + int(target.index.value) * typ.ram_size
            self.load_temp(typ, temp_addr)
            for index in range(typ.ram_size):
                self.emit(f"MOV R0, R{index + 1}")
                self.emit(f"MOV [{address + index}], R0")
            return

        self.compile_ram_addr(symbol, target.index, scope, target.line)
        if typ is DWORD:
            # Store directly from the value temp: R1..R8 have no spare
            # address pair.
            for index in range(8):
                self.emit(f"MOV R0, [{temp_addr + index}]")
                self.emit("MOV [R4:R5], R0")
                if index != 7:
                    self.emit("INC R5")
                    self.emit("SKIP NC, 1")
                    self.emit("INC R4")
            return
        if typ is WORD:
            self.emit("MOV R6, R4")
            self.emit("MOV R7, R5")
        self.load_temp(typ, temp_addr)
        if typ is NIBBLE:
            self.emit("MOV R0, R1")
            self.emit("MOV [R4:R5], R0")
            return
        if typ is CHAR:
            self.emit("MOV R0, R1")
            self.emit("MOV [R4:R5], R0")
            self.emit("INC R5")
            self.emit("SKIP NC, 1")
            self.emit("INC R4")
            self.emit("MOV R0, R2")
            self.emit("MOV [R4:R5], R0")
            return
        if typ in (WORD, DWORD):
            for index in range(typ.ram_size):
                self.emit(f"MOV R0, R{index + 1}")
                self.emit("MOV [R6:R7], R0")
                if index != typ.ram_size - 1:
                    self.emit("INC R7")
                    self.emit("SKIP NC, 1")
                    self.emit("INC R6")
            return
        raise BadgeTypeError(
            f"{location(self.filename, line)}: cannot store to {typ} array"
        )

    def load_symbol(self, symbol: VarSymbol, line: int) -> None:
        if symbol.const_value is not None:
            self._emit_immediate(symbol.const_value, _REGS[symbol.type.ram_size])
            return
        if symbol.address is None:
            raise BadgeCompileError(
                f"{location(self.filename, line)}: {symbol.name!r} has no RAM storage"
            )
        addr = symbol.address
        if symbol.type is NIBBLE:
            self.emit(f"MOV R0, [{addr}]")
            self.emit("MOV R1, R0")
        elif symbol.type is CHAR:
            self.emit(f"MOV R0, [{addr}]")
            self.emit("MOV R1, R0")
            self.emit(f"MOV R0, [{addr + 1}]")
            self.emit("MOV R2, R0")
        elif symbol.type is FLASHPTR:
            self.emit(f"MOV R0, [{addr}]")
            self.emit("MOV R1, R0")
            self.emit(f"MOV R0, [{addr + 1}]")
            self.emit("MOV R2, R0")
            self.emit(f"MOV R0, [{addr + 2}]")
            self.emit("MOV R3, R0")
        elif symbol.type is WORD:
            for index in range(4):
                self.emit(f"MOV R0, [{addr + index}]")
                self.emit(f"MOV R{index + 1}, R0")
        elif symbol.type is DWORD:
            for index in range(8):
                self.emit(f"MOV R0, [{addr + index}]")
                self.emit(f"MOV R{index + 1}, R0")
        else:
            raise BadgeTypeError(
                f"{location(self.filename, line)}: cannot load {symbol.type} value"
            )

    def store_symbol(self, symbol: VarSymbol, line: int) -> None:
        if symbol.address is None:
            raise BadgeCompileError(
                f"{location(self.filename, line)}: {symbol.name!r} has no RAM storage"
            )
        if symbol.is_const:
            raise BadgeTypeError(
                f"{location(self.filename, line)}: cannot write to const {symbol.name!r}"
            )
        addr = symbol.address
        if symbol.type is NIBBLE:
            self.emit("MOV R0, R1")
            self.emit(f"MOV [{addr}], R0")
        elif symbol.type is CHAR:
            self.emit("MOV R0, R1")
            self.emit(f"MOV [{addr}], R0")
            self.emit("MOV R0, R2")
            self.emit(f"MOV [{addr + 1}], R0")
        elif symbol.type is FLASHPTR:
            self.emit("MOV R0, R1")
            self.emit(f"MOV [{addr}], R0")
            self.emit("MOV R0, R2")
            self.emit(f"MOV [{addr + 1}], R0")
            self.emit("MOV R0, R3")
            self.emit(f"MOV [{addr + 2}], R0")
        elif symbol.type is WORD:
            for index in range(4):
                self.emit(f"MOV R0, R{index + 1}")
                self.emit(f"MOV [{addr + index}], R0")
        elif symbol.type is DWORD:
            for index in range(8):
                self.emit(f"MOV R0, R{index + 1}")
                self.emit(f"MOV [{addr + index}], R0")
        else:
            raise BadgeTypeError(
                f"{location(self.filename, line)}: cannot store {symbol.type} value"
            )

    def store_temp(self, typ: Type, address: int) -> None:
        if typ is NIBBLE:
            self.emit("MOV R0, R1")
            self.emit(f"MOV [{address}], R0")
        elif typ is CHAR:
            self.emit("MOV R0, R1")
            self.emit(f"MOV [{address}], R0")
            self.emit("MOV R0, R2")
            self.emit(f"MOV [{address + 1}], R0")
        elif typ is FLASHPTR:
            self.emit("MOV R0, R1")
            self.emit(f"MOV [{address}], R0")
            self.emit("MOV R0, R2")
            self.emit(f"MOV [{address + 1}], R0")
            self.emit("MOV R0, R3")
            self.emit(f"MOV [{address + 2}], R0")
        elif typ is WORD:
            for index in range(4):
                self.emit(f"MOV R0, R{index + 1}")
                self.emit(f"MOV [{address + index}], R0")
        elif typ is DWORD:
            for index in range(8):
                self.emit(f"MOV R0, R{index + 1}")
                self.emit(f"MOV [{address + index}], R0")
        else:
            raise BadgeCompileError(f"cannot spill {typ}")

    def load_temp(self, typ: Type, address: int) -> None:
        if typ is NIBBLE:
            self.emit(f"MOV R0, [{address}]")
            self.emit("MOV R1, R0")
        elif typ is CHAR:
            self.emit(f"MOV R0, [{address}]")
            self.emit("MOV R1, R0")
            self.emit(f"MOV R0, [{address + 1}]")
            self.emit("MOV R2, R0")
        elif typ is FLASHPTR:
            self.emit(f"MOV R0, [{address}]")
            self.emit("MOV R1, R0")
            self.emit(f"MOV R0, [{address + 1}]")
            self.emit("MOV R2, R0")
            self.emit(f"MOV R0, [{address + 2}]")
            self.emit("MOV R3, R0")
        elif typ is WORD:
            for index in range(4):
                self.emit(f"MOV R0, [{address + index}]")
                self.emit(f"MOV R{index + 1}, R0")
        elif typ is DWORD:
            for index in range(8):
                self.emit(f"MOV R0, [{address + index}]")
                self.emit(f"MOV R{index + 1}, R0")
        else:
            raise BadgeCompileError(f"cannot reload {typ}")

    def coerce(self, source: Type, target: Type, line: int) -> None:
        if source is target:
            return
        if source is VOID:
            raise BadgeTypeError(
                f"{location(self.filename, line)}: expression has no value"
            )
        if is_integer(source) and is_integer(target) and source.ram_size < target.ram_size:
            # Zero-extend: the low source.ram_size nibbles already hold the
            # value in R1, R2, ...
            for index in range(source.ram_size, target.ram_size):
                self.emit(f"MOV R{index + 1}, 0")
            return
        raise BadgeTypeError(
            f"{location(self.filename, line)}: cannot convert {source} to {target}"
        )

    # ------------------------------------------------------------------
    # Conditions
    # ------------------------------------------------------------------

    def emit_jump_if_false(self, expr: ast.Expr, label: str, scope: Scope) -> None:
        self._emit_cond_branch(expr, label, when_true=False, scope=scope)

    def emit_jump_if_true(self, expr: ast.Expr, label: str, scope: Scope) -> None:
        self._emit_cond_branch(expr, label, when_true=True, scope=scope)

    def _emit_cond_branch(
        self, expr: ast.Expr, label: str, when_true: bool, scope: Scope
    ) -> None:
        """Branch directly from flags instead of materialising a 0/1 value."""

        if isinstance(expr, ast.Number):
            if (expr.value != 0) == when_true:
                self.emit(f"GOTO {label}")
            return

        if isinstance(expr, ast.Unary) and expr.op == "!":
            self._emit_cond_branch(expr.operand, label, not when_true, scope)
            return

        if isinstance(expr, ast.Binary) and expr.op in _COMPARE_OPS:
            flag = self._compare_flag(expr, scope)
            if flag is True:
                if when_true:
                    self.emit(f"GOTO {label}")
                return
            if flag is False:
                if not when_true:
                    self.emit(f"GOTO {label}")
                return
            if flag is not None:
                self._branch_on_flag(flag if when_true else _FLAG_INVERSE[flag], label)
                return

        typ = self.compile_expr(expr, scope)
        if when_true:
            self.emit_branch_if_value_true(typ, label)
        else:
            self.emit_branch_if_value_false(typ, label)

    def _branch_on_flag(self, flag: str, label: str) -> None:
        # SKIP the two-word GOTO when the flag is clear.  Keeping the SKIP
        # directly before the GOTO lets branch relaxation shorten it to JR.
        self.emit(f"SKIP {_FLAG_INVERSE[flag]}, 2")
        self.emit(f"GOTO {label}")

    def _compare_flag(self, expr: ast.Binary, scope: Scope):
        """Leave C/Z set for a comparison and return its true flag.

        Returns ``True``/``False`` when the comparison folds to a constant and
        ``None`` when the shape is not handled (the caller then falls back to
        materialising the value).
        """

        op = expr.op
        left, right = expr.left, expr.right

        if isinstance(left, ast.Number) and isinstance(right, ast.Number):
            a, b = int(left.value), int(right.value)
            return {
                "==": a == b,
                "!=": a != b,
                "<": a < b,
                "<=": a <= b,
                ">": a > b,
                ">=": a >= b,
            }[op]

        # Normalise ``constant OP expr`` to ``expr OP constant``.
        if isinstance(left, ast.Number) and not isinstance(right, ast.Number):
            left, right = right, left
            op = _FLAG_SWAP[op]

        if isinstance(right, ast.Number):
            constant = int(right.value)
            typ = self.infer_type(left, scope)
            if typ is NIBBLE:
                return self._compare_nibble_imm(left, constant, op, scope, expr.line)
            if typ is CHAR:
                return self._compare_char_imm(left, constant, op, scope, expr.line)
            if typ is WORD:
                return self._compare_word_imm(left, constant, op, scope, expr.line)
            if typ is DWORD:
                return self._compare_dword_imm(left, constant, op, scope, expr.line)
            return None

        left_type = self.infer_type(left, scope)
        right_type = self.infer_type(right, scope)
        if not is_comparable(left_type) or not is_comparable(right_type):
            return None
        if not self._is_leaf(right):
            return None
        if DWORD in (left_type, right_type):
            return None
        if WORD in (left_type, right_type):
            return self._compare_word_regs(left, right, op, scope, expr.line)
        return self._compare_regs(left, right, op, left_type, right_type, scope, expr.line)

    def _compare_nibble_imm(
        self, left: ast.Expr, constant: int, op: str, scope: Scope, line: int
    ):
        if constant > 15:
            # The result is independent of the operand, but the operand may
            # still have side effects (for example a function call).
            typ = self.compile_expr(left, scope)
            self.coerce(typ, NIBBLE, line)
            return {
                "<": True,
                "<=": True,
                ">": False,
                ">=": False,
                "==": False,
                "!=": True,
            }[op]

        if (op == "<=" and constant == 15) or (op == ">" and constant == 15):
            typ = self.compile_expr(left, scope)
            self.coerce(typ, NIBBLE, line)
            return op == "<="

        typ = self.compile_expr(left, scope)
        self.coerce(typ, NIBBLE, line)
        self.emit("MOV R0, R1")

        if op in ("<", ">=", "==", "!="):
            self.emit(f"CP R0, {constant}")
            return {"<": "NC", ">=": "C", "==": "Z", "!=": "NZ"}[op]

        # > and <= compare against constant + 1.
        self.emit(f"CP R0, {constant + 1}")
        return {"<": "NC", ">=": "C", ">": "C", "<=": "NC"}[op]

    def _compare_char_imm(
        self, left: ast.Expr, constant: int, op: str, scope: Scope, line: int
    ):
        if constant == 0:
            if op in ("<", ">="):
                typ = self.compile_expr(left, scope)
                self.coerce(typ, CHAR, line)
                return op == ">="
            typ = self.compile_expr(left, scope)
            self.coerce(typ, CHAR, line)
            self.emit("OR R1, R2")
            return "Z" if op in ("==", "<=") else "NZ"

        if constant == 255 and op in ("==", "!="):
            typ = self.compile_expr(left, scope)
            self.coerce(typ, CHAR, line)
            # R0 = (high ^ 15) | (low ^ 15): zero only for 0xFF.
            self.emit("MOV R0, R2")
            self.emit("XOR R0, 15")
            self.emit("MOV R3, R0")
            self.emit("MOV R0, R1")
            self.emit("XOR R0, 15")
            self.emit("OR R0, R3")
            return "Z" if op == "==" else "NZ"

        if constant == 16 and op in ("<", ">="):
            typ = self.compile_expr(left, scope)
            self.coerce(typ, CHAR, line)
            self.emit("MOV R0, R2")
            self.emit("CP R0, 0")
            return "Z" if op == "<" else "NZ"

        if constant == 15 and op in (">", "<="):
            typ = self.compile_expr(left, scope)
            self.coerce(typ, CHAR, line)
            self.emit("MOV R0, R2")
            self.emit("CP R0, 0")
            return "NZ" if op == ">" else "Z"

        return None

    def _compile_word_comparison(
        self,
        left: ast.Expr,
        right: ast.Expr,
        op: str,
        scope: Scope,
        line: int,
    ) -> Type:
        mark = self.temp.mark()
        temp_addr = self.temp.alloc(WORD.ram_size, "comparison", self.filename, line)

        typ = self.compile_expr(left, scope)
        self.coerce(typ, WORD, line)
        self.store_temp(WORD, temp_addr)

        typ = self.compile_expr(right, scope)
        self.coerce(typ, WORD, line)
        self._move(("R1", "R2", "R3", "R4"), ("R5", "R6", "R7", "R8"))
        self.load_temp(WORD, temp_addr)

        flag = self._word_compare_flag(
            op, ("R1", "R2", "R3", "R4"), ("R5", "R6", "R7", "R8")
        )
        self.emit("MOV R1, 0")
        self.emit(f"SKIP {_FLAG_INVERSE[flag]}, 1")
        self.emit("INC R1")
        self.emit("MOV R2, 0")
        self.temp.reset(mark)
        return NIBBLE

    def _word_compare_flag(
        self,
        op: str,
        left_regs: tuple[str, ...],
        right_regs: tuple[str, ...],
    ) -> str:
        if op in ("==", "!="):
            self.emit("MOV R9, 0")
            for left_reg, right_reg in zip(left_regs, right_regs):
                self.emit(f"MOV R0, {left_reg}")
                self.emit(f"XOR R0, {right_reg}")
                self.emit("OR R9, R0")
            self.emit("MOV R0, R9")
            self.emit("CP R0, 0")
            return "Z" if op == "==" else "NZ"

        if op in ("<", ">="):
            self.emit(f"SUB {left_regs[0]}, {right_regs[0]}")
            for left_reg, right_reg in zip(left_regs[1:], right_regs[1:]):
                self.emit(f"SBB {left_reg}, {right_reg}")
            return "NC" if op == "<" else "C"

        self.emit(f"SUB {right_regs[0]}, {left_regs[0]}")
        for left_reg, right_reg in zip(left_regs[1:], right_regs[1:]):
            self.emit(f"SBB {right_reg}, {left_reg}")
        return "NC" if op == ">" else "C"

    def _compare_word_imm(
        self, left: ast.Expr, constant: int, op: str, scope: Scope, line: int
    ) -> str:
        typ = self.compile_expr(left, scope)
        self.coerce(typ, WORD, line)
        if op in ("==", "!="):
            self.emit("MOV R9, 0")
            for index in range(4):
                self.emit(f"MOV R0, R{index + 1}")
                self.emit(f"XOR R0, {(constant >> (4 * index)) & 0xF}")
                self.emit("OR R9, R0")
            self.emit("MOV R0, R9")
            self.emit("CP R0, 0")
            return "Z" if op == "==" else "NZ"

        self._emit_immediate(constant & 0xFFFF, ("R5", "R6", "R7", "R8"))
        return self._word_compare_flag(
            op, ("R1", "R2", "R3", "R4"), ("R5", "R6", "R7", "R8")
        )

    def _compare_word_regs(
        self, left: ast.Expr, right: ast.Expr, op: str, scope: Scope, line: int
    ) -> str:
        typ = self.compile_expr(left, scope)
        self.coerce(typ, WORD, line)
        self._move(("R1", "R2", "R3", "R4"), ("R5", "R6", "R7", "R8"))
        typ = self.compile_expr(right, scope)
        self.coerce(typ, WORD, line)
        return self._word_compare_flag(
            op, ("R5", "R6", "R7", "R8"), ("R1", "R2", "R3", "R4")
        )

    def _compare_dword_imm(
        self, left: ast.Expr, constant: int, op: str, scope: Scope, line: int
    ) -> str:
        typ = self.compile_expr(left, scope)
        self.coerce(typ, DWORD, line)
        if op in ("==", "!="):
            self.emit("MOV R9, 0")
            for index in range(8):
                self.emit(f"MOV R0, R{index + 1}")
                self.emit(f"XOR R0, {(constant >> (4 * index)) & 0xF}")
                self.emit("OR R9, R0")
            self.emit("MOV R0, R9")
            self.emit("CP R0, 0")
            return "Z" if op == "==" else "NZ"

        if op in ("<", ">="):
            for index in range(8):
                self.emit(f"MOV R0, {(constant >> (4 * index)) & 0xF}")
                instruction = "SUB" if index == 0 else "SBB"
                self.emit(f"{instruction} R{index + 1}, R0")
            return "NC" if op == "<" else "C"

        for index in range(8):
            self.emit(f"MOV R0, {(constant >> (4 * index)) & 0xF}")
            instruction = "SUB" if index == 0 else "SBB"
            self.emit(f"{instruction} R0, R{index + 1}")
        return "NC" if op == ">" else "C"

    def _dword_compare_flag_memory(self, op: str, addr: int) -> str:
        if op in ("==", "!="):
            self.emit("MOV R9, 0")
            for index in range(8):
                self.emit(f"MOV R0, [{addr + index}]")
                self.emit(f"XOR R0, R{index + 1}")
                self.emit("OR R9, R0")
            self.emit("MOV R0, R9")
            self.emit("CP R0, 0")
            return "Z" if op == "==" else "NZ"

        if op in ("<", ">="):
            for index in range(8):
                self.emit(f"MOV R0, [{addr + index}]")
                instruction = "SUB" if index == 0 else "SBB"
                self.emit(f"{instruction} R{index + 1}, R0")
            return "NC" if op == "<" else "C"

        for index in range(8):
            self.emit(f"MOV R0, [{addr + index}]")
            instruction = "SUB" if index == 0 else "SBB"
            self.emit(f"{instruction} R0, R{index + 1}")
        return "NC" if op == ">" else "C"

    def _compile_dword_comparison(
        self,
        left: ast.Expr,
        right: ast.Expr,
        op: str,
        scope: Scope,
        line: int,
    ) -> Type:
        mark = self.temp.mark()
        left_addr = self.temp.alloc(8, "dword comparison", self.filename, line)
        right_addr = self.temp.alloc(8, "dword comparison", self.filename, line)
        typ = self.compile_expr(left, scope)
        self.coerce(typ, DWORD, line)
        self.store_temp(DWORD, left_addr)
        typ = self.compile_expr(right, scope)
        self.coerce(typ, DWORD, line)
        self.store_temp(DWORD, right_addr)
        self.load_temp(DWORD, left_addr)
        flag = self._dword_compare_flag_memory(op, right_addr)
        self.emit("MOV R1, 0")
        self.emit(f"SKIP {_FLAG_INVERSE[flag]}, 1")
        self.emit("INC R1")
        self.emit("MOV R2, 0")
        self.temp.reset(mark)
        return NIBBLE

    def _compare_regs(
        self,
        left: ast.Expr,
        right: ast.Expr,
        op: str,
        left_type: Type,
        right_type: Type,
        scope: Scope,
        line: int,
    ) -> str:
        common = CHAR if CHAR in (left_type, right_type) else NIBBLE
        typ = self.compile_expr(left, scope)
        self.coerce(typ, common, line)
        if common is NIBBLE:
            self.emit("MOV R3, R1")
        else:
            self.emit("MOV R3, R1")
            self.emit("MOV R4, R2")

        typ = self.compile_expr(right, scope)
        self.coerce(typ, common, line)

        # left-right for <, >=, ==, !=; right-left for >, <= so that a single
        # C or NC test is enough.
        left_first = op in ("<", ">=", "==", "!=")
        if common is NIBBLE:
            if left_first:
                self.emit("SUB R3, R1")
            else:
                self.emit("SUB R1, R3")
        else:
            if left_first:
                self.emit("SUB R4, R2")
            else:
                self.emit("SUB R2, R4")
            self.emit("SKIP NZ, 1")
            if left_first:
                self.emit("SUB R3, R1")
            else:
                self.emit("SUB R1, R3")

        return {"<": "NC", ">=": "C", "==": "Z", "!=": "NZ", ">": "NC", "<=": "C"}[op]

    def _is_leaf(self, expr: ast.Expr) -> bool:
        # A leaf cannot clobber R3/R4, which hold the left operand.
        return isinstance(expr, (ast.Number, ast.Var, ast.AddressOf))

    def emit_branch_if_value_false(self, typ: Type, label: str) -> None:
        if typ is NIBBLE:
            # OR R1,R1 leaves R1 unchanged but sets Z when it is zero.
            self.emit("OR R1, R1")
            self.emit("SKIP NZ, 2")
            self.emit(f"GOTO {label}")
            return
        if typ is CHAR:
            self.emit("OR R1, R2")
            self.emit("SKIP NZ, 2")
            self.emit(f"GOTO {label}")
            return
        if typ is WORD:
            self.emit("OR R1, R2")
            self.emit("OR R1, R3")
            self.emit("OR R1, R4")
            self.emit("SKIP NZ, 2")
            self.emit(f"GOTO {label}")
            return
        if typ is DWORD:
            self.emit("OR R1, R2")
            self.emit("OR R1, R3")
            self.emit("OR R1, R4")
            self.emit("OR R1, R5")
            self.emit("OR R1, R6")
            self.emit("OR R1, R7")
            self.emit("OR R1, R8")
            self.emit("SKIP NZ, 2")
            self.emit(f"GOTO {label}")
            return
        if typ is FLASHPTR:
            self.emit("OR R1, R2")
            self.emit("OR R1, R3")
            self.emit("SKIP NZ, 2")
            self.emit(f"GOTO {label}")
            return
        raise BadgeTypeError(f"cannot test value of type {typ}")

    def emit_branch_if_value_true(self, typ: Type, label: str) -> None:
        if typ is NIBBLE:
            self.emit("OR R1, R1")
            self.emit("SKIP Z, 2")
            self.emit(f"GOTO {label}")
            return
        if typ is CHAR:
            self.emit("OR R1, R2")
            self.emit("SKIP Z, 2")
            self.emit(f"GOTO {label}")
            return
        if typ is WORD:
            self.emit("OR R1, R2")
            self.emit("OR R1, R3")
            self.emit("OR R1, R4")
            self.emit("SKIP Z, 2")
            self.emit(f"GOTO {label}")
            return
        if typ is DWORD:
            self.emit("OR R1, R2")
            self.emit("OR R1, R3")
            self.emit("OR R1, R4")
            self.emit("OR R1, R5")
            self.emit("OR R1, R6")
            self.emit("OR R1, R7")
            self.emit("OR R1, R8")
            self.emit("SKIP Z, 2")
            self.emit(f"GOTO {label}")
            return
        if typ is FLASHPTR:
            self.emit("OR R1, R2")
            self.emit("OR R1, R3")
            self.emit("SKIP Z, 2")
            self.emit(f"GOTO {label}")
            return
        raise BadgeTypeError(f"cannot test value of type {typ}")

    def emit_truth_value(self, typ: Type) -> None:
        if typ is NIBBLE:
            return
        if typ is CHAR:
            self.emit("MOV R0, R1")
            self.emit("OR R0, R2")
            self.emit("MOV R1, R0")
            return
        if typ is WORD:
            self.emit("MOV R0, R1")
            self.emit("OR R0, R2")
            self.emit("OR R0, R3")
            self.emit("OR R0, R4")
            self.emit("MOV R1, R0")
            return
        if typ is DWORD:
            self.emit("MOV R0, R1")
            self.emit("OR R0, R2")
            self.emit("OR R0, R3")
            self.emit("OR R0, R4")
            self.emit("OR R0, R5")
            self.emit("OR R0, R6")
            self.emit("OR R0, R7")
            self.emit("OR R0, R8")
            self.emit("MOV R1, R0")
            return
        if typ is FLASHPTR:
            self.emit("MOV R0, R1")
            self.emit("OR R0, R2")
            self.emit("OR R0, R3")
            self.emit("MOV R1, R0")
            return
        raise BadgeTypeError(f"cannot convert {typ} to a truth value")

    # ------------------------------------------------------------------
    # Type inference
    # ------------------------------------------------------------------

    def infer_type(self, expr: ast.Expr, scope: Scope) -> Type:
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
            symbol = self.lookup(expr.name, scope, expr.line)
            if symbol.array_len is not None:
                if symbol.flash_label is not None:
                    return FLASHPTR
                raise BadgeTypeError(
                    f"{location(self.filename, expr.line)}: array {expr.name!r} used without an index"
                )
            return symbol.type
        if isinstance(expr, ast.Index):
            if not isinstance(expr.base, ast.Var):
                raise BadgeTypeError(
                    f"{location(self.filename, expr.line)}: only named arrays can be indexed"
                )
            symbol = self.lookup(expr.base.name, scope, expr.line)
            if symbol.array_len is None:
                raise BadgeTypeError(
                    f"{location(self.filename, expr.line)}: {symbol.name!r} is not an array"
                )
            return symbol.type
        if isinstance(expr, ast.Unary):
            if expr.op == "&":
                return CHAR
            if expr.op == "!":
                return NIBBLE
            return self.infer_type(expr.operand, scope)
        if isinstance(expr, ast.Binary):
            if expr.op in ("==", "!=", "<", "<=", ">", ">=", "&&", "||"):
                return NIBBLE
            if expr.op in ("<<", ">>"):
                return self.infer_type(expr.left, scope)
            left = self.infer_type(expr.left, scope)
            right = self.infer_type(expr.right, scope)
            if expr.op == "*":
                return promoted_mul_type(wider(left, right))
            return wider(left, right)
        if isinstance(expr, ast.Call):
            if expr.name in BUILTINS:
                return BUILTINS[expr.name]
            fn = self.functions.get(expr.name)
            if fn is None:
                raise BadgeCompileError(
                    f"{location(self.filename, expr.line)}: unknown function {expr.name!r}"
                )
            return fn.decl.return_type
        if isinstance(expr, ast.AddressOf):
            return CHAR
        if isinstance(expr, (ast.ToType, ast.Cast)):
            return expr.type
        raise BadgeCompileError(
            f"{location(self.filename, expr.line)}: cannot infer type of {type(expr).__name__}"
        )

    # ------------------------------------------------------------------
    # Flash data
    # ------------------------------------------------------------------

    def new_flash_string(self, value: str) -> str:
        label = self.new_flash_label()
        self.flash.append(
            FlashItem(label, CHAR, [ord(ch) & 0xFF for ch in value] + [0xFF], string_value=value)
        )
        return label

    def emit_flashptr(self, label: str) -> None:
        self.emit(f"MOV R1, LOW {label}")
        self.emit(f"MOV R2, MID {label}")
        self.emit(f"MOV R3, HIGH {label}")

    def emit_flash_data(self) -> None:
        if not self.flash:
            return
        self.emit("")
        self.emit("; flash data (RET R0, nibble tables)")
        self.emit("__bc_flash_data:")
        for item in self.flash:
            self.emit(f"{item.label}:")
            if item.type is NIBBLE:
                for value in item.values:
                    self.emit(f"NIBBLE 0x{value & 0xF:X}")
            elif item.type is CHAR:
                for value in item.values:
                    self.emit(f"BYTE 0x{value & 0xFF:02X}")
            elif item.type is WORD:
                for value in item.values:
                    for index in range(4):
                        self.emit(f"NIBBLE 0x{(value >> (4 * index)) & 0xF:X}")
            elif item.type is DWORD:
                for value in item.values:
                    for index in range(8):
                        self.emit(f"NIBBLE 0x{(value >> (4 * index)) & 0xF:X}")
            else:
                raise BadgeCompileError(f"unsupported flash data type {item.type}")
            self.emit("")

    # ------------------------------------------------------------------
    # Validation and output
    # ------------------------------------------------------------------

    def validate_call_graph(self) -> None:
        edges: dict[str, list[tuple[str, bool, int, str]]] = {}
        for caller, callee, tail, line, filename in self.calls:
            edges.setdefault(caller, []).append((callee, tail, line, filename))

        on_stack: set[str] = set()
        visited: set[str] = set()
        path: list[tuple[str, str, bool, int, str]] = []

        def visit(node: str) -> None:
            if node in visited:
                return
            on_stack.add(node)
            for callee, tail, line, filename in edges.get(node, []):
                if callee in on_stack:
                    # Locate the start of the cycle on the path.
                    start = 0
                    for index, (src, dst, _, _, _) in enumerate(path):
                        if src == callee or dst == callee:
                            start = index
                            break
                    cycle = path[start:] + [(node, callee, tail, line, filename)]
                    if not all(edge_tail for _, _, edge_tail, _, _ in cycle):
                        raise BadgeCompileError(
                            f"{location(filename, line)}: non-tail recursion involving "
                            f"{callee!r} is not supported; rewrite it as a loop or a tail call"
                        )
                else:
                    path.append((node, callee, tail, line, filename))
                    visit(callee)
                    path.pop()
            on_stack.remove(node)
            visited.add(node)

        for name in self.functions:
            visit(name)

        # Report maximum hardware stack depth for non-tail calls.
        memo: dict[str, int] = {}

        def depth(node: str, visiting: set[str]) -> int:
            if node in memo:
                return memo[node]
            if node in visiting:
                return 0
            visiting.add(node)
            best = 0
            for callee, tail, _, _ in edges.get(node, []):
                child = depth(callee, visiting)
                if not tail:
                    child += 1
                best = max(best, child)
            visiting.remove(node)
            memo[node] = best
            return best

        self.max_call_depth = depth("main", set())
        # The hardware stack has five entries.  Leave one level of headroom
        # for runtime helpers (UART/flash) that are called from user code.
        if self.max_call_depth > 4:
            raise BadgeCompileError(
                f"{self.filename}: maximum non-tail call depth is {self.max_call_depth}, "
                "but the badge hardware stack has only five entries"
            )

        # Maximum entry depth for every function reachable from main.  Tail
        # calls do not add a stack entry, so a tail-call cycle terminates
        # because the candidate depth stops increasing.
        self.function_depths = {"main": 0}
        parents: dict[str, tuple[str, bool, int, str]] = {}
        work = ["main"]
        while work:
            caller = work.pop()
            base = self.function_depths[caller]
            for callee, tail, line, filename in edges.get(caller, []):
                candidate = base + (0 if tail else 1)
                if candidate > self.function_depths.get(callee, -1):
                    self.function_depths[callee] = candidate
                    parents[callee] = (caller, tail, line, filename)
                    work.append(callee)

        if self.function_depths:
            deepest = max(
                self.function_depths,
                key=lambda name: (self.function_depths[name], name),
            )
            chain = [deepest]
            while chain[-1] != "main" and chain[-1] in parents:
                chain.append(parents[chain[-1]][0])
            self.deepest_path = list(reversed(chain))

        # Runtime helpers cost stack entries too.  Costs are derived from
        # the runtime assembly, including flash-table ``MOV JSR`` calls.
        self.runtime_costs = runtime_stack_costs(self.runtime_text)
        self.stack_call_sites = []
        self.stack_warnings = []
        for caller, entry, line, filename in self.runtime_calls:
            cost = self.runtime_costs.get(entry, 1)
            user_depth = self.function_depths.get(caller, 0)
            total = user_depth + cost
            self.stack_call_sites.append(
                {
                    "caller": caller,
                    "entry": entry,
                    "line": line,
                    "file": filename,
                    "user_depth": user_depth,
                    "cost": cost,
                    "total": total,
                }
            )
            if total > 5:
                self.stack_warnings.append(
                    f"{location(filename, line)}: {caller} calls {entry} at user "
                    f"depth {user_depth}; runtime cost {cost} needs {total} stack "
                    f"levels (the hardware stack has 5)"
                )

    def debug_map(self) -> dict:
        """Return a PC-to-source map for the optimized program."""

        from .debugmap import build_debug_map

        return build_debug_map(self.asm_text, self)

    def code_sizes(self, total_words: Optional[int] = None) -> dict:
        """Return per-function, per-runtime, and flash word counts."""
        labels = {fn.label for fn in self.functions.values()}
        labels.update(self.linked_runtime)
        labels.add("__bc_flash_data")
        sizes = word_sizes(self.asm_text, labels, total_words)

        function_words = {
            name: sizes.get(fn.label, 0) for name, fn in self.functions.items()
        }
        runtime_words = {
            label: sizes.get(label, 0) for label in sorted(self.linked_runtime)
        }
        flash_words = sizes.get("__bc_flash_data", 0)
        total = total_words if total_words is not None else asm_word_count(self.asm_text)
        startup_words = max(
            0,
            total
            - sum(function_words.values())
            - sum(runtime_words.values())
            - flash_words,
        )
        return {
            "functions": function_words,
            "runtime": runtime_words,
            "flash": flash_words,
            "startup": startup_words,
            "total": total,
        }

    def stack_data(self) -> dict:
        """Return the static stack-report data used by ``--stack``."""

        return {
            "max_call_depth": self.max_call_depth,
            "deepest_path": list(self.deepest_path),
            "function_depths": dict(self.function_depths),
            "runtime_costs": {
                label: self.runtime_costs.get(label, 1)
                for label in sorted(self.linked_runtime)
            },
            "call_sites": list(self.stack_call_sites),
            "warnings": list(self.stack_warnings),
        }

    def map_data(self, total_words: Optional[int] = None) -> dict:
        """Return a JSON-serializable symbol/size map."""

        sizes = self.code_sizes(total_words)
        globals_data = []
        for name, symbol in self.globals.items():
            globals_data.append(
                {
                    "name": name,
                    "type": str(symbol.type),
                    "address": symbol.address,
                    "array_len": symbol.array_len,
                    "const": symbol.is_const,
                    "value": symbol.const_value,
                    "flash_label": symbol.flash_label,
                }
            )

        functions_data = []
        for name, fn in self.functions.items():
            functions_data.append(
                {
                    "name": name,
                    "label": fn.label,
                    "return_type": str(fn.decl.return_type),
                    "words": sizes["functions"].get(name, 0),
                    "extern": fn.decl.is_extern,
                    "params": [
                        {
                            "name": param.name,
                            "type": str(param.type),
                            "address": param.address,
                        }
                        for param in fn.params
                    ],
                }
            )

        flash_data = [
            {
                "label": item.label,
                "type": str(item.type),
                "count": len(item.values),
                "string": item.string_value,
            }
            for item in self.flash
        ]

        return {
            "source": self.filename,
            "globals": globals_data,
            "functions": functions_data,
            "flash": flash_data,
            "calls": [
                {
                    "caller": caller,
                    "callee": callee,
                    "tail": tail,
                    "line": line,
                    "file": filename,
                }
                for caller, callee, tail, line, filename in self.calls
            ],
            "runtime": sorted(self.used_runtime),
            "runtime_linked": sorted(self.linked_runtime),
            "runtime_words": sizes["runtime"],
            "flash_words": sizes["flash"],
            "startup_words": sizes["startup"],
            "asm_words": sizes["total"],
            "stack": self.stack_data(),
            "ram_nibbles_used": self.mem.used(),
            "max_call_depth": self.max_call_depth,
        }

    # ------------------------------------------------------------------
    # Emission helpers
    # ------------------------------------------------------------------

    def emit(self, line: str) -> None:
        stripped = line.strip()
        if self.current_source is None:
            self.last_emitted_source = None
        if (
            self.current_source is not None
            and self.current_source != self.last_emitted_source
            and stripped
            and not stripped.startswith(";")
        ):
            file, source_line = self.current_source
            self.lines.append(f"; @badgec-src {file}:{source_line}")
            self.last_emitted_source = self.current_source
        self.lines.append(line)
