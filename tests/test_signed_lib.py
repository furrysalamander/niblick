"""Tests for the raw-bit signed helpers and Q4.4 fixed-point module."""

from __future__ import annotations

from pathlib import Path

from badgec.assembler import assemble_file
from badgec.compiler import Compiler
from badgec.emulator import Emulator
from badgec.loader import load_source


def compile_source(
    tmp_path: Path, source: str, name: str = "signedlib"
) -> tuple[Compiler, Emulator]:
    filename = tmp_path / f"{name}.badge"
    program = load_source(source, filename=str(filename))
    compiler = Compiler(program, str(filename))
    asm_path = tmp_path / f"{name}.asm"
    asm_path.write_text(compiler.compile())
    hex_path = tmp_path / f"{name}.hex"
    assemble_file(asm_path, hex_path)

    emu = Emulator()
    emu.load_hex(hex_path)
    done = compiler.globals["done"].address
    assert done is not None
    steps = 0
    while steps < 5_000_000 and emu.ram[done] == 0:
        emu.run(50_000)
        steps += 50_000
    assert emu.ram[done] != 0, f"program did not finish after {steps} steps"
    return compiler, emu


def elem(compiler: Compiler, emu: Emulator, name: str, index: int = 0) -> int:
    symbol = compiler.globals[name]
    assert symbol.address is not None
    base = symbol.address + index * symbol.type.ram_size
    return sum(
        emu.ram[base + offset] << (4 * offset)
        for offset in range(symbol.type.ram_size)
    )


def test_signed_4bit_helpers(tmp_path: Path) -> None:
    compiler, emu = compile_source(
        tmp_path,
        """
        import "lib/signed.badge";

        nibble r[32];
        char q[6];
        char done;

        fn main() {
            r[0] = s_lt4(15, 0);
            r[1] = s_le4(15, 0);
            r[2] = s_gt4(15, 0);
            r[3] = s_ge4(15, 0);
            r[4] = s_lt4(0, 15);
            r[5] = s_le4(0, 15);
            r[6] = s_gt4(0, 15);
            r[7] = s_ge4(0, 15);

            r[8] = s_min4(15, 0);
            r[9] = s_max4(15, 0);
            r[10] = s_clamp4(15, 0, 7);
            r[11] = s_clamp4(8, 15, 7);

            r[12] = s_neg4(15);
            r[13] = s_abs4(8);
            r[14] = s_is_neg4(15);
            r[15] = s_is_neg4(7);
            q[0] = s_ext4(15);
            q[1] = s_ext4(7);

            r[16] = s_sar4(15, 1);
            r[17] = s_sar4(8, 1);
            r[18] = s_sar4(4, 1);

            q[2] = s_mul4(15, 15);
            q[3] = s_mul4(15, 2);
            q[4] = s_mul4(8, 2);
            r[19] = s_mul4_nib(15, 15);
            r[20] = s_mul4_nib(15, 2);
            r[21] = s_mul4_nib(8, 2);

            r[22] = s_div4(15, 2);
            r[23] = s_mod4(15, 2);
            r[24] = s_div4(14, 2);
            r[25] = s_div4(8, 15);
            r[26] = s_mod4(8, 15);
            r[27] = s_div4(15, 0);

            done = 1;
        }
        """,
        "signed4",
    )

    assert [elem(compiler, emu, "r", i) for i in range(8)] == [
        1, 1, 0, 0, 0, 0, 1, 1,
    ]
    assert elem(compiler, emu, "r", 8) == 15
    assert elem(compiler, emu, "r", 9) == 0
    assert elem(compiler, emu, "r", 10) == 0
    assert elem(compiler, emu, "r", 11) == 15
    assert elem(compiler, emu, "r", 12) == 1
    assert elem(compiler, emu, "r", 13) == 8
    assert elem(compiler, emu, "r", 14) == 1
    assert elem(compiler, emu, "r", 15) == 0
    assert [elem(compiler, emu, "q", i) for i in range(5)] == [
        255, 7, 1, 254, 240,
    ]
    assert [elem(compiler, emu, "r", i) for i in range(16, 19)] == [15, 12, 2]
    assert [elem(compiler, emu, "r", i) for i in range(19, 22)] == [1, 14, 0]
    assert [elem(compiler, emu, "r", i) for i in range(22, 28)] == [
        0, 15, 15, 8, 0, 0,
    ]


def test_signed_8bit_helpers(tmp_path: Path) -> None:
    compiler, emu = compile_source(
        tmp_path,
        """
        import "lib/signed.badge";

        nibble r[8];
        char q[24];
        word w[2];
        char done;

        fn main() {
            r[0] = s_lt8(255, 0);
            r[1] = s_le8(255, 0);
            r[2] = s_gt8(255, 0);
            r[3] = s_ge8(255, 0);
            r[4] = s_lt8(0, 255);
            r[5] = s_le8(0, 255);
            r[6] = s_gt8(0, 255);
            r[7] = s_ge8(0, 255);

            q[19] = s_min8(255, 0);
            q[20] = s_max8(255, 0);
            q[21] = s_clamp8(255, 0, 7);
            q[22] = s_clamp8(128, 255, 7);

            q[0] = s_neg8(255);
            q[1] = s_abs8(128);
            q[2] = s_is_neg8(128);
            q[3] = s_is_neg8(127);
            w[0] = s_ext8(255);
            w[1] = s_ext8(127);

            q[4] = s_mul8(255, 255);
            q[5] = s_mul8(254, 2);
            q[6] = s_mul8(128, 128);

            q[7] = s_div8(255, 2);
            q[8] = s_div8(254, 2);
            q[9] = s_div8(252, 254);
            q[10] = s_div8(128, 255);
            q[11] = s_div8(1, 0);

            q[12] = s_mod8(255, 2);
            q[13] = s_mod8(254, 2);
            q[14] = s_mod8(253, 2);
            q[15] = s_mod8(254, 255);

            q[16] = s_sar8(255, 2);
            q[17] = s_sar8(128, 3);
            q[18] = s_sar8(64, 2);

            done = 1;
        }
        """,
        "signed8",
    )

    assert [elem(compiler, emu, "r", i) for i in range(8)] == [
        1, 1, 0, 0, 0, 0, 1, 1,
    ]
    assert [elem(compiler, emu, "q", i) for i in range(20)] == [
        1, 128, 1, 0,
        1, 252, 0,
        0, 255, 2, 128, 0,
        255, 0, 255, 0,
        255, 240, 16,
        255,
    ]
    assert elem(compiler, emu, "q", 20) == 0
    assert elem(compiler, emu, "q", 21) == 0
    assert elem(compiler, emu, "q", 22) == 255
    assert elem(compiler, emu, "w", 0) == 0xFFFF
    assert elem(compiler, emu, "w", 1) == 127


def test_signed_16bit_compare_and_clamp(tmp_path: Path) -> None:
    compiler, emu = compile_source(
        tmp_path,
        """
        import "lib/signed.badge";

        nibble r[8];
        word w[16];
        char done;

        fn main() {
            r[0] = s_lt16(0xFFFF, 0);
            r[1] = s_le16(0xFFFF, 0);
            r[2] = s_gt16(0xFFFF, 0);
            r[3] = s_ge16(0xFFFF, 0);
            r[4] = s_lt16(0, 0xFFFF);
            r[5] = s_le16(0, 0xFFFF);
            r[6] = s_gt16(0, 0xFFFF);
            r[7] = s_ge16(0, 0xFFFF);

            w[0] = s_min16(0xFFFF, 0);
            w[1] = s_max16(0xFFFF, 0);
            w[2] = s_clamp16(0xFFFF, 0, 7);
            w[3] = s_clamp16(0x8000, 0xFFFF, 7);

            done = 1;
        }
        """,
        "signed16cmp",
    )

    assert [elem(compiler, emu, "r", i) for i in range(8)] == [
        1, 1, 0, 0, 0, 0, 1, 1,
    ]
    assert elem(compiler, emu, "w", 0) == 0xFFFF
    assert elem(compiler, emu, "w", 1) == 0
    assert elem(compiler, emu, "w", 2) == 0
    assert elem(compiler, emu, "w", 3) == 0xFFFF


def test_signed_16bit_math(tmp_path: Path) -> None:
    compiler, emu = compile_source(
        tmp_path,
        """
        import "lib/signed.badge";

        nibble r[4];
        word w[16];
        dword d[2];
        char done;

        fn main() {
            w[0] = s_neg16(0xFFFF);
            w[1] = s_abs16(0x8000);
            r[0] = s_is_neg16(0x8000);
            r[1] = s_is_neg16(0x7FFF);
            d[0] = s_ext16(0xFFFF);
            d[1] = s_ext16(0x7FFF);

            w[2] = s_sar16(0xFFFF, 4);
            w[3] = s_sar16(0x8000, 4);
            w[4] = s_sar16(0x4000, 2);

            w[5] = s_mul16(0xFFFF, 0xFFFF);
            w[6] = s_mul16(0xFFFE, 2);
            w[7] = s_mul16(0x8000, 2);

            w[8] = s_div16(0xFFFF, 2);
            w[9] = s_div16(0xFFFE, 2);
            w[10] = s_div16(0xFFFC, 0xFFFE);
            w[11] = s_div16(0x8000, 0xFFFF);
            w[12] = s_div16(1, 0);

            w[13] = s_mod16(0xFFFD, 2);
            w[14] = s_mod16(0xFFFE, 2);
            w[15] = s_mod16(0xFFFC, 0xFFFE);

            done = 1;
        }
        """,
        "signed16math",
    )

    assert elem(compiler, emu, "w", 0) == 1
    assert elem(compiler, emu, "w", 1) == 0x8000
    assert elem(compiler, emu, "r", 0) == 1
    assert elem(compiler, emu, "r", 1) == 0
    assert elem(compiler, emu, "d", 0) == 0xFFFFFFFF
    assert elem(compiler, emu, "d", 1) == 0x7FFF
    assert elem(compiler, emu, "w", 2) == 0xFFFF
    assert elem(compiler, emu, "w", 3) == 0xF800
    assert elem(compiler, emu, "w", 4) == 0x1000
    assert elem(compiler, emu, "w", 5) == 1
    assert elem(compiler, emu, "w", 6) == 0xFFFC
    assert elem(compiler, emu, "w", 7) == 0
    assert elem(compiler, emu, "w", 8) == 0
    assert elem(compiler, emu, "w", 9) == 0xFFFF
    assert elem(compiler, emu, "w", 10) == 2
    assert elem(compiler, emu, "w", 11) == 0x8000
    assert elem(compiler, emu, "w", 12) == 0
    assert elem(compiler, emu, "w", 13) == 0xFFFF
    assert elem(compiler, emu, "w", 14) == 0
    assert elem(compiler, emu, "w", 15) == 0


def test_q4_4_fixed_point(tmp_path: Path) -> None:
    compiler, emu = compile_source(
        tmp_path,
        """
        import "lib/fixed.badge";

        char q[16];
        nibble r[4];
        char done;

        fn main() {
            q[0] = q4_4_add(0x18, 0x08);
            q[1] = q4_4_sub(0x08, 0x18);
            q[2] = q4_4_neg(0x18);
            q[3] = q4_4_mul(0x10, 0x10);
            q[4] = q4_4_mul(0x18, 0x08);
            q[5] = q4_4_mul(0xF8, 0x08);
            q[6] = q4_4_mul(0xE0, 0x20);
            q[7] = q4_4_div(0x10, 0x20);
            q[8] = q4_4_div(0xF0, 0x20);
            q[9] = q4_4_div(0x10, 0);
            q[10] = q4_4_from_int(2);
            q[11] = q4_4_from_int(15);
            r[0] = q4_4_to_int(0x20);
            r[1] = q4_4_to_int(0xF8);
            r[2] = q4_4_to_int(0xF0);
            q[12] = q4_4_min(0xF8, 0x08);
            q[13] = q4_4_max(0xF8, 0x08);
            q[14] = q4_4_clamp(0xE0, 0xF0, 0x10);

            done = 1;
        }
        """,
        "q44",
    )

    assert [elem(compiler, emu, "q", i) for i in range(15)] == [
        0x20, 0xF0, 0xE8,
        0x10, 0x0C, 0xFC, 0xC0,
        0x08, 0xF8, 0x00,
        0x20, 0xF0,
        0xF8, 0x08, 0xF0,
    ]
    assert elem(compiler, emu, "r", 0) == 2
    assert elem(compiler, emu, "r", 1) == 0
    assert elem(compiler, emu, "r", 2) == 15


def test_signed_decimal_printing(tmp_path: Path) -> None:
    _, emu = compile_source(
        tmp_path,
        """
        import "lib/uart.badge";

        char done;

        fn main() {
            uart_route(1);
            uart_init(3);
            uart_print_dec8_signed(255);
            uart_putc(' ');
            uart_print_dec8_signed(128);
            uart_putc(' ');
            uart_print_dec16_signed(0xFFFE);
            uart_putc(' ');
            uart_print_dec16_signed(0x8000);
            uart_putc(' ');
            uart_print_dec16_signed(7);
            uart_nl();
            done = 1;
        }
        """,
        "signedprint",
    )
    assert bytes(emu.uart_tx) == b"-1 -128 -2 -32768 7\n"
