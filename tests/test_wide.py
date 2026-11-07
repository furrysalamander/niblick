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
    return sum(emu.ram[symbol.address + i] << (4 * i) for i in range(4))


def test_word_literals_arithmetic_and_shifts(tmp_path: Path) -> None:
    compiler, emu = build(
        tmp_path,
        """
        word a;
        word b;
        word sum;
        word diff;
        word band;
        word bor;
        word bxor;
        word shl;
        word shr;
        word neg;
        word inv;
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
        word w;
        char c;
        nibble n;
        word back;
        char from_word;
        nibble low;
        fn main() {
            w = 0x1234;
            from_word = (char)w;
            low = (nibble)w;
            c = 0xAB;
            back = (word)c;
            n = 9;
            w = (word)n << 4;
        }
        """,
    )
    assert val(compiler, emu, "from_word") == 0x34
    assert val(compiler, emu, "low") == 4
    assert val(compiler, emu, "back") == 0x00AB
    # w was overwritten by (word)n << 4 at the end.
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
        word medium;
        word e;
        word f;
        word large;
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
        word cp;
        char cq;
        char cr;
        word e;
        word f;
        word wp;
        word wq;
        word wr;
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
        word w;
        char c2;
        char c0;
        char cd2;
        char cm4;
        word w2;
        word w0;
        word wd16;
        word wm8;
        word folded;
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
        const word table[] = { 0x1234, 0xABCD, 0x0001 };
        word arr[4];
        char i;
        word from_flash;
        word from_array;
        word from_function;
        fn word add_word(word a, word b) {
            word r;
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
        word a;
        word b;
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
