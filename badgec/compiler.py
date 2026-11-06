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

from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from . import ast_nodes as ast
from .asm_opt import optimize_asm
from .inline import optimize as optimize_program
from .runtime_linker import link_runtime, reachable_labels
from .errors import BadgeCompileError, BadgeTypeError, location
from .types import CHAR, FLASHPTR, NIBBLE, VOID, Type, is_comparable, is_integer


RAM_START = 0x40
RAM_END = 0xF0
TEMP_START = 0x20
TEMP_END = 0x40

BUILTINS = {
    "uart_init": VOID,
    "uart_putc": VOID,
    "putchar": VOID,
    "uart_getc": CHAR,
    "uart_available": NIBBLE,
    "uart_puts": VOID,
    "puts": VOID,
    "uart_write": VOID,
    "flash_read_char": CHAR,
    "flash_read_nibble": NIBBLE,
    "flash_next": CHAR,
    "out": VOID,
    "in": NIBBLE,
    "peek": NIBBLE,
    "poke": VOID,
    "gpio_read": NIBBLE,
    "gpio_write": VOID,
    "gpio_set": VOID,
    "gpio_clear": VOID,
    "gpio_toggle": VOID,
    "gpio_test": NIBBLE,
    "gpio_alt": VOID,
    "uart_route": VOID,
    "leds_enable": VOID,
    "matrix_enable": VOID,
    "display_page": VOID,
    "display_poke": VOID,
    "display_peek": NIBBLE,
    "random": NIBBLE,
    "seed": VOID,
    "dimmer": VOID,
    "key_status": NIBBLE,
    "key_code": NIBBLE,
    "key_any": NIBBLE,
    "key_alt": NIBBLE,
    "key_just": NIBBLE,
    "key_last": NIBBLE,
    "delay": VOID,
    "memset": VOID,
    "memcpy": VOID,
}


# Builtins that are implemented by a runtime label.
RUNTIME_ENTRY = {
    "uart_init": "__bc_uart_init",
    "uart_putc": "__bc_uart_putc",
    "putchar": "__bc_uart_putc",
    "uart_getc": "__bc_uart_getc",
    "uart_available": "__bc_uart_available",
    "uart_puts": "__bc_uart_puts",
    "puts": "__bc_uart_puts",
    "uart_write": "__bc_uart_write",
    "flash_read_char": "__bc_flash_read_char",
    "flash_read_nibble": "__bc_flash_read_nibble",
    "flash_next": "__bc_flash_read_char_ptr",
    "gpio_read": "__bc_gpio_read",
    "gpio_write": "__bc_gpio_write",
    "gpio_set": "__bc_gpio_set",
    "gpio_clear": "__bc_gpio_clear",
    "gpio_toggle": "__bc_gpio_toggle",
    "gpio_test": "__bc_gpio_test",
    "gpio_alt": "__bc_gpio_alt",
    "uart_route": "__bc_uart_route",
    "leds_enable": "__bc_leds_enable",
    "matrix_enable": "__bc_matrix_enable",
    "random": "__bc_random",
    "seed": "__bc_seed",
    "dimmer": "__bc_dimmer",
    "key_status": "__bc_key_status",
    "key_code": "__bc_key_code",
    "key_any": "__bc_key_any",
    "key_alt": "__bc_key_alt",
    "key_just": "__bc_key_just",
    "key_last": "__bc_key_last",
    "delay": "__bc_delay",
}

_COMPARE_OPS = {"==", "!=", "<", "<=", ">", ">="}
_FLAG_INVERSE = {"C": "NC", "NC": "C", "Z": "NZ", "NZ": "Z"}
_FLAG_SWAP = {"<": ">", "<=": ">=", ">": "<", ">=": "<=", "==": "==", "!=": "!="}


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


@dataclass
class FunctionSymbol:
    name: str
    decl: ast.FunctionDecl
    label: str
    params: list[VarSymbol] = field(default_factory=list)
    labels_seen: set[str] = field(default_factory=set)


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
        self.current_function: Optional[FunctionSymbol] = None
        self.loop_stack: list[tuple[str, str]] = []  # (break label, continue label)
        self.calls: list[tuple[str, str, bool, int]] = []  # caller, callee, tail, line
        self.max_call_depth = 0

    # ------------------------------------------------------------------
    # Entry point
    # ------------------------------------------------------------------

    def compile(self) -> str:
        optimize_program(self.program)
        self.prepare_globals()
        self.prepare_functions()
        if "main" not in self.functions:
            raise BadgeCompileError(f"{self.filename}: no main() function found")

        self.emit("; BadgeC generated assembly")
        self.emit("GOTO fn_main")
        for fn in self.program.functions:
            self.compile_function(self.functions[fn.name])
        self.emit("")
        runtime_text = Path(__file__).with_name("runtime").joinpath("runtime.asm").read_text()
        if self.strip_runtime:
            runtime_text = link_runtime(runtime_text, self.used_runtime)
        self.emit(runtime_text)
        self.emit_flash_data()
        self.validate_call_graph()
        asm = "\n".join(self.lines) + "\n"
        if self.asm_optimize:
            asm = optimize_asm(asm)
        return asm

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

    def prepare_globals(self) -> None:
        for decl in self.program.globals:
            if decl.name in self.globals:
                raise BadgeCompileError(
                    f"{location(self.filename, decl.line)}: duplicate global {decl.name!r}"
                )

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
                values.append(int(expr.value) & 0xFF)
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
            fn = FunctionSymbol(
                name=decl.name,
                decl=decl,
                label=f"fn_{decl.name}",
            )
            for param in decl.params:
                address = self.mem.alloc(
                    param.type.ram_size, f"parameter {param.name}", self.filename, param.line
                )
                fn.params.append(
                    VarSymbol(
                        name=param.name,
                        type=param.type,
                        address=address,
                        is_param=True,
                        line=param.line,
                    )
                )
            self.functions[decl.name] = fn

    # ------------------------------------------------------------------
    # Function code generation
    # ------------------------------------------------------------------

    def compile_function(self, fn: FunctionSymbol) -> None:
        self.current_function = fn
        self.loop_stack = []
        scope = Scope()
        for param in fn.params:
            scope.define(param, self.filename)

        self.emit(f"; function {fn.name}")
        self.emit(f"{fn.label}:")
        if fn.name == "main":
            for symbol, expr in self.global_inits:
                typ = self.compile_expr(expr, scope)
                self.coerce(typ, symbol.type, expr.line)
                self.store_symbol(symbol, expr.line)

        self.compile_block(fn.decl.body, scope, tail=False)

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
        if isinstance(stmt, ast.Block):
            self.compile_block(stmt, scope, tail=tail)

        elif isinstance(stmt, ast.VarDecl):
            self.compile_var_decl(stmt, scope)

        elif isinstance(stmt, ast.Assign):
            target_type = self.lvalue_type(stmt.target, scope)
            if isinstance(stmt.value, ast.Number) and target_type in (NIBBLE, CHAR):
                value = int(stmt.value.value)
                if target_type is NIBBLE and value > 15:
                    raise BadgeTypeError(
                        f"{location(self.filename, stmt.line)}: cannot convert char to nibble"
                    )
                if 0 <= value <= 255 and self.store_constant(
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

    def compile_var_decl(self, stmt: ast.VarDecl, scope: Scope) -> None:
        if stmt.name in scope.symbols:
            raise BadgeCompileError(
                f"{location(self.filename, stmt.line)}: duplicate local {stmt.name!r}"
            )
        size = (stmt.array_len or 1) * stmt.type.ram_size
        address = self.mem.alloc(size, stmt.name, self.filename, stmt.line)
        symbol = VarSymbol(
            name=stmt.name,
            type=stmt.type,
            address=address,
            array_len=stmt.array_len,
            is_const=stmt.is_const,
            line=stmt.line,
        )
        scope.define(symbol, self.filename)
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
        if isinstance(expr, ast.Number):
            if expr.value < 0 or expr.value > 255:
                raise BadgeCompileError(
                    f"{location(self.filename, expr.line)}: integer {expr.value} does not fit in a char"
                )
            if expr.value <= 15:
                self.emit(f"MOV R1, {expr.value}")
                return NIBBLE
            self.emit(f"MOV R1, {expr.value & 0xF}")
            self.emit(f"MOV R2, {(expr.value >> 4) & 0xF}")
            return CHAR

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

        raise BadgeCompileError(
            f"{location(self.filename, getattr(expr, 'line', 0))}: unsupported expression {type(expr).__name__}"
        )

    def compile_unary(self, expr: ast.Unary, scope: Scope) -> Type:
        if expr.op == "&":
            return self.compile_address_of(ast.AddressOf(expr.operand, line=expr.line), scope)

        typ = self.compile_expr(expr.operand, scope)
        if expr.op == "!":
            if typ not in (NIBBLE, CHAR):
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
                self.emit("CPL R1")
                return NIBBLE
            if typ is CHAR:
                self.emit("CPL R1")
                self.emit("CPL R2")
                return CHAR
            raise BadgeTypeError(
                f"{location(self.filename, expr.line)}: ~ requires an integer operand"
            )

        if expr.op == "-":
            if typ is NIBBLE:
                self.emit("CPL R1")
                self.emit("INC R1")
                return NIBBLE
            if typ is CHAR:
                self.emit("CPL R1")
                self.emit("CPL R2")
                self.emit("MOV R0, 1")
                self.emit("ADD R1, R0")
                self.emit("MOV R0, 0")
                self.emit("ADC R2, R0")
                return CHAR
            raise BadgeTypeError(
                f"{location(self.filename, expr.line)}: unary - requires an integer operand"
            )

        raise BadgeCompileError(
            f"{location(self.filename, expr.line)}: unsupported unary operator {expr.op!r}"
        )

    def compile_address_of(self, expr: ast.AddressOf, scope: Scope) -> Type:
        if not isinstance(expr.operand, ast.Var):
            raise BadgeTypeError(
                f"{location(self.filename, expr.line)}: & is only supported on simple variables"
            )
        symbol = self.lookup(expr.operand.name, scope, expr.line)
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
        if op in ("*", "/", "%", "<<", ">>"):
            raise BadgeCompileError(
                f"{location(self.filename, expr.line)}: operator {op!r} is not implemented yet"
            )
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
        materialize = op
        if op == "<=":
            left, right = right, left
            materialize = ">="
        elif op == ">":
            left, right = right, left
            materialize = "<"

        left_type = self.infer_type(left, scope)
        right_type = self.infer_type(right, scope)
        if not is_comparable(left_type) or not is_comparable(right_type):
            raise BadgeTypeError(
                f"{location(self.filename, expr.line)}: comparisons require integer operands"
            )
        common = CHAR if CHAR in (left_type, right_type) else NIBBLE

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

        if isinstance(expr.left, ast.Number) and isinstance(expr.right, ast.Number):
            a, b = int(expr.left.value), int(expr.right.value)
            result = {
                "+": a + b,
                "-": a - b,
                "&": a & b,
                "|": a | b,
                "^": a ^ b,
            }[expr.op]
            if CHAR in (left_type, right_type):
                result &= 0xFF
                self.emit(f"MOV R1, {result & 0xF}")
                self.emit(f"MOV R2, {(result >> 4) & 0xF}")
                return CHAR
            # Nibble arithmetic wraps to four bits.
            self.emit(f"MOV R1, {result & 0xF}")
            return NIBBLE
        if not is_integer(left_type) or not is_integer(right_type):
            raise BadgeTypeError(
                f"{location(self.filename, expr.line)}: arithmetic requires integer operands"
            )
        common = CHAR if CHAR in (left_type, right_type) else NIBBLE

        if (
            expr.op in ("+", "-")
            and isinstance(expr.right, ast.Number)
            and int(expr.right.value) == 1
        ):
            typ = self.compile_expr(expr.left, scope)
            self.coerce(typ, common, expr.line)
            if common is NIBBLE:
                self.emit("INC R1" if expr.op == "+" else "DEC R1")
            else:
                self.emit("MOV R0, 1")
                self.emit("ADD R1, R0" if expr.op == "+" else "SUB R1, R0")
                self.emit("MOV R0, 0")
                self.emit("ADC R2, R0" if expr.op == "+" else "SBB R2, R0")
            return common

        mark = self.temp.mark()
        temp_addr = self.temp.alloc(common.ram_size, "expression", self.filename, expr.line)

        typ = self.compile_expr(expr.left, scope)
        self.coerce(typ, common, expr.line)
        self.store_temp(common, temp_addr)

        typ = self.compile_expr(expr.right, scope)
        self.coerce(typ, common, expr.line)
        if common is NIBBLE:
            self.emit("MOV R2, R1")
        else:
            self.emit("MOV R3, R1")
            self.emit("MOV R4, R2")

        self.load_temp(common, temp_addr)

        if common is NIBBLE:
            instruction = {"+": "ADD", "-": "SUB", "&": "AND", "|": "OR", "^": "XOR"}[expr.op]
            self.emit(f"{instruction} R1, R2")
        else:
            if expr.op == "+":
                self.emit("ADD R1, R3")
                self.emit("ADC R2, R4")
            elif expr.op == "-":
                self.emit("SUB R1, R3")
                self.emit("SBB R2, R4")
            elif expr.op == "&":
                self.emit("AND R1, R3")
                self.emit("AND R2, R4")
            elif expr.op == "|":
                self.emit("OR R1, R3")
                self.emit("OR R2, R4")
            elif expr.op == "^":
                self.emit("XOR R1, R3")
                self.emit("XOR R2, R4")
            else:
                raise BadgeCompileError(
                    f"{location(self.filename, expr.line)}: unsupported char operator {expr.op!r}"
                )

        self.temp.reset(mark)
        return common

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
                self.used_runtime.add("__bc_flash_read_char")
                self.emit("GOSUB __bc_flash_read_char")
                return CHAR
            self.used_runtime.add("__bc_flash_read_nibble")
            self.emit("GOSUB __bc_flash_read_nibble")
            return NIBBLE

        assert symbol.address is not None
        if isinstance(expr.index, ast.Number):
            # A constant index addresses a fixed nibble, so no R4:R5 address
            # calculation and no indirect access are needed.
            address = symbol.address + int(expr.index.value) * symbol.type.ram_size
            self.emit(f"MOV R0, [{address}]")
            self.emit("MOV R1, R0")
            if symbol.type is CHAR:
                self.emit(f"MOV R0, [{address + 1}]")
                self.emit("MOV R2, R0")
                return CHAR
            return NIBBLE

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
        if scale == 1:
            self.emit(f"MOV R4, {(base >> 4) & 0xF}")
            self.emit(f"MOV R5, {base & 0xF}")
            self.emit("MOV R0, R1")
            self.emit("ADD R5, R0")
            self.emit("SKIP NC, 1")
            self.emit("INC R4")
            if index_type is CHAR:
                self.emit("MOV R0, R2")
                self.emit("ADD R4, R0")
        elif scale == 2:
            self.emit("MOV R4, 0")
            self.emit("MOV R5, R1")
            self.emit("ADD R5, R5")
            self.emit("SKIP NC, 1")
            self.emit("INC R4")
            if index_type is CHAR:
                self.emit("MOV R0, R2")
                self.emit("ADD R0, R0")
                self.emit("ADD R4, R0")
            self.emit(f"MOV R0, {base & 0xF}")
            self.emit("ADD R5, R0")
            self.emit("SKIP NC, 1")
            self.emit("INC R4")
            self.emit(f"MOV R0, {(base >> 4) & 0xF}")
            self.emit("ADD R4, R0")
        else:
            raise BadgeCompileError(
                f"{location(self.filename, line)}: unsupported array element size {scale}"
            )

    def compile_flash_addr(self, symbol: VarSymbol, index: ast.Expr, scope: Scope, line: int) -> None:
        assert symbol.flash_label is not None
        index_type = self.compile_expr(index, scope)
        if index_type not in (NIBBLE, CHAR):
            raise BadgeTypeError(
                f"{location(self.filename, line)}: flash array index must be a nibble or char"
            )

        scale = symbol.type.flash_size
        self.emit("MOV R4, R1")
        if index_type is CHAR:
            self.emit("MOV R5, R2")
        else:
            self.emit("MOV R5, 0")
        if scale == 2:
            self.emit("ADD R5, R5")
            self.emit("ADD R4, R4")
            self.emit("SKIP NC, 1")
            self.emit("INC R5")
        elif scale != 1:
            raise BadgeCompileError(
                f"{location(self.filename, line)}: unsupported flash element size {scale}"
            )

        self.emit_flashptr(symbol.flash_label)
        self.emit("MOV R0, R4")
        self.emit("ADD R1, R0")
        self.emit("MOV R0, 0")
        self.emit("ADC R2, R0")
        self.emit("ADC R3, R0")
        self.emit("MOV R0, R5")
        self.emit("ADD R2, R0")
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
        self.calls.append((self.current_function.name, fn.name, False, expr.line))
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
        self.calls.append((self.current_function.name, fn.name, True, expr.line))
        self.temp.reset(mark)
        return fn.decl.return_type

    def compile_builtin(self, expr: ast.Call, scope: Scope) -> Type:
        name = expr.name
        entry = RUNTIME_ENTRY.get(name)
        if entry is not None:
            self.used_runtime.add(entry)

        if name == "uart_init":
            self.require_args(expr, 1)
            typ = self.compile_expr(expr.args[0], scope)
            self.coerce(typ, NIBBLE, expr.line)
            self.emit("GOSUB __bc_uart_init")
            return VOID

        if name in ("uart_putc", "putchar"):
            self.require_args(expr, 1)
            typ = self.compile_expr(expr.args[0], scope)
            self.coerce(typ, CHAR, expr.line)
            self.emit("GOSUB __bc_uart_putc")
            return VOID

        if name == "uart_getc":
            self.require_args(expr, 0)
            self.emit("GOSUB __bc_uart_getc")
            return CHAR

        if name == "uart_available":
            self.require_args(expr, 0)
            self.emit("GOSUB __bc_uart_available")
            return NIBBLE

        if name in ("uart_puts", "puts"):
            self.require_args(expr, 1)
            arg = expr.args[0]
            if isinstance(arg, ast.StringLiteral):
                label = self.new_flash_string(arg.value)
                self.emit_flashptr(label)
            elif isinstance(arg, ast.Var):
                symbol = self.lookup(arg.name, scope, arg.line)
                if symbol.flash_label is not None and symbol.type is CHAR:
                    self.emit_flashptr(symbol.flash_label)
                else:
                    typ = self.compile_expr(arg, scope)
                    self.coerce(typ, FLASHPTR, arg.line)
            else:
                typ = self.compile_expr(arg, scope)
                self.coerce(typ, FLASHPTR, arg.line)
            self.emit("GOSUB __bc_uart_puts")
            return VOID

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

        if name == "uart_write":
            self.require_args(expr, 2)
            buf_arg = expr.args[0]
            if not isinstance(buf_arg, ast.Var):
                raise BadgeTypeError(
                    f"{location(self.filename, expr.line)}: uart_write expects a RAM char array"
                )
            symbol = self.lookup(buf_arg.name, scope, expr.line)
            if (
                symbol.address is None
                or symbol.type is not CHAR
                or symbol.array_len is None
                or symbol.flash_label is not None
            ):
                raise BadgeTypeError(
                    f"{location(self.filename, expr.line)}: uart_write expects a RAM char array"
                )
            typ = self.compile_expr(expr.args[1], scope)
            self.coerce(typ, NIBBLE, expr.line)
            addr = symbol.address
            self.emit(f"MOV R4, {(addr >> 4) & 0xF}")
            self.emit(f"MOV R5, {addr & 0xF}")
            self.emit("GOSUB __bc_uart_write")
            return VOID

        if name == "gpio_read":
            self.require_args(expr, 0)
            self.emit("GOSUB __bc_gpio_read")
            return NIBBLE

        if name == "gpio_write":
            self.require_args(expr, 1)
            typ = self.compile_expr(expr.args[0], scope)
            self.coerce(typ, NIBBLE, expr.line)
            self.emit("GOSUB __bc_gpio_write")
            return VOID

        if name in ("gpio_set", "gpio_clear", "gpio_toggle", "gpio_test"):
            self.require_args(expr, 1)
            typ = self.compile_expr(expr.args[0], scope)
            self.coerce(typ, NIBBLE, expr.line)
            self.emit(f"GOSUB __bc_{name}")
            return NIBBLE if name == "gpio_test" else VOID

        if name in ("gpio_alt", "uart_route", "leds_enable", "matrix_enable"):
            self.require_args(expr, 1)
            typ = self.compile_expr(expr.args[0], scope)
            self.coerce(typ, NIBBLE, expr.line)
            self.emit(f"GOSUB __bc_{name}")
            return VOID

        if name == "display_page":
            self.require_args(expr, 1)
            typ = self.compile_expr(expr.args[0], scope)
            self.coerce(typ, NIBBLE, expr.line)
            self.emit("MOV R0, R1")
            self.emit("MOV [0xF0], R0")
            return VOID

        if name == "display_poke":
            self.require_args(expr, 3)
            mark = self.temp.mark()
            page_addr = self.temp.alloc(1, "display page", self.filename, expr.line)
            index_addr = self.temp.alloc(1, "display index", self.filename, expr.line)
            value_addr = self.temp.alloc(1, "display value", self.filename, expr.line)
            typ = self.compile_expr(expr.args[0], scope)
            self.coerce(typ, NIBBLE, expr.line)
            self.store_temp(NIBBLE, page_addr)
            typ = self.compile_expr(expr.args[1], scope)
            self.coerce(typ, NIBBLE, expr.line)
            self.store_temp(NIBBLE, index_addr)
            typ = self.compile_expr(expr.args[2], scope)
            self.coerce(typ, NIBBLE, expr.line)
            self.store_temp(NIBBLE, value_addr)
            self.load_temp(NIBBLE, page_addr)
            self.emit("MOV R4, R1")
            self.load_temp(NIBBLE, index_addr)
            self.emit("MOV R5, R1")
            self.load_temp(NIBBLE, value_addr)
            self.emit("MOV R0, R1")
            self.emit("MOV [R4:R5], R0")
            self.temp.reset(mark)
            return VOID

        if name == "display_peek":
            self.require_args(expr, 2)
            mark = self.temp.mark()
            page_addr = self.temp.alloc(1, "display page", self.filename, expr.line)
            index_addr = self.temp.alloc(1, "display index", self.filename, expr.line)
            typ = self.compile_expr(expr.args[0], scope)
            self.coerce(typ, NIBBLE, expr.line)
            self.store_temp(NIBBLE, page_addr)
            typ = self.compile_expr(expr.args[1], scope)
            self.coerce(typ, NIBBLE, expr.line)
            self.store_temp(NIBBLE, index_addr)
            self.load_temp(NIBBLE, index_addr)
            self.emit("MOV R5, R1")
            self.load_temp(NIBBLE, page_addr)
            self.emit("MOV R4, R1")
            self.emit("MOV R0, [R4:R5]")
            self.emit("MOV R1, R0")
            self.temp.reset(mark)
            return NIBBLE

        if name == "random":
            self.require_args(expr, 0)
            self.emit("GOSUB __bc_random")
            return NIBBLE

        if name == "seed":
            self.require_args(expr, 1)
            typ = self.compile_expr(expr.args[0], scope)
            self.coerce(typ, NIBBLE, expr.line)
            self.emit("GOSUB __bc_seed")
            return VOID

        if name == "dimmer":
            self.require_args(expr, 1)
            typ = self.compile_expr(expr.args[0], scope)
            self.coerce(typ, NIBBLE, expr.line)
            self.emit("GOSUB __bc_dimmer")
            return VOID

        if name == "key_status":
            self.require_args(expr, 0)
            self.emit("GOSUB __bc_key_status")
            return NIBBLE

        if name == "key_code":
            self.require_args(expr, 0)
            self.emit("GOSUB __bc_key_code")
            return NIBBLE

        if name in ("key_any", "key_alt", "key_just", "key_last"):
            self.require_args(expr, 0)
            self.emit(f"GOSUB __bc_{name}")
            return NIBBLE

        if name == "delay":
            self.require_args(expr, 1)
            typ = self.compile_expr(expr.args[0], scope)
            self.coerce(typ, NIBBLE, expr.line)
            self.emit("GOSUB __bc_delay")
            return VOID

        if name == "memcpy":
            self.require_args(expr, 3)
            dst_arg, src_arg = expr.args[0], expr.args[1]
            if not isinstance(dst_arg, ast.Var) or not isinstance(src_arg, ast.Var):
                raise BadgeTypeError(
                    f"{location(self.filename, expr.line)}: memcpy expects named RAM arrays"
                )
            dst = self.lookup(dst_arg.name, scope, expr.line)
            src = self.lookup(src_arg.name, scope, expr.line)
            for symbol in (dst, src):
                if symbol.address is None or symbol.array_len is None or symbol.flash_label is not None:
                    raise BadgeTypeError(
                        f"{location(self.filename, expr.line)}: memcpy expects named RAM arrays"
                    )
            if dst.type is not src.type or dst.type not in (NIBBLE, CHAR):
                raise BadgeTypeError(
                    f"{location(self.filename, expr.line)}: memcpy source and destination must have the same element type"
                )
            mark = self.temp.mark()
            length_addr = self.temp.alloc(1, "memcpy length", self.filename, expr.line)
            typ = self.compile_expr(expr.args[2], scope)
            self.coerce(typ, NIBBLE, expr.line)
            self.store_temp(NIBBLE, length_addr)

            self.emit(f"MOV R4, {(dst.address >> 4) & 0xF}")
            self.emit(f"MOV R5, {dst.address & 0xF}")
            self.emit(f"MOV R6, {(src.address >> 4) & 0xF}")
            self.emit(f"MOV R7, {src.address & 0xF}")
            self.load_temp(NIBBLE, length_addr)
            if dst.type is NIBBLE:
                self.used_runtime.add("__bc_memcpy_nibbles")
                self.emit("GOSUB __bc_memcpy_nibbles")
            else:
                self.used_runtime.add("__bc_memcpy_chars")
                self.emit("GOSUB __bc_memcpy_chars")
            self.temp.reset(mark)
            return VOID

        if name == "memset":
            self.require_args(expr, 3)
            buf_arg = expr.args[0]
            if not isinstance(buf_arg, ast.Var):
                raise BadgeTypeError(
                    f"{location(self.filename, expr.line)}: memset expects a named RAM array"
                )
            symbol = self.lookup(buf_arg.name, scope, expr.line)
            if symbol.address is None or symbol.array_len is None or symbol.flash_label is not None:
                raise BadgeTypeError(
                    f"{location(self.filename, expr.line)}: memset expects a named RAM array"
                )
            if symbol.type not in (NIBBLE, CHAR):
                raise BadgeTypeError(
                    f"{location(self.filename, expr.line)}: memset cannot fill {symbol.type} arrays"
                )
            mark = self.temp.mark()
            value_addr = self.temp.alloc(
                symbol.type.ram_size, "memset value", self.filename, expr.line
            )
            length_addr = self.temp.alloc(1, "memset length", self.filename, expr.line)
            typ = self.compile_expr(expr.args[1], scope)
            self.coerce(typ, symbol.type, expr.line)
            self.store_temp(symbol.type, value_addr)
            typ = self.compile_expr(expr.args[2], scope)
            self.coerce(typ, NIBBLE, expr.line)
            self.store_temp(NIBBLE, length_addr)

            addr = symbol.address
            self.emit(f"MOV R4, {(addr >> 4) & 0xF}")
            self.emit(f"MOV R5, {addr & 0xF}")
            if symbol.type is NIBBLE:
                self.used_runtime.add("__bc_memset_nibbles")
                self.load_temp(NIBBLE, value_addr)
                self.emit("MOV R3, R1")
                self.load_temp(NIBBLE, length_addr)
                self.emit("GOSUB __bc_memset_nibbles")
            else:
                self.used_runtime.add("__bc_memset_chars")
                self.load_temp(CHAR, value_addr)
                self.emit("MOV R3, R2")
                self.emit("MOV R2, R1")
                self.load_temp(NIBBLE, length_addr)
                self.emit("GOSUB __bc_memset_chars")
            self.temp.reset(mark)
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
            typ = self.compile_expr(expr.args[0], scope)
            self.coerce(typ, CHAR, expr.line)
            self.emit("MOV R4, R2")
            self.emit("MOV R5, R1")
            self.emit("MOV R0, [R4:R5]")
            self.emit("MOV R1, R0")
            return NIBBLE

        if name == "poke":
            self.require_args(expr, 2)
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
        self.emit(f"MOV R0, {value & 0xF}")
        self.emit(f"MOV [{address}], R0")
        if typ is CHAR:
            self.emit(f"MOV R0, {(value >> 4) & 0xF}")
            self.emit(f"MOV [{address + 1}], R0")
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
            self.emit("MOV R0, R1")
            self.emit(f"MOV [{address}], R0")
            if typ is CHAR:
                self.emit("MOV R0, R2")
                self.emit(f"MOV [{address + 1}], R0")
            return

        self.compile_ram_addr(symbol, target.index, scope, target.line)
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
        raise BadgeTypeError(
            f"{location(self.filename, line)}: cannot store to {typ} array"
        )

    def load_symbol(self, symbol: VarSymbol, line: int) -> None:
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
        else:
            raise BadgeCompileError(f"cannot reload {typ}")

    def coerce(self, source: Type, target: Type, line: int) -> None:
        if source is target:
            return
        if source is NIBBLE and target is CHAR:
            self.emit("MOV R2, 0")
            return
        if source is VOID:
            raise BadgeTypeError(
                f"{location(self.filename, line)}: expression has no value"
            )
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
            return None

        left_type = self.infer_type(left, scope)
        right_type = self.infer_type(right, scope)
        if left_type not in (NIBBLE, CHAR) or right_type not in (NIBBLE, CHAR):
            return None
        if not self._is_leaf(right):
            return None
        return self._compare_regs(left, right, op, left_type, right_type, scope, expr.line)

    def _compare_nibble_imm(
        self, left: ast.Expr, constant: int, op: str, scope: Scope, line: int
    ):
        if constant > 15:
            return {
                "<": True,
                "<=": True,
                ">": False,
                ">=": False,
                "==": False,
                "!=": True,
            }[op]

        if op == "<=" and constant == 15:
            return True
        if op == ">" and constant == 15:
            return False

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
            if op == "<":
                return False
            if op == ">=":
                return True
            typ = self.compile_expr(left, scope)
            self.coerce(typ, CHAR, line)
            self.emit("OR R1, R2")
            return "Z" if op in ("==", "<=") else "NZ"

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
                self.emit("MOV R0, R3")
                self.emit("SUB R0, R1")
            else:
                self.emit("MOV R0, R1")
                self.emit("SUB R0, R3")
        else:
            if left_first:
                self.emit("MOV R0, R4")
                self.emit("SUB R0, R2")
            else:
                self.emit("MOV R0, R2")
                self.emit("SUB R0, R4")
            self.emit("SKIP NZ, 2")
            if left_first:
                self.emit("MOV R0, R3")
                self.emit("SUB R0, R1")
            else:
                self.emit("MOV R0, R1")
                self.emit("SUB R0, R3")

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
            return NIBBLE if expr.value <= 15 else CHAR
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
            left = self.infer_type(expr.left, scope)
            right = self.infer_type(expr.right, scope)
            return CHAR if CHAR in (left, right) else NIBBLE
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
                # Emit two NIBBLE directives per byte instead of BYTE.
                # The upstream assembler miscounts BYTE/ASCII data when a
                # later label is resolved, but NIBBLE is one word per line.
                for value in item.values:
                    self.emit(f"NIBBLE 0x{value & 0xF:X}")
                    self.emit(f"NIBBLE 0x{(value >> 4) & 0xF:X}")
            else:
                raise BadgeCompileError(f"unsupported flash data type {item.type}")
            self.emit("")

    # ------------------------------------------------------------------
    # Validation and output
    # ------------------------------------------------------------------

    def validate_call_graph(self) -> None:
        edges: dict[str, list[tuple[str, bool, int]]] = {}
        for caller, callee, tail, line in self.calls:
            edges.setdefault(caller, []).append((callee, tail, line))

        on_stack: set[str] = set()
        visited: set[str] = set()
        path: list[tuple[str, str, bool, int]] = []

        def visit(node: str) -> None:
            if node in visited:
                return
            on_stack.add(node)
            for callee, tail, line in edges.get(node, []):
                if callee in on_stack:
                    # Locate the start of the cycle on the path.
                    start = 0
                    for index, (src, dst, _, _) in enumerate(path):
                        if src == callee or dst == callee:
                            start = index
                            break
                    cycle = path[start:] + [(node, callee, tail, line)]
                    if not all(edge_tail for _, _, edge_tail, _ in cycle):
                        raise BadgeCompileError(
                            f"{location(self.filename, line)}: non-tail recursion involving "
                            f"{callee!r} is not supported; rewrite it as a loop or a tail call"
                        )
                else:
                    path.append((node, callee, tail, line))
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
            for callee, tail, _ in edges.get(node, []):
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

    def map_data(self) -> dict:
        """Return a JSON-serializable symbol/size map."""
        globals_data = []
        for name, symbol in self.globals.items():
            globals_data.append(
                {
                    "name": name,
                    "type": str(symbol.type),
                    "address": symbol.address,
                    "array_len": symbol.array_len,
                    "const": symbol.is_const,
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
                {"caller": caller, "callee": callee, "tail": tail, "line": line}
                for caller, callee, tail, line in self.calls
            ],
            "runtime": sorted(self.used_runtime),
            "ram_nibbles_used": self.mem.used(),
            "max_call_depth": self.max_call_depth,
        }

    # ------------------------------------------------------------------
    # Emission helpers
    # ------------------------------------------------------------------

    def emit(self, line: str) -> None:
        self.lines.append(line)
