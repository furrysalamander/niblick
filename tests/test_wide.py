"""Tests for 16-bit words, casts, and multiply/divide/modulo."""

from __future__ import annotations

from pathlib import Path

from badgec.assembler import assemble_file
from badgec.compiler import Compiler
from badgec.emulator import Emulator
from badgec.parser import parse


def build(tmp_path: Path, source: str, name: str = "wide"):
    path = tmp_path / f"{name}.badge"
    path.write_text(source)
    compiler = Compiler(parse(source, str(path)), str(path))
    asm_path = tmp_path / f"{name}.asm"
    asm_path.write_text(compiler.compile())
    hex_path = tmp_path / f"{name}.hex"
    assemble_file(asm_path, hex_path)
    emu = Emulator()
    emu.load_hex(hex_path)
    emu.run(500000)
    return compiler, emu


def val(compiler: Compiler, emu: Emulator, name: str) -> int:
    symbol = compiler.globals[name]
    assert symbol.address is not None
    if symbol.type.name == "nibble":
        return emu.ram[symbol.address]
    if symbol.type.name == "char":
        return emu.ram[symbol.address] | (emu.ram[symbol.address + 1] << 4)
    width = 8 if symbol.type.name == "uint32_t" else 4
    return sum(emu.ram[symbol.address + i] << (4 * i) for i in range(width))


def test_word_literals_arithmetic_and_shifts(tmp_path: Path) -> None:
    compiler, emu = build(
        tmp_path,
        """
        uint16_t a;
        uint16_t b;
        uint16_t sum;
        uint16_t diff;
        uint16_t band;
        uint16_t bor;
        uint16_t bxor;
        uint16_t shl;
        uint16_t shr;
        uint16_t neg;
        uint16_t inv;
        nibble lt;
        nibble eq;
        nibble gt;
        fn main() {
            a = 0x1234;
            b = 0x00FF;
            sum = a + b;
            diff = a - b;
            band = a & b;
            bor = a | b;
            bxor = a ^ b;
            shl = a << 4;
            shr = a >> 4;
            neg = -a;
            inv = ~a;
            lt = (a < b);
            eq = (a == 0x1234);
            gt = (a > b);
        }
        """,
    )
    assert val(compiler, emu, "sum") == 0x1333
    assert val(compiler, emu, "diff") == 0x1135
    assert val(compiler, emu, "band") == 0x0034
    assert val(compiler, emu, "bor") == 0x12FF
    assert val(compiler, emu, "bxor") == 0x12CB
    assert val(compiler, emu, "shl") == 0x2340
    assert val(compiler, emu, "shr") == 0x0123
    assert val(compiler, emu, "neg") == 0xEDCC
    assert val(compiler, emu, "inv") == 0xEDCB
    assert val(compiler, emu, "lt") == 0
    assert val(compiler, emu, "eq") == 1
    assert val(compiler, emu, "gt") == 1


def test_casts_widen_and_narrow(tmp_path: Path) -> None:
    compiler, emu = build(
        tmp_path,
        """
        uint16_t w;
        char c;
        nibble n;
        uint16_t back;
        char from_word;
        nibble low;
        fn main() {
            w = 0x1234;
            from_word = (char)w;
            low = (nibble)w;
            c = 0xAB;
            back = (uint16_t)c;
            n = 9;
            w = (uint16_t)n << 4;
        }
        """,
    )
    assert val(compiler, emu, "from_word") == 0x34
    assert val(compiler, emu, "low") == 4
    assert val(compiler, emu, "back") == 0x00AB
    # w was overwritten by (uint16_t)n << 4 at the end.
    assert val(compiler, emu, "w") == 0x0090


def test_widening_multiplication(tmp_path: Path) -> None:
    compiler, emu = build(
        tmp_path,
        """
        nibble a;
        nibble b;
        char small;
        char c;
        char d;
        uint16_t medium;
        uint16_t e;
        uint16_t f;
        uint16_t large;
        fn main() {
            a = 15;
            b = 15;
            small = a * b;
            c = 200;
            d = 200;
            medium = c * d;
            e = 300;
            f = 400;
            large = e * f;
        }
        """,
    )
    assert val(compiler, emu, "small") == 225
    assert val(compiler, emu, "medium") == 40000
    assert val(compiler, emu, "large") == (300 * 400) & 0xFFFF


def test_mul_div_mod_across_widths(tmp_path: Path) -> None:
    compiler, emu = build(
        tmp_path,
        """
        nibble a;
        nibble b;
        char np;
        nibble nq;
        nibble nr;
        char c;
        char d;
        uint16_t cp;
        char cq;
        char cr;
        uint16_t e;
        uint16_t f;
        uint16_t wp;
        uint16_t wq;
        uint16_t wr;
        char zeroq;
        char zeror;
        fn main() {
            a = 7; b = 9;
            np = a * b;
            nq = a / b;
            nr = a % b;
            c = 200; d = 7;
            cp = c * d;
            cq = c / d;
            cr = c % d;
            e = 65535; f = 255;
            wp = e * f;
            wq = e / f;
            wr = e % f;
            zeroq = c / 0;
            zeror = c % 0;
        }
        """,
    )
    assert val(compiler, emu, "np") == 63
    assert val(compiler, emu, "nq") == 0
    assert val(compiler, emu, "nr") == 7
    assert val(compiler, emu, "cp") == 1400
    assert val(compiler, emu, "cq") == 28
    assert val(compiler, emu, "cr") == 4
    assert val(compiler, emu, "wp") == (65535 * 255) & 0xFFFF
    assert val(compiler, emu, "wq") == 257
    assert val(compiler, emu, "wr") == 0
    assert val(compiler, emu, "zeroq") == 0
    assert val(compiler, emu, "zeror") == 0


def test_constant_strength_reduction(tmp_path: Path) -> None:
    compiler, emu = build(
        tmp_path,
        """
        char c;
        uint16_t w;
        char c2;
        char c0;
        char cd2;
        char cm4;
        uint16_t w2;
        uint16_t w0;
        uint16_t wd16;
        uint16_t wm8;
        uint16_t folded;
        fn main() {
            c = 201;
            w = 50000;
            c2 = (char)(c * 2);
            c0 = (char)(c * 0);
            cd2 = c / 2;
            cm4 = c % 4;
            w2 = w * 2;
            w0 = w * 0;
            wd16 = w / 16;
            wm8 = w % 8;
            folded = 1000 * 37;
        }
        """,
    )
    assert val(compiler, emu, "c2") == (201 * 2) & 0xFF
    assert val(compiler, emu, "c0") == 0
    assert val(compiler, emu, "cd2") == 100
    assert val(compiler, emu, "cm4") == 1
    assert val(compiler, emu, "w2") == (50000 * 2) & 0xFFFF
    assert val(compiler, emu, "w0") == 0
    assert val(compiler, emu, "wd16") == 50000 // 16
    assert val(compiler, emu, "wm8") == 50000 % 8
    assert val(compiler, emu, "folded") == 37000


def test_word_arrays_params_returns_and_flash(tmp_path: Path) -> None:
    compiler, emu = build(
        tmp_path,
        """
        const uint16_t table[] = { 0x1234, 0xABCD, 0x0001 };
        uint16_t arr[4];
        char i;
        uint16_t from_flash;
        uint16_t from_array;
        uint16_t from_function;
        fn uint16_t add_word(uint16_t a, uint16_t b) {
            uint16_t r;
            r = a + b;
            return r;
        }
        fn main() {
            i = 2;
            arr[0] = 0x1111;
            arr[i] = 0x2222;
            from_array = arr[2];
            from_flash = table[1];
            from_function = add_word(from_array, 1);
        }
        """,
    )
    assert val(compiler, emu, "from_array") == 0x2222
    assert val(compiler, emu, "from_flash") == 0xABCD
    assert val(compiler, emu, "from_function") == 0x2223


def test_word_comparison_edges(tmp_path: Path) -> None:
    compiler, emu = build(
        tmp_path,
        """
        uint16_t a;
        uint16_t b;
        nibble eq;
        nibble ne;
        nibble lt;
        nibble le;
        nibble gt;
        nibble ge;
        nibble c16;
        nibble c255;
        fn main() {
            a = 0x00FF;
            b = 0x0100;
            eq = (a == b);
            ne = (a != b);
            lt = (a < b);
            le = (a <= b);
            gt = (a > b);
            ge = (a >= b);
            c16 = (a < 16);
            c255 = (a > 255);
        }
        """,
    )
    assert val(compiler, emu, "eq") == 0
    assert val(compiler, emu, "ne") == 1
    assert val(compiler, emu, "lt") == 1
    assert val(compiler, emu, "le") == 1
    assert val(compiler, emu, "gt") == 0
    assert val(compiler, emu, "ge") == 0
    assert val(compiler, emu, "c16") == 0
    assert val(compiler, emu, "c255") == 0


def test_dword_arithmetic_shifts_and_compare(tmp_path: Path) -> None:
    compiler, emu = build(
        tmp_path,
        """
        uint32_t a;
        uint32_t b;
        uint32_t sum;
        uint32_t diff;
        uint32_t band;
        uint32_t bor;
        uint32_t bxor;
        uint32_t shl;
        uint32_t shr;
        uint32_t neg;
        uint32_t inv;
        nibble lt;
        nibble eq;
        nibble gt;
        fn main() {
            a = 0x12345678;
            b = 0x0000FFFF;
            sum = a + b;
            diff = b - a;
            band = a & b;
            bor = a | b;
            bxor = a ^ b;
            shl = a << 4;
            shr = a >> 4;
            neg = -a;
            inv = ~a;
            lt = (a < b);
            eq = (a == 0x12345678);
            gt = (a > b);
        }
        """,
    )
    assert val(compiler, emu, "sum") == 0x12355677
    assert val(compiler, emu, "diff") == 0xEDCCA987
    assert val(compiler, emu, "band") == 0x00005678
    assert val(compiler, emu, "bor") == 0x1234FFFF
    assert val(compiler, emu, "bxor") == 0x1234A987
    assert val(compiler, emu, "shl") == 0x23456780
    assert val(compiler, emu, "shr") == 0x01234567
    assert val(compiler, emu, "neg") == 0xEDCBA988
    assert val(compiler, emu, "inv") == 0xEDCBA987
    assert val(compiler, emu, "lt") == 0
    assert val(compiler, emu, "eq") == 1
    assert val(compiler, emu, "gt") == 1


def test_dword_arrays_flash_params_and_casts(tmp_path: Path) -> None:
    compiler, emu = build(
        tmp_path,
        """
        const uint32_t table[] = { 0x12345678, 0xDEADBEEF, 0x00000001 };
        uint32_t arr[4];
        char i;
        uint32_t from_array;
        uint32_t from_flash;
        uint32_t from_function;
        char low;
        uint16_t mid;
        nibble high;
        fn uint32_t add_word(uint32_t x, uint32_t y) {
            uint32_t r;
            r = x + y;
            return r;
        }
        fn main() {
            i = 2;
            arr[0] = 0x11111111;
            arr[i] = 0x22222222;
            from_array = arr[2];
            from_flash = table[1];
            from_function = add_word(from_array, 1);
            low = (char)from_flash;
            mid = (uint16_t)from_flash;
            high = (nibble)(from_flash >> 24);
        }
        """,
    )
    assert val(compiler, emu, "from_array") == 0x22222222
    assert val(compiler, emu, "from_flash") == 0xDEADBEEF
    assert val(compiler, emu, "from_function") == 0x22222223
    assert val(compiler, emu, "low") == 0xEF
    assert val(compiler, emu, "mid") == 0xBEEF
    assert val(compiler, emu, "high") == 0xE


def test_dword_mul_div_mod_edges(tmp_path: Path) -> None:
    compiler, emu = build(
        tmp_path,
        """
        uint32_t a;
        uint32_t b;
        uint32_t product;
        uint32_t quotient;
        uint32_t remainder;
        uint32_t c;
        uint32_t d;
        uint32_t product2;
        uint32_t quotient2;
        uint32_t remainder2;
        fn main() {
            a = 100000;
            b = 37;
            product = a * b;
            quotient = a / b;
            remainder = a % b;
            c = 0xFFFFFFFF;
            d = 0x0000FFFF;
            product2 = c * d;
            quotient2 = c / d;
            remainder2 = c % d;
        }
        """,
    )
    assert val(compiler, emu, "product") == (100000 * 37) & 0xFFFFFFFF
    assert val(compiler, emu, "quotient") == 100000 // 37
    assert val(compiler, emu, "remainder") == 100000 % 37
    assert val(compiler, emu, "product2") == (0xFFFFFFFF * 0xFFFF) & 0xFFFFFFFF
    assert val(compiler, emu, "quotient2") == 0xFFFFFFFF // 0xFFFF
    assert val(compiler, emu, "remainder2") == 0xFFFFFFFF % 0xFFFF


def test_dword_divide_by_zero(tmp_path: Path) -> None:
    compiler, emu = build(
        tmp_path,
        """
        uint32_t a;
        uint32_t q;
        uint32_t r;
        fn main() {
            a = 123456;
            q = a / 0;
            r = a % 0;
        }
        """,
    )
    assert val(compiler, emu, "q") == 0
    assert val(compiler, emu, "r") == 0


def test_variable_shift_counts(tmp_path: Path) -> None:
    compiler, emu = build(
        tmp_path,
        """
        uint32_t x;
        nibble n;
        char c;
        uint16_t w;
        nibble v;
        char b;
        uint32_t y1;
        uint32_t y2;
        uint16_t w1;
        uint16_t w2;
        char b1;
        char b2;
        fn main() {
            x = 0x12345678;
            n = 4;
            c = 31;
            w = 0xABCD;
            v = 3;
            b = 9;
            y1 = x << n;
            y2 = x >> c;
            w1 = w << v;
            w2 = w >> v;
            b1 = (char)(w << b);
            b2 = (char)(w >> b);
        }
        """,
    )
    assert val(compiler, emu, "y1") == (0x12345678 << 4) & 0xFFFFFFFF
    assert val(compiler, emu, "y2") == 0x12345678 >> 31
    assert val(compiler, emu, "w1") == (0xABCD << 3) & 0xFFFF
    assert val(compiler, emu, "w2") == 0xABCD >> 3
    assert val(compiler, emu, "b1") == (0xABCD << 9) & 0xFF
    assert val(compiler, emu, "b2") == (0xABCD >> 9) & 0xFF
