"""Tests for the Niblick type system: aliases, signed types, bool, and target typing."""

from __future__ import annotations

from pathlib import Path

import pytest

from niblick.assembler import assemble_file
from niblick.compiler import Compiler
from niblick.emulator import Emulator
from niblick.errors import NiblickError
from niblick.loader import load_source
from niblick.parser import parse


def build(tmp_path: Path, source: str):
    filename = str(tmp_path / "types.nbl")
    compiler = Compiler(load_source(source, filename=filename), filename)
    asm_path = tmp_path / "types.asm"
    asm_path.write_text(compiler.compile())
    hex_path = tmp_path / "types.hex"
    assemble_file(asm_path, hex_path)
    emu = Emulator()
    emu.load_hex(hex_path)
    emu.run(2_000_000)
    return compiler, emu


def value(compiler: Compiler, emu: Emulator, name: str) -> int:
    symbol = compiler.globals[name]
    assert symbol.address is not None
    width = symbol.type.ram_size
    bits = sum(emu.ram[symbol.address + index] << (4 * index) for index in range(width))
    if symbol.type.signed:
        sign = 1 << (4 * width - 1)
        if bits & sign:
            bits -= 1 << (4 * width)
    return bits


def test_cstdint_and_c_alias_spellings(tmp_path: Path) -> None:
    compiler, emu = build(
        tmp_path,
        """
        uint8_t u8v;
        int8_t i8v;
        uint16_t u16v;
        int16_t i16v;
        uint32_t u32v;
        int32_t i32v;
        short shortv;
        int intv;
        long longv;
        u4 nibv;
        i4 snibv;
        fn main() {
            u8v = 200;
            i8v = -5;
            u16v = 40000;
            i16v = -20000;
            u32v = 3000000000;
            i32v = -100000;
            shortv = -7;
            intv = -8;
            longv = -9;
            nibv = 15;
            snibv = -8;
        }
        """,
    )
    assert value(compiler, emu, "u8v") == 200
    assert value(compiler, emu, "i8v") == -5
    assert value(compiler, emu, "u16v") == 40000
    assert value(compiler, emu, "i16v") == -20000
    assert value(compiler, emu, "u32v") == 3000000000
    assert value(compiler, emu, "i32v") == -100000
    assert value(compiler, emu, "shortv") == -7
    assert value(compiler, emu, "intv") == -8
    assert value(compiler, emu, "longv") == -9
    assert value(compiler, emu, "nibv") == 15
    assert value(compiler, emu, "snibv") == -8


def test_word_and_dword_type_spellings_are_gone(tmp_path: Path) -> None:
    for source in ("word x;", "dword x;"):
        with pytest.raises((NiblickError, ValueError)):
            compiler = Compiler(parse(source, "gone.nbl"), "gone.nbl")
            compiler.compile()


def test_target_typing_width_floor(tmp_path: Path) -> None:
    compiler, emu = build(
        tmp_path,
        """
        uint8_t a;
        uint8_t b;
        uint8_t narrow;
        uint16_t wide;
        int8_t x;
        int8_t y;
        int8_t p;
        int16_t q;
        uint16_t shifted;
        int16_t negated;
        fn main() {
            a = 200;
            b = 200;
            narrow = a + b;
            wide = a + b;
            x = 100;
            y = 100;
            p = x + y;
            q = x + y;
            shifted = 1 << 8;
            negated = -a;
        }
        """,
    )
    assert value(compiler, emu, "narrow") == 144
    assert value(compiler, emu, "wide") == 400
    assert value(compiler, emu, "p") == -56
    assert value(compiler, emu, "q") == 200
    assert value(compiler, emu, "shifted") == 0x100
    assert value(compiler, emu, "negated") == -200


def test_signed_comparisons_and_literals(tmp_path: Path) -> None:
    compiler, emu = build(
        tmp_path,
        """
        int8_t x;
        bool lt_zero;
        bool lt_200;
        int16_t wide_compare;
        fn main() {
            x = -1;
            lt_zero = x < 0;
            lt_200 = x < 200;
            wide_compare = x + 100;
        }
        """,
    )
    assert value(compiler, emu, "lt_zero") == 1
    assert value(compiler, emu, "lt_200") == 1
    assert value(compiler, emu, "wide_compare") == 99


def test_signed_arithmetic_division_and_shifts(tmp_path: Path) -> None:
    compiler, emu = build(
        tmp_path,
        """
        int8_t a8;
        int8_t b8;
        int8_t q8;
        int8_t r8;
        int16_t a16;
        int16_t b16;
        int16_t q16;
        int16_t r16;
        int16_t sar16;
        int32_t a32;
        int32_t b32;
        int32_t q32;
        int32_t r32;
        int32_t mul32;
        fn main() {
            a8 = -7;
            b8 = 2;
            q8 = a8 / b8;
            r8 = a8 % b8;
            a16 = -7;
            b16 = 2;
            q16 = a16 / b16;
            r16 = a16 % b16;
            sar16 = a16 >> 1;
            a32 = -100000;
            b32 = 7;
            q32 = a32 / b32;
            r32 = a32 % b32;
            mul32 = a32 * b32;
        }
        """,
    )
    assert value(compiler, emu, "q8") == -3
    assert value(compiler, emu, "r8") == -1
    assert value(compiler, emu, "q16") == -3
    assert value(compiler, emu, "r16") == -1
    assert value(compiler, emu, "sar16") == -4
    assert value(compiler, emu, "q32") == -14285
    assert value(compiler, emu, "r32") == -5
    assert value(compiler, emu, "mul32") == -700000


def test_bool_normalization_and_logical_ops(tmp_path: Path) -> None:
    compiler, emu = build(
        tmp_path,
        """
        bool from_two;
        bool from_zero;
        bool not_zero;
        bool not_two;
        bool and_result;
        bool or_result;
        uint8_t sum;
        bool comparison;
        fn main() {
            from_two = 2;
            from_zero = 0;
            not_zero = !0;
            not_two = !2;
            and_result = 3 && 4;
            or_result = 0 || 0;
            sum = true + true;
            comparison = 5 < 7;
        }
        """,
    )
    assert value(compiler, emu, "from_two") == 1
    assert value(compiler, emu, "from_zero") == 0
    assert value(compiler, emu, "not_zero") == 1
    assert value(compiler, emu, "not_two") == 0
    assert value(compiler, emu, "and_result") == 1
    assert value(compiler, emu, "or_result") == 0
    assert value(compiler, emu, "sum") == 2
    assert value(compiler, emu, "comparison") == 1


def test_target_typing_in_calls_returns_and_lvalues(tmp_path: Path) -> None:
    compiler, emu = build(
        tmp_path,
        """
        struct Pair {
            uint8_t narrow;
            uint16_t wide;
        };
        Pair pair;
        uint8_t narrow_array[2];
        uint16_t wide_array[2];

        fn int8_t add8(int8_t a, int8_t b) {
            return a + b;
        }
        fn uint16_t add8_wide(int8_t a, int8_t b) {
            return a + b;
        }
        fn uint16_t add16(uint16_t a, uint16_t b) {
            return a + b;
        }

        int8_t x;
        int8_t y;
        int8_t narrow_return;
        uint16_t wide_return;
        uint16_t via_argument;
        fn main() {
            x = 100;
            y = 100;
            narrow_return = add8(x, y);
            wide_return = add8_wide(x, y);
            via_argument = add16(x, y);
            pair.narrow = x + y;
            pair.wide = x + y;
            narrow_array[0] = 200 + 200;
            wide_array[0] = 200 + 200;
        }
        """,
    )
    assert value(compiler, emu, "narrow_return") == -56
    assert value(compiler, emu, "wide_return") == 200
    assert value(compiler, emu, "via_argument") == 200
    pair_base = compiler.globals["pair"].address
    assert (emu.ram[pair_base] | (emu.ram[pair_base + 1] << 4)) == 200
    assert sum(emu.ram[pair_base + 2 + i] << (4 * i) for i in range(4)) == 200
    narrow_base = compiler.globals["narrow_array"].address
    assert (emu.ram[narrow_base] | (emu.ram[narrow_base + 1] << 4)) == 144
    wide_base = compiler.globals["wide_array"].address
    assert sum(emu.ram[wide_base + i] << (4 * i) for i in range(4)) == 400


def test_bool_storage_in_structs_arrays_and_calls(tmp_path: Path) -> None:
    compiler, emu = build(
        tmp_path,
        """
        struct Flags {
            bool a;
            bool b;
        };
        Flags flags;
        bool bits[2];
        bool result;
        const bool ALWAYS = true;
        const bool NEVER = false;
        bool from_const_true;
        bool from_const_false;

        fn bool invert(bool value) {
            return !value;
        }
        fn bool choose(bool value) {
            return value;
        }

        fn main() {
            flags.a = 2;
            flags.b = 0;
            bits[0] = 3;
            bits[1] = 0;
            result = invert(flags.a);
            result = choose(bits[0]);
            from_const_true = ALWAYS;
            from_const_false = NEVER;
        }
        """,
    )
    base = compiler.globals["flags"].address
    assert emu.ram[base] == 1
    assert emu.ram[base + 1] == 0
    bits = compiler.globals["bits"].address
    assert emu.ram[bits] == 1
    assert emu.ram[bits + 1] == 0
    assert value(compiler, emu, "result") == 1
    assert value(compiler, emu, "from_const_true") == 1
    assert value(compiler, emu, "from_const_false") == 0


def test_qword_arithmetic_shifts_and_comparisons(tmp_path: Path) -> None:
    compiler, emu = build(
        tmp_path,
        """
        uint64_t a;
        uint64_t b;
        uint64_t sum;
        uint64_t diff;
        uint64_t band;
        uint64_t shl;
        uint64_t shr;
        bool lt;
        bool eq;
        fn main() {
            a = 0x123456789ABCDEF0;
            b = 0x0F0F0F0F0F0F0F0F;
            sum = a + b;
            diff = a - b;
            band = a & b;
            shl = a << 4;
            shr = a >> 4;
            lt = (int64_t)a < (int64_t)b;
            eq = a == b;
        }
        """,
    )
    assert value(compiler, emu, "sum") == 0x21436587A9CBEDFF
    assert value(compiler, emu, "diff") == 0x032547698BADCFE1
    assert value(compiler, emu, "band") == 0x020406080A0C0E00
    assert value(compiler, emu, "shl") == 0x23456789ABCDEF00
    assert value(compiler, emu, "shr") == 0x0123456789ABCDEF
    assert value(compiler, emu, "lt") == 0
    assert value(compiler, emu, "eq") == 0


def test_qword_multiply_and_unsigned_divide(tmp_path: Path) -> None:
    compiler, emu = build(
        tmp_path,
        """
        uint64_t a;
        uint64_t b;
        uint64_t r;
        fn main() {
            a = 0x123456789;
            b = 0x12345;
            r = a * b;
        }
        """,
    )
    assert value(compiler, emu, "r") == 0x123456789 * 0x12345

    compiler, emu = build(
        tmp_path,
        """
        uint64_t a;
        uint64_t b;
        uint64_t q;
        fn main() {
            a = 0x123456789ABCDEF0;
            b = 0x12345;
            q = a / b;
        }
        """,
    )
    assert value(compiler, emu, "q") == 0x123456789ABCDEF0 // 0x12345


def test_qword_signed_divide_and_mod(tmp_path: Path) -> None:
    compiler, emu = build(
        tmp_path,
        """
        int64_t a;
        int64_t q;
        fn main() {
            a = -1000000000000;
            q = a / 7;
        }
        """,
    )
    assert value(compiler, emu, "q") == -142857142857

    compiler, emu = build(
        tmp_path,
        """
        int64_t a;
        int64_t r;
        fn main() {
            a = -1000000000000;
            r = a % 7;
        }
        """,
    )
    assert value(compiler, emu, "r") == -1


def test_qword_casts_and_function_roundtrip(tmp_path: Path) -> None:
    compiler, emu = build(
        tmp_path,
        """
        uint64_t x;
        uint64_t r;
        fn uint64_t addq(uint64_t a, uint64_t b) {
            uint64_t t;
            t = a + b;
            return t;
        }
        fn main() {
            x = 0x123456789ABCDEF0;
            r = addq(x, 0x11111111);
        }
        """,
    )
    assert value(compiler, emu, "r") == 0x12345678ABCDF001

    compiler, emu = build(
        tmp_path,
        """
        uint64_t wide;
        uint32_t low;
        int64_t negative;
        uint32_t bits;
        fn main() {
            wide = 0x123456789ABCDEF0;
            low = (uint32_t)wide;
            negative = -1;
            bits = (uint32_t)negative;
        }
        """,
    )
    assert value(compiler, emu, "low") == 0x9ABCDEF0
    assert value(compiler, emu, "bits") == 0xFFFFFFFF


def test_qword_arrays_and_struct_fields(tmp_path: Path) -> None:
    compiler, emu = build(
        tmp_path,
        """
        struct S { uint64_t v; };
        S s;
        uint64_t arr[2];
        fn main() {
            arr[0] = 0x123456789ABCDEF0;
            arr[1] = arr[0] + 1;
            s.v = arr[1] + 1;
        }
        """,
    )
    array = compiler.globals["arr"].address
    second = sum(emu.ram[array + 16 + i] << (4 * i) for i in range(16))
    assert second == 0x123456789ABCDEF1
    struct_base = compiler.globals["s"].address
    assert sum(emu.ram[struct_base + i] << (4 * i) for i in range(16)) == 0x123456789ABCDEF2
