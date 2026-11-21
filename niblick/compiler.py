"""Niblick semantic analysis and code generation.

Values are kept in fixed registers at expression boundaries:

    nibble    R1
    char      R1 (low), R2 (high)
    flashptr  R1 (low), R2 (mid), R3 (high)

Temporaries for nested expressions live in a static scratch area
(0x20..0x3F).  Variables and arrays live from 0x40 upward.  The hardware
call stack is used for GOSUB/RET; tail calls become GOTO.
"""

from __future__ import annotations

import copy
import dataclasses
import math
import re
import struct
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
from .errors import NiblickCompileError, NiblickError, NiblickTypeError, location
from .format import expand_print
from .types import (
    BOOL,
    F16,
    F32,
    FLASHPTR,
    I8,
    I16,
    I32,
    I64,
    U4,
    U8,
    U16,
    U32,
    U64,
    VOID,
    StructType,
    Type,
    common_type,
    fits_value,
    is_comparable,
    is_float_type,
    is_integer,
    is_testable,
    promoted_mul_type,
    smallest_type_for,
    type_for,
    widen_type,
)


RAM_START = 0x40
RAM_END = 0xF0
TEMP_START = 0x20
# 0x38..0x3F holds runtime/assembly scratch.  Functions with live temporaries
# at a call use their own frame instead, so the full range is safe here.
TEMP_END = 0x40

BUILTINS = {
    "print": VOID,
    "uart_putc": VOID,
    "uart_getc": U8,
    "flash_read_char": U8,
    "flash_read_nibble": U4,
    "flash_next": U8,
    "out": VOID,
    "in": U4,
    "peek": U4,
    "poke": VOID,
    "gpio_set": VOID,
    "gpio_clear": VOID,
    "gpio_toggle": VOID,
    "gpio_test": U4,
    "peek8": U8,
    "poke8": VOID,
    "high_nibble": U4,
    "low_nibble": U4,
    "w5500_spi_tx_fast": VOID,
    "w5500_spi_xfer_fast": U8,
    "delay": VOID,
    "__nib_f16_bits": U16,
    "__nib_f16_from_bits": F16,
    "__nib_f32_bits": U32,
    "__nib_f32_from_bits": F32,
}


# Builtins that are implemented by a runtime label.
RUNTIME_ENTRY = {
    "uart_putc": "__nib_uart_putc",
    "uart_getc": "__nib_uart_getc",
    "flash_read_char": "__nib_flash_read_char",
    "flash_read_nibble": "__nib_flash_read_nibble",
    "flash_next": "__nib_flash_read_char_ptr",
    "gpio_set": "__nib_gpio_set",
    "gpio_clear": "__nib_gpio_clear",
    "gpio_toggle": "__nib_gpio_toggle",
    "gpio_test": "__nib_gpio_test",
    "delay": "__nib_delay",
    "w5500_spi_tx_fast": "__nib_w5500_spi_tx_fast",
    "w5500_spi_xfer_fast": "__nib_w5500_spi_xfer_fast",
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
    temp_size: int = 0
    temp_base: int = 0


class Scope:
    def __init__(self, parent: Optional["Scope"] = None) -> None:
        self.parent = parent
        self.symbols: dict[str, VarSymbol] = {}

    def define(self, symbol: VarSymbol, filename: str = "<input>") -> None:
        if symbol.name in self.symbols:
            raise NiblickCompileError(
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
            raise NiblickCompileError(f"{location(filename, line)}: cannot allocate zero-sized {what}")
        if self.next + size > self.end:
            raise NiblickCompileError(
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
        self.peak = 0

    def mark(self) -> int:
        return self.top

    def reset(self, mark: int) -> None:
        self.top = mark

    def alloc(self, size: int, what: str, filename: str, line: int) -> int:
        if self.top + size > self.end:
            raise NiblickCompileError(
                f"{location(filename, line)}: expression is too complex for the temporary area "
                f"({size} nibbles needed, {self.end - self.top} free)"
            )
        address = self.top
        self.top += size
        self.peak = max(self.peak, self.top - self.start)
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
        self.spill_sizes: dict[str, int] = {}
        self.qword_result_addr: Optional[int] = None
        self.struct_result_addr: Optional[int] = None
        self.struct_result_size = 0
        self.qword_slots: list[int] = []
        self.qword_top = 0
        self.call_temp_live: dict[str, int] = {}
        self.temp_peak: dict[str, int] = {}
        self._is_probe = False
        self.lines: list[str] = []
        self.globals: dict[str, VarSymbol] = {}
        self.functions: dict[str, FunctionSymbol] = {}
        self.global_inits: list[tuple[VarSymbol, ast.Expr]] = []
        self.global_aggregate_inits: list[ast.Stmt] = []
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

    def trim_unused_f16_asm(self) -> None:
        """Drop unreachable binary16 multiply/divide code from the core.

        The f16 helpers share one assembly core.  When a program does not use
        multiplication or division, remove those blocks before the assembly is
        scanned so the 32-bit divider is not linked and the add/sub path remains
        separate.
        """
        from .inline import _float_helpers_needed

        needed = _float_helpers_needed(self.program, 16)
        if not needed:
            return
        use_mul = "__nib_f16_mul" in needed
        use_div = "__nib_f16_div" in needed
        if use_mul and use_div:
            return
        for source in self.emitted_asm_sources:
            if not str(source.path).endswith("float16.asm"):
                continue
            text = source.text
            if not use_mul and not use_div:
                mode_check = (
                    "    MOV R0, [0x3F]\n"
                    "    CP R0, 0\n"
                    "    SKIP Z, 2\n"
                    "    GOTO .muldiv_special\n"
                    "    GOTO .add_special\n"
                    ".add_special:\n"
                )
                text = text.replace(mode_check, ".add_special:\n", 1)
                start = text.find(".unpack_done:")
                end = text.find("\n.align:", start)
                if start != -1 and end != -1:
                    text = text[:start] + ".unpack_done:\n" + text[end + 1:]
            elif not use_div:
                text = text.replace(
                    "    GOSUB __nib_divmod32\n", "    MOV R0, R0\n"
                )
            source.text = text


    def trim_unused_f32_asm(self) -> None:
        """Drop the binary32 multiply/divide blocks when they are unused.

        The f32 helpers share one assembly core.  Trimming the marked blocks
        keeps an add/sub-only program from linking the 32-bit multiply and
        divide runtimes.
        """
        from .inline import _float_helpers_needed

        needed = _float_helpers_needed(self.program, 32)
        if not needed:
            return
        use_mul = "__nib_f32_mul" in needed
        use_div = "__nib_f32_div" in needed
        if use_mul and use_div:
            return
        for source in self.emitted_asm_sources:
            if not str(source.path).endswith("float32.asm"):
                continue
            text = source.text
            names: tuple[str, ...]
            if use_mul:
                names = ("div-special", "div-calc")
            elif use_div:
                names = ("mul-special", "mul-calc")
            else:
                names = ("muldiv", "dispatch", "align-dispatch")
            for name in names:
                begin = f"; @niblick-f32: {name}-begin"
                end = f"; @niblick-f32: {name}-end"
                while True:
                    start = text.find(begin)
                    if start == -1:
                        break
                    stop = text.find(end, start)
                    if stop == -1:
                        break
                    stop = text.find("\n", stop)
                    if stop == -1:
                        stop = len(text)
                    text = text[:start] + text[stop + 1 :]
            source.text = text

    def compile(self) -> str:
        if self.program.imports:
            raise NiblickCompileError(
                f"{self.filename}: imports must be resolved first; "
                "load the program with niblick.loader.load_program()"
            )
        expand_print(self.program, self.filename)
        optimize_program(self.program)
        probe = Compiler(copy.deepcopy(self.program), self.filename)
        probe.run_probe()
        self.spill_sizes = {
            name: probe.temp_peak.get(name, 0)
            for name, live in probe.call_temp_live.items()
            if live > 0
        }
        self.prepare_globals()
        self.prepare_functions()
        if "main" not in self.functions:
            raise NiblickCompileError(f"{self.filename}: no main() function found")
        self.current_source = None
        self.emit("; Niblick generated assembly")
        self.emit("GOTO fn_main")
        for fn in self.program.functions:
            self.compile_function(self.functions[fn.name])
        self.emit("")
        self.current_source = None
        self.all_asm_scans = self.scan_asm_sources(self.program.asm_sources)
        self.emitted_asm_sources = self.kept_asm_sources()
        self.trim_unused_f16_asm()
        self.trim_unused_f32_asm()
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
        self.emit("; @niblick-src-end")
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
            raise NiblickCompileError(
                f"{self.filename}: imports must be resolved first; "
                "load the program with niblick.loader.load_program()"
            )
        expand_print(self.program, self.filename)
        if prune and "main" in {fn.name for fn in self.program.functions}:
            optimize_program(self.program)
        probe = Compiler(copy.deepcopy(self.program), self.filename)
        probe.run_probe()
        self.spill_sizes = {
            name: probe.temp_peak.get(name, 0)
            for name, live in probe.call_temp_live.items()
            if live > 0
        }
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

    @staticmethod
    def _wrap_value(value: int, typ: Type) -> int:
        """Wrap a mathematical integer into *typ*'s two's-complement range."""

        bits = 4 * max(typ.ram_size, 1)
        value &= (1 << bits) - 1
        if typ.signed and value >= (1 << (bits - 1)):
            value -= 1 << bits
        return value

    @staticmethod
    def _arith_type(typ: Type) -> Type:
        """Bool promotes to a 4-bit integer when used in arithmetic."""

        return U4 if typ is BOOL else typ

    @staticmethod
    def _pack_float(value: float, typ: Type) -> int:
        if typ is F16:
            try:
                data = struct.pack(">e", value)
            except OverflowError:
                data = struct.pack(">e", math.copysign(math.inf, value))
            return int.from_bytes(data, "big")
        if typ is F32:
            try:
                data = struct.pack(">f", value)
            except OverflowError:
                data = struct.pack(">f", math.copysign(math.inf, value))
            return int.from_bytes(data, "big")
        raise NiblickCompileError(f"cannot pack float type {typ}")

    @staticmethod
    def _unpack_float(bits: int, typ: Type) -> float:
        if typ is F16:
            return struct.unpack(">e", bits.to_bytes(2, "big"))[0]
        if typ is F32:
            return struct.unpack(">f", bits.to_bytes(4, "big"))[0]
        raise NiblickCompileError(f"cannot unpack float type {typ}")

    def _emit_float_bits(self, value: float, typ: Type) -> None:
        bits = self._pack_float(value, typ)
        if typ is F16:
            self._emit_immediate(bits, _REGS[4])
        elif typ is F32:
            self._emit_immediate(bits, _REGS[8])
        else:
            raise NiblickCompileError(f"cannot emit float type {typ}")

    def _float_int_type(self, typ: Type) -> Type:
        if typ is F16:
            return U16
        if typ is F32:
            return U32
        raise NiblickCompileError(f"not a float type: {typ}")

    @staticmethod
    def _is_qword(typ: Type) -> bool:
        return is_integer(typ) and typ.ram_size == 16

    def ensure_qword_result(self) -> int:
        if self.qword_result_addr is None:
            self.qword_result_addr = self.mem.alloc(
                16, "64-bit result", self.filename, 0
            )
        return self.qword_result_addr

    def _qword_slot(self, index: int) -> int:
        while len(self.qword_slots) <= index:
            self.qword_slots.append(
                self.mem.alloc(16, "64-bit temporary", self.filename, 0)
            )
        return self.qword_slots[index]

    def qword_mark(self) -> int:
        return self.qword_top

    def qword_reset(self, mark: int) -> None:
        self.qword_top = mark

    def alloc_qword_slot(self) -> int:
        address = self._qword_slot(self.qword_top)
        self.qword_top += 1
        return address

    @staticmethod
    def _fits_width(typ: Type, value: int) -> bool:
        """Whether *value* is representable in *typ*'s bit width.

        This accepts both the signed and unsigned interpretation of the bit
        pattern, so explicit masks such as ``0xFFFF`` can initialize a signed
        16-bit value.
        """

        bits = 4 * max(typ.ram_size, 1)
        return -(1 << (bits - 1)) <= value <= (1 << bits) - 1

    @staticmethod
    def _stored_value(value: int, typ: Type) -> int:
        """Interpret a stored bit pattern as a mathematical value."""

        return Compiler._wrap_value(value, typ)

    @staticmethod
    def _literal_value(expr: ast.Expr) -> Optional[int]:
        """Return the mathematical value of a numeric literal expression."""

        if isinstance(expr, ast.Number):
            return int(expr.value)
        if (
            isinstance(expr, ast.Unary)
            and expr.op == "-"
            and isinstance(expr.operand, ast.Number)
        ):
            return -int(expr.operand.value)
        return None

    @staticmethod
    def _natural_literal_type(value: int) -> Type:
        return smallest_type_for(value, signed_hint=False)

    def _literal_type_for(self, value: int, context: Optional[Type]) -> Type:
        """Choose a type for a literal in a typed context.

        A literal adopts the context type when the value fits.  In a signed
        context, an oversized literal widens to a signed type that can hold it.
        In an unsigned context, a negative literal wraps modulo the context
        width (preserving the existing unsigned arithmetic behavior), while an
        oversized positive literal widens to a larger unsigned type.
        """

        if context is not None and is_integer(context):
            if fits_value(context, value):
                return context
            if context.signed:
                for width in (1, 2, 4, 8, 16):
                    if width >= context.ram_size:
                        candidate = type_for(width, True)
                        if fits_value(candidate, value):
                            return candidate
                return context
            if value < 0:
                return context
            for width in (2, 4, 8, 16):
                if width >= context.ram_size:
                    candidate = type_for(width, False)
                    if fits_value(candidate, value):
                        return candidate
            return context
        return self._natural_literal_type(value)

    def _common_for_literals(self, left: int, right: int) -> Type:
        signed = left < 0 or right < 0
        for width in (1, 2, 4, 8, 16):
            candidate = type_for(width, signed)
            if fits_value(candidate, left) and fits_value(candidate, right):
                return candidate
        return I64 if signed else U64

    def _common_expr_type(
        self, left: ast.Expr, right: ast.Expr, scope: Scope
    ) -> Type:
        """Common type of two expressions, adapting literals to their context."""

        left_value = self._literal_value(left)
        right_value = self._literal_value(right)
        if left_value is not None and right_value is not None:
            return self._common_for_literals(left_value, right_value)

        if left_value is not None:
            right_type = self._arith_type(self.infer_type(right, scope))
            if not is_integer(right_type):
                return right_type
            left_type = self._literal_type_for(left_value, right_type)
            return common_type(left_type, right_type)

        if right_value is not None:
            left_type = self._arith_type(self.infer_type(left, scope))
            if not is_integer(left_type):
                return left_type
            right_type = self._literal_type_for(right_value, left_type)
            return common_type(left_type, right_type)

        return common_type(
            self._arith_type(self.infer_type(left, scope)),
            self._arith_type(self.infer_type(right, scope)),
        )

    def _common_const_type(
        self,
        left_value: Optional[int],
        left_type: Type,
        right_value: Optional[int],
        right_type: Type,
    ) -> Type:
        """Common type for already-evaluated constant operands."""

        if left_value is not None and right_value is not None:
            return self._common_for_literals(left_value, right_value)
        left_type = self._arith_type(left_type)
        right_type = self._arith_type(right_type)
        if left_value is not None and is_integer(right_type):
            return common_type(self._literal_type_for(left_value, right_type), right_type)
        if right_value is not None and is_integer(left_type):
            return common_type(left_type, self._literal_type_for(right_value, left_type))
        return common_type(left_type, right_type)

    def _emit_qword_copy(self, source: int, target: int) -> None:
        for index in range(16):
            self.emit(f"MOV R0, [{source + index}]")
            self.emit(f"MOV [{target + index}], R0")

    def _emit_qword_zero(self, target: int) -> None:
        self.emit("MOV R0, 0")
        for index in range(16):
            self.emit(f"MOV [{target + index}], R0")

    def _emit_extend_to_qword(self, source: Type, target: int) -> None:
        width = source.ram_size
        for index in range(width):
            self.emit(f"MOV R0, R{index + 1}")
            self.emit(f"MOV [{target + index}], R0")
        if source.signed:
            top = f"R{width}"
            self.emit(f"MOV R0, {top}")
            self.emit("AND R0, 8")
            self.emit("CP R0, 0")
            self.emit("MOV R9, 0")
            self.emit("SKIP Z, 1")
            self.emit("MOV R9, 15")
            for index in range(width, 16):
                self.emit("MOV R0, R9")
                self.emit(f"MOV [{target + index}], R0")
        else:
            self.emit("MOV R0, 0")
            for index in range(width, 16):
                self.emit(f"MOV [{target + index}], R0")

    def _emit_load_low_regs(self, source: int, width: int) -> None:
        for index in range(width):
            self.emit(f"MOV R0, [{source + index}]")
            self.emit(f"MOV R{index + 1}, R0")

    def _emit_qword_truth_to_r1(self, address: Optional[int] = None) -> None:
        addr = self.ensure_qword_result() if address is None else address
        self.emit(f"MOV R0, [{addr}]")
        self.emit("MOV R1, R0")
        for index in range(1, 16):
            self.emit(f"MOV R0, [{addr + index}]")
            self.emit("OR R1, R0")

    def _emit_qword_immediate(self, value: int, typ: Type, address: int) -> None:
        value = self._wrap_value(value, typ)
        for index in range(16):
            self.emit(f"MOV R0, {(value >> (4 * index)) & 0xF}")
            self.emit(f"MOV [{address + index}], R0")

    def _emit_qword_load_indirect(self, address: int) -> None:
        for index in range(16):
            self.emit("MOV R0, [R4:R5]")
            self.emit(f"MOV [{address + index}], R0")
            if index != 15:
                self.emit("INC R5")
                self.emit("SKIP NC, 1")
                self.emit("INC R4")

    def _emit_qword_store_indirect(self, source: int) -> None:
        for index in range(16):
            self.emit(f"MOV R0, [{source + index}]")
            self.emit("MOV [R4:R5], R0")
            if index != 15:
                self.emit("INC R5")
                self.emit("SKIP NC, 1")
                self.emit("INC R4")

    def _emit_qword_binary(
        self, op: str, left: int, right: int, result: int
    ) -> None:
        if op in ("+", "-"):
            first = "ADD" if op == "+" else "SUB"
            rest = "ADC" if op == "+" else "SBB"
            for index in range(16):
                if op == "-":
                    self.emit(f"MOV R0, [{right + index}]")
                    self.emit("MOV R1, R0")
                    self.emit(f"MOV R0, [{left + index}]")
                else:
                    self.emit(f"MOV R0, [{left + index}]")
                    self.emit("MOV R1, R0")
                    self.emit(f"MOV R0, [{right + index}]")
                self.emit(f"{first if index == 0 else rest} R0, R1")
                self.emit(f"MOV [{result + index}], R0")
            return
        instruction = _NIBBLE_BINARY[op]
        for index in range(16):
            self.emit(f"MOV R0, [{left + index}]")
            self.emit("MOV R1, R0")
            self.emit(f"MOV R0, [{right + index}]")
            self.emit(f"{instruction} R0, R1")
            self.emit(f"MOV [{result + index}], R0")

    def _emit_qword_complement(self, address: int) -> None:
        for index in range(16):
            self.emit(f"MOV R0, [{address + index}]")
            self.emit("XOR R0, 15")
            self.emit(f"MOV [{address + index}], R0")

    def _emit_qword_negate(self, address: int) -> None:
        self._emit_qword_complement(address)
        self.emit("MOV R0, 15")
        self.emit("ADD R0, 1")  # set carry
        for index in range(16):
            self.emit(f"MOV R0, [{address + index}]")
            self.emit("MOV R1, 0")
            self.emit("ADC R0, R1")
            self.emit(f"MOV [{address + index}], R0")

    def _emit_qword_shift_step(
        self, address: int, op: str, arithmetic: bool
    ) -> None:
        if op == "<<":
            for index in range(16):
                self.emit(f"MOV R0, [{address + index}]")
                self.emit(f"{'ADD' if index == 0 else 'ADC'} R0, R0")
                self.emit(f"MOV [{address + index}], R0")
            return
        if arithmetic:
            self.emit(f"MOV R0, [{address + 15}]")
            self.emit("ADD R0, R0")  # carry = sign bit
        else:
            self.emit("MOV R0, 0")
            self.emit("ADD R0, 0")   # clear carry
        for index in range(15, -1, -1):
            self.emit(f"MOV R0, [{address + index}]")
            self.emit("RRC R0")
            self.emit(f"MOV [{address + index}], R0")

    def _emit_qword_shift_loop(
        self, address: int, count_address: int, op: str, arithmetic: bool
    ) -> None:
        loop = self.new_label("qshift")
        done = self.new_label("qshiftdone")
        self.emit(f"{loop}:")
        self.emit(f"MOV R0, [{count_address}]")
        self.emit("MOV R1, R0")
        self.emit(f"MOV R0, [{count_address + 1}]")
        self.emit("OR R0, R1")
        self.emit("CP R0, 0")
        self.emit("SKIP NZ, 2")
        self.emit(f"GOTO {done}")
        self._emit_qword_shift_step(address, op, arithmetic)
        self.emit("MOV R9, 1")
        self.emit(f"MOV R0, [{count_address}]")
        self.emit("SUB R0, R9")
        self.emit(f"MOV [{count_address}], R0")
        self.emit("MOV R9, 0")
        self.emit(f"MOV R0, [{count_address + 1}]")
        self.emit("SBB R0, R9")
        self.emit(f"MOV [{count_address + 1}], R0")
        self.emit(f"GOTO {loop}")
        self.emit(f"{done}:")

    def _emit_qword_compare(
        self, left: int, right: int, signed: bool, op: str
    ) -> Type:
        if op in ("==", "!="):
            self.emit("MOV R9, 0")
            for index in range(16):
                self.emit(f"MOV R0, [{left + index}]")
                self.emit("MOV R1, R0")
                self.emit(f"MOV R0, [{right + index}]")
                self.emit("XOR R0, R1")
                self.emit("OR R9, R0")
            self.emit("MOV R0, R9")
            self.emit("CP R0, 0")
            self.emit("MOV R1, 0")
            self.emit(f"SKIP {'NZ' if op == '==' else 'Z'}, 1")
            self.emit("INC R1")
            return BOOL

        diff_label = self.new_label("qdiff")
        equal_label = self.new_label("qequal")
        end_label = self.new_label("qcmpend")

        if signed:
            same_label = self.new_label("qsame")
            sign_diff_label = self.new_label("qsign")
            self.emit(f"MOV R0, [{left + 15}]")
            self.emit("AND R0, 8")
            self.emit("MOV R1, R0")
            self.emit(f"MOV R0, [{right + 15}]")
            self.emit("AND R0, 8")
            self.emit("MOV R9, R1")
            self.emit("MOV R1, R0")
            self.emit("SUB R9, R1")
            self.emit("MOV R0, R9")
            self.emit("SKIP Z, 2")
            self.emit(f"GOTO {sign_diff_label}")
            self.emit(f"GOTO {same_label}")
            self.emit(f"{sign_diff_label}:")
            flag = "C" if op in ("<", "<=") else "NC"
            self.emit("MOV R1, 0")
            self.emit(f"SKIP {_FLAG_INVERSE[flag]}, 1")
            self.emit("INC R1")
            self.emit(f"GOTO {end_label}")
            self.emit(f"{same_label}:")

        for index in range(15, -1, -1):
            self.emit(f"MOV R0, [{left + index}]")
            self.emit("MOV R1, R0")
            self.emit(f"MOV R0, [{right + index}]")
            self.emit("SUB R1, R0")
            self.emit("SKIP Z, 2")
            self.emit(f"GOTO {diff_label}")
        self.emit(f"GOTO {equal_label}")
        self.emit(f"{diff_label}:")
        flag = "C" if op in (">", ">=") else "NC"
        self.emit("MOV R1, 0")
        self.emit(f"SKIP {_FLAG_INVERSE[flag]}, 1")
        self.emit("INC R1")
        self.emit(f"GOTO {end_label}")
        self.emit(f"{equal_label}:")
        self.emit(f"MOV R1, {1 if op in ('<=', '>=') else 0}")
        self.emit(f"{end_label}:")
        return BOOL

    def _emit_sign_fill(self, source_width: int, target_width: int) -> None:
        """Fill registers above *source_width* with the source's sign nibble."""

        if source_width >= target_width:
            return
        top = f"R{source_width}"
        self.emit(f"MOV R0, {top}")
        self.emit("AND R0, 8")
        self.emit("CP R0, 0")
        self.emit("MOV R9, 0")
        self.emit("SKIP Z, 1")
        self.emit("MOV R9, 15")
        for index in range(source_width, target_width):
            self.emit(f"MOV R{index + 1}, R9")

    def _normalize_bool(self, source: Type, line: int) -> None:
        """Convert the integer value in R1..Rn to a 0/1 bool in R1."""

        self.emit_truth_value(source)
        self.emit("MOV R0, R1")
        self.emit("CP R0, 0")
        self.emit("MOV R1, 0")
        self.emit("SKIP Z, 1")
        self.emit("INC R1")

    def _flip_sign_bit(self, common: Type, regs: tuple[str, ...]) -> None:
        """Map signed order onto unsigned order by flipping the top bit."""

        if not common.signed:
            return
        top = regs[-1]
        self.emit(f"MOV R0, {top}")
        self.emit("XOR R0, 8")
        self.emit(f"MOV {top}, R0")

    def fold_const_decl(
        self,
        target: Type,
        init: ast.Expr,
        scope: Optional[Scope],
        line: int,
    ) -> Optional[int]:
        """Fold a scalar const initializer, or return None if it is dynamic."""

        folded = self.eval_const(init, scope, target)
        if folded is None:
            return None
        value, typ = folded
        if typ.ram_size > target.ram_size:
            raise NiblickTypeError(
                f"{location(self.filename, line)}: cannot convert {typ} value {value} "
                f"to {target}"
            )
        return self._wrap_value(value, target) & self._width_mask(target)

    def eval_const(
        self,
        expr: ast.Expr,
        scope: Optional[Scope],
        expected: Optional[Type] = None,
    ) -> Optional[tuple[int, Type]]:
        """Return ``(value, type)`` when *expr* is a compile-time integer.

        Values are mathematical integers in the type's range: unsigned values
        are non-negative, signed values may be negative.  The rules mirror
        :meth:`infer_type` and runtime arithmetic, including the expected-type
        width floor, so a folded expression produces exactly the same bits as
        generated code would.  Anything with a side effect or unknown value
        returns ``None`` and is compiled normally.
        """

        if isinstance(expr, ast.FloatLiteral):
            typ = expected if expected is not None and is_float_type(expected) else F32
            return self._pack_float(expr.value, typ), typ

        if isinstance(expr, ast.Number):
            value = int(expr.value)
            if value < 0 or value > 0xFFFFFFFFFFFFFFFF:
                raise NiblickCompileError(
                    f"{location(self.filename, expr.line)}: integer {value} "
                    "does not fit in 64 bits"
                )
            if expected is not None and expected is BOOL:
                return (1 if value else 0), BOOL
            typ = (
                expected
                if expected is not None
                and is_integer(expected)
                and fits_value(expected, value)
                else self._natural_literal_type(value)
            )
            return value, typ

        if isinstance(expr, ast.Var):
            symbol = scope.lookup(expr.name) if scope is not None else None
            if symbol is not None:
                if symbol.const_value is None:
                    return None
                return self._stored_value(symbol.const_value, symbol.type), symbol.type
            if expr.name in self.const_globals:
                value, typ = self.const_globals[expr.name]
                return self._stored_value(value, typ), typ
            symbol = self.globals.get(expr.name)
            if symbol is not None and symbol.const_value is not None:
                return self._stored_value(symbol.const_value, symbol.type), symbol.type
            return None

        if isinstance(expr, (ast.ToType, ast.Cast)):
            target = expr.type
            if not (is_integer(target) or target is BOOL):
                return None
            folded = self.eval_const(expr.operand, scope)
            if folded is None:
                return None
            value, source = folded
            if target is BOOL:
                return (1 if value else 0), BOOL
            if not (is_integer(source) or source is BOOL):
                return None
            return self._wrap_value(value, target), target

        if isinstance(expr, ast.Conditional):
            condition = self.eval_const(expr.condition, scope)
            if condition is None:
                return None
            result_type = self.infer_type(expr, scope or Scope())
            if expected is not None:
                if is_integer(result_type) and is_integer(expected):
                    result_type = widen_type(result_type, expected)
                elif expected is BOOL:
                    result_type = BOOL
                elif is_float_type(expected):
                    if not is_float_type(result_type):
                        return None
                    result_type = expected
            selected = expr.then_expr if condition[0] else expr.else_expr
            folded = self.eval_const(selected, scope, result_type)
            if folded is None:
                return None
            value, typ = folded
            if result_type is BOOL:
                return (1 if value else 0), BOOL
            if is_integer(result_type) and is_integer(typ):
                return self._wrap_value(value, result_type), result_type
            if is_float_type(result_type) and is_float_type(typ):
                return value, result_type
            return folded

        if isinstance(expr, ast.Unary):
            if expr.op == "&":
                return None
            if expr.op == "-" and isinstance(expr.operand, ast.FloatLiteral):
                typ = expected if expected is not None and is_float_type(expected) else F32
                return self._pack_float(-expr.operand.value, typ), typ
            if expr.op == "-":
                literal = self._literal_value(expr)
                if literal is not None:
                    if literal < -(1 << 63):
                        raise NiblickCompileError(
                            f"{location(self.filename, expr.line)}: integer "
                            f"{literal} does not fit in 64 bits"
                        )
                    typ = smallest_type_for(literal, signed_hint=True)
                    typ = widen_type(typ, expected)
                    return self._wrap_value(literal, typ), typ
                folded = self.eval_const(expr.operand, scope)
                if folded is None:
                    return None
                value, operand_type = folded
                if not is_integer(operand_type):
                    return None
                width = operand_type.ram_size
                if expected is not None and is_integer(expected):
                    width = max(width, expected.ram_size)
                result_type = type_for(width, True)
                return self._wrap_value(-value, result_type), result_type

            if expr.op == "+":
                return self.eval_const(expr.operand, scope, expected)
            folded = self.eval_const(expr.operand, scope)
            if folded is None:
                return None
            value, typ = folded
            if expr.op == "!":
                return (0 if value else 1), BOOL
            if expr.op == "~":
                if not is_integer(typ):
                    return None
                result_type = widen_type(typ, expected)
                value = self._wrap_value(value, result_type)
                return self._wrap_value(~value, result_type), result_type
            return None

        if isinstance(expr, ast.Binary):
            left = self.eval_const(expr.left, scope)
            right = self.eval_const(expr.right, scope)
            if left is None or right is None:
                return None
            left_value, left_type = left
            right_value, right_type = right

            if expr.op in ("&&", "||"):
                result = (
                    bool(left_value) and bool(right_value)
                    if expr.op == "&&"
                    else bool(left_value) or bool(right_value)
                )
                return (1 if result else 0), BOOL

            if expr.op in ("==", "!=", "<", "<=", ">", ">="):
                common = self._common_const_type(left_value, left_type, right_value, right_type)
                if common is BOOL:
                    common = U4
                if not is_integer(common):
                    return None
                a = self._wrap_value(left_value, common)
                b = self._wrap_value(right_value, common)
                result = {
                    "==": a == b,
                    "!=": a != b,
                    "<": a < b,
                    "<=": a <= b,
                    ">": a > b,
                    ">=": a >= b,
                }[expr.op]
                return (1 if result else 0), BOOL

            if expr.op in ("<<", ">>"):
                if not is_integer(left_type):
                    return None
                result_type = widen_type(left_type, expected)
                width = 4 * result_type.ram_size
                value = self._wrap_value(left_value, result_type)
                count = right_value
                if count < 0:
                    count = 0
                if expr.op == "<<":
                    shifted = (value << count) & self._width_mask(result_type)
                else:
                    shifted = value >> count
                return self._wrap_value(shifted, result_type), result_type

            if expr.op == "*":
                common = self._common_const_type(left_value, left_type, right_value, right_type)
                if not is_integer(common):
                    return None
                result_type = widen_type(promoted_mul_type(common), expected)
                a = self._wrap_value(left_value, result_type)
                b = self._wrap_value(right_value, result_type)
                return self._wrap_value(a * b, result_type), result_type

            if expr.op in ("/", "%"):
                common = self._common_const_type(left_value, left_type, right_value, right_type)
                if not is_integer(common):
                    return None
                result_type = widen_type(common, expected)
                a = self._wrap_value(left_value, result_type)
                b = self._wrap_value(right_value, result_type)
                if b == 0:
                    value = 0
                elif result_type.signed:
                    quotient = abs(a) // abs(b)
                    if (a < 0) != (b < 0):
                        quotient = -quotient
                    value = quotient if expr.op == "/" else a - quotient * b
                else:
                    value = a // b if expr.op == "/" else a % b
                return self._wrap_value(value, result_type), result_type

            if expr.op in ("+", "-", "&", "|", "^"):
                common = self._common_const_type(left_value, left_type, right_value, right_type)
                if not is_integer(common):
                    return None
                result_type = widen_type(common, expected)
                a = self._wrap_value(left_value, result_type)
                b = self._wrap_value(right_value, result_type)
                value = {
                    "+": a + b,
                    "-": a - b,
                    "&": a & b,
                    "|": a | b,
                    "^": a ^ b,
                }[expr.op]
                return self._wrap_value(value, result_type), result_type

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
            and not decl.is_array
            and decl.init is not None
            and (is_integer(decl.type) or decl.type is BOOL or decl.type.is_float)
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

    def _max_struct_size(self) -> int:
        best = 0
        for fn in self.program.functions:
            typ = fn.return_type
            if isinstance(typ, StructType):
                best = max(best, typ.ram_size)
        return best

    def resolve_array_len(
        self,
        array_len: Optional[int],
        array_len_expr: Optional[ast.Expr],
        scope: Optional[Scope],
        name: str,
        line: int,
    ) -> Optional[int]:
        if array_len_expr is not None:
            folded = self.eval_const(array_len_expr, scope)
            if folded is None:
                raise NiblickCompileError(
                    f"{location(self.filename, line)}: array length for "
                    f"{name!r} must be a compile-time integer constant"
                )
            value, typ = folded
            if not is_integer(typ):
                raise NiblickTypeError(
                    f"{location(self.filename, line)}: array length for "
                    f"{name!r} must be an integer"
                )
            array_len = value
        if array_len is None:
            return None
        if array_len <= 0:
            raise NiblickCompileError(
                f"{location(self.filename, line)}: array length for {name!r} "
                "must be positive"
            )
        return int(array_len)

    def resolve_local_array_lengths(self) -> None:
        def walk(stmt: ast.Stmt) -> None:
            if isinstance(stmt, ast.VarDecl):
                stmt.array_len = self.resolve_array_len(
                    stmt.array_len,
                    stmt.array_len_expr,
                    None,
                    stmt.name,
                    stmt.line,
                )
            elif isinstance(stmt, ast.Block):
                for child in stmt.statements:
                    walk(child)
            elif isinstance(stmt, ast.If):
                walk(stmt.then_block)
                if stmt.else_block is not None:
                    walk(stmt.else_block)
            elif isinstance(stmt, ast.While):
                walk(stmt.body)
            elif isinstance(stmt, ast.For):
                if stmt.init is not None:
                    walk(stmt.init)
                walk(stmt.body)

        for fn in self.program.functions:
            if not fn.is_extern:
                walk(fn.body)

    def build_aggregate_inits(
        self,
        name: str,
        type_: Type,
        is_array: bool,
        array_len: Optional[int],
        init_list: Optional[list[ast.Expr]],
        init_string: Optional[str],
        line: int,
        column: int,
    ) -> list[ast.Stmt]:
        base = ast.Var(name, line=line, column=column)
        if init_string is not None:
            if not is_array or type_ is not U8:
                raise NiblickTypeError(
                    f"{location(self.filename, line)}: string initializer "
                    f"requires a char array"
                )
            values: list[ast.Expr] = [
                ast.Number(ord(ch) & 0xFF, line=line, column=column)
                for ch in init_string
            ]
            values.append(ast.Number(0, line=line, column=column))
            if array_len is None:
                array_len = len(values)
            if len(values) > array_len:
                raise NiblickCompileError(
                    f"{location(self.filename, line)}: string initializer for "
                    f"{name!r} does not fit in {array_len} elements"
                )
            while len(values) < array_len:
                values.append(ast.Number(0, line=line, column=column))
            return [
                ast.Assign(
                    ast.Index(base, ast.Number(index, line=line, column=column)),
                    value,
                    line=line,
                    column=column,
                )
                for index, value in enumerate(values)
            ]

        if init_list is None:
            return []

        if not is_array and not isinstance(type_, StructType):
            raise NiblickTypeError(
                f"{location(self.filename, line)}: brace initializer requires "
                "an array or struct"
            )

        if is_array and array_len is None:
            array_len = len(init_list)

        initializer = ast.InitList(init_list, line=line, column=column)
        return self._init_target(
            base,
            type_,
            array_len if array_len is not None else 0,
            initializer,
            name,
            line,
            column,
        )

    def _zero_target(
        self, target: ast.Expr, type_: Type, array_len: int, line: int, column: int
    ) -> list[ast.Stmt]:
        if array_len > 0:
            assignments: list[ast.Stmt] = []
            for index in range(array_len):
                assignments.extend(
                    self._zero_target(
                        ast.Index(
                            target,
                            ast.Number(index, line=line, column=column),
                            line=line,
                            column=column,
                        ),
                        type_,
                        0,
                        line,
                        column,
                    )
                )
            return assignments
        if isinstance(type_, StructType):
            assignments = []
            for struct_field in type_.fields:
                assignments.extend(
                    self._zero_target(
                        ast.Member(
                            target, struct_field.name, line=line, column=column
                        ),
                        struct_field.type,
                        struct_field.array_len,
                        line,
                        column,
                    )
                )
            return assignments
        return [
            ast.Assign(
                target,
                ast.Number(0, line=line, column=column),
                line=line,
                column=column,
            )
        ]

    def _init_target(
        self,
        target: ast.Expr,
        type_: Type,
        array_len: int,
        initializer: ast.Expr,
        name: str,
        line: int,
        column: int,
    ) -> list[ast.Stmt]:
        if array_len > 0:
            if not isinstance(initializer, ast.InitList):
                if isinstance(initializer, ast.Number) and initializer.value == 0:
                    return self._zero_target(
                        target, type_, array_len, line, column
                    )
                raise NiblickTypeError(
                    f"{location(self.filename, line)}: array field {name!r} "
                    "requires a brace initializer"
                )
            values = initializer.values
            if len(values) > array_len:
                raise NiblickCompileError(
                    f"{location(self.filename, line)}: too many initializers "
                    f"for {name!r}"
                )
            assignments = []
            for index in range(array_len):
                value = (
                    values[index]
                    if index < len(values)
                    else ast.Number(0, line=line, column=column)
                )
                assignments.extend(
                    self._init_target(
                        ast.Index(
                            target,
                            ast.Number(index, line=line, column=column),
                            line=line,
                            column=column,
                        ),
                        type_,
                        0,
                        value,
                        f"{name}[{index}]",
                        line,
                        column,
                    )
                )
            return assignments

        if isinstance(type_, StructType):
            if not isinstance(initializer, ast.InitList):
                if isinstance(initializer, ast.Number) and initializer.value == 0:
                    return self._zero_target(target, type_, 0, line, column)
                raise NiblickTypeError(
                    f"{location(self.filename, line)}: struct field {name!r} "
                    "requires a brace initializer"
                )
            values = initializer.values
            fields = type_.fields
            if len(values) > len(fields):
                raise NiblickCompileError(
                    f"{location(self.filename, line)}: too many initializers "
                    f"for {name!r}"
                )
            assignments = []
            for index, struct_field in enumerate(fields):
                value = (
                    values[index]
                    if index < len(values)
                    else ast.Number(0, line=line, column=column)
                )
                assignments.extend(
                    self._init_target(
                        ast.Member(
                            target, struct_field.name, line=line, column=column
                        ),
                        struct_field.type,
                        struct_field.array_len,
                        value,
                        f"{name}.{struct_field.name}",
                        line,
                        column,
                    )
                )
            return assignments

        if isinstance(initializer, ast.InitList):
            raise NiblickTypeError(
                f"{location(self.filename, line)}: scalar field {name!r} "
                "cannot use a brace initializer"
            )
        return [
            ast.Assign(
                target,
                initializer,
                line=line,
                column=column,
            )
        ]

    def prepare_globals(self) -> None:
        self.prepare_const_globals()
        for decl in self.program.globals:
            if decl.name in self.globals:
                raise NiblickCompileError(
                    f"{location(self.filename, decl.line)}: duplicate global {decl.name!r}"
                )

            decl.array_len = self.resolve_array_len(
                decl.array_len,
                decl.array_len_expr,
                None,
                decl.name,
                decl.line,
            )

            if decl.type is VOID:
                raise NiblickTypeError(
                    f"{location(self.filename, decl.line)}: global {decl.name!r} "
                    "cannot have type void"
                )

            if isinstance(decl.type, StructType):
                if decl.is_const:
                    if decl.init_string is not None:
                        raise NiblickCompileError(
                            f"{location(self.filename, decl.line)}: string "
                            "initializer requires a char array"
                        )
                    label = self.new_flash_label()
                    values = self.constant_struct_values(decl)
                    self.flash.append(FlashItem(label, decl.type, values))
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
                if decl.init_string is not None:
                    raise NiblickCompileError(
                        f"{location(self.filename, decl.line)}: string initializer "
                        f"requires a char array"
                    )

            if decl.is_const and not decl.is_array:
                if not (is_integer(decl.type) or decl.type is BOOL or decl.type.is_float):
                    raise NiblickTypeError(
                        f"{location(self.filename, decl.line)}: scalar const "
                        f"{decl.name!r} must have an integer type"
                    )
                if decl.name not in self.const_globals:
                    raise NiblickTypeError(
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

            if decl.is_const and decl.is_array:
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

            if decl.is_array and decl.array_len is None:
                raise NiblickCompileError(
                    f"{location(self.filename, decl.line)}: array {decl.name!r} "
                    "requires a length or initializer"
                )
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
                if decl.is_array:
                    raise NiblickCompileError(
                        f"{location(self.filename, decl.line)}: array initializer "
                        f"for {decl.name!r} must use braces or a string"
                    )
                self.global_inits.append((symbol, decl.init))
            elif decl.init_list is not None or decl.init_string is not None:
                self.global_aggregate_inits.extend(
                    self.build_aggregate_inits(
                        decl.name,
                        decl.type,
                        decl.is_array,
                        decl.array_len,
                        decl.init_list,
                        decl.init_string,
                        decl.line,
                        decl.column,
                    )
                )

        size = self._max_struct_size()
        if size:
            self.struct_result_size = size
            self.struct_result_addr = self.mem.alloc(
                size, "struct result", self.filename, 0
            )

    def constant_flash_values(self, decl: ast.GlobalDecl) -> list[int]:
        mask = (1 << (4 * max(decl.type.ram_size, 1))) - 1
        values: list[int] = []
        if decl.init_string is not None:
            values = [ord(ch) & 0xFF for ch in decl.init_string]
            values.append(0x00)
        elif decl.init_list is not None:
            for expr in decl.init_list:
                folded = self.eval_const(expr, None, decl.type)
                if folded is None:
                    raise NiblickCompileError(
                        f"{location(self.filename, expr.line)}: flash array "
                        "initializers must be compile-time constants"
                    )
                value, typ = folded
                if not (is_integer(typ) or typ is BOOL):
                    raise NiblickTypeError(
                        f"{location(self.filename, expr.line)}: flash array "
                        "initializers must be integers"
                    )
                values.append(self._wrap_value(value, decl.type) & mask)
        else:
            values = [0] * (decl.array_len or 0)

        if decl.array_len is not None:
            if len(values) > decl.array_len:
                raise NiblickCompileError(
                    f"{location(self.filename, decl.line)}: too many initializers for {decl.name!r}"
                )
            values.extend([0] * (decl.array_len - len(values)))
        return values

    def constant_struct_values(self, decl: ast.GlobalDecl) -> list[int]:
        values: list[int] = []
        if decl.is_array:
            length = decl.array_len or 0
            items = decl.init_list or []
            if len(items) > length:
                raise NiblickCompileError(
                    f"{location(self.filename, decl.line)}: too many "
                    f"initializers for {decl.name!r}"
                )
            for index in range(length):
                initializer = (
                    items[index]
                    if index < len(items)
                    else ast.Number(0, line=decl.line, column=decl.column)
                )
                self._flatten_struct(
                    decl.type,
                    initializer,
                    values,
                    f"{decl.name}[{index}]",
                    decl.line,
                    decl.column,
                )
            expected = length * decl.type.ram_size
        else:
            initializer = (
                ast.InitList(decl.init_list, line=decl.line, column=decl.column)
                if decl.init_list is not None
                else ast.Number(0, line=decl.line, column=decl.column)
            )
            self._flatten_struct(
                decl.type, initializer, values, decl.name, decl.line, decl.column
            )
            expected = decl.type.ram_size
        if len(values) != expected:
            raise NiblickCompileError(
                f"{location(self.filename, decl.line)}: struct initializer for "
                f"{decl.name!r} has the wrong size"
            )
        return values

    def _flatten_struct(
        self,
        type_: StructType,
        initializer: ast.Expr,
        values: list[int],
        name: str,
        line: int,
        column: int,
    ) -> None:
        if not isinstance(initializer, ast.InitList):
            if isinstance(initializer, ast.Number) and initializer.value == 0:
                values.extend([0] * type_.ram_size)
                return
            raise NiblickTypeError(
                f"{location(self.filename, line)}: struct {name!r} requires "
                "a brace initializer"
            )
        items = initializer.values
        if len(items) > len(type_.fields):
            raise NiblickCompileError(
                f"{location(self.filename, line)}: too many initializers for "
                f"{name!r}"
            )
        for index, struct_field in enumerate(type_.fields):
            value = (
                items[index]
                if index < len(items)
                else ast.Number(0, line=line, column=column)
            )
            field_name = f"{name}.{struct_field.name}"
            if struct_field.array_len > 0:
                if isinstance(value, ast.StringLiteral) and struct_field.type is U8:
                    raw: list[int] = []
                    for character in value.value:
                        code = ord(character) & 0xFF
                        raw.extend([code & 0xF, (code >> 4) & 0xF])
                    raw.extend([0, 0])
                    limit = struct_field.array_len * struct_field.type.ram_size
                    if len(raw) > limit:
                        raise NiblickCompileError(
                            f"{location(self.filename, line)}: string "
                            f"initializer for {field_name!r} is too long"
                        )
                    raw.extend([0] * (limit - len(raw)))
                    values.extend(raw)
                    continue
                if not isinstance(value, ast.InitList):
                    if isinstance(value, ast.Number) and value.value == 0:
                        values.extend([0] * (struct_field.array_len * struct_field.type.ram_size))
                        continue
                    raise NiblickTypeError(
                        f"{location(self.filename, line)}: array field "
                        f"{field_name!r} requires a brace initializer"
                    )
                if len(value.values) > struct_field.array_len:
                    raise NiblickCompileError(
                        f"{location(self.filename, line)}: too many initializers "
                        f"for {field_name!r}"
                    )
                for item_index in range(struct_field.array_len):
                    item = (
                        value.values[item_index]
                        if item_index < len(value.values)
                        else ast.Number(0, line=line, column=column)
                    )
                    values.extend(
                        self._flatten_scalar(item, struct_field.type, field_name, line)
                    )
                continue
            if isinstance(struct_field.type, StructType):
                self._flatten_struct(
                    struct_field.type, value, values, field_name, line, column
                )
                continue
            values.extend(
                self._flatten_scalar(value, struct_field.type, field_name, line)
            )

    def _flatten_scalar(
        self, expr: ast.Expr, type_: Type, name: str, line: int
    ) -> list[int]:
        if isinstance(expr, ast.InitList):
            raise NiblickTypeError(
                f"{location(self.filename, line)}: scalar field {name!r} "
                "cannot use a brace initializer"
            )
        folded = self.eval_const(expr, None, type_)
        if folded is None:
            raise NiblickTypeError(
                f"{location(self.filename, line)}: initializer for {name!r} "
                "must be a compile-time constant"
            )
        value, typ = folded
        if not (is_integer(typ) or typ is BOOL):
            raise NiblickTypeError(
                f"{location(self.filename, line)}: initializer for {name!r} "
                "must be an integer"
            )
        value = self._wrap_value(value, type_) & self._width_mask(type_)
        return [
            (value >> (4 * index)) & 0xF
            for index in range(max(type_.ram_size, 1))
        ]

    def prepare_functions(self) -> None:
        self.resolve_local_array_lengths()
        for decl in self.program.functions:
            if decl.name in self.functions:
                raise NiblickCompileError(
                    f"{location(self.filename, decl.line)}: duplicate function {decl.name!r}"
                )
            if decl.name in BUILTINS:
                raise NiblickCompileError(
                    f"{location(self.filename, decl.line)}: cannot redefine builtin {decl.name!r}"
                )
            if decl.name == "main" and decl.params:
                raise NiblickCompileError(
                    f"{location(self.filename, decl.line)}: main() must not take parameters"
                )
            if decl.name == "main" and decl.is_extern:
                raise NiblickCompileError(
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
                if not (stmt.is_const and not stmt.is_array):
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
        size += self.spill_sizes.get(decl.name, 0)
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
        groups: list[tuple[str, set[str]]] = []

        def add_edge(a: str, b: str) -> None:
            if a != b and a in edges and b in edges:
                edges[a].add(b)
                edges[b].add(a)

        def add_clique(caller: str, callees: set[str]) -> None:
            calls[caller].update(callees)
            groups.append((caller, set(callees)))
            for callee in callees:
                add_edge(caller, callee)

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

        # Imported assembly routines can call Niblick functions directly.
        for source in self.program.asm_sources:
            scan = scan_asm(source.text, source.path)
            for call in scan.calls:
                if call.caller_label.startswith("fn_") and call.target_label.startswith("fn_"):
                    caller = call.caller_label[3:]
                    target = call.target_label[3:]
                    if caller in known and target in known:
                        calls[caller].add(target)
                        add_edge(caller, target)

        def descendants(name: str) -> set[str]:
            seen: set[str] = set()
            stack = list(calls.get(name, ()))
            while stack:
                callee = stack.pop()
                if callee in seen:
                    continue
                seen.add(callee)
                stack.extend(calls.get(callee, ()))
            return seen

        # A function's frame is live for its entire subtree, so it cannot
        # share slots with any transitive callee.
        for name in self.functions:
            for callee in descendants(name):
                add_edge(name, callee)

        # A callee's parameter slots stay live while its remaining arguments
        # are evaluated, and those arguments can call other functions.  Every
        # function reachable from a same-statement callee must therefore stay
        # disjoint from the other functions in that statement.
        for caller, callees in groups:
            members: set[str] = set(callees)
            for callee in callees:
                members.update(descendants(callee))
            members.add(caller)
            items = sorted(members)
            for index, left in enumerate(items):
                for right in items[index + 1 :]:
                    add_edge(left, right)
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
            fn.temp_size = self.spill_sizes.get(name, 0)
            fn.temp_base = fn.block_end - fn.temp_size
            if fn.param_size + fn.temp_size > size:
                raise NiblickCompileError(
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
                    raise NiblickCompileError(
                        f"{location(scan.path, runtime_call.line)}: unknown runtime routine "
                        f"{runtime_call.target_label!r}"
                    )
                caller = (
                    runtime_call.caller_label[3:]
                    if runtime_call.caller_label.startswith("fn_")
                    else runtime_call.caller_label
                )
                if runtime_call.target_label in ("__nib_mul32", "__nib_divmod32"):
                    self.ensure_d32_scratch()
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
                    raise NiblickCompileError(
                        f"{location(scan.path, call.line)}: call from undeclared "
                        f"assembly routine {call.caller_label!r}"
                    )
                if callee not in self.functions:
                    raise NiblickCompileError(
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
                    raise NiblickCompileError(
                        f"{location(scan.path, line)}: duplicate assembly label "
                        f"{label!r} (already defined at {location(path, first_line)})"
                    )
                locations[label] = (scan.path, line)

        for label, (path, line) in locations.items():
            if label in {"__nib_flash_data"} or any(
                item.label == label for item in self.flash
            ):
                raise NiblickCompileError(
                    f"{location(path, line)}: assembly label {label!r} collides with "
                    "compiler-generated flash data"
                )
            if not label.startswith("fn_"):
                continue
            name = label[3:]
            declaration = self.declared_functions.get(name)
            if declaration is None:
                raise NiblickCompileError(
                    f"{location(path, line)}: assembly defines {label!r} but there is "
                    f"no extern fn {name}() declaration"
                )
            if not declaration.is_extern:
                raise NiblickCompileError(
                    f"{location(path, line)}: assembly redefines Niblick function "
                    f"{name!r}"
                )

        for name, fn in self.functions.items():
            if fn.decl.is_extern and fn.label not in locations:
                raise NiblickCompileError(
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
                raise NiblickCompileError(
                    f"{location(path, line)}: unknown function {function_name!r} "
                    f"in asm placeholder"
                )
            for param in fn.params:
                if param.name == param_name:
                    return param
            raise NiblickCompileError(
                f"{location(path, line)}: function {function_name!r} has no parameter "
                f"{param_name!r}"
            )

        symbol = scope.lookup(name)
        if symbol is None:
            symbol = self.globals.get(name)
        if symbol is None:
            raise NiblickCompileError(
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
        raise NiblickCompileError(
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
                raise NiblickCompileError(
                    f"{location(path, line)}: '&' in an asm placeholder requires "
                    "a variable name"
                )
            symbol = self._asm_symbol(text, scope, path, line)
            if symbol.const_value is not None and symbol.address is None and symbol.flash_label is None:
                raise NiblickCompileError(
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
                    raise NiblickCompileError(
                        f"{location(path, line)}: asm address expression "
                        f"{text!r} is negative"
                    )
                return f"0x{value:X}"
            if amount:
                raise NiblickCompileError(
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
            raise NiblickCompileError(
                f"{location(path, line)}: invalid asm placeholder {text!r}: {exc}"
            ) from exc

        folded = self.eval_const(expr, scope)
        if folded is None:
            raise NiblickCompileError(
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
                        f"{substituted} ; @niblick-src "
                        f"{source.path}:{line_number}"
                    )

            if file_opaque:
                self.emit(NO_OPTIMIZE_END)
            self.emit("")
        self.current_source = None
        self.emit("; @niblick-src-end")

    # ------------------------------------------------------------------
    # Function code generation
    # ------------------------------------------------------------------

    def compile_function(self, fn: FunctionSymbol) -> None:
        if fn.decl.is_extern:
            # The body and fn_* label come from an imported .asm file.
            return
        self.current_function = fn
        self.loop_stack = []
        if self._is_probe:
            self.temp = TempAllocator(TEMP_START, TEMP_START + 128)
        elif fn.temp_size:
            self.temp = TempAllocator(fn.temp_base, fn.temp_base + fn.temp_size)
        else:
            self.temp = TempAllocator()
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
                if isinstance(symbol.type, StructType):
                    assert symbol.address is not None
                    self.compile_struct_expr(expr, scope)
                    self._emit_struct_copy_regs_to_static(
                        symbol.type.ram_size, symbol.address
                    )
                else:
                    typ = self.compile_expr(expr, scope, symbol.type)
                    self.coerce(typ, symbol.type, expr.line)
                    self.store_symbol(symbol, expr.line)
            for init_stmt in self.global_aggregate_inits:
                self.compile_stmt(init_stmt, scope)

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
            if is_integer(target_type):
                literal = self._literal_value(stmt.value)
                if literal is not None:
                    if not self._fits_width(target_type, literal):
                        raise NiblickTypeError(
                            f"{location(self.filename, stmt.line)}: cannot convert "
                            f"value {literal} to {target_type}"
                        )
                    if self.store_constant(
                        stmt.target,
                        scope,
                        target_type,
                        self._wrap_value(literal, target_type),
                        stmt.line,
                    ):
                        return
                else:
                    folded = self.eval_const(stmt.value, scope, target_type)
                    if folded is not None:
                        value, value_type = folded
                        if value_type.ram_size > target_type.ram_size:
                            raise NiblickTypeError(
                                f"{location(self.filename, stmt.line)}: cannot convert {value_type} "
                                f"value {value} to {target_type}"
                            )
                        if self.store_constant(
                            stmt.target,
                            scope,
                            target_type,
                            self._wrap_value(value, target_type),
                            stmt.line,
                        ):
                            return
            if isinstance(target_type, StructType):
                self.compile_struct_expr(stmt.value, scope)
                self.store_struct_lvalue(
                    stmt.target, scope, target_type.ram_size, stmt.line
                )
                return

            typ = self.compile_expr(stmt.value, scope, target_type)
            self.coerce(typ, target_type, stmt.line)

            if isinstance(stmt.target, (ast.Index, ast.Member)):
                # The index/address expression may clobber R1/R2, so park the
                # value while the address is computed.
                if self._is_qword(target_type):
                    mark = self.qword_mark()
                    temp_addr = self.alloc_qword_slot()
                    self._emit_qword_copy(
                        self.ensure_qword_result(), temp_addr
                    )
                    if isinstance(stmt.target, ast.Member):
                        self.store_member_from_temp(
                            stmt.target, scope, target_type, temp_addr, stmt.line
                        )
                    else:
                        self.store_index_from_temp(
                            stmt.target, scope, target_type, temp_addr, stmt.line
                        )
                    self.qword_reset(mark)
                else:
                    mark = self.temp.mark()
                    temp_addr = self.temp.alloc(
                        target_type.ram_size, "assignment", self.filename, stmt.line
                    )
                    self.store_temp(target_type, temp_addr)
                    if isinstance(stmt.target, ast.Member):
                        self.store_member_from_temp(
                            stmt.target, scope, target_type, temp_addr, stmt.line
                        )
                    else:
                        self.store_index_from_temp(
                            stmt.target, scope, target_type, temp_addr, stmt.line
                        )
                    self.temp.reset(mark)
            else:
                self.store_lvalue(stmt.target, scope, stmt.line)

        elif isinstance(stmt, ast.CompoundAssign):
            self.compile_compound_assign(stmt, scope)

        elif isinstance(stmt, ast.ExprStmt):
            if isinstance(stmt.expr, ast.IncDec):
                self.compile_incdec(stmt.expr, scope)
                return
            if isinstance(stmt.expr, ast.Call):
                fn = self.current_function
                callee = self.functions.get(stmt.expr.name)
                if (
                    tail
                    and fn is not None
                    and fn.decl.return_type is VOID
                    and callee is not None
                    and self._can_tail_call(fn, callee)
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
                raise NiblickCompileError(
                    f"{location(self.filename, stmt.line)}: break outside a loop"
                )
            self.emit(f"GOTO {self.loop_stack[-1][0]}")

        elif isinstance(stmt, ast.Continue):
            if not self.loop_stack:
                raise NiblickCompileError(
                    f"{location(self.filename, stmt.line)}: continue outside a loop"
                )
            self.emit(f"GOTO {self.loop_stack[-1][1]}")

        else:
            raise NiblickCompileError(
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
        except NiblickError as exc:
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
                raise NiblickCompileError(
                    f"{location(path, source_line)}: call to undeclared function "
                    f"{call.target_label!r}; add an extern fn declaration"
                )
            self.calls.append(
                (caller, callee, call.tail, source_line, path)
            )

        for runtime_call in scan.runtime_calls:
            source_line = runtime_call.line + base_line - 2
            if runtime_call.target_label not in ROUTINE_LABELS:
                raise NiblickCompileError(
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
                + f" ; @niblick-src {path}:{source_line}"
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
                    raise NiblickCompileError(
                        f"{location(path, source_line)}: inline asm labels must "
                        "start with '.'"
                    )
                continue
            op = code.split(None, 1)[0].upper()
            if op == "RET":
                raise NiblickCompileError(
                    f"{location(path, source_line)}: RET is not allowed in "
                    "inline asm; let the Niblick function return normally"
                )

    def _shifted_asm_error(self, exc: NiblickError, delta: int) -> NiblickError:
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
        return NiblickCompileError(f"{prefix}: {match.group('msg')}")

    def alloc_local(self, size: int, what: str, filename: str, line: int) -> int:
        fn = self.current_function
        if fn is None:
            raise NiblickCompileError(
                f"{location(filename, line)}: local allocation outside a function"
            )
        local_limit = fn.block_end - fn.temp_size
        if fn.local_next + size > local_limit:
            raise NiblickCompileError(
                f"{location(filename, line)}: function slot overflow allocating {what} "
                f"({size} nibbles; {local_limit - fn.local_next} free)"
            )
        address = fn.local_next
        fn.local_next += size
        return address

    def compile_var_decl(self, stmt: ast.VarDecl, scope: Scope) -> None:
        if stmt.name in scope.symbols:
            raise NiblickCompileError(
                f"{location(self.filename, stmt.line)}: duplicate local {stmt.name!r}"
            )
        stmt.array_len = self.resolve_array_len(
            stmt.array_len,
            stmt.array_len_expr,
            scope,
            stmt.name,
            stmt.line,
        )
        if isinstance(stmt.type, StructType) and stmt.is_const:
            raise NiblickTypeError(
                f"{location(self.filename, stmt.line)}: const struct "
                f"{stmt.name!r} is not supported"
            )
        if stmt.is_const and stmt.is_array:
            raise NiblickTypeError(
                f"{location(self.filename, stmt.line)}: local const array "
                f"{stmt.name!r} is not supported"
            )
        if stmt.is_const and not stmt.is_array:
            if not (is_integer(stmt.type) or stmt.type is BOOL or stmt.type.is_float):
                raise NiblickTypeError(
                    f"{location(self.filename, stmt.line)}: scalar const "
                    f"{stmt.name!r} must have an integer type"
                )
            if stmt.init is None:
                raise NiblickTypeError(
                    f"{location(self.filename, stmt.line)}: const {stmt.name!r} "
                    f"requires an initializer"
                )
            value = self.fold_const_decl(stmt.type, stmt.init, scope, stmt.line)
            if value is None:
                raise NiblickTypeError(
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
        if stmt.is_array and stmt.array_len is None:
            raise NiblickCompileError(
                f"{location(self.filename, stmt.line)}: array {stmt.name!r} "
                "requires a length or initializer"
            )
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
            if stmt.is_array:
                raise NiblickCompileError(
                    f"{location(self.filename, stmt.line)}: array initializer "
                    f"for {stmt.name!r} must use braces or a string"
                )
            if isinstance(stmt.type, StructType):
                assert symbol.address is not None
                self.compile_struct_expr(stmt.init, scope)
                self._emit_struct_copy_regs_to_static(
                    stmt.type.ram_size, symbol.address
                )
                return
            typ = self.compile_expr(stmt.init, scope, stmt.type)
            self.coerce(typ, stmt.type, stmt.line)
            self.store_symbol(symbol, stmt.line)
            return
        if stmt.init_list is not None or stmt.init_string is not None:
            for init_stmt in self.build_aggregate_inits(
                stmt.name,
                stmt.type,
                stmt.is_array,
                stmt.array_len,
                stmt.init_list,
                stmt.init_string,
                stmt.line,
                stmt.column,
            ):
                self.compile_stmt(init_stmt, scope)

    def _expr_has_side_effect(self, expr: ast.Expr) -> bool:
        if isinstance(expr, (ast.Call, ast.IncDec)):
            return True
        for expr_field in dataclasses.fields(expr):
            value = getattr(expr, expr_field.name)
            if isinstance(value, ast.Expr) and self._expr_has_side_effect(value):
                return True
            if isinstance(value, list):
                for item in value:
                    if isinstance(item, ast.Expr) and self._expr_has_side_effect(item):
                        return True
        return False

    def _require_pure_lvalue(self, target: ast.Expr, line: int) -> None:
        if self._expr_has_side_effect(target):
            raise NiblickCompileError(
                f"{location(self.filename, line)}: compound assignment and "
                "increment/decrement require a side-effect-free lvalue"
            )

    def compile_compound_assign(
        self, stmt: ast.CompoundAssign, scope: Scope
    ) -> None:
        target_type = self.lvalue_type(stmt.target, scope)
        if not (
            is_integer(target_type)
            or target_type is BOOL
            or target_type.is_float
        ):
            raise NiblickTypeError(
                f"{location(self.filename, stmt.line)}: compound assignment "
                "requires an integer, bool, or float target"
            )
        self._require_pure_lvalue(stmt.target, stmt.line)
        value = ast.Binary(
            stmt.op,
            stmt.target,
            stmt.value,
            line=stmt.line,
            column=stmt.column,
        )
        self.compile_stmt(
            ast.Assign(
                stmt.target,
                value,
                line=stmt.line,
                column=stmt.column,
            ),
            scope,
        )

    def compile_incdec(self, expr: ast.IncDec, scope: Scope) -> None:
        target_type = self.lvalue_type(expr.target, scope)
        if not (
            is_integer(target_type)
            or target_type is BOOL
            or target_type.is_float
        ):
            raise NiblickTypeError(
                f"{location(self.filename, expr.line)}: increment/decrement "
                "requires an integer, bool, or float target"
            )
        self._require_pure_lvalue(expr.target, expr.line)
        op = "+" if expr.op == "++" else "-"
        one = ast.Number(1, line=expr.line, column=expr.column)
        value = ast.Binary(
            op,
            expr.target,
            one,
            line=expr.line,
            column=expr.column,
        )
        self.compile_stmt(
            ast.Assign(
                expr.target,
                value,
                line=expr.line,
                column=expr.column,
            ),
            scope,
        )

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
            callee = self.functions.get(stmt.value.name)
            if (
                callee is not None
                and fn.name != "main"
                and self._can_tail_call(fn, callee)
            ):
                self.compile_tail_call(stmt.value, scope)
                return

        if isinstance(fn.decl.return_type, StructType):
            if stmt.value is None:
                raise NiblickCompileError(
                    f"{location(self.filename, stmt.line)}: struct-returning "
                    f"function {fn.name!r} must return a value"
                )
            if self.struct_result_addr is None:
                raise NiblickCompileError(
                    f"{location(self.filename, stmt.line)}: struct result "
                    "buffer is not allocated"
                )
            self.compile_struct_expr(stmt.value, scope)
            self._emit_struct_copy_regs_to_static(
                fn.decl.return_type.ram_size, self.struct_result_addr
            )
            self.emit("RET R0, 0")
            return

        if stmt.value is not None:
            typ = self.compile_expr(stmt.value, scope, fn.decl.return_type)
            if fn.decl.return_type is not VOID:
                self.coerce(typ, fn.decl.return_type, stmt.line)

        if fn.name == "main":
            self.emit("JR -1")
        else:
            self.emit("RET R0, 0")

    # ------------------------------------------------------------------
    # Expressions
    # ------------------------------------------------------------------

    def compile_expr(
        self,
        expr: ast.Expr,
        scope: Scope,
        expected: Optional[Type] = None,
    ) -> Type:
        natural = self.infer_type(expr, scope)
        if isinstance(natural, StructType):
            if expected is not None and not isinstance(expected, StructType):
                raise NiblickTypeError(
                    f"{location(self.filename, getattr(expr, 'line', 0))}: "
                    f"cannot use struct {natural.name} as {expected}"
                )
            return self.compile_struct_expr(expr, scope)
        if isinstance(expr, ast.Conditional):
            return self.compile_conditional(expr, scope, expected, natural)
        if isinstance(expr, (ast.Cast, ast.ToType)) and (
            is_float_type(expr.type)
            or is_float_type(self.infer_type(expr.operand, scope))
        ):
            return self.compile_float_expr(expr, scope, expected)
        if self._is_qword(natural) or (
            expected is not None and self._is_qword(expected) and is_integer(natural)
        ):
            return self.compile_qword_expr(expr, scope, expected or natural)
        if is_float_type(natural) or (
            expected is not None
            and is_float_type(expected)
            and (is_integer(natural) or is_float_type(natural))
        ):
            return self.compile_float_expr(expr, scope, expected or natural)

        if not isinstance(expr, ast.Number):
            folded = self.eval_const(expr, scope, expected)
            if folded is not None:
                value, typ = folded
                if (
                    expected is not None
                    and is_integer(expected)
                    and is_integer(typ)
                    and expected.ram_size > typ.ram_size
                ):
                    typ = type_for(expected.ram_size, typ.signed)
                    value = self._wrap_value(value, typ)
                elif expected is BOOL and typ is not BOOL:
                    typ = BOOL
                    value = 1 if value else 0
                self._emit_immediate(value, _REGS[typ.ram_size])
                return typ

        if isinstance(expr, ast.FloatLiteral):
            typ = expected if expected is not None and is_float_type(expected) else F32
            self._emit_float_bits(expr.value, typ)
            return typ

        if isinstance(expr, ast.Number):
            value = int(expr.value)
            if value < 0 or value > 0xFFFFFFFFFFFFFFFF:
                raise NiblickCompileError(
                    f"{location(self.filename, expr.line)}: integer {value} "
                    "does not fit in 64 bits"
                )
            if expected is BOOL:
                self.emit(f"MOV R1, {1 if value else 0}")
                return BOOL
            if (
                expected is not None
                and is_integer(expected)
                and fits_value(expected, value)
            ):
                typ = expected
            elif value < 0:
                typ = smallest_type_for(value, signed_hint=True)
            else:
                typ = self._natural_literal_type(value)
            self._emit_immediate(self._wrap_value(value, typ), _REGS[typ.ram_size])
            return typ

        if isinstance(expr, ast.StringLiteral):
            label = self.new_flash_string(expr.value)
            self.emit_flashptr(label)
            return FLASHPTR

        if isinstance(expr, ast.Member):
            field = self.member_info(expr, scope)
            if field.array_len > 0:
                raise NiblickTypeError(
                    f"{location(self.filename, expr.line)}: field {expr.field!r} "
                    "is an array and requires an index"
                )
            if isinstance(field.type, StructType):
                raise NiblickTypeError(
                    f"{location(self.filename, expr.line)}: struct field "
                    f"{expr.field!r} must be used through a field"
                )
            if self._struct_is_flash(expr, scope):
                self.compile_flash_member_addr(expr, scope)
                self.load_flash_indirect(field.type, expr.line)
            else:
                self.compile_member_addr(expr, scope)
                self.load_indirect(field.type, expr.line)
            return field.type

        if isinstance(expr, ast.Var):
            symbol = self.lookup(expr.name, scope, expr.line)
            if symbol.array_len is not None:
                if symbol.flash_label is not None:
                    self.emit_flashptr(symbol.flash_label)
                    return FLASHPTR
                raise NiblickTypeError(
                    f"{location(self.filename, expr.line)}: array {expr.name!r} used without an index"
                )
            if isinstance(symbol.type, StructType):
                raise NiblickTypeError(
                    f"{location(self.filename, expr.line)}: struct {expr.name!r} "
                    "must be used through a field"
                )
            self.load_symbol(symbol, expr.line)
            return symbol.type

        if isinstance(expr, ast.Index):
            return self.compile_index(expr, scope)

        if isinstance(expr, ast.Unary):
            return self.compile_unary(expr, scope, expected)

        if isinstance(expr, ast.Binary):
            return self.compile_binary(expr, scope, expected)

        if isinstance(expr, ast.Call):
            return self.compile_call(expr, scope)

        if isinstance(expr, ast.AddressOf):
            return self.compile_address_of(expr, scope)

        if isinstance(expr, (ast.ToType, ast.Cast)):
            target = expr.type
            if not (is_integer(target) or target is BOOL):
                raise NiblickTypeError(
                    f"{location(self.filename, expr.line)}: unsupported cast target {target}"
                )
            typ = self.compile_expr(expr.operand, scope, target)
            if not (is_integer(typ) or typ is BOOL):
                raise NiblickTypeError(
                    f"{location(self.filename, expr.line)}: cannot cast {typ} to {target}"
                )
            if self._is_qword(typ):
                if target is BOOL:
                    self._emit_qword_truth_to_r1(self.ensure_qword_result())
                    self.emit("MOV R0, R1")
                    self.emit("CP R0, 0")
                    self.emit("MOV R1, 0")
                    self.emit("SKIP Z, 1")
                    self.emit("INC R1")
                    return BOOL
                if is_integer(target):
                    self._emit_load_low_regs(
                        self.ensure_qword_result(), target.ram_size
                    )
                    return target
                raise NiblickTypeError(
                    f"{location(self.filename, expr.line)}: cannot cast {typ} to {target}"
                )
            if target is BOOL:
                self.coerce(typ, BOOL, expr.line)
            elif is_integer(target) and typ is BOOL:
                self.coerce(typ, target, expr.line)
            elif is_integer(target) and is_integer(typ):
                if typ.ram_size < target.ram_size:
                    self.coerce(typ, target, expr.line)
                elif typ.ram_size > target.ram_size:
                    # Explicit narrowing: the low nibbles already hold the
                    # truncated value.
                    pass
            return target

        raise NiblickCompileError(
            f"{location(self.filename, getattr(expr, 'line', 0))}: unsupported expression {type(expr).__name__}"
        )

    def compile_qword_expr(
        self,
        expr: ast.Expr,
        scope: Scope,
        expected: Optional[Type] = None,
    ) -> Type:
        result = self.ensure_qword_result()
        natural = self.infer_type(expr, scope)

        # Arithmetic, bitwise, shift, and unary nodes always use the 64-bit
        # path when the destination is 64-bit, so target typing does not
        # silently wrap in 32 bits first.
        if isinstance(expr, ast.Binary) and expr.op in (
            "+", "-", "&", "|", "^", "<<", ">>", "*", "/", "%"
        ):
            return self._compile_qword_binary(expr, scope, expected)
        if isinstance(expr, ast.Unary) and expr.op in ("-", "~", "+"):
            return self._compile_qword_unary(expr, scope, expected)

        if not self._is_qword(natural):
            typ = self.compile_expr(expr, scope)
            target = (
                expected
                if expected is not None and self._is_qword(expected)
                else type_for(16, typ.signed)
            )
            self._emit_extend_to_qword(typ, result)
            return target

        folded = self.eval_const(expr, scope, expected)
        if folded is not None:
            value, typ = folded
            if not self._is_qword(typ):
                typ = type_for(16, typ.signed)
            self._emit_qword_immediate(value, typ, result)
            return typ

        if isinstance(expr, ast.Var):
            symbol = self.lookup(expr.name, scope, expr.line)
            if symbol.array_len is not None:
                raise NiblickTypeError(
                    f"{location(self.filename, expr.line)}: array {expr.name!r} used without an index"
                )
            if isinstance(symbol.type, StructType):
                raise NiblickTypeError(
                    f"{location(self.filename, expr.line)}: struct {expr.name!r} "
                    "must be used through a field"
                )
            self.load_symbol(symbol, expr.line)
            return symbol.type

        if isinstance(expr, ast.Member):
            field = self.member_info(expr, scope)
            if not self._is_qword(field.type):
                typ = self.compile_expr(expr, scope)
                self._emit_extend_to_qword(typ, result)
                return type_for(16, typ.signed)
            self.compile_member_addr(expr, scope)
            self._emit_qword_load_indirect(result)
            return field.type

        if isinstance(expr, ast.Index):
            if not isinstance(expr.base, ast.Var):
                raise NiblickTypeError(
                    f"{location(self.filename, expr.line)}: only named arrays can be indexed"
                )
            symbol = self.lookup(expr.base.name, scope, expr.line)
            if symbol.array_len is None:
                raise NiblickTypeError(
                    f"{location(self.filename, expr.line)}: {symbol.name!r} is not an array"
                )
            if not self._is_qword(symbol.type):
                typ = self.compile_expr(expr, scope)
                self._emit_extend_to_qword(typ, result)
                return type_for(16, typ.signed)
            if symbol.flash_label is not None:
                raise NiblickCompileError(
                    f"{location(self.filename, expr.line)}: 64-bit const flash arrays "
                    "are not supported"
                )
            if isinstance(expr.index, ast.Number):
                assert symbol.address is not None
                address = symbol.address + int(expr.index.value) * 16
                self._emit_qword_copy(address, result)
                return symbol.type
            self.compile_ram_addr(symbol, expr.index, scope, expr.line)
            self._emit_qword_load_indirect(result)
            return symbol.type

        if isinstance(expr, (ast.ToType, ast.Cast)):
            target = expr.type
            source_type = self.infer_type(expr.operand, scope)
            if self._is_qword(target):
                if self._is_qword(source_type):
                    self.compile_qword_expr(expr.operand, scope, target)
                else:
                    typ = self.compile_expr(expr.operand, scope)
                    self._emit_extend_to_qword(typ, result)
                return target
            # Casting a 64-bit value down to a register-sized type.
            self.compile_qword_expr(expr.operand, scope, source_type if self._is_qword(source_type) else None)
            if target is BOOL:
                self._emit_qword_truth_to_r1(result)
                self.emit("MOV R0, R1")
                self.emit("CP R0, 0")
                self.emit("MOV R1, 0")
                self.emit("SKIP Z, 1")
                self.emit("INC R1")
                if expected is not None and self._is_qword(expected):
                    widened = type_for(16, False)
                    self._emit_extend_to_qword(BOOL, result)
                    return widened
                return BOOL
            if not is_integer(target):
                raise NiblickTypeError(
                    f"{location(self.filename, expr.line)}: cannot cast {source_type} to {target}"
                )
            self._emit_load_low_regs(result, target.ram_size)
            if expected is not None and self._is_qword(expected):
                widened = type_for(16, target.signed)
                self._emit_extend_to_qword(target, result)
                return widened
            return target

        if isinstance(expr, ast.Call):
            typ = self.compile_call(expr, scope)
            if not self._is_qword(typ):
                target = (
                    expected
                    if expected is not None and self._is_qword(expected)
                    else type_for(16, typ.signed)
                )
                self._emit_extend_to_qword(typ, result)
                return target
            return typ

        raise NiblickCompileError(
            f"{location(self.filename, expr.line)}: unsupported 64-bit expression "
            f"{type(expr).__name__}"
        )

    def _float_helper(self, typ: Type, op: str) -> str:
        prefix = {F16: "f16", F32: "f32"}.get(typ)
        if prefix is None:
            raise NiblickCompileError(f"not a float type: {typ}")
        return f"__nib_{prefix}_{op}"

    def _compile_float_from_integer(
        self, expr: ast.Expr, scope: Scope, target: Type
    ) -> Type:
        source = self.infer_type(expr, scope)
        if source is BOOL:
            signed = False
            width = 32
        elif is_integer(source):
            signed = source.signed
            width = 64 if source.ram_size == 16 else 32
        else:
            raise NiblickTypeError(
                f"{location(self.filename, expr.line)}: cannot convert {source} to {target}"
            )
        prefix = {F16: "f16", F32: "f32"}.get(target)
        if prefix is None:
            raise NiblickTypeError(
                f"{location(self.filename, expr.line)}: cannot convert {source} to {target}"
            )
        integer = ("i" if signed else "u") + str(width)
        name = f"__nib_{integer}_to_{prefix}"
        self.compile_call(
            ast.Call(name, [expr], line=expr.line, column=expr.column, file=expr.file),
            scope,
        )
        return target

    def _compile_float_operand(
        self, expr: ast.Expr, scope: Scope, target: Type
    ) -> Type:
        source = self.infer_type(expr, scope)
        if source.is_float:
            if source is not target:
                raise NiblickTypeError(
                    f"{location(self.filename, expr.line)}: mixed float types "
                    f"{source} and {target}; use an explicit cast"
                )
            return self.compile_expr(expr, scope, target)
        if is_integer(source) or source is BOOL:
            return self._compile_float_from_integer(expr, scope, target)
        raise NiblickTypeError(
            f"{location(self.filename, expr.line)}: cannot use {source} in float arithmetic"
        )

    def compile_float_expr(
        self,
        expr: ast.Expr,
        scope: Scope,
        expected: Optional[Type] = None,
    ) -> Type:
        natural = self.infer_type(expr, scope)

        if isinstance(expr, ast.FloatLiteral):
            target = expected if expected is not None and is_float_type(expected) else F32
            self._emit_float_bits(expr.value, target)
            return target

        if isinstance(expr, ast.Number):
            target = expected if expected is not None and is_float_type(expected) else F32
            self._emit_float_bits(float(expr.value), target)
            return target

        if isinstance(expr, ast.Var) and natural.is_float:
            symbol = self.lookup(expr.name, scope, expr.line)
            if symbol.array_len is not None:
                raise NiblickTypeError(
                    f"{location(self.filename, expr.line)}: array {expr.name!r} used without an index"
                )
            self.load_symbol(symbol, expr.line)
            return symbol.type

        if isinstance(expr, ast.Member) and natural.is_float:
            field = self.member_info(expr, scope)
            self.compile_member_addr(expr, scope)
            self.load_indirect(field.type, expr.line)
            return field.type

        if isinstance(expr, ast.Index) and natural.is_float:
            self.compile_index(expr, scope)
            return natural

        if isinstance(expr, (ast.ToType, ast.Cast)):
            target = expr.type
            source = self.infer_type(expr.operand, scope)
            if target.is_float:
                if source.is_float:
                    if source is target:
                        self.compile_expr(expr.operand, scope, target)
                        return target
                    if source is F16 and target is F32:
                        helper = "__nib_f16_to_f32"
                    elif source is F32 and target is F16:
                        helper = "__nib_f32_to_f16"
                    else:
                        raise NiblickTypeError(
                            f"{location(self.filename, expr.line)}: cannot convert "
                            f"{source} to {target}"
                        )
                    self.compile_call(
                        ast.Call(
                            helper,
                            [expr.operand],
                            line=expr.line,
                            column=expr.column,
                            file=expr.file,
                        ),
                        scope,
                    )
                    return target
                return self._compile_float_from_integer(expr.operand, scope, target)
            if source.is_float and (is_integer(target) or target is BOOL):
                if target is BOOL:
                    self.compile_call(
                        ast.Call(
                            self._float_helper(source, "is_zero"),
                            [expr.operand],
                            line=expr.line,
                            column=expr.column,
                            file=expr.file,
                        ),
                        scope,
                    )
                    self.emit("MOV R0, R1")
                    self.emit("CP R0, 0")
                    self.emit("MOV R1, 0")
                    self.emit("SKIP NZ, 1")
                    self.emit("INC R1")
                    return BOOL
                prefix = {F16: "f16", F32: "f32"}.get(source)
                if prefix is None:
                    raise NiblickTypeError(
                        f"{location(self.filename, expr.line)}: cannot convert "
                        f"{source} to {target}"
                    )
                integer = ("i" if target.signed else "u") + (
                    "64" if target.ram_size == 16 else "32"
                )
                name = f"__nib_{prefix}_to_{integer}"
                self.compile_call(
                    ast.Call(name, [expr.operand], line=expr.line, column=expr.column, file=expr.file),
                    scope,
                )
                if target.ram_size < 4:
                    self.emit("MOV R0, R1")
                    if target.ram_size == 1:
                        self.emit("MOV R1, R0")
                    else:
                        self.emit("MOV R1, R0")
                        self.emit("MOV R0, R2")
                        self.emit("MOV R2, R0")
                return target
            raise NiblickTypeError(
                f"{location(self.filename, expr.line)}: unsupported float cast "
                f"{source} to {target}"
            )

        if isinstance(expr, ast.Unary) and expr.op == "+" and natural.is_float:
            typ = expected if expected is not None and is_float_type(expected) else natural
            self.compile_expr(expr.operand, scope, typ)
            return typ

        if isinstance(expr, ast.Unary) and expr.op == "-" and natural.is_float:
            typ = expected if expected is not None and is_float_type(expected) else natural
            self.compile_expr(expr.operand, scope, typ)
            if typ is F16:
                self.emit("MOV R0, R4")
                self.emit("XOR R0, 8")
                self.emit("MOV R4, R0")
            elif typ is F32:
                self.emit("MOV R0, R8")
                self.emit("XOR R0, 8")
                self.emit("MOV R8, R0")
            return typ

        if isinstance(expr, ast.Binary) and natural.is_float:
            left_type = self.infer_type(expr.left, scope)
            right_type = self.infer_type(expr.right, scope)
            if left_type.is_float and right_type.is_float and left_type is not right_type:
                raise NiblickTypeError(
                    f"{location(self.filename, expr.line)}: mixed float types "
                    f"{left_type} and {right_type}; use an explicit cast"
                )
            target = expected if expected is not None and is_float_type(expected) else (
                left_type if left_type.is_float else right_type
            )
            opnames = {"+": "add", "-": "sub", "*": "mul", "/": "div"}
            if expr.op not in opnames:
                raise NiblickTypeError(
                    f"{location(self.filename, expr.line)}: operator {expr.op!r} "
                    "is not supported for floating point"
                )
            name = self._float_helper(target, opnames[expr.op])
            self.compile_call(
                ast.Call(
                    name,
                    [expr.left, expr.right],
                    line=expr.line,
                    column=expr.column,
                    file=expr.file,
                ),
                scope,
            )
            return target

        if isinstance(expr, ast.Call):
            typ = self.compile_call(expr, scope)
            if typ.is_float:
                return typ
            if expected is not None and is_float_type(expected):
                return self._compile_float_from_integer(expr, scope, expected)
            raise NiblickTypeError(
                f"{location(self.filename, expr.line)}: expected a float value"
            )

        if is_integer(natural) or natural is BOOL:
            return self._compile_float_from_integer(
                expr, scope, expected if expected is not None and is_float_type(expected) else F32
            )

        raise NiblickCompileError(
            f"{location(self.filename, expr.line)}: unsupported float expression "
            f"{type(expr).__name__}"
        )

    def _compile_qword_binary(
        self,
        expr: ast.Binary,
        scope: Scope,
        expected: Optional[Type],
    ) -> Type:
        if expr.op in ("<<", ">>"):
            return self._compile_qword_shift(expr, scope, expected)
        left_type = self.infer_type(expr.left, scope)
        right_type = self.infer_type(expr.right, scope)
        if not is_integer(left_type) or not is_integer(right_type):
            raise NiblickTypeError(
                f"{location(self.filename, expr.line)}: arithmetic requires integer operands"
            )
        common = self._common_expr_type(expr.left, expr.right, scope)
        result = widen_type(common, expected)
        if not self._is_qword(result):
            result = type_for(16, common.signed)

        if expr.op in ("*", "/", "%"):
            names = {
                ("*", False): "__nib_mul64",
                ("*", True): "__nib_smul64",
                ("/", False): "__nib_div64",
                ("/", True): "__nib_sdiv64",
                ("%", False): "__nib_mod64",
                ("%", True): "__nib_smod64",
            }
            name = names[(expr.op, common.signed)]
            call = ast.Call(
                name,
                [expr.left, expr.right],
                line=expr.line,
                column=expr.column,
                file=expr.file,
            )
            self.compile_call(call, scope)
            return result

        mark = self.qword_mark()
        left_slot = self.alloc_qword_slot()
        self.compile_qword_expr(expr.left, scope, result)
        self._emit_qword_copy(self.ensure_qword_result(), left_slot)
        self.compile_qword_expr(expr.right, scope, result)
        result_addr = self.ensure_qword_result()
        self._emit_qword_binary(expr.op, left_slot, result_addr, result_addr)
        self.qword_reset(mark)
        return result

    def _compile_qword_shift(
        self,
        expr: ast.Binary,
        scope: Scope,
        expected: Optional[Type],
    ) -> Type:
        left_type = self.infer_type(expr.left, scope)
        if not is_integer(left_type):
            raise NiblickTypeError(
                f"{location(self.filename, expr.line)}: shifts require an integer operand"
            )
        result = widen_type(left_type, expected)
        if not self._is_qword(result):
            result = type_for(16, left_type.signed)
        arithmetic = result.signed and expr.op == ">>"

        right_type = self.infer_type(expr.right, scope)
        if not is_integer(right_type) or right_type.ram_size > 2:
            raise NiblickTypeError(
                f"{location(self.filename, expr.line)}: shift counts must fit in a char"
            )

        mark = self.temp.mark()
        count_addr = self.temp.alloc(2, "64-bit shift count", self.filename, expr.line)
        constant = self._literal_value(expr.right)
        if constant is not None:
            if constant < 0:
                constant = 0
            self._emit_immediate(constant & 0xFF, ("R1", "R2"))
            self.store_temp(U8, count_addr)
        else:
            typ = self.compile_expr(expr.right, scope)
            self.coerce(typ, U8, expr.line)
            self.store_temp(U8, count_addr)

        self.compile_qword_expr(expr.left, scope, result)
        result_addr = self.ensure_qword_result()
        if constant is not None and constant >= 64:
            if arithmetic:
                self.emit(f"MOV R0, [{result_addr + 15}]")
                self.emit("AND R0, 8")
                self.emit("CP R0, 0")
                self.emit("MOV R9, 0")
                self.emit("SKIP Z, 1")
                self.emit("MOV R9, 15")
                for index in range(16):
                    self.emit(f"MOV [{result_addr + index}], R9")
            else:
                self._emit_qword_zero(result_addr)
        else:
            self._emit_qword_shift_loop(result_addr, count_addr, expr.op, arithmetic)
        self.temp.reset(mark)
        return result

    def _compile_qword_unary(
        self,
        expr: ast.Unary,
        scope: Scope,
        expected: Optional[Type],
    ) -> Type:
        if expr.op == "+":
            target = (
                expected
                if expected is not None and self._is_qword(expected)
                else type_for(16, False)
            )
            return self.compile_qword_expr(expr.operand, scope, target)

        literal = self._literal_value(expr)
        if literal is not None:
            if literal < -(1 << 63) or literal > (1 << 64) - 1:
                raise NiblickCompileError(
                    f"{location(self.filename, expr.line)}: integer {literal} "
                    "does not fit in 64 bits"
                )
            typ = (
                expected
                if expected is not None
                and self._is_qword(expected)
                and fits_value(expected, literal)
                else smallest_type_for(literal, signed_hint=literal < 0)
            )
            self._emit_qword_immediate(literal, typ, self.ensure_qword_result())
            return typ

        operand_type = self._arith_type(self.infer_type(expr.operand, scope))
        if not is_integer(operand_type):
            raise NiblickTypeError(
                f"{location(self.filename, expr.line)}: unary {expr.op} requires an integer operand"
            )
        if expr.op == "-":
            result = type_for(16, True)
        else:
            result = widen_type(operand_type, expected)
            if not self._is_qword(result):
                result = type_for(16, operand_type.signed)
        self.compile_qword_expr(expr.operand, scope, result)
        address = self.ensure_qword_result()
        if expr.op == "-":
            self._emit_qword_negate(address)
        else:
            self._emit_qword_complement(address)
        return result

    def compile_unary(
        self,
        expr: ast.Unary,
        scope: Scope,
        expected: Optional[Type] = None,
    ) -> Type:
        if expr.op == "&":
            return self.compile_address_of(ast.AddressOf(expr.operand, line=expr.line), scope)

        if expr.op == "+":
            return self.compile_expr(expr.operand, scope, expected)

        if expr.op == "!":
            typ = self.compile_expr(expr.operand, scope)
            if not is_testable(typ):
                raise NiblickTypeError(
                    f"{location(self.filename, expr.line)}: ! requires a testable operand"
                )
            self.emit_truth_value(typ)
            self.emit("MOV R0, R1")
            self.emit("CP R0, 0")
            self.emit("MOV R1, 0")
            self.emit("SKIP NZ, 1")
            self.emit("INC R1")
            return BOOL

        if expr.op == "~":
            typ = self._arith_type(self.compile_expr(expr.operand, scope, expected))
            if not is_integer(typ):
                raise NiblickTypeError(
                    f"{location(self.filename, expr.line)}: ~ requires an integer operand"
                )
            result_type = widen_type(typ, expected)
            if result_type.ram_size > typ.ram_size:
                self.coerce(typ, result_type, expr.line)
            self._emit_complement(_REGS[result_type.ram_size])
            return result_type

        if expr.op == "-":
            literal = self._literal_value(expr)
            if literal is not None:
                if literal < -(1 << 31):
                    raise NiblickCompileError(
                        f"{location(self.filename, expr.line)}: integer {literal} "
                        "does not fit in 32 bits"
                    )
                typ = smallest_type_for(literal, signed_hint=True)
                typ = widen_type(typ, expected)
                self._emit_immediate(
                    self._wrap_value(literal, typ), _REGS[typ.ram_size]
                )
                return typ

            typ = self._arith_type(self.compile_expr(expr.operand, scope))
            if not is_integer(typ):
                raise NiblickTypeError(
                    f"{location(self.filename, expr.line)}: unary - requires an integer operand"
                )
            width = typ.ram_size
            if expected is not None and is_integer(expected):
                width = max(width, expected.ram_size)
            result_type = type_for(width, True)
            self.coerce(typ, result_type, expr.line)
            regs = _REGS[result_type.ram_size]
            self._emit_complement(regs)
            self.emit("MOV R0, 1")
            self.emit(f"ADD {regs[0]}, R0")
            self.emit("MOV R0, 0")
            for reg in regs[1:]:
                self.emit(f"ADC {reg}, R0")
            return result_type

        raise NiblickCompileError(
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
            raise NiblickTypeError(
                f"{location(self.filename, expr.line)}: & is only supported on simple variables"
            )
        symbol = self.lookup(expr.operand.name, scope, expr.line)
        if symbol.const_value is not None:
            raise NiblickTypeError(
                f"{location(self.filename, expr.line)}: cannot take the address of const "
                f"{symbol.name!r}"
            )
        if symbol.address is None:
            raise NiblickTypeError(
                f"{location(self.filename, expr.line)}: cannot take the address of {symbol.name!r}"
            )
        self.emit(f"MOV R1, {symbol.address & 0xF}")
        self.emit(f"MOV R2, {(symbol.address >> 4) & 0xF}")
        return U8

    def compile_conditional(
        self,
        expr: ast.Conditional,
        scope: Scope,
        expected: Optional[Type],
        natural: Type,
    ) -> Type:
        result_type = natural
        if expected is not None:
            if expected is BOOL:
                result_type = BOOL
            elif is_integer(result_type) and is_integer(expected):
                result_type = widen_type(result_type, expected)
            elif is_float_type(expected):
                if is_float_type(result_type) and result_type is not expected:
                    raise NiblickTypeError(
                        f"{location(self.filename, expr.line)}: mixed float types "
                        f"{result_type} and {expected}; use an explicit cast"
                    )
                result_type = expected

        condition = self.eval_const(expr.condition, scope)
        if condition is not None:
            selected = expr.then_expr if condition[0] else expr.else_expr
            return self.compile_expr(selected, scope, result_type)

        else_label = self.new_label("ternary_else")
        end_label = self.new_label("ternary_end")
        self.emit_jump_if_false(expr.condition, else_label, scope)
        self.compile_expr(expr.then_expr, scope, result_type)
        self.emit(f"GOTO {end_label}")
        self.emit(f"{else_label}:")
        self.compile_expr(expr.else_expr, scope, result_type)
        self.emit(f"{end_label}:")
        return result_type

    def compile_binary(
        self,
        expr: ast.Binary,
        scope: Scope,
        expected: Optional[Type] = None,
    ) -> Type:
        op = expr.op
        if op in ("&&", "||"):
            return self.compile_logical(expr, scope)
        if op in ("==", "!=", "<", "<=", ">", ">="):
            return self.compile_comparison(expr, scope)
        if op in ("+", "-", "&", "|", "^"):
            return self.compile_arithmetic(expr, scope, expected)
        if op in ("<<", ">>"):
            return self.compile_shift(expr, scope, expected)
        if op == "*":
            return self.compile_mul(expr, scope, expected)
        if op in ("/", "%"):
            return self.compile_divmod(expr, scope, expected)
        raise NiblickCompileError(
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
            return BOOL

        true_label = self.new_label("ortrue")
        self._emit_cond_branch(expr.left, true_label, when_true=True, scope=scope)
        self._emit_cond_branch(expr.right, true_label, when_true=True, scope=scope)
        self.emit("MOV R1, 0")
        self.emit(f"GOTO {end_label}")
        self.emit(f"{true_label}:")
        self.emit("MOV R1, 1")
        self.emit(f"{end_label}:")
        return BOOL

    def compile_comparison(self, expr: ast.Binary, scope: Scope) -> Type:
        op = expr.op
        left = expr.left
        right = expr.right

        left_type = self.infer_type(left, scope)
        right_type = self.infer_type(right, scope)
        if isinstance(left_type, StructType) or isinstance(right_type, StructType):
            if not isinstance(left_type, StructType) or left_type is not right_type:
                raise NiblickTypeError(
                    f"{location(self.filename, expr.line)}: cannot compare "
                    f"{left_type} and {right_type}"
                )
            if op not in ("==", "!="):
                raise NiblickTypeError(
                    f"{location(self.filename, expr.line)}: struct comparison "
                    "supports only == and !="
                )
            return self.compile_struct_comparison(
                left, right, left_type, op, scope, expr.line
            )
        if left_type.is_float or right_type.is_float:
            if left_type.is_float and right_type.is_float and left_type is not right_type:
                raise NiblickTypeError(
                    f"{location(self.filename, expr.line)}: mixed float types "
                    f"{left_type} and {right_type}; use an explicit cast"
                )
            target = left_type if left_type.is_float else right_type
            self.compile_call(
                ast.Call(
                    self._float_helper(target, "cmp"),
                    [left, right],
                    line=expr.line,
                    column=expr.column,
                    file=expr.file,
                ),
                scope,
            )
            self.emit("MOV R9, R1")
            if op in ("<=", ">="):
                first = 15 if op == "<=" else 1
                self.emit("MOV R1, 0")
                self.emit("MOV R0, R9")
                self.emit(f"CP R0, {first}")
                self.emit("SKIP NZ, 1")
                self.emit("INC R1")
                self.emit("MOV R2, R1")
                self.emit("MOV R1, 0")
                self.emit("MOV R0, R9")
                self.emit("CP R0, 0")
                self.emit("SKIP NZ, 1")
                self.emit("INC R1")
                self.emit("OR R1, R2")
            else:
                value = {"==": 0, "!=": 0, "<": 15, ">": 1}[op]
                self.emit("MOV R1, 0")
                self.emit("MOV R0, R9")
                self.emit(f"CP R0, {value}")
                if op == "!=":
                    self.emit("SKIP Z, 1")
                else:
                    self.emit("SKIP NZ, 1")
                self.emit("INC R1")
            return BOOL

        if not is_comparable(left_type) or not is_comparable(right_type):
            raise NiblickTypeError(
                f"{location(self.filename, expr.line)}: comparisons require integer or bool operands"
            )

        common = self._common_expr_type(left, right, scope)
        if common is BOOL:
            common = U4
        if not is_integer(common):
            raise NiblickTypeError(
                f"{location(self.filename, expr.line)}: comparisons require integer operands"
            )

        if self._is_qword(common):
            mark = self.qword_mark()
            left_slot = self.alloc_qword_slot()
            self.compile_qword_expr(left, scope, common)
            self._emit_qword_copy(self.ensure_qword_result(), left_slot)
            self.compile_qword_expr(right, scope, common)
            result = self._emit_qword_compare(
                left_slot, self.ensure_qword_result(), common.signed, op
            )
            self.qword_reset(mark)
            return result

        if common.ram_size == 8:
            return self._compile_dword_comparison(
                left, right, op, scope, expr.line, common
            )
        if common.ram_size == 4:
            return self._compile_word_comparison(
                left, right, op, scope, expr.line, common
            )

        materialize = op
        if op == "<=":
            left, right = right, left
            materialize = ">="
        elif op == ">":
            left, right = right, left
            materialize = "<"

        mark = self.temp.mark()
        temp_addr = self.temp.alloc(common.ram_size, "comparison", self.filename, expr.line)

        typ = self.compile_expr(left, scope, common)
        self.coerce(typ, common, expr.line)
        if common.signed:
            self._flip_sign_bit(common, _REGS[common.ram_size])
        self.store_temp(common, temp_addr)

        typ = self.compile_expr(right, scope, common)
        self.coerce(typ, common, expr.line)
        if common.signed:
            self._flip_sign_bit(common, _REGS[common.ram_size])
        if common.ram_size == 1:
            self.emit("MOV R2, R1")
        else:
            self.emit("MOV R3, R1")
            self.emit("MOV R4, R2")

        self.load_temp(common, temp_addr)
        if common.ram_size == 1:
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
        self.temp.reset(mark)
        return BOOL

    def compile_struct_comparison(
        self,
        left: ast.Expr,
        right: ast.Expr,
        typ: StructType,
        op: str,
        scope: Scope,
        line: int,
    ) -> Type:
        size = typ.ram_size
        mark = self.temp.mark()
        left_slot = self.temp.alloc(
            size if isinstance(left, ast.Call) else 2,
            "struct comparison",
            self.filename,
            line,
        )
        if isinstance(left, ast.Call):
            self.compile_struct_expr(left, scope)
            self._emit_addr(left_slot)
            self.emit("MOV R6, R4")
            self.emit("MOV R7, R5")
            self._emit_struct_copy_indirect(size)
            self._emit_addr(left_slot)
        else:
            self.compile_struct_expr(left, scope)
            self.emit("MOV R0, R4")
            self.emit(f"MOV [{left_slot}], R0")
            self.emit("MOV R0, R5")
            self.emit(f"MOV [{left_slot + 1}], R0")

        self.compile_struct_expr(right, scope)
        self.emit("MOV R6, R4")
        self.emit("MOV R7, R5")
        if isinstance(left, ast.Call):
            self._emit_addr(left_slot)
        else:
            self.emit(f"MOV R0, [{left_slot}]")
            self.emit("MOV R4, R0")
            self.emit(f"MOV R0, [{left_slot + 1}]")
            self.emit("MOV R5, R0")

        loop = self.new_label("struct_eq")
        mismatch = self.new_label("struct_ne")
        done = self.new_label("struct_eq_done")
        self.emit("MOV R1, 1")
        self.emit(f"MOV R8, {size & 0xF}")
        self.emit(f"MOV R9, {(size >> 4) & 0xF}")
        self.emit(f"{loop}:")
        self.emit("MOV R0, [R4:R5]")
        self.emit("MOV R2, R0")
        self.emit("MOV R0, [R6:R7]")
        self.emit("XOR R0, R2")
        self.emit("SKIP Z, 1")
        self.emit(f"JR {mismatch}")
        self.emit("INC R5")
        self.emit("SKIP NC, 1")
        self.emit("INC R4")
        self.emit("INC R7")
        self.emit("SKIP NC, 1")
        self.emit("INC R6")
        self.emit("DEC R8")
        self.emit("SKIP C, 1")
        self.emit("DEC R9")
        self.emit("MOV R0, R8")
        self.emit("OR R0, R9")
        self.emit("CP R0, 0")
        self.emit("SKIP Z, 1")
        self.emit(f"JR {loop}")
        self.emit(f"JR {done}")
        self.emit(f"{mismatch}:")
        self.emit("MOV R1, 0")
        self.emit(f"{done}:")
        if op == "!=":
            self.emit("MOV R0, 1")
            self.emit("XOR R1, R0")
        self.temp.reset(mark)
        return BOOL

    def compile_arithmetic(
        self,
        expr: ast.Binary,
        scope: Scope,
        expected: Optional[Type] = None,
    ) -> Type:
        left_type = self._arith_type(self.infer_type(expr.left, scope))
        right_type = self._arith_type(self.infer_type(expr.right, scope))
        if not is_integer(left_type) or not is_integer(right_type):
            raise NiblickTypeError(
                f"{location(self.filename, expr.line)}: arithmetic requires integer operands"
            )

        common = self._common_expr_type(expr.left, expr.right, scope)
        if not is_integer(common):
            raise NiblickTypeError(
                f"{location(self.filename, expr.line)}: arithmetic requires integer operands"
            )
        result = widen_type(common, expected)

        if result.ram_size == 8:
            return self._compile_dword_arithmetic(expr, scope, result)

        width = result.ram_size
        dest = _REGS[width]
        saved = _SAVED_REGS[width]

        if isinstance(expr.left, ast.Number) and isinstance(expr.right, ast.Number):
            a, b = int(expr.left.value), int(expr.right.value)
            value = {
                "+": a + b,
                "-": a - b,
                "&": a & b,
                "|": a | b,
                "^": a ^ b,
            }[expr.op]
            self._emit_immediate(self._wrap_value(value, result), dest)
            return result

        if (
            expr.op in ("+", "-")
            and isinstance(expr.right, ast.Number)
            and int(expr.right.value) == 1
        ):
            typ = self.compile_expr(expr.left, scope, result)
            self.coerce(typ, result, expr.line)
            if width == 1:
                self.emit("INC R1" if expr.op == "+" else "DEC R1")
            else:
                self.emit("MOV R0, 1")
                self.emit(f"{'ADD' if expr.op == '+' else 'SUB'} {dest[0]}, R0")
                self.emit("MOV R0, 0")
                for reg in dest[1:]:
                    self.emit(f"{'ADC' if expr.op == '+' else 'SBB'} {reg}, R0")
            return result

        if isinstance(expr.right, ast.Number):
            typ = self.compile_expr(expr.left, scope, result)
            self.coerce(typ, result, expr.line)
            constant = self._wrap_value(int(expr.right.value), result)
            self._emit_immediate(constant, saved)
            self._emit_binary(expr.op, dest, saved)
            return result

        if self._is_leaf(expr.right):
            typ = self.compile_expr(expr.left, scope, result)
            self.coerce(typ, result, expr.line)
            self._move(dest, saved)
            typ = self.compile_expr(expr.right, scope, result)
            self.coerce(typ, result, expr.line)
            if expr.op == "-":
                self._emit_binary("-", saved, dest)
                self._move(saved, dest)
            else:
                self._emit_binary(expr.op, dest, saved)
            return result

        mark = self.temp.mark()
        temp_addr = self.temp.alloc(width, "expression", self.filename, expr.line)

        typ = self.compile_expr(expr.left, scope, result)
        self.coerce(typ, result, expr.line)
        self.store_temp(result, temp_addr)

        typ = self.compile_expr(expr.right, scope, result)
        self.coerce(typ, result, expr.line)
        self._move(dest, saved)
        self.load_temp(result, temp_addr)
        self._emit_binary(expr.op, dest, saved)
        self.temp.reset(mark)
        return result

    def _compile_dword_arithmetic(
        self,
        expr: ast.Binary,
        scope: Scope,
        result_type: Type = U32,
    ) -> Type:
        op = expr.op
        mask = 0xFFFFFFFF

        if isinstance(expr.left, ast.Number) and isinstance(expr.right, ast.Number):
            a, b = int(expr.left.value), int(expr.right.value)
            value = {
                "+": a + b,
                "-": a - b,
                "&": a & b,
                "|": a | b,
                "^": a ^ b,
            }[op]
            self._emit_immediate(
                self._wrap_value(value, result_type), _REGS[8]
            )
            return result_type

        if isinstance(expr.right, ast.Number):
            typ = self.compile_expr(expr.left, scope, result_type)
            self.coerce(typ, result_type, expr.line)
            value = self._wrap_value(int(expr.right.value), result_type) & mask
            for index in range(8):
                self.emit(f"MOV R0, {(value >> (4 * index)) & 0xF}")
                if op == "+":
                    self.emit(f"{'ADD' if index == 0 else 'ADC'} R{index + 1}, R0")
                elif op == "-":
                    self.emit(f"{'SUB' if index == 0 else 'SBB'} R{index + 1}, R0")
                else:
                    self.emit(f"{_NIBBLE_BINARY[op]} R{index + 1}, R0")
            return result_type

        mark = self.temp.mark()
        # Allocate the operand slots one at a time.  A nested 32-bit
        # expression needs 16 nibbles of its own, so holding both slots
        # while compiling the left side would exhaust the temporary area.
        left_addr = self.temp.alloc(8, "32-bit expression", self.filename, expr.line)
        typ = self.compile_expr(expr.left, scope, result_type)
        self.coerce(typ, result_type, expr.line)
        self.store_temp(result_type, left_addr)
        right_addr = self.temp.alloc(8, "32-bit expression", self.filename, expr.line)
        typ = self.compile_expr(expr.right, scope, result_type)
        self.coerce(typ, result_type, expr.line)
        self.store_temp(result_type, right_addr)
        self.load_temp(result_type, left_addr)

        for index in range(8):
            self.emit(f"MOV R0, [{right_addr + index}]")
            if op == "+":
                self.emit(f"{'ADD' if index == 0 else 'ADC'} R{index + 1}, R0")
            elif op == "-":
                self.emit(f"{'SUB' if index == 0 else 'SBB'} R{index + 1}, R0")
            else:
                self.emit(f"{_NIBBLE_BINARY[op]} R{index + 1}, R0")
        self.temp.reset(mark)
        return result_type

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


    def _emit_shift_right(self, typ: Type, count: int, arithmetic: bool = False) -> None:
        for _ in range(count):
            self._emit_shift_step(typ, ">>", arithmetic)

    def _emit_mask(self, typ: Type, mask: int) -> None:
        if is_integer(typ) and typ.ram_size == 8:
            for index in range(8):
                self.emit(f"MOV R0, {(mask >> (4 * index)) & 0xF}")
                self.emit(f"AND R{index + 1}, R0")
            return
        dest = _REGS[typ.ram_size]
        saved = _SAVED_REGS[typ.ram_size]
        self._emit_immediate(mask, saved)
        self._emit_binary("&", dest, saved)

    def _emit_shift_step(self, typ: Type, op: str, arithmetic: bool = False) -> None:
        regs = _REGS[typ.ram_size]
        if op == "<<":
            self.emit(f"ADD {regs[0]}, {regs[0]}")
            for reg in regs[1:]:
                self.emit(f"ADC {reg}, {reg}")
        else:
            if arithmetic:
                # ADD Rn,Rn puts the old top bit (the sign) into carry.
                self.emit(f"MOV R0, {regs[-1]}")
                self.emit("ADD R0, R0")
            else:
                self.emit("ADD R0, 0")           # clear carry
            for reg in reversed(regs):
                self.emit(f"RRC {reg}")

    def compile_shift(
        self,
        expr: ast.Binary,
        scope: Scope,
        expected: Optional[Type] = None,
    ) -> Type:
        left_type = self._arith_type(self.infer_type(expr.left, scope))
        if not is_integer(left_type):
            raise NiblickTypeError(
                f"{location(self.filename, expr.line)}: shifts require an integer operand"
            )
        result_type = widen_type(left_type, expected)
        width = 4 * result_type.ram_size
        regs = _REGS[result_type.ram_size]
        arithmetic = result_type.signed and expr.op == ">>"

        if isinstance(expr.right, ast.Number):
            count = int(expr.right.value)
            if isinstance(expr.left, ast.Number):
                value = self._wrap_value(int(expr.left.value), result_type)
                if expr.op == "<<":
                    result = (value << count) & self._width_mask(result_type)
                else:
                    result = value >> count
                self._emit_immediate(
                    self._wrap_value(result, result_type), regs
                )
                return result_type

            typ = self.compile_expr(expr.left, scope, result_type)
            self.coerce(typ, result_type, expr.line)
            if count == 0:
                return result_type
            if count >= width:
                if arithmetic:
                    self._emit_sign_fill_from_value(result_type)
                else:
                    self._emit_immediate(0, regs)
            else:
                for _ in range(count):
                    self._emit_shift_step(result_type, expr.op, arithmetic)
            return result_type

        # Variable count: loop one shift at a time.  Counts must fit in a
        # char; the count is unsigned, so a large count just shifts to zero
        # (or fills with the sign for an arithmetic right shift).
        right_type = self.infer_type(expr.right, scope)
        if not is_integer(right_type) or right_type.ram_size > U8.ram_size:
            raise NiblickTypeError(
                f"{location(self.filename, expr.line)}: shift counts must fit in a char"
            )

        mark = self.temp.mark()
        value_addr = self.temp.alloc(
            result_type.ram_size, "shift value", self.filename, expr.line
        )
        count_addr = self.temp.alloc(U8.ram_size, "shift count", self.filename, expr.line)

        typ = self.compile_expr(expr.left, scope, result_type)
        self.coerce(typ, result_type, expr.line)
        self.store_temp(result_type, value_addr)
        typ = self.compile_expr(expr.right, scope)
        self.coerce(typ, U8, expr.line)
        self.store_temp(U8, count_addr)
        self.load_temp(result_type, value_addr)

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

        self._emit_shift_step(result_type, expr.op, arithmetic)

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
        return result_type

    def _emit_sign_fill_from_value(self, typ: Type) -> None:
        """Replace the value with all zeros or all ones based on its sign."""

        regs = _REGS[typ.ram_size]
        self.emit(f"MOV R0, {regs[-1]}")
        self.emit("AND R0, 8")
        self.emit("CP R0, 0")
        self.emit("MOV R9, 0")
        self.emit("SKIP Z, 1")
        self.emit("MOV R9, 15")
        for reg in regs:
            self.emit(f"MOV {reg}, R9")

    def ensure_d32_scratch(self) -> int:
        if self.d32_scratch_addr is None:
            self.d32_scratch_addr = self.mem.alloc(
                24, "32-bit math scratch", self.filename, 0
            )
        return self.d32_scratch_addr

    def compile_mul(
        self,
        expr: ast.Binary,
        scope: Scope,
        expected: Optional[Type] = None,
    ) -> Type:
        left_type = self._arith_type(self.infer_type(expr.left, scope))
        right_type = self._arith_type(self.infer_type(expr.right, scope))
        if not is_integer(left_type) or not is_integer(right_type):
            raise NiblickTypeError(
                f"{location(self.filename, expr.line)}: multiplication requires integer operands"
            )
        common = self._common_expr_type(expr.left, expr.right, scope)
        if not is_integer(common):
            raise NiblickTypeError(
                f"{location(self.filename, expr.line)}: multiplication requires integer operands"
            )
        product_type = promoted_mul_type(common)
        result = widen_type(product_type, expected)

        left, right = expr.left, expr.right
        if isinstance(left, ast.Number) and not isinstance(right, ast.Number):
            left, right = right, left

        if isinstance(left, ast.Number) and isinstance(right, ast.Number):
            value = int(left.value) * int(right.value)
            self._emit_immediate(
                self._wrap_value(value, result), _REGS[result.ram_size]
            )
            return result

        right_value = self._literal_value(right)
        if right_value is not None:
            if right_value == 0:
                typ = self.compile_expr(left, scope, result)
                self.coerce(typ, result, expr.line)
                self._emit_immediate(0, _REGS[result.ram_size])
                return result
            if right_value == 1:
                typ = self.compile_expr(left, scope, result)
                self.coerce(typ, result, expr.line)
                return result
            if right_value > 0 and right_value & (right_value - 1) == 0:
                typ = self.compile_expr(left, scope, result)
                self.coerce(typ, result, expr.line)
                self._emit_shift_left(result, right_value.bit_length() - 1)
                return result

        if result.ram_size == 8:
            return self._compile_dword_mul(left, right, scope, expr.line, result)

        mark = self.temp.mark()
        temp_addr = self.temp.alloc(common.ram_size, "multiply", self.filename, expr.line)
        typ = self.compile_expr(left, scope, common)
        self.coerce(typ, common, expr.line)
        self.store_temp(common, temp_addr)

        typ = self.compile_expr(right, scope, common)
        self.coerce(typ, common, expr.line)
        if common.ram_size == 1:
            self.emit("MOV R2, R1")
            self.load_temp(common, temp_addr)
            self.use_runtime("__nib_mul4", expr.line)
            self.emit("GOSUB __nib_mul4")
        elif common.ram_size == 2:
            self._move(("R1", "R2"), ("R3", "R4"))
            self.load_temp(common, temp_addr)
            self.use_runtime("__nib_mul8", expr.line)
            self.emit("GOSUB __nib_mul8")
        else:
            self._move(("R1", "R2", "R3", "R4"), ("R5", "R6", "R7", "R8"))
            self.load_temp(common, temp_addr)
            self.use_runtime("__nib_mul16", expr.line)
            self.emit("GOSUB __nib_mul16")
        self.temp.reset(mark)
        if product_type is not result:
            self.coerce(product_type, result, expr.line)
        return result

    def _compile_dword_mul(
        self,
        left: ast.Expr,
        right: ast.Expr,
        scope: Scope,
        line: int,
        result_type: Type = U32,
    ) -> Type:
        mark = self.temp.mark()
        left_addr = self.temp.alloc(8, "32-bit multiply", self.filename, line)
        typ = self.compile_expr(left, scope, result_type)
        self.coerce(typ, result_type, line)
        self.store_temp(result_type, left_addr)
        right_addr = self.temp.alloc(8, "32-bit multiply", self.filename, line)
        typ = self.compile_expr(right, scope, result_type)
        self.coerce(typ, result_type, line)
        self.store_temp(result_type, right_addr)

        self.ensure_d32_scratch()
        self.emit(f"MOV R4, {(left_addr >> 4) & 0xF}")
        self.emit(f"MOV R5, {left_addr & 0xF}")
        self.emit(f"MOV R6, {(right_addr >> 4) & 0xF}")
        self.emit(f"MOV R7, {right_addr & 0xF}")
        self.use_runtime("__nib_mul32", line)
        self.emit("GOSUB __nib_mul32")
        self.temp.reset(mark)
        return result_type

    def compile_divmod(
        self,
        expr: ast.Binary,
        scope: Scope,
        expected: Optional[Type] = None,
    ) -> Type:
        left_type = self._arith_type(self.infer_type(expr.left, scope))
        right_type = self._arith_type(self.infer_type(expr.right, scope))
        if not is_integer(left_type) or not is_integer(right_type):
            raise NiblickTypeError(
                f"{location(self.filename, expr.line)}: division requires integer operands"
            )
        common = self._common_expr_type(expr.left, expr.right, scope)
        if not is_integer(common):
            raise NiblickTypeError(
                f"{location(self.filename, expr.line)}: division requires integer operands"
            )
        result = widen_type(common, expected)
        is_div = expr.op == "/"

        if common.signed:
            return self._compile_signed_divmod(
                expr, scope, common, result, is_div
            )

        if isinstance(expr.left, ast.Number) and isinstance(expr.right, ast.Number):
            a, b = int(expr.left.value), int(expr.right.value)
            value = 0 if b == 0 else (a // b if is_div else a % b)
            self._emit_immediate(
                self._wrap_value(value, result), _REGS[result.ram_size]
            )
            return result

        if isinstance(expr.right, ast.Number):
            constant = int(expr.right.value)
            if constant == 0:
                typ = self.compile_expr(expr.left, scope, result)
                self.coerce(typ, result, expr.line)
                self._emit_immediate(0, _REGS[result.ram_size])
                return result
            if constant == 1:
                typ = self.compile_expr(expr.left, scope, result)
                self.coerce(typ, result, expr.line)
                if not is_div:
                    self._emit_immediate(0, _REGS[result.ram_size])
                return result
            if constant > 0 and constant & (constant - 1) == 0:
                shift = constant.bit_length() - 1
                typ = self.compile_expr(expr.left, scope, common)
                self.coerce(typ, common, expr.line)
                if is_div:
                    self._emit_shift_right(common, shift)
                else:
                    self._emit_mask(common, constant - 1)
                if common is not result:
                    self.coerce(common, result, expr.line)
                return result

        if common.ram_size == 8:
            return self._compile_dword_divmod(
                expr.left, expr.right, is_div, scope, expr.line, result
            )

        mark = self.temp.mark()
        temp_common = U8 if common.ram_size == 1 else common
        temp_addr = self.temp.alloc(
            temp_common.ram_size, "divide", self.filename, expr.line
        )

        typ = self.compile_expr(expr.left, scope, common)
        self.coerce(typ, common, expr.line)
        self.coerce(common, temp_common, expr.line)
        self.store_temp(temp_common, temp_addr)

        typ = self.compile_expr(expr.right, scope, common)
        self.coerce(typ, common, expr.line)
        self.coerce(common, temp_common, expr.line)

        if common.ram_size == 1:
            self._move(("R1", "R2"), ("R3", "R4"))
            self.load_temp(U8, temp_addr)
            self.use_runtime("__nib_divmod8", expr.line)
            self.emit("GOSUB __nib_divmod8")
            if is_div:
                value_regs = ("R1", "R2")
            else:
                value_regs = ("R3", "R4")
            self._move(value_regs, ("R1", "R2"))
            if result.ram_size > 1:
                self.coerce(U4, result, expr.line)
            self.temp.reset(mark)
            return result

        if common.ram_size == 2:
            self._move(("R1", "R2"), ("R3", "R4"))
            self.load_temp(U8, temp_addr)
            self.use_runtime("__nib_divmod8", expr.line)
            self.emit("GOSUB __nib_divmod8")
            if not is_div:
                self._move(("R3", "R4"), ("R1", "R2"))
            self.temp.reset(mark)
            if common is not result:
                self.coerce(common, result, expr.line)
            return result

        self._move(("R1", "R2", "R3", "R4"), ("R5", "R6", "R7", "R8"))
        self.load_temp(U16, temp_addr)
        self.use_runtime("__nib_divmod16", expr.line)
        self.emit("GOSUB __nib_divmod16")
        if not is_div:
            self._move(("R5", "R6", "R7", "R8"), ("R1", "R2", "R3", "R4"))
        self.temp.reset(mark)
        if common is not result:
            self.coerce(common, result, expr.line)
        return result

    def _compile_signed_divmod(
        self,
        expr: ast.Binary,
        scope: Scope,
        common: Type,
        result: Type,
        is_div: bool,
    ) -> Type:
        # Signed 4-bit division is computed at 8 bits and narrowed back, which
        # also gives the correct wrap for the most-negative value divided by -1.
        compute_type = common
        if common.ram_size == 1:
            compute_type = I8
        elif common.ram_size == 2:
            compute_type = I8
        elif common.ram_size == 4:
            compute_type = I16
        elif common.ram_size == 8:
            return self._compile_signed_divmod32(expr, scope, result, is_div)

        mark = self.temp.mark()
        left_addr = self.temp.alloc(
            compute_type.ram_size, "signed divide", self.filename, expr.line
        )
        right_addr = self.temp.alloc(
            compute_type.ram_size, "signed divide", self.filename, expr.line
        )

        typ = self.compile_expr(expr.left, scope)
        self.coerce(typ, compute_type, expr.line)
        self.store_temp(compute_type, left_addr)
        typ = self.compile_expr(expr.right, scope)
        self.coerce(typ, compute_type, expr.line)
        self.store_temp(compute_type, right_addr)

        if compute_type.ram_size == 2:
            self.load_temp(compute_type, left_addr)
            self.load_temp(compute_type, right_addr)
            self._move(("R1", "R2"), ("R3", "R4"))
            self.load_temp(compute_type, left_addr)
            self.use_runtime("__nib_sdivmod8", expr.line)
            self.emit("GOSUB __nib_sdivmod8")
            if not is_div:
                self._move(("R3", "R4"), ("R1", "R2"))
            self.temp.reset(mark)
            if compute_type is not result:
                if result.ram_size < compute_type.ram_size:
                    # Explicit narrowing is not needed here: the result type
                    # came from the operand types, so it is at least as wide.
                    pass
                else:
                    self.coerce(compute_type, result, expr.line)
            return result

        self.load_temp(compute_type, right_addr)
        self._move(("R1", "R2", "R3", "R4"), ("R5", "R6", "R7", "R8"))
        self.load_temp(compute_type, left_addr)
        self.use_runtime("__nib_sdivmod16", expr.line)
        self.emit("GOSUB __nib_sdivmod16")
        if not is_div:
            self._move(("R5", "R6", "R7", "R8"), ("R1", "R2", "R3", "R4"))
        self.temp.reset(mark)
        if compute_type is not result:
            self.coerce(compute_type, result, expr.line)
        return result

    def _emit_negate_regs(self, regs: tuple[str, ...]) -> None:
        for reg in regs:
            self.emit(f"MOV R0, {reg}")
            self.emit(f"CPL {reg}, R0")
        self.emit("MOV R0, 1")
        self.emit(f"ADD {regs[0]}, R0")
        self.emit("MOV R0, 0")
        for reg in regs[1:]:
            self.emit(f"ADC {reg}, R0")

    def _emit_negate_if_flag(self, flag_addr: int, regs: tuple[str, ...]) -> None:
        neg_label = self.new_label("sneg")
        done_label = self.new_label("snegdone")
        self.emit(f"MOV R0, [{flag_addr}]")
        self.emit("CP R0, 0")
        self.emit("SKIP NZ, 2")
        self.emit(f"GOTO {done_label}")
        self.emit(f"{neg_label}:")
        self._emit_negate_regs(regs)
        self.emit(f"{done_label}:")

    def _store_abs32(self, addr: int, sign_addr: int) -> None:
        self.load_temp(I32, addr)
        neg_label = self.new_label("sabs")
        done_label = self.new_label("sabsdone")
        self.emit("MOV R0, R8")
        self.emit("AND R0, 8")
        self.emit("CP R0, 0")
        self.emit("MOV R0, 0")
        self.emit(f"MOV [{sign_addr}], R0")
        self.emit("SKIP Z, 2")
        self.emit(f"GOTO {neg_label}")
        self.emit(f"GOTO {done_label}")
        self.emit(f"{neg_label}:")
        self.emit("MOV R0, 1")
        self.emit(f"MOV [{sign_addr}], R0")
        self._emit_negate_regs(("R1", "R2", "R3", "R4", "R5", "R6", "R7", "R8"))
        self.emit(f"{done_label}:")
        self.store_temp(I32, addr)

    def _compile_signed_divmod32(
        self,
        expr: ast.Binary,
        scope: Scope,
        result: Type,
        is_div: bool,
    ) -> Type:
        mark = self.temp.mark()
        sign_addr = self.temp.alloc(
            3, "signed divide signs", self.filename, expr.line
        )
        left_addr = self.temp.alloc(
            8, "signed divide", self.filename, expr.line
        )
        right_addr = self.temp.alloc(
            8, "signed divide", self.filename, expr.line
        )

        typ = self.compile_expr(expr.left, scope, I32)
        self.coerce(typ, I32, expr.line)
        self.store_temp(I32, left_addr)
        self._store_abs32(left_addr, sign_addr)

        typ = self.compile_expr(expr.right, scope, I32)
        self.coerce(typ, I32, expr.line)
        self.store_temp(I32, right_addr)
        self._store_abs32(right_addr, sign_addr + 1)

        # signq = signa xor signb
        self.emit(f"MOV R0, [{sign_addr}]")
        self.emit("MOV R9, R0")
        self.emit(f"MOV R0, [{sign_addr + 1}]")
        self.emit("XOR R0, R9")
        self.emit(f"MOV [{sign_addr + 2}], R0")

        self.ensure_d32_scratch()
        self.emit(f"MOV R4, {(left_addr >> 4) & 0xF}")
        self.emit(f"MOV R5, {left_addr & 0xF}")
        self.emit(f"MOV R6, {(right_addr >> 4) & 0xF}")
        self.emit(f"MOV R7, {right_addr & 0xF}")
        self.use_runtime("__nib_divmod32", expr.line)
        self.emit("GOSUB __nib_divmod32")

        if is_div:
            self.load_temp(I32, left_addr)
            self._emit_negate_if_flag(
                sign_addr + 2, ("R1", "R2", "R3", "R4", "R5", "R6", "R7", "R8")
            )
        else:
            self.load_temp(I32, right_addr)
            self._emit_negate_if_flag(
                sign_addr, ("R1", "R2", "R3", "R4", "R5", "R6", "R7", "R8")
            )
        self.temp.reset(mark)
        if result is not I32:
            self.coerce(I32, result, expr.line)
        return result

    def _compile_dword_divmod(
        self,
        left: ast.Expr,
        right: ast.Expr,
        is_div: bool,
        scope: Scope,
        line: int,
        result_type: Type = U32,
    ) -> Type:
        mark = self.temp.mark()
        left_addr = self.temp.alloc(8, "32-bit divide", self.filename, line)
        typ = self.compile_expr(left, scope, result_type)
        self.coerce(typ, result_type, line)
        self.store_temp(result_type, left_addr)
        right_addr = self.temp.alloc(8, "32-bit divide", self.filename, line)
        typ = self.compile_expr(right, scope, result_type)
        self.coerce(typ, result_type, line)
        self.store_temp(result_type, right_addr)

        self.ensure_d32_scratch()
        self.emit(f"MOV R4, {(left_addr >> 4) & 0xF}")
        self.emit(f"MOV R5, {left_addr & 0xF}")
        self.emit(f"MOV R6, {(right_addr >> 4) & 0xF}")
        self.emit(f"MOV R7, {right_addr & 0xF}")
        self.use_runtime("__nib_divmod32", line)
        self.emit("GOSUB __nib_divmod32")
        self.load_temp(result_type, left_addr if is_div else right_addr)
        self.temp.reset(mark)
        return result_type

    def compile_index(self, expr: ast.Index, scope: Scope) -> Type:
        if isinstance(expr.base, ast.Member):
            field = self.member_info(expr.base, scope)
            if field.array_len <= 0:
                raise NiblickTypeError(
                    f"{location(self.filename, expr.line)}: field "
                    f"{expr.base.field!r} is not an array"
                )
            if isinstance(field.type, StructType):
                raise NiblickTypeError(
                    f"{location(self.filename, expr.line)}: struct array fields "
                    "are not supported"
                )
            if self._struct_is_flash(expr.base, scope):
                self.compile_flash_member_addr(expr.base, scope)
                if isinstance(expr.index, ast.Number):
                    index = int(expr.index.value)
                    if index < 0 or index >= field.array_len:
                        raise NiblickCompileError(
                            f"{location(self.filename, expr.line)}: index {index} "
                            f"out of bounds for field {expr.base.field}"
                            f"[{field.array_len}]"
                        )
                    self._add_flash_offset(index * field.type.ram_size)
                else:
                    mark = self.temp.mark()
                    base_slot = self.temp.alloc(
                        3, "flash array base", self.filename, expr.line
                    )
                    self.emit("MOV R0, R1")
                    self.emit(f"MOV [{base_slot}], R0")
                    self.emit("MOV R0, R2")
                    self.emit(f"MOV [{base_slot + 1}], R0")
                    self.emit("MOV R0, R3")
                    self.emit(f"MOV [{base_slot + 2}], R0")
                    index_type = self.compile_expr(expr.index, scope)
                    if not (
                        is_integer(index_type) and index_type.ram_size in (1, 2)
                    ):
                        raise NiblickTypeError(
                            f"{location(self.filename, expr.line)}: array index "
                            "must be a nibble or char"
                        )
                    self._emit_scaled_index(field.type.ram_size, index_type)
                    self.emit(f"MOV R0, [{base_slot}]")
                    self.emit("MOV R1, R0")
                    self.emit(f"MOV R0, [{base_slot + 1}]")
                    self.emit("MOV R2, R0")
                    self.emit(f"MOV R0, [{base_slot + 2}]")
                    self.emit("MOV R3, R0")
                    self._add_flash_offset_regs()
                    self.temp.reset(mark)
                self.load_flash_indirect(field.type, expr.line)
                return field.type
            if isinstance(expr.index, ast.Number):
                index = int(expr.index.value)
                if index < 0 or index >= field.array_len:
                    raise NiblickCompileError(
                        f"{location(self.filename, expr.line)}: index {index} out "
                        f"of bounds for field {expr.base.field}[{field.array_len}]"
                    )
                self.compile_member_addr(expr.base, scope)
                offset = index * field.type.ram_size
                if offset:
                    self.emit(f"MOV R0, {offset & 0xF}")
                    self.emit("ADD R5, R0")
                    self.emit("SKIP NC, 1")
                    self.emit("INC R4")
                    if offset >> 4:
                        self.emit(f"MOV R0, {(offset >> 4) & 0xF}")
                        self.emit("ADD R4, R0")
            else:
                mark = self.temp.mark()
                base_slot = self.temp.alloc(
                    2, "array base", self.filename, expr.line
                )
                self.compile_member_addr(expr.base, scope)
                self.emit("MOV R0, R4")
                self.emit(f"MOV [{base_slot}], R0")
                self.emit("MOV R0, R5")
                self.emit(f"MOV [{base_slot + 1}], R0")
                index_type = self.compile_expr(expr.index, scope)
                if not (
                    is_integer(index_type) and index_type.ram_size in (1, 2)
                ):
                    raise NiblickTypeError(
                        f"{location(self.filename, expr.line)}: array index must "
                        "be a nibble or char"
                    )
                self._emit_scaled_index(field.type.ram_size, index_type)
                self.emit(f"MOV R0, [{base_slot + 1}]")
                self.emit("ADD R5, R0")
                self.emit("SKIP NC, 1")
                self.emit("INC R4")
                self.emit(f"MOV R0, [{base_slot}]")
                self.emit("ADD R4, R0")
                self.temp.reset(mark)
            self.load_indirect(field.type, expr.line)
            return field.type

        if not isinstance(expr.base, ast.Var):
            raise NiblickTypeError(
                f"{location(self.filename, expr.line)}: only named arrays can be indexed"
            )
        symbol = self.lookup(expr.base.name, scope, expr.line)
        if symbol.array_len is None:
            raise NiblickTypeError(
                f"{location(self.filename, expr.line)}: {symbol.name!r} is not an array"
            )

        if isinstance(expr.index, ast.Number):
            if expr.index.value < 0 or expr.index.value >= symbol.array_len:
                raise NiblickCompileError(
                    f"{location(self.filename, expr.line)}: index {expr.index.value} out of bounds "
                    f"for {symbol.name}[{symbol.array_len}]"
                )

        if isinstance(symbol.type, StructType):
            if symbol.flash_label is not None:
                self.compile_flash_struct_addr(symbol, expr.index, scope, expr.line)
                dest = self.temp.alloc(
                    symbol.type.ram_size,
                    "flash struct element",
                    self.filename,
                    expr.line,
                )
                self._copy_flash_struct_to_ram(
                    dest, symbol.type.ram_size, expr.line
                )
                self._emit_addr(dest)
                return symbol.type
            self.compile_ram_addr(symbol, expr.index, scope, expr.line)
            return symbol.type

        if symbol.flash_label is not None:
            self.compile_flash_addr(symbol, expr.index, scope, expr.line)
            if symbol.type.ram_size == 2:
                self.use_runtime("__nib_flash_read_char", expr.line)
                self.emit("GOSUB __nib_flash_read_char")
                return U8
            if symbol.type.ram_size == 4:
                self.use_runtime("__nib_flash_read_word", expr.line)
                self.emit("GOSUB __nib_flash_read_word")
                return U16
            if symbol.type.ram_size == 8:
                self.ensure_d32_scratch()
                self.use_runtime("__nib_flash_read_dword", expr.line)
                self.emit("GOSUB __nib_flash_read_dword")
                return U32
            self.use_runtime("__nib_flash_read_nibble", expr.line)
            self.emit("GOSUB __nib_flash_read_nibble")
            return U4

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
        if symbol.type.ram_size == 1:
            self.emit("MOV R0, [R4:R5]")
            self.emit("MOV R1, R0")
            return symbol.type
        if symbol.type.ram_size == 2:
            self.emit("MOV R0, [R4:R5]")
            self.emit("MOV R1, R0")
            self.emit("INC R5")
            self.emit("SKIP NC, 1")
            self.emit("INC R4")
            self.emit("MOV R0, [R4:R5]")
            self.emit("MOV R2, R0")
            return U8
        if symbol.type.ram_size == 8:
            # A 32-bit value occupies R1..R8, leaving no free address pair.
            # Stage the value through a temp buffer.
            mark = self.temp.mark()
            temp_addr = self.temp.alloc(8, "32-bit index", self.filename, expr.line)
            for index in range(8):
                self.emit("MOV R0, [R4:R5]")
                self.emit(f"MOV [{temp_addr + index}], R0")
                if index != 7:
                    self.emit("INC R5")
                    self.emit("SKIP NC, 1")
                    self.emit("INC R4")
            self.load_temp(U32, temp_addr)
            self.temp.reset(mark)
            return U32
        if symbol.type.ram_size == 4:
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
            return U16
        raise NiblickTypeError(
            f"{location(self.filename, expr.line)}: cannot index {symbol.type} array {symbol.name!r}"
        )

    # ------------------------------------------------------------------
    # Address helpers
    # ------------------------------------------------------------------

    def _is_const_struct_write(self, expr: ast.Expr, scope: Scope) -> bool:
        if isinstance(expr, ast.Var):
            symbol = self.lookup(expr.name, scope, expr.line)
            return (
                symbol.is_const
                and symbol.flash_label is not None
                and isinstance(symbol.type, StructType)
            )
        if isinstance(expr, (ast.Member, ast.Index)):
            return self._is_const_struct_write(expr.base, scope)
        return False

    def _struct_is_flash(self, expr: ast.Expr, scope: Scope) -> bool:
        if isinstance(expr, ast.Var):
            symbol = self.lookup(expr.name, scope, expr.line)
            return (
                symbol.flash_label is not None
                and isinstance(symbol.type, StructType)
            )
        if isinstance(expr, ast.Member):
            return self._struct_is_flash(expr.base, scope)
        return False

    def member_info(self, expr: ast.Member, scope: Scope):
        base_type = self.infer_type(expr.base, scope)
        if not isinstance(base_type, StructType):
            raise NiblickTypeError(
                f"{location(self.filename, expr.line)}: {base_type} has no field "
                f"{expr.field!r}"
            )
        field = base_type.field(expr.field)
        if field is None:
            raise NiblickTypeError(
                f"{location(self.filename, expr.line)}: struct {base_type.name} has "
                f"no field {expr.field!r}"
            )
        return field

    def _add_flash_offset(self, offset: int) -> None:
        if offset:
            self.emit(f"MOV R0, {offset & 0xF}")
            self.emit("ADD R1, R0")
            self.emit("MOV R0, 0")
            self.emit("ADC R2, R0")
            self.emit("ADC R3, R0")
            high = (offset >> 4) & 0xF
            if high:
                self.emit(f"MOV R0, {high}")
                self.emit("ADD R2, R0")
                self.emit("MOV R0, 0")
                self.emit("ADC R3, R0")

    def compile_flash_member_addr(self, expr: ast.Member, scope: Scope) -> None:
        field = self.member_info(expr, scope)
        base = expr.base
        if isinstance(base, ast.Var):
            symbol = self.lookup(base.name, scope, base.line)
            if symbol.flash_label is None:
                raise NiblickTypeError(
                    f"{location(self.filename, base.line)}: {base.name!r} "
                    "is not in flash"
                )
            self.emit_flashptr(symbol.flash_label)
        elif isinstance(base, ast.Member):
            self.compile_flash_member_addr(base, scope)
        else:
            raise NiblickTypeError(
                f"{location(self.filename, base.line)}: unsupported flash "
                "struct field base"
            )
        self._add_flash_offset(field.offset)

    def _add_flash_offset_regs(self) -> None:
        self.emit("MOV R0, R5")
        self.emit("ADD R1, R0")
        self.emit("MOV R0, 0")
        self.emit("ADC R2, R0")
        self.emit("ADC R3, R0")
        self.emit("MOV R0, R4")
        self.emit("ADD R2, R0")
        self.emit("MOV R0, 0")
        self.emit("ADC R3, R0")

    def load_flash_indirect(self, typ: Type, line: int) -> None:
        if typ is U8:
            self.use_runtime("__nib_flash_read_char", line)
            self.emit("GOSUB __nib_flash_read_char")
            return
        if typ is U16:
            self.use_runtime("__nib_flash_read_word", line)
            self.emit("GOSUB __nib_flash_read_word")
            return
        if typ is U32:
            self.ensure_d32_scratch()
            self.use_runtime("__nib_flash_read_dword", line)
            self.emit("GOSUB __nib_flash_read_dword")
            return
        if is_integer(typ) and typ.ram_size == 1:
            self.use_runtime("__nib_flash_read_nibble", line)
            self.emit("GOSUB __nib_flash_read_nibble")
            return
        raise NiblickTypeError(
            f"{location(self.filename, line)}: cannot read {typ} from a flash struct"
        )

    def _copy_flash_struct_to_ram(
        self, dest: int, size: int, line: int
    ) -> None:
        mark = self.temp.mark()
        source = self.temp.alloc(3, "flash struct source", self.filename, line)
        dest_slot = self.temp.alloc(2, "flash struct destination", self.filename, line)
        count = self.temp.alloc(2, "flash struct count", self.filename, line)
        self.emit("MOV R0, R1")
        self.emit(f"MOV [{source}], R0")
        self.emit("MOV R0, R2")
        self.emit(f"MOV [{source + 1}], R0")
        self.emit("MOV R0, R3")
        self.emit(f"MOV [{source + 2}], R0")
        self.emit(f"MOV R0, {(dest >> 4) & 0xF}")
        self.emit(f"MOV [{dest_slot}], R0")
        self.emit(f"MOV R0, {dest & 0xF}")
        self.emit(f"MOV [{dest_slot + 1}], R0")
        self.emit(f"MOV R0, {size & 0xF}")
        self.emit(f"MOV [{count}], R0")
        self.emit(f"MOV R0, {(size >> 4) & 0xF}")
        self.emit(f"MOV [{count + 1}], R0")

        loop = self.new_label("flash_struct_copy")
        self.emit(f"{loop}:")
        self.emit(f"MOV R0, [{source}]")
        self.emit("MOV R1, R0")
        self.emit(f"MOV R0, [{source + 1}]")
        self.emit("MOV R2, R0")
        self.emit(f"MOV R0, [{source + 2}]")
        self.emit("MOV R3, R0")
        self.use_runtime("__nib_flash_read_nibble", line)
        self.emit("GOSUB __nib_flash_read_nibble")

        self.emit(f"MOV R0, [{dest_slot}]")
        self.emit("MOV R4, R0")
        self.emit(f"MOV R0, [{dest_slot + 1}]")
        self.emit("MOV R5, R0")
        self.emit("MOV R0, R1")
        self.emit("MOV [R4:R5], R0")
        self.emit("INC R5")
        self.emit("SKIP NC, 1")
        self.emit("INC R4")
        self.emit("MOV R0, R4")
        self.emit(f"MOV [{dest_slot}], R0")
        self.emit("MOV R0, R5")
        self.emit(f"MOV [{dest_slot + 1}], R0")

        self.emit(f"MOV R0, [{source}]")
        self.emit("MOV R1, R0")
        self.emit(f"MOV R0, [{source + 1}]")
        self.emit("MOV R2, R0")
        self.emit(f"MOV R0, [{source + 2}]")
        self.emit("MOV R3, R0")
        self.emit("INC R1")
        self.emit("SKIP NC, 1")
        self.emit("INC R2")
        self.emit("SKIP NC, 1")
        self.emit("INC R3")
        self.emit("MOV R0, R1")
        self.emit(f"MOV [{source}], R0")
        self.emit("MOV R0, R2")
        self.emit(f"MOV [{source + 1}], R0")
        self.emit("MOV R0, R3")
        self.emit(f"MOV [{source + 2}], R0")

        self.emit(f"MOV R0, [{count}]")
        self.emit("MOV R1, R0")
        self.emit(f"MOV R0, [{count + 1}]")
        self.emit("MOV R2, R0")
        self.emit("DEC R1")
        self.emit("SKIP C, 1")
        self.emit("DEC R2")
        self.emit("MOV R0, R1")
        self.emit(f"MOV [{count}], R0")
        self.emit("MOV R0, R2")
        self.emit(f"MOV [{count + 1}], R0")
        self.emit("MOV R0, R1")
        self.emit("OR R0, R2")
        self.emit("CP R0, 0")
        self.emit("SKIP Z, 1")
        self.emit(f"JR {loop}")
        self.temp.reset(mark)

    def compile_member_addr(self, expr: ast.Member, scope: Scope) -> None:
        if self._struct_is_flash(expr, scope):
            raise NiblickTypeError(
                f"{location(self.filename, expr.line)}: const struct field "
                "is read-only"
            )
        field = self.member_info(expr, scope)
        base = expr.base
        if isinstance(base, ast.Var):
            symbol = self.lookup(base.name, scope, base.line)
            if symbol.array_len is not None:
                raise NiblickTypeError(
                    f"{location(self.filename, base.line)}: struct array "
                    f"{symbol.name!r} needs an index"
                )
            if symbol.address is None:
                raise NiblickCompileError(
                    f"{location(self.filename, base.line)}: {symbol.name!r} has no RAM storage"
                )
            self.emit(f"MOV R4, {(symbol.address >> 4) & 0xF}")
            self.emit(f"MOV R5, {symbol.address & 0xF}")
        elif isinstance(base, ast.Index):
            base_type = self.compile_expr(base, scope)
            if not isinstance(base_type, StructType):
                raise NiblickTypeError(
                    f"{location(self.filename, base.line)}: indexed value is not a struct"
                )
        elif isinstance(base, ast.Call):
            self.compile_struct_expr(base, scope)
        elif isinstance(base, ast.Member):
            self.compile_member_addr(base, scope)
        else:
            raise NiblickTypeError(
                f"{location(self.filename, base.line)}: unsupported struct field base"
            )

        offset = field.offset
        low = offset & 0xF
        high = (offset >> 4) & 0xF
        if low:
            self.emit(f"MOV R0, {low}")
            self.emit("ADD R5, R0")
            self.emit("SKIP NC, 1")
            self.emit("INC R4")
        if high:
            self.emit(f"MOV R0, {high}")
            self.emit("ADD R4, R0")

    def _emit_addr(self, address: int) -> None:
        self.emit(f"MOV R4, {(address >> 4) & 0xF}")
        self.emit(f"MOV R5, {address & 0xF}")

    def _emit_ptr_step(self, high: str, low: str) -> None:
        self.emit(f"INC {low}")
        self.emit("SKIP NC, 1")
        self.emit(f"INC {high}")

    def _emit_struct_copy_indirect(self, size: int) -> None:
        for _ in range(size):
            self.emit("MOV R0, [R4:R5]")
            self.emit("MOV [R6:R7], R0")
            self._emit_ptr_step("R4", "R5")
            self._emit_ptr_step("R6", "R7")

    def _emit_struct_copy_regs_to_static(self, size: int, address: int) -> None:
        self.emit(f"MOV R6, {(address >> 4) & 0xF}")
        self.emit(f"MOV R7, {address & 0xF}")
        self._emit_struct_copy_indirect(size)

    def compile_struct_expr(self, expr: ast.Expr, scope: Scope) -> Type:
        typ = self.infer_type(expr, scope)
        if not isinstance(typ, StructType):
            raise NiblickTypeError(
                f"{location(self.filename, getattr(expr, 'line', 0))}: "
                f"{typ} is not a struct value"
            )
        if self._struct_is_flash(expr, scope):
            if isinstance(expr, ast.Var):
                symbol = self.lookup(expr.name, scope, expr.line)
                if symbol.flash_label is None or symbol.array_len is not None:
                    raise NiblickTypeError(
                        f"{location(self.filename, expr.line)}: {expr.name!r} "
                        "is not a single flash struct"
                    )
                self.emit_flashptr(symbol.flash_label)
            elif isinstance(expr, ast.Member):
                self.compile_flash_member_addr(expr, scope)
            else:
                raise NiblickTypeError(
                    f"{location(self.filename, expr.line)}: unsupported flash "
                    "struct expression"
                )
            dest = self.temp.alloc(
                typ.ram_size, "flash struct copy", self.filename, expr.line
            )
            self._copy_flash_struct_to_ram(dest, typ.ram_size, expr.line)
            self._emit_addr(dest)
            return typ
        if isinstance(expr, ast.Var):
            symbol = self.lookup(expr.name, scope, expr.line)
            if symbol.array_len is not None:
                raise NiblickTypeError(
                    f"{location(self.filename, expr.line)}: struct array "
                    f"{expr.name!r} used without an index"
                )
            if symbol.address is None:
                raise NiblickCompileError(
                    f"{location(self.filename, expr.line)}: {expr.name!r} "
                    "has no RAM storage"
                )
            self._emit_addr(symbol.address)
            return typ
        if isinstance(expr, ast.Index):
            return self.compile_index(expr, scope)
        if isinstance(expr, ast.Member):
            self.compile_member_addr(expr, scope)
            return typ
        if isinstance(expr, ast.Call):
            self.compile_call(expr, scope)
            if self.struct_result_addr is None:
                raise NiblickCompileError(
                    f"{location(self.filename, expr.line)}: struct result "
                    "buffer is not allocated"
                )
            self._emit_addr(self.struct_result_addr)
            return typ
        raise NiblickTypeError(
            f"{location(self.filename, getattr(expr, 'line', 0))}: cannot use "
            f"{type(expr).__name__} as a struct value"
        )

    def store_struct_lvalue(
        self, target: ast.Expr, scope: Scope, size: int, line: int
    ) -> None:
        if isinstance(target, ast.Var):
            symbol = self.lookup(target.name, scope, target.line)
            if symbol.address is None:
                raise NiblickCompileError(
                    f"{location(self.filename, line)}: {symbol.name!r} "
                    "has no RAM storage"
                )
            self._emit_struct_copy_regs_to_static(size, symbol.address)
            return
        if isinstance(target, (ast.Index, ast.Member)):
            mark = self.temp.mark()
            saved = self.temp.alloc(2, "struct source", self.filename, line)
            self.emit("MOV R0, R4")
            self.emit(f"MOV [{saved}], R0")
            self.emit("MOV R0, R5")
            self.emit(f"MOV [{saved + 1}], R0")
            if isinstance(target, ast.Index):
                self.compile_index(target, scope)
            else:
                self.compile_member_addr(target, scope)
            self.emit("MOV R6, R4")
            self.emit("MOV R7, R5")
            self.emit(f"MOV R0, [{saved}]")
            self.emit("MOV R4, R0")
            self.emit(f"MOV R0, [{saved + 1}]")
            self.emit("MOV R5, R0")
            self._emit_struct_copy_indirect(size)
            self.temp.reset(mark)
            return
        raise NiblickTypeError(
            f"{location(self.filename, line)}: invalid struct assignment target"
        )

    def load_indirect(self, typ: Type, line: int) -> None:
        if is_integer(typ) and typ.ram_size == 16:
            self._emit_qword_load_indirect(self.ensure_qword_result())
            return
        if typ is BOOL or (is_integer(typ) and typ.ram_size == 1):
            self.emit("MOV R0, [R4:R5]")
            self.emit("MOV R1, R0")
            return
        if (is_integer(typ) or typ.is_float) and typ.ram_size == 8:
            mark = self.temp.mark()
            temp_addr = self.temp.alloc(8, "indirect load", self.filename, line)
            self.emit("MOV R6, R4")
            self.emit("MOV R7, R5")
            for index in range(8):
                self.emit("MOV R0, [R6:R7]")
                self.emit(f"MOV [{temp_addr + index}], R0")
                if index != 7:
                    self.emit("INC R7")
                    self.emit("SKIP NC, 1")
                    self.emit("INC R6")
            self.load_temp(typ, temp_addr)
            self.temp.reset(mark)
            return
        if typ is not FLASHPTR and not (
            (is_integer(typ) or typ.is_float) and typ.ram_size in (2, 4)
        ):
            raise NiblickTypeError(
                f"{location(self.filename, line)}: cannot load {typ} from memory"
            )
        for index in range(typ.ram_size):
            self.emit("MOV R0, [R4:R5]")
            self.emit(f"MOV R{index + 1}, R0")
            if index != typ.ram_size - 1:
                self.emit("INC R5")
                self.emit("SKIP NC, 1")
                self.emit("INC R4")

    def store_member_from_temp(
        self, target: ast.Member, scope: Scope, typ: Type, temp_addr: int, line: int
    ) -> None:
        self.compile_member_addr(target, scope)
        if is_integer(typ) and typ.ram_size == 16:
            self._emit_qword_store_indirect(temp_addr)
            return
        if (is_integer(typ) or typ.is_float) and typ.ram_size == 8:
            self.emit("MOV R6, R4")
            self.emit("MOV R7, R5")
            for index in range(8):
                self.emit(f"MOV R0, [{temp_addr + index}]")
                self.emit("MOV [R6:R7], R0")
                if index != 7:
                    self.emit("INC R7")
                    self.emit("SKIP NC, 1")
                    self.emit("INC R6")
            return
        if (is_integer(typ) or typ.is_float) and typ.ram_size == 4:
            self.emit("MOV R6, R4")
            self.emit("MOV R7, R5")
        self.load_temp(typ, temp_addr)
        if typ is BOOL or (is_integer(typ) and typ.ram_size == 1):
            self.emit("MOV R0, R1")
            self.emit("MOV [R4:R5], R0")
            return
        if is_integer(typ) and typ.ram_size == 2:
            self.emit("MOV R0, R1")
            self.emit("MOV [R4:R5], R0")
            self.emit("INC R5")
            self.emit("SKIP NC, 1")
            self.emit("INC R4")
            self.emit("MOV R0, R2")
            self.emit("MOV [R4:R5], R0")
            return
        if typ is FLASHPTR:
            self.emit("MOV R0, R1")
            self.emit("MOV [R4:R5], R0")
            self.emit("INC R5")
            self.emit("SKIP NC, 1")
            self.emit("INC R4")
            self.emit("MOV R0, R2")
            self.emit("MOV [R4:R5], R0")
            self.emit("INC R5")
            self.emit("SKIP NC, 1")
            self.emit("INC R4")
            self.emit("MOV R0, R3")
            self.emit("MOV [R4:R5], R0")
            return
        if (is_integer(typ) or typ.is_float) and typ.ram_size in (4, 8):
            for index in range(typ.ram_size):
                self.emit(f"MOV R0, R{index + 1}")
                self.emit("MOV [R6:R7], R0")
                if index != typ.ram_size - 1:
                    self.emit("INC R7")
                    self.emit("SKIP NC, 1")
                    self.emit("INC R6")
            return
        raise NiblickTypeError(
            f"{location(self.filename, line)}: cannot store {typ} to a struct field"
        )

    def compile_ram_addr(self, symbol: VarSymbol, index: ast.Expr, scope: Scope, line: int) -> None:
        assert symbol.address is not None
        base = symbol.address
        index_type = self.compile_expr(index, scope)
        if not (is_integer(index_type) and index_type.ram_size in (1, 2)):
            raise NiblickTypeError(
                f"{location(self.filename, line)}: array index must be a nibble or char"
            )

        scale = symbol.type.ram_size
        if scale == 1 and (base & 0xF) == 0:
            # The array starts on a 16-nibble page boundary, so a nibble
            # index never carries into the high address nibble.  A char
            # index only ever adds to the high nibble.
            self.emit(f"MOV R4, {(base >> 4) & 0xF}")
            self.emit("MOV R5, R1")
            if index_type.ram_size == 2:
                self.emit("ADD R4, R2")
            return

        self._emit_scaled_index(scale, index_type)
        self.emit(f"MOV R0, {base & 0xF}")
        self.emit("ADD R5, R0")
        self.emit("SKIP NC, 1")
        self.emit("INC R4")
        self.emit(f"MOV R0, {(base >> 4) & 0xF}")
        self.emit("ADD R4, R0")

    def _emit_scaled_index(self, scale: int, index_type: Type) -> None:
        """Put index * scale in R4:R5.

        The product for an in-bounds access fits in one data address, so this
        uses 8-bit arithmetic. Shift/add sequences handle non-power-of-two
        struct sizes.
        """
        if scale < 1:
            raise NiblickCompileError(f"invalid array element size {scale}")

        self.emit("MOV R5, R1")
        if index_type.ram_size == 2:
            self.emit("MOV R4, R2")
        else:
            self.emit("MOV R4, 0")

        if scale == 1:
            return
        if scale & (scale - 1) == 0:
            for _ in range(scale.bit_length() - 1):
                self.emit("ADD R4, R4")
                self.emit("ADD R5, R5")
                self.emit("SKIP NC, 1")
                self.emit("INC R4")
            return

        # R6:R7 = index, R8:R9 = shifted index, R4:R5 = accumulator.
        self.emit("MOV R6, R5")
        self.emit("MOV R7, R4")
        self.emit("MOV R4, 0")
        self.emit("MOV R5, 0")
        self.emit("MOV R8, R6")
        self.emit("MOV R9, R7")
        bit = 1
        while bit <= scale:
            if scale & bit:
                self.emit("ADD R5, R8")
                self.emit("ADC R4, R9")
            if bit != 1 << (scale.bit_length() - 1):
                self.emit("ADD R8, R8")
                self.emit("ADC R9, R9")
            bit <<= 1

    def compile_flash_struct_addr(
        self, symbol: VarSymbol, index: ast.Expr, scope: Scope, line: int
    ) -> None:
        assert symbol.flash_label is not None
        index_type = self.compile_expr(index, scope)
        if not (is_integer(index_type) and index_type.ram_size in (1, 2)):
            raise NiblickTypeError(
                f"{location(self.filename, line)}: flash array index must be "
                "a nibble or char"
            )
        self._emit_scaled_index(symbol.type.ram_size, index_type)
        self.emit_flashptr(symbol.flash_label)
        self._add_flash_offset_regs()

    def compile_flash_addr(self, symbol: VarSymbol, index: ast.Expr, scope: Scope, line: int) -> None:
        assert symbol.flash_label is not None
        index_type = self.compile_expr(index, scope)
        if not (is_integer(index_type) and index_type.ram_size in (1, 2)):
            raise NiblickTypeError(
                f"{location(self.filename, line)}: flash array index must be a nibble or char"
            )

        scale = symbol.type.flash_size
        if scale < 1 or scale & (scale - 1):
            raise NiblickCompileError(
                f"{location(self.filename, line)}: unsupported flash element size {scale}"
            )
        self.emit("MOV R4, R1")
        if index_type.ram_size == 2:
            self.emit("MOV R5, R2")
        else:
            self.emit("MOV R5, 0")
        shifts = scale.bit_length() - 1
        # A char index can reach 255, so a multi-nibble element needs a
        # ninth (and tenth) offset bit.  A nibble index tops out at 240
        # nibbles even for a 16-nibble element, so it fits in R5:R4.
        use_high = shifts > 0 and index_type.ram_size == 2
        if use_high:
            self.emit("MOV R6, 0")
        for _ in range(shifts):
            self.emit("ADD R4, R4")
            self.emit("ADC R5, R5")
            if use_high:
                self.emit("ADC R6, R6")

        self.emit_flashptr(symbol.flash_label)
        self.emit("ADD R1, R4")
        self.emit("MOV R0, 0")
        self.emit("ADC R2, R0")
        self.emit("ADC R3, R0")
        self.emit("ADD R2, R5")
        self.emit("MOV R0, 0")
        self.emit("ADC R3, R0")
        if use_high:
            self.emit("ADD R3, R6")

    # ------------------------------------------------------------------
    # Calls
    # ------------------------------------------------------------------

    def _record_call_temp(self) -> None:
        if self.current_function is None:
            return
        live = self.temp.top - self.temp.start
        name = self.current_function.name
        self.call_temp_live[name] = max(self.call_temp_live.get(name, 0), live)

    def run_probe(self) -> dict[str, int]:
        """Compile once to measure how many temporaries are live at calls."""
        self._is_probe = True
        self.prepare_globals()
        self.prepare_functions()
        for fn in self.program.functions:
            self.compile_function(self.functions[fn.name])
            self.temp_peak[fn.name] = self.temp.peak
        return self.call_temp_live

    def _can_tail_call(self, caller: FunctionSymbol, callee: FunctionSymbol) -> bool:
        if isinstance(caller.decl.return_type, StructType):
            return False
        return not any(isinstance(p.type, StructType) for p in callee.params)

    def compile_call(self, expr: ast.Call, scope: Scope) -> Type:
        if expr.name in BUILTINS:
            return self.compile_builtin(expr, scope)
        fn = self.functions.get(expr.name)
        if fn is None:
            raise NiblickCompileError(
                f"{location(self.filename, expr.line)}: unknown function {expr.name!r}"
            )
        if len(expr.args) != len(fn.params):
            raise NiblickTypeError(
                f"{location(self.filename, expr.line)}: {expr.name} expects {len(fn.params)} "
                f"arguments, got {len(expr.args)}"
            )

        self._record_call_temp()
        for arg, param in zip(expr.args, fn.params):
            if isinstance(param.type, StructType):
                assert param.address is not None
                self.compile_struct_expr(arg, scope)
                self._emit_struct_copy_regs_to_static(
                    param.type.ram_size, param.address
                )
                continue
            typ = self.compile_expr(arg, scope, param.type)
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
            raise NiblickCompileError(
                f"{location(self.filename, expr.line)}: cannot tail-call unknown function {expr.name!r}"
            )
        if len(expr.args) != len(fn.params):
            raise NiblickTypeError(
                f"{location(self.filename, expr.line)}: {expr.name} expects {len(fn.params)} "
                f"arguments, got {len(expr.args)}"
            )

        self._record_call_temp()
        mark = self.temp.mark()
        temp_addresses: list[int] = []
        for arg, param in zip(expr.args, fn.params):
            typ = self.compile_expr(arg, scope, param.type)
            self.coerce(typ, param.type, arg.line)
            if self._is_qword(param.type):
                address = self.alloc_qword_slot()
            else:
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
        if is_integer(typ) and typ.ram_size == 1 and 0 <= value <= 15:
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
        if name == "__nib_f16_bits":
            self.require_args(expr, 1)
            typ = self.compile_expr(expr.args[0], scope)
            if typ is not F16:
                raise NiblickTypeError(
                    f"{location(self.filename, expr.line)}: expected f16"
                )
            return U16
        if name == "__nib_f16_from_bits":
            self.require_args(expr, 1)
            typ = self.compile_expr(expr.args[0], scope)
            self.coerce(typ, U16, expr.line)
            return F16
        if name == "__nib_f32_bits":
            self.require_args(expr, 1)
            typ = self.compile_expr(expr.args[0], scope)
            if typ is not F32:
                raise NiblickTypeError(
                    f"{location(self.filename, expr.line)}: expected f32"
                )
            return U32
        if name == "__nib_f32_from_bits":
            self.require_args(expr, 1)
            typ = self.compile_expr(expr.args[0], scope)
            self.coerce(typ, U32, expr.line)
            return F32
        if name == "print":
            raise NiblickCompileError(
                f"{location(self.filename, expr.line)}: print() must be used as a "
                "statement with a literal format string"
            )
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
            self.coerce(typ, U8, expr.line)
            self.emit("GOSUB __nib_uart_putc")
            return VOID

        if name == "uart_getc":
            self.require_args(expr, 0)
            self.emit("GOSUB __nib_uart_getc")
            return U8

        if name == "flash_read_char":
            self.require_args(expr, 1)
            typ = self.compile_expr(expr.args[0], scope)
            self.coerce(typ, FLASHPTR, expr.line)
            self.emit("GOSUB __nib_flash_read_char")
            return U8

        if name == "flash_read_nibble":
            self.require_args(expr, 1)
            typ = self.compile_expr(expr.args[0], scope)
            self.coerce(typ, FLASHPTR, expr.line)
            self.emit("GOSUB __nib_flash_read_nibble")
            return U4

        if name == "flash_next":
            self.require_args(expr, 1)
            arg = expr.args[0]
            if not isinstance(arg, ast.AddressOf) or not isinstance(arg.operand, ast.Var):
                raise NiblickTypeError(
                    f"{location(self.filename, expr.line)}: flash_next expects &variable"
                )
            symbol = self.lookup(arg.operand.name, scope, expr.line)
            if symbol.type is not FLASHPTR or symbol.address is None or symbol.is_const:
                raise NiblickTypeError(
                    f"{location(self.filename, expr.line)}: flash_next expects a mutable flashptr variable"
                )
            addr = symbol.address
            self.emit(f"MOV R0, [{addr}]")
            self.emit("MOV R6, R0")
            self.emit(f"MOV R0, [{addr + 1}]")
            self.emit("MOV R7, R0")
            self.emit(f"MOV R0, [{addr + 2}]")
            self.emit("MOV R8, R0")
            self.emit("GOSUB __nib_flash_read_char_ptr")
            # Store the advanced pointer without disturbing R1/R2.
            self.emit("MOV R0, R6")
            self.emit(f"MOV [{addr}], R0")
            self.emit("MOV R0, R7")
            self.emit(f"MOV [{addr + 1}], R0")
            self.emit("MOV R0, R8")
            self.emit(f"MOV [{addr + 2}], R0")
            return U8

        if name in ("gpio_set", "gpio_clear", "gpio_toggle", "gpio_test"):
            self.require_args(expr, 1)
            mask = self._constant_nibble(expr.args[0], scope)
            if mask is not None:
                if name == "gpio_test":
                    if mask == 0:
                        self.emit("MOV R1, 0")
                        return U4
                    if mask.bit_count() == 1:
                        bit = mask.bit_length() - 1
                        self.emit(f"BIT R3, {bit}")
                        self.emit("MOV R1, 0")
                        self.emit("SKIP Z, 1")
                        self.emit("INC R1")
                        return U4
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
            self.coerce(typ, U4, expr.line)
            self.emit(f"GOSUB __nib_{name}")
            return U4 if name == "gpio_test" else VOID

        if name == "w5500_spi_tx_fast":
            self.require_args(expr, 1)
            typ = self.compile_expr(expr.args[0], scope)
            self.coerce(typ, U8, expr.line)
            self.emit("GOSUB __nib_w5500_spi_tx_fast")
            return VOID

        if name == "w5500_spi_xfer_fast":
            self.require_args(expr, 1)
            typ = self.compile_expr(expr.args[0], scope)
            self.coerce(typ, U8, expr.line)
            self.emit("GOSUB __nib_w5500_spi_xfer_fast")
            return U8

        if name == "delay":
            self.require_args(expr, 1)
            typ = self.compile_expr(expr.args[0], scope)
            self.coerce(typ, U4, expr.line)
            self.emit("GOSUB __nib_delay")
            return VOID

        if name == "out":
            self.require_args(expr, 1)
            typ = self.compile_expr(expr.args[0], scope)
            self.coerce(typ, U4, expr.line)
            self.emit("MOV R0, R1")
            self.emit("MOV [0x0A], R0")
            return VOID

        if name == "in":
            self.require_args(expr, 0)
            self.emit("MOV R0, [0x0B]")
            self.emit("MOV R1, R0")
            return U4

        if name == "peek":
            self.require_args(expr, 1)
            constant_addr = self._constant_address(expr.args[0], scope)
            if constant_addr is not None:
                self.emit(f"MOV R0, [0x{constant_addr:02X}]")
                self.emit("MOV R1, R0")
                return U4
            typ = self.compile_expr(expr.args[0], scope)
            self.coerce(typ, U8, expr.line)
            self.emit("MOV R4, R2")
            self.emit("MOV R5, R1")
            self.emit("MOV R0, [R4:R5]")
            self.emit("MOV R1, R0")
            return U4

        if name == "poke":
            self.require_args(expr, 2)
            constant_addr = self._constant_address(expr.args[0], scope)
            if constant_addr is not None:
                typ = self.compile_expr(expr.args[1], scope)
                self.coerce(typ, U4, expr.line)
                self.emit("MOV R0, R1")
                self.emit(f"MOV [0x{constant_addr:02X}], R0")
                return VOID
            mark = self.temp.mark()
            temp_addr = self.temp.alloc(1, "poke value", self.filename, expr.line)
            typ = self.compile_expr(expr.args[1], scope)
            self.coerce(typ, U4, expr.line)
            self.store_temp(U4, temp_addr)
            typ = self.compile_expr(expr.args[0], scope)
            self.coerce(typ, U8, expr.line)
            self.emit("MOV R4, R2")
            self.emit("MOV R5, R1")
            self.load_temp(U4, temp_addr)
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
                return U8
            typ = self.compile_expr(expr.args[0], scope)
            self.coerce(typ, U8, expr.line)
            self.emit("MOV R4, R2")
            self.emit("MOV R5, R1")
            self.emit("MOV R0, [R4:R5]")
            self.emit("MOV R1, R0")
            self.emit("INC R5")
            self.emit("SKIP NC, 1")
            self.emit("INC R4")
            self.emit("MOV R0, [R4:R5]")
            self.emit("MOV R2, R0")
            return U8

        if name == "poke8":
            self.require_args(expr, 2)
            constant_addr = self._constant_address(expr.args[0], scope)
            if constant_addr is not None:
                high_addr = (constant_addr + 1) & 0xFF
                typ = self.compile_expr(expr.args[1], scope)
                self.coerce(typ, U8, expr.line)
                self.emit("MOV R0, R1")
                self.emit(f"MOV [0x{constant_addr:02X}], R0")
                self.emit("MOV R0, R2")
                self.emit(f"MOV [0x{high_addr:02X}], R0")
                return VOID
            mark = self.temp.mark()
            temp_addr = self.temp.alloc(2, "poke8 value", self.filename, expr.line)
            typ = self.compile_expr(expr.args[1], scope)
            self.coerce(typ, U8, expr.line)
            self.store_temp(U8, temp_addr)

            typ = self.compile_expr(expr.args[0], scope)
            self.coerce(typ, U8, expr.line)
            self.emit("MOV R4, R2")
            self.emit("MOV R5, R1")
            self.load_temp(U8, temp_addr)
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
            self.coerce(typ, U8, expr.line)
            if name == "high_nibble":
                self.emit("MOV R1, R2")
            return U4

        raise NiblickCompileError(
            f"{location(self.filename, expr.line)}: unsupported builtin {name!r}"
        )

    def require_args(self, expr: ast.Call, count: int) -> None:
        if len(expr.args) != count:
            raise NiblickTypeError(
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
            raise NiblickCompileError(
                f"{location(self.filename, line)}: unknown identifier {name!r}"
            )
        return symbol

    def lvalue_type(self, target: ast.Expr, scope: Scope) -> Type:
        if isinstance(target, ast.Var):
            symbol = self.lookup(target.name, scope, target.line)
            if symbol.array_len is not None:
                raise NiblickTypeError(
                    f"{location(self.filename, target.line)}: cannot assign to array {target.name!r}"
                )
            if symbol.is_const:
                raise NiblickTypeError(
                    f"{location(self.filename, target.line)}: cannot assign to const {target.name!r}"
                )
            return symbol.type
        if isinstance(target, ast.Index):
            if isinstance(target.base, ast.Member):
                field = self.member_info(target.base, scope)
                if field.array_len <= 0:
                    raise NiblickTypeError(
                        f"{location(self.filename, target.line)}: field "
                        f"{target.base.field!r} is not an array"
                    )
                if self._is_const_struct_write(target.base, scope):
                    raise NiblickTypeError(
                        f"{location(self.filename, target.line)}: cannot assign "
                        "to a const struct field"
                    )
                return field.type
            if not isinstance(target.base, ast.Var):
                raise NiblickTypeError(
                    f"{location(self.filename, target.line)}: only named arrays can be indexed"
                )
            symbol = self.lookup(target.base.name, scope, target.line)
            if symbol.array_len is None:
                raise NiblickTypeError(
                    f"{location(self.filename, target.line)}: {symbol.name!r} is not an array"
                )
            if symbol.is_const:
                raise NiblickTypeError(
                    f"{location(self.filename, target.line)}: cannot write to const array {symbol.name!r}"
                )
            return symbol.type
        if isinstance(target, ast.Member):
            field = self.member_info(target, scope)
            if field.array_len > 0:
                raise NiblickTypeError(
                    f"{location(self.filename, target.line)}: cannot assign to "
                    f"array field {target.field!r}"
                )
            if self._is_const_struct_write(target, scope):
                raise NiblickTypeError(
                    f"{location(self.filename, target.line)}: cannot assign to "
                    "a const struct field"
                )
            return field.type
        raise NiblickTypeError(
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
                raise NiblickCompileError(
                    f"{location(self.filename, line)}: index {index} out of bounds "
                    f"for {symbol.name}[{symbol.array_len}]"
                )
            address = symbol.address + index * typ.ram_size
        else:
            return False

        if address is None:
            return False
        value &= (1 << (4 * typ.ram_size)) - 1
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
            if isinstance(target.base, ast.Member):
                field = self.member_info(target.base, scope)
                typ = field.type
            else:
                assert isinstance(target.base, ast.Var)
                symbol = self.lookup(target.base.name, scope, target.line)
                typ = symbol.type
            mark = self.temp.mark()
            temp_addr = self.temp.alloc(
                typ.ram_size, "assignment", self.filename, line
            )
            self.store_temp(typ, temp_addr)
            self.store_index_from_temp(target, scope, typ, temp_addr, line)
            self.temp.reset(mark)
            return
        raise NiblickTypeError(
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
        if isinstance(target.base, ast.Member):
            field = self.member_info(target.base, scope)
            if isinstance(target.index, ast.Number):
                index = int(target.index.value)
                if index < 0 or index >= field.array_len:
                    raise NiblickCompileError(
                        f"{location(self.filename, target.line)}: index {index} "
                        f"out of bounds for field {target.base.field}"
                        f"[{field.array_len}]"
                    )
                self.compile_member_addr(target.base, scope)
                offset = index * typ.ram_size
                if offset:
                    self.emit(f"MOV R0, {offset & 0xF}")
                    self.emit("ADD R5, R0")
                    self.emit("SKIP NC, 1")
                    self.emit("INC R4")
                    if offset >> 4:
                        self.emit(f"MOV R0, {(offset >> 4) & 0xF}")
                        self.emit("ADD R4, R0")
            else:
                mark = self.temp.mark()
                base_slot = self.temp.alloc(
                    2, "array base", self.filename, target.line
                )
                self.compile_member_addr(target.base, scope)
                self.emit("MOV R0, R4")
                self.emit(f"MOV [{base_slot}], R0")
                self.emit("MOV R0, R5")
                self.emit(f"MOV [{base_slot + 1}], R0")
                index_type = self.compile_expr(target.index, scope)
                if not (
                    is_integer(index_type) and index_type.ram_size in (1, 2)
                ):
                    raise NiblickTypeError(
                        f"{location(self.filename, target.line)}: array index "
                        "must be a nibble or char"
                    )
                self._emit_scaled_index(typ.ram_size, index_type)
                self.emit(f"MOV R0, [{base_slot + 1}]")
                self.emit("ADD R5, R0")
                self.emit("SKIP NC, 1")
                self.emit("INC R4")
                self.emit(f"MOV R0, [{base_slot}]")
                self.emit("ADD R4, R0")
                self.temp.reset(mark)
            self._store_temp_indirect(typ, temp_addr, line)
            return

        assert isinstance(target.base, ast.Var)
        symbol = self.lookup(target.base.name, scope, target.line)
        if isinstance(target.index, ast.Number) and symbol.address is not None:
            address = symbol.address + int(target.index.value) * typ.ram_size
            if is_integer(typ) and typ.ram_size == 16:
                self._emit_qword_copy(temp_addr, address)
                return
            self.load_temp(typ, temp_addr)
            for index in range(typ.ram_size):
                self.emit(f"MOV R0, R{index + 1}")
                self.emit(f"MOV [{address + index}], R0")
            return

        self.compile_ram_addr(symbol, target.index, scope, target.line)
        self._store_temp_indirect(typ, temp_addr, line)

    def _store_temp_indirect(self, typ: Type, temp_addr: int, line: int) -> None:
        if is_integer(typ) and typ.ram_size == 16:
            self._emit_qword_store_indirect(temp_addr)
            return
        if is_integer(typ) and typ.ram_size == 8:
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
        if is_integer(typ) and typ.ram_size == 4:
            self.emit("MOV R6, R4")
            self.emit("MOV R7, R5")
        self.load_temp(typ, temp_addr)
        if typ is BOOL or (is_integer(typ) and typ.ram_size == 1):
            self.emit("MOV R0, R1")
            self.emit("MOV [R4:R5], R0")
            return
        if is_integer(typ) and typ.ram_size == 2:
            self.emit("MOV R0, R1")
            self.emit("MOV [R4:R5], R0")
            self.emit("INC R5")
            self.emit("SKIP NC, 1")
            self.emit("INC R4")
            self.emit("MOV R0, R2")
            self.emit("MOV [R4:R5], R0")
            return
        if is_integer(typ) and typ.ram_size in (4, 8):
            for index in range(typ.ram_size):
                self.emit(f"MOV R0, R{index + 1}")
                self.emit("MOV [R6:R7], R0")
                if index != typ.ram_size - 1:
                    self.emit("INC R7")
                    self.emit("SKIP NC, 1")
                    self.emit("INC R6")
            return
        raise NiblickTypeError(
            f"{location(self.filename, line)}: cannot store to {typ} array"
        )

    def load_symbol(self, symbol: VarSymbol, line: int) -> None:
        if symbol.const_value is not None:
            if symbol.type.is_float:
                self._emit_immediate(
                    symbol.const_value, _REGS[symbol.type.ram_size]
                )
            elif self._is_qword(symbol.type):
                self._emit_qword_immediate(
                    self._stored_value(symbol.const_value, symbol.type),
                    symbol.type,
                    self.ensure_qword_result(),
                )
            else:
                self._emit_immediate(symbol.const_value, _REGS[symbol.type.ram_size])
            return
        if symbol.address is None:
            raise NiblickCompileError(
                f"{location(self.filename, line)}: {symbol.name!r} has no RAM storage"
            )
        addr = symbol.address
        if symbol.type.ram_size == 1:
            self.emit(f"MOV R0, [{addr}]")
            self.emit("MOV R1, R0")
        elif symbol.type.ram_size == 2:
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
        elif symbol.type.ram_size == 4:
            for index in range(4):
                self.emit(f"MOV R0, [{addr + index}]")
                self.emit(f"MOV R{index + 1}, R0")
        elif symbol.type.ram_size == 8:
            for index in range(8):
                self.emit(f"MOV R0, [{addr + index}]")
                self.emit(f"MOV R{index + 1}, R0")
        elif symbol.type.ram_size == 16:
            self._emit_qword_copy(addr, self.ensure_qword_result())
        else:
            raise NiblickTypeError(
                f"{location(self.filename, line)}: cannot load {symbol.type} value"
            )

    def store_symbol(self, symbol: VarSymbol, line: int) -> None:
        if symbol.address is None:
            raise NiblickCompileError(
                f"{location(self.filename, line)}: {symbol.name!r} has no RAM storage"
            )
        if symbol.is_const:
            raise NiblickTypeError(
                f"{location(self.filename, line)}: cannot write to const {symbol.name!r}"
            )
        addr = symbol.address
        if symbol.type.ram_size == 1:
            self.emit("MOV R0, R1")
            self.emit(f"MOV [{addr}], R0")
        elif symbol.type.ram_size == 2:
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
        elif symbol.type.ram_size == 4:
            for index in range(4):
                self.emit(f"MOV R0, R{index + 1}")
                self.emit(f"MOV [{addr + index}], R0")
        elif symbol.type.ram_size == 8:
            for index in range(8):
                self.emit(f"MOV R0, R{index + 1}")
                self.emit(f"MOV [{addr + index}], R0")
        elif symbol.type.ram_size == 16:
            self._emit_qword_copy(self.ensure_qword_result(), addr)
        else:
            raise NiblickTypeError(
                f"{location(self.filename, line)}: cannot store {symbol.type} value"
            )

    def store_temp(self, typ: Type, address: int) -> None:
        if typ is BOOL or (is_integer(typ) and typ.ram_size == 1):
            self.emit("MOV R0, R1")
            self.emit(f"MOV [{address}], R0")
        elif is_integer(typ) and typ.ram_size == 2:
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
        elif is_integer(typ) and typ.ram_size == 4:
            for index in range(4):
                self.emit(f"MOV R0, R{index + 1}")
                self.emit(f"MOV [{address + index}], R0")
        elif is_integer(typ) and typ.ram_size == 8:
            for index in range(8):
                self.emit(f"MOV R0, R{index + 1}")
                self.emit(f"MOV [{address + index}], R0")
        elif is_integer(typ) and typ.ram_size == 16:
            self._emit_qword_copy(self.ensure_qword_result(), address)
        elif typ.is_float:
            for index in range(typ.ram_size):
                self.emit(f"MOV R0, R{index + 1}")
                self.emit(f"MOV [{address + index}], R0")
        else:
            raise NiblickCompileError(f"cannot spill {typ}")

    def load_temp(self, typ: Type, address: int) -> None:
        if typ is BOOL or (is_integer(typ) and typ.ram_size == 1):
            self.emit(f"MOV R0, [{address}]")
            self.emit("MOV R1, R0")
        elif is_integer(typ) and typ.ram_size == 2:
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
        elif is_integer(typ) and typ.ram_size == 4:
            for index in range(4):
                self.emit(f"MOV R0, [{address + index}]")
                self.emit(f"MOV R{index + 1}, R0")
        elif is_integer(typ) and typ.ram_size == 8:
            for index in range(8):
                self.emit(f"MOV R0, [{address + index}]")
                self.emit(f"MOV R{index + 1}, R0")
        elif is_integer(typ) and typ.ram_size == 16:
            self._emit_qword_copy(address, self.ensure_qword_result())
        elif typ.is_float:
            for index in range(typ.ram_size):
                self.emit(f"MOV R0, [{address + index}]")
                self.emit(f"MOV R{index + 1}, R0")
        else:
            raise NiblickCompileError(f"cannot reload {typ}")

    def coerce(self, source: Type, target: Type, line: int) -> None:
        if source is target:
            return
        if source.is_float or target.is_float:
            self._coerce_float(source, target, line)
            return
        if self._is_qword(source) or self._is_qword(target):
            self._coerce_qword(source, target, line)
            return
        if source is VOID:
            raise NiblickTypeError(
                f"{location(self.filename, line)}: expression has no value"
            )
        if source is BOOL:
            if target is BOOL:
                return
            if is_integer(target):
                for index in range(1, target.ram_size):
                    self.emit(f"MOV R{index + 1}, 0")
                return
        if target is BOOL:
            if is_integer(source):
                self._normalize_bool(source, line)
                return
        if is_integer(source) and is_integer(target):
            if source.ram_size < target.ram_size:
                if source.signed:
                    self._emit_sign_fill(source.ram_size, target.ram_size)
                else:
                    for index in range(source.ram_size, target.ram_size):
                        self.emit(f"MOV R{index + 1}, 0")
                return
            if source.ram_size == target.ram_size:
                # Bit-preserving conversion, including signed <-> unsigned.
                return
        raise NiblickTypeError(
            f"{location(self.filename, line)}: cannot convert {source} to {target}"
        )

    def _coerce_float(self, source: Type, target: Type, line: int) -> None:
        if source is target:
            return
        raise NiblickTypeError(
            f"{location(self.filename, line)}: cannot convert {source} to {target} "
            "without an explicit cast"
        )

    def _coerce_qword(self, source: Type, target: Type, line: int) -> None:
        if source is VOID:
            raise NiblickTypeError(
                f"{location(self.filename, line)}: expression has no value"
            )
        if self._is_qword(source) and self._is_qword(target):
            # The value is already in the 64-bit result buffer; signedness
            # changes are bit-preserving.
            return
        if self._is_qword(source) and target is BOOL:
            self._emit_qword_truth_to_r1(self.ensure_qword_result())
            self.emit("MOV R0, R1")
            self.emit("CP R0, 0")
            self.emit("MOV R1, 0")
            self.emit("SKIP Z, 1")
            self.emit("INC R1")
            return
        if self._is_qword(source):
            raise NiblickTypeError(
                f"{location(self.filename, line)}: cannot convert {source} to {target} "
                "without an explicit cast"
            )
        if self._is_qword(target):
            if source is BOOL or is_integer(source):
                self._emit_extend_to_qword(source, self.ensure_qword_result())
                return
        raise NiblickTypeError(
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
        materialising the value).  Signed and bool comparisons always use the
        general path so their semantics stay in one place.
        """

        op = expr.op
        left, right = expr.left, expr.right

        left_value = self._literal_value(left)
        right_value = self._literal_value(right)
        if left_value is not None and right_value is not None:
            return {
                "==": left_value == right_value,
                "!=": left_value != right_value,
                "<": left_value < right_value,
                "<=": left_value <= right_value,
                ">": left_value > right_value,
                ">=": left_value >= right_value,
            }[op]

        # Normalise ``constant OP expr`` to ``expr OP constant``.
        if left_value is not None and right_value is None:
            left, right = right, left
            op = _FLAG_SWAP[op]
            right_value = left_value

        if right_value is not None:
            typ = self.infer_type(left, scope)
            if not is_integer(typ) or typ.signed:
                return None
            literal_type = self._literal_type_for(right_value, typ)
            if literal_type is not typ or right_value < 0:
                return None
            if typ.ram_size == 1:
                return self._compare_nibble_imm(left, right_value, op, scope, expr.line)
            if typ.ram_size == 2:
                return self._compare_char_imm(left, right_value, op, scope, expr.line)
            if typ.ram_size == 4:
                return self._compare_word_imm(left, right_value, op, scope, expr.line)
            if typ.ram_size == 8:
                return self._compare_dword_imm(left, right_value, op, scope, expr.line)
            return None

        left_type = self.infer_type(left, scope)
        right_type = self.infer_type(right, scope)
        if not is_comparable(left_type) or not is_comparable(right_type):
            return None
        common = self._common_expr_type(left, right, scope)
        if not is_integer(common) or common.signed:
            return None
        if not self._is_leaf(right):
            return None
        if common.ram_size == 4:
            return self._compare_word_regs(left, right, op, scope, expr.line)
        if common.ram_size in (1, 2):
            return self._compare_regs(left, right, op, left_type, right_type, scope, expr.line)
        return None

    def _compare_nibble_imm(
        self, left: ast.Expr, constant: int, op: str, scope: Scope, line: int
    ):
        if constant > 15:
            # The result is independent of the operand, but the operand may
            # still have side effects (for example a function call).
            typ = self.compile_expr(left, scope)
            self.coerce(typ, U4, line)
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
            self.coerce(typ, U4, line)
            return op == "<="

        typ = self.compile_expr(left, scope)
        self.coerce(typ, U4, line)
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
                self.coerce(typ, U8, line)
                return op == ">="
            typ = self.compile_expr(left, scope)
            self.coerce(typ, U8, line)
            self.emit("OR R1, R2")
            return "Z" if op in ("==", "<=") else "NZ"

        if constant == 255 and op in ("==", "!="):
            typ = self.compile_expr(left, scope)
            self.coerce(typ, U8, line)
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
            self.coerce(typ, U8, line)
            self.emit("MOV R0, R2")
            self.emit("CP R0, 0")
            return "Z" if op == "<" else "NZ"

        if constant == 15 and op in (">", "<="):
            typ = self.compile_expr(left, scope)
            self.coerce(typ, U8, line)
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
        common: Type = U16,
    ) -> Type:
        mark = self.temp.mark()
        temp_addr = self.temp.alloc(common.ram_size, "comparison", self.filename, line)

        typ = self.compile_expr(left, scope, common)
        self.coerce(typ, common, line)
        if common.signed:
            self._flip_sign_bit(common, ("R1", "R2", "R3", "R4"))
        self.store_temp(common, temp_addr)

        typ = self.compile_expr(right, scope, common)
        self.coerce(typ, common, line)
        if common.signed:
            self._flip_sign_bit(common, ("R1", "R2", "R3", "R4"))
        self._move(("R1", "R2", "R3", "R4"), ("R5", "R6", "R7", "R8"))
        self.load_temp(common, temp_addr)

        flag = self._word_compare_flag(
            op, ("R1", "R2", "R3", "R4"), ("R5", "R6", "R7", "R8")
        )
        self.emit("MOV R1, 0")
        self.emit(f"SKIP {_FLAG_INVERSE[flag]}, 1")
        self.emit("INC R1")
        self.temp.reset(mark)
        return BOOL

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
        self.coerce(typ, U16, line)
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
        self.coerce(typ, U16, line)
        self._move(("R1", "R2", "R3", "R4"), ("R5", "R6", "R7", "R8"))
        typ = self.compile_expr(right, scope)
        self.coerce(typ, U16, line)
        return self._word_compare_flag(
            op, ("R5", "R6", "R7", "R8"), ("R1", "R2", "R3", "R4")
        )

    def _compare_dword_imm(
        self, left: ast.Expr, constant: int, op: str, scope: Scope, line: int
    ) -> str:
        typ = self.compile_expr(left, scope)
        self.coerce(typ, U32, line)
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
        common: Type = U32,
    ) -> Type:
        mark = self.temp.mark()
        left_addr = self.temp.alloc(8, "32-bit comparison", self.filename, line)
        right_addr = self.temp.alloc(8, "32-bit comparison", self.filename, line)
        typ = self.compile_expr(left, scope, common)
        self.coerce(typ, common, line)
        if common.signed:
            self._flip_sign_bit(common, ("R1", "R2", "R3", "R4", "R5", "R6", "R7", "R8"))
        self.store_temp(common, left_addr)
        typ = self.compile_expr(right, scope, common)
        self.coerce(typ, common, line)
        if common.signed:
            self._flip_sign_bit(common, ("R1", "R2", "R3", "R4", "R5", "R6", "R7", "R8"))
        self.store_temp(common, right_addr)
        self.load_temp(common, left_addr)
        flag = self._dword_compare_flag_memory(op, right_addr)
        self.emit("MOV R1, 0")
        self.emit(f"SKIP {_FLAG_INVERSE[flag]}, 1")
        self.emit("INC R1")
        self.temp.reset(mark)
        return BOOL

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
        common = U8 if U8 in (left_type, right_type) else U4
        typ = self.compile_expr(left, scope)
        self.coerce(typ, common, line)
        if common.ram_size == 1:
            self.emit("MOV R3, R1")
        else:
            self.emit("MOV R3, R1")
            self.emit("MOV R4, R2")

        typ = self.compile_expr(right, scope)
        self.coerce(typ, common, line)

        # left-right for <, >=, ==, !=; right-left for >, <= so that a single
        # C or NC test is enough.
        left_first = op in ("<", ">=", "==", "!=")
        if common.ram_size == 1:
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
        if typ is BOOL or (is_integer(typ) and typ.ram_size == 1):
            # OR R1,R1 leaves R1 unchanged but sets Z when it is zero.
            self.emit("OR R1, R1")
            self.emit("SKIP NZ, 2")
            self.emit(f"GOTO {label}")
            return
        if is_integer(typ) and typ.ram_size == 2:
            self.emit("OR R1, R2")
            self.emit("SKIP NZ, 2")
            self.emit(f"GOTO {label}")
            return
        if is_integer(typ) and typ.ram_size == 4:
            self.emit("OR R1, R2")
            self.emit("OR R1, R3")
            self.emit("OR R1, R4")
            self.emit("SKIP NZ, 2")
            self.emit(f"GOTO {label}")
            return
        if is_integer(typ) and typ.ram_size == 8:
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
        if is_integer(typ) and typ.ram_size == 16:
            self._emit_qword_truth_to_r1()
            self.emit("OR R1, R1")
            self.emit("SKIP NZ, 2")
            self.emit(f"GOTO {label}")
            return
        if typ is FLASHPTR:
            self.emit("OR R1, R2")
            self.emit("OR R1, R3")
            self.emit("SKIP NZ, 2")
            self.emit(f"GOTO {label}")
            return
        raise NiblickTypeError(f"cannot test value of type {typ}")

    def emit_branch_if_value_true(self, typ: Type, label: str) -> None:
        if typ is BOOL or (is_integer(typ) and typ.ram_size == 1):
            self.emit("OR R1, R1")
            self.emit("SKIP Z, 2")
            self.emit(f"GOTO {label}")
            return
        if is_integer(typ) and typ.ram_size == 2:
            self.emit("OR R1, R2")
            self.emit("SKIP Z, 2")
            self.emit(f"GOTO {label}")
            return
        if is_integer(typ) and typ.ram_size == 4:
            self.emit("OR R1, R2")
            self.emit("OR R1, R3")
            self.emit("OR R1, R4")
            self.emit("SKIP Z, 2")
            self.emit(f"GOTO {label}")
            return
        if is_integer(typ) and typ.ram_size == 8:
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
        if is_integer(typ) and typ.ram_size == 16:
            self._emit_qword_truth_to_r1()
            self.emit("OR R1, R1")
            self.emit("SKIP Z, 2")
            self.emit(f"GOTO {label}")
            return
        if typ is FLASHPTR:
            self.emit("OR R1, R2")
            self.emit("OR R1, R3")
            self.emit("SKIP Z, 2")
            self.emit(f"GOTO {label}")
            return
        raise NiblickTypeError(f"cannot test value of type {typ}")

    def emit_truth_value(self, typ: Type) -> None:
        if typ is BOOL or (is_integer(typ) and typ.ram_size == 1):
            return
        if is_integer(typ) and typ.ram_size == 2:
            self.emit("MOV R0, R1")
            self.emit("OR R0, R2")
            self.emit("MOV R1, R0")
            return
        if is_integer(typ) and typ.ram_size == 4:
            self.emit("MOV R0, R1")
            self.emit("OR R0, R2")
            self.emit("OR R0, R3")
            self.emit("OR R0, R4")
            self.emit("MOV R1, R0")
            return
        if is_integer(typ) and typ.ram_size == 8:
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
        if is_integer(typ) and typ.ram_size == 16:
            self._emit_qword_truth_to_r1()
            return
        if typ is FLASHPTR:
            self.emit("MOV R0, R1")
            self.emit("OR R0, R2")
            self.emit("OR R0, R3")
            self.emit("MOV R1, R0")
            return
        raise NiblickTypeError(f"cannot convert {typ} to a truth value")

    # ------------------------------------------------------------------
    # Type inference
    # ------------------------------------------------------------------

    def infer_type(self, expr: ast.Expr, scope: Scope) -> Type:
        if isinstance(expr, ast.Number):
            return self._natural_literal_type(int(expr.value))
        if isinstance(expr, ast.FloatLiteral):
            return F32
        if isinstance(expr, ast.StringLiteral):
            return FLASHPTR
        if isinstance(expr, ast.Var):
            symbol = self.lookup(expr.name, scope, expr.line)
            if symbol.array_len is not None:
                if symbol.flash_label is not None:
                    return FLASHPTR
                raise NiblickTypeError(
                    f"{location(self.filename, expr.line)}: array {expr.name!r} used without an index"
                )
            return symbol.type
        if isinstance(expr, ast.Index):
            if isinstance(expr.base, ast.Member):
                field = self.member_info(expr.base, scope)
                if field.array_len <= 0:
                    raise NiblickTypeError(
                        f"{location(self.filename, expr.line)}: field "
                        f"{expr.base.field!r} is not an array"
                    )
                return field.type
            if not isinstance(expr.base, ast.Var):
                raise NiblickTypeError(
                    f"{location(self.filename, expr.line)}: only named arrays can be indexed"
                )
            symbol = self.lookup(expr.base.name, scope, expr.line)
            if symbol.array_len is None:
                raise NiblickTypeError(
                    f"{location(self.filename, expr.line)}: {symbol.name!r} is not an array"
                )
            return symbol.type
        if isinstance(expr, ast.Member):
            field = self.member_info(expr, scope)
            if field.array_len > 0:
                raise NiblickTypeError(
                    f"{location(self.filename, expr.line)}: field {expr.field!r} "
                    "is an array and requires an index"
                )
            return field.type
        if isinstance(expr, ast.Unary):
            if expr.op == "&":
                return U8
            if expr.op == "!":
                return BOOL
            if expr.op == "-" and isinstance(expr.operand, ast.FloatLiteral):
                return F32
            if expr.op == "-":
                literal = self._literal_value(expr)
                if literal is not None:
                    return smallest_type_for(literal, signed_hint=True)
                operand = self._arith_type(self.infer_type(expr.operand, scope))
                if operand.is_float:
                    return operand
                if not is_integer(operand):
                    raise NiblickTypeError(
                        f"{location(self.filename, expr.line)}: unary - requires an integer operand"
                    )
                return type_for(operand.ram_size, True)
            return self._arith_type(self.infer_type(expr.operand, scope))
        if isinstance(expr, ast.Binary):
            if expr.op in ("==", "!=", "<", "<=", ">", ">=", "&&", "||"):
                return BOOL
            left_type = self.infer_type(expr.left, scope)
            right_type = self.infer_type(expr.right, scope)
            if left_type.is_float or right_type.is_float:
                if left_type.is_float and right_type.is_float:
                    if left_type is not right_type:
                        raise NiblickTypeError(
                            f"{location(self.filename, expr.line)}: mixed float types "
                            f"{left_type} and {right_type}; use an explicit cast"
                        )
                    return left_type
                return left_type if left_type.is_float else right_type
            if expr.op in ("<<", ">>"):
                return left_type
            if expr.op == "*":
                return promoted_mul_type(
                    self._common_expr_type(expr.left, expr.right, scope)
                )
            return self._common_expr_type(expr.left, expr.right, scope)
        if isinstance(expr, ast.Conditional):
            then_type = self.infer_type(expr.then_expr, scope)
            else_type = self.infer_type(expr.else_expr, scope)
            if then_type is VOID or else_type is VOID:
                raise NiblickTypeError(
                    f"{location(self.filename, expr.line)}: ternary branches "
                    "must produce a value"
                )
            if isinstance(then_type, StructType) or isinstance(else_type, StructType):
                raise NiblickTypeError(
                    f"{location(self.filename, expr.line)}: ternary branches "
                    "cannot be struct values"
                )
            if then_type.is_float or else_type.is_float:
                if (
                    then_type.is_float
                    and else_type.is_float
                    and then_type is not else_type
                ):
                    raise NiblickTypeError(
                        f"{location(self.filename, expr.line)}: mixed float types "
                        f"{then_type} and {else_type}; use an explicit cast"
                    )
                return then_type if then_type.is_float else else_type
            if then_type is FLASHPTR or else_type is FLASHPTR:
                if then_type is FLASHPTR and else_type is FLASHPTR:
                    return FLASHPTR
                raise NiblickTypeError(
                    f"{location(self.filename, expr.line)}: ternary branches "
                    "must both be flash pointers"
                )
            return self._common_expr_type(expr.then_expr, expr.else_expr, scope)
        if isinstance(expr, ast.IncDec):
            raise NiblickCompileError(
                f"{location(self.filename, expr.line)}: increment/decrement "
                "must be a statement"
            )
        if isinstance(expr, ast.Call):
            if expr.name in BUILTINS:
                return BUILTINS[expr.name]
            fn = self.functions.get(expr.name)
            if fn is None:
                raise NiblickCompileError(
                    f"{location(self.filename, expr.line)}: unknown function {expr.name!r}"
                )
            return fn.decl.return_type
        if isinstance(expr, ast.AddressOf):
            return U8
        if isinstance(expr, (ast.ToType, ast.Cast)):
            return expr.type
        raise NiblickCompileError(
            f"{location(self.filename, expr.line)}: cannot infer type of {type(expr).__name__}"
        )

    # ------------------------------------------------------------------
    # Flash data
    # ------------------------------------------------------------------

    def new_flash_string(self, value: str) -> str:
        label = self.new_flash_label()
        self.flash.append(
            FlashItem(label, U8, [ord(ch) & 0xFF for ch in value] + [0x00], string_value=value)
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
        self.emit("__nib_flash_data:")
        for item in self.flash:
            self.emit(f"{item.label}:")
            if isinstance(item.type, StructType):
                for value in item.values:
                    self.emit(f"NIBBLE 0x{value & 0xF:X}")
            elif item.type.ram_size == 1:
                for value in item.values:
                    self.emit(f"NIBBLE 0x{value & 0xF:X}")
            elif item.type.ram_size == 2:
                for value in item.values:
                    self.emit(f"BYTE 0x{value & 0xFF:02X}")
            elif item.type.ram_size == 4:
                for value in item.values:
                    for index in range(4):
                        self.emit(f"NIBBLE 0x{(value >> (4 * index)) & 0xF:X}")
            elif item.type.ram_size == 8:
                for value in item.values:
                    for index in range(8):
                        self.emit(f"NIBBLE 0x{(value >> (4 * index)) & 0xF:X}")
            else:
                raise NiblickCompileError(f"unsupported flash data type {item.type}")
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
                        raise NiblickCompileError(
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
            raise NiblickCompileError(
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
        labels.add("__nib_flash_data")
        sizes = word_sizes(self.asm_text, labels, total_words)

        function_words = {
            name: sizes.get(fn.label, 0) for name, fn in self.functions.items()
        }
        runtime_words = {
            label: sizes.get(label, 0) for label in sorted(self.linked_runtime)
        }
        flash_words = sizes.get("__nib_flash_data", 0)
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
            self.lines.append(f"; @niblick-src {file}:{source_line}")
            self.last_emitted_source = self.current_source
        self.lines.append(line)
