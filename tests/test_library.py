"""End-to-end tests for the BadgeC library modules in ``lib/``."""

from __future__ import annotations

from pathlib import Path

from badgec.assembler import assemble_file
from badgec.compiler import Compiler
from badgec.emulator import Emulator
from badgec.loader import load_source


def compile_source(tmp_path: Path, source: str, name: str = "libtest", rx: list[int] | None = None):
    filename = tmp_path / f"{name}.badge"
    program = load_source(source, filename=str(filename))
    compiler = Compiler(program, str(filename))
    asm = compiler.compile()
    asm_path = tmp_path / f"{name}.asm"
    asm_path.write_text(asm)
    hex_path = tmp_path / f"{name}.hex"
    assemble_file(asm_path, hex_path)

    emu = Emulator()
    emu.load_hex(hex_path)
    if rx is not None:
        emu.uart_rx = list(rx)
    emu.run(500000)
    return compiler, emu


def value(compiler: Compiler, emu: Emulator, name: str) -> int:
    base = compiler.globals[name].address
    assert base is not None
    if compiler.globals[name].type.name == "nibble":
        return emu.ram[base]
    return emu.ram[base] | (emu.ram[base + 1] << 4)


def test_uart_formatting(tmp_path: Path) -> None:
    _, emu = compile_source(
        tmp_path,
        """
        import "lib/uart.badge";
        fn main() {
            uart_route(1);
            uart_init(3);
            uart_print_hex8(171);
            uart_putc(' ');
            uart_print_dec8(234);
            uart_putc(' ');
            uart_print_bin8(165);
            uart_nl();
        }
        """,
    )
    assert bytes(emu.uart_tx) == b"AB 234 10100101\n"


def test_uart_16bit_formatting(tmp_path: Path) -> None:
    _, emu = compile_source(
        tmp_path,
        """
        import "lib/uart.badge";
        fn main() {
            uart_route(1);
            uart_init(3);
            uart_print_hex16(0x9088);
            uart_putc(' ');
            uart_print_dec16(37000);
            uart_nl();
        }
        """,
    )
    assert bytes(emu.uart_tx) == b"9088 37000\n"


def test_string_module(tmp_path: Path) -> None:
    compiler, emu = compile_source(
        tmp_path,
        """
        import "lib/string.badge";
        import "lib/uart.badge";
        char a[24];
        char b[12];
        char len;
        nibble eq;
        char found;
        char base;
        fn main() {
            uart_route(1);
            uart_init(3);
            str_copy_flash(&a, "hello");
            str_copy_flash(&b, "hello");
            len = str_len(&a);
            eq = str_eq(&a, &b);
            base = &a;
            found = str_chr(&a, 'l');
            str_cat(&a, &b);
            uart_print_str(&a);
            uart_putc(' ');
            uart_print_dec8(len);
            uart_putc(' ');
            uart_print_dec8(eq);
            uart_putc(' ');
            uart_print_dec8(found - base);
            uart_nl();
        }
        """,
    )
    assert bytes(emu.uart_tx) == b"hellohello 5 1 4\n"
    assert value(compiler, emu, "len") == 5


def test_math_module(tmp_path: Path) -> None:
    compiler, emu = compile_source(
        tmp_path,
        """
        import "lib/math.badge";
        char product;
        char quotient;
        nibble remainder;
        nibble root;
        char big_quotient;
        char power;
        fn main() {
            product = math_mul(7, 9);
            quotient = math_div(15, 4);
            remainder = math_mod(15, 4);
            root = math_isqrt(49);
            big_quotient = math_div8(200, 7);
            power = math_pow2(5);
        }
        """,
    )
    assert value(compiler, emu, "product") == 63
    assert value(compiler, emu, "quotient") == 3
    assert value(compiler, emu, "remainder") == 3
    assert value(compiler, emu, "root") == 7
    assert value(compiler, emu, "big_quotient") == 28
    assert value(compiler, emu, "power") == 32


def test_mem_module(tmp_path: Path) -> None:
    compiler, emu = compile_source(
        tmp_path,
        """
        import "lib/mem.badge";
        char a[16];
        char b[16];
        nibble same;
        nibble bit;
        nibble bits;
        fn main() {
            mem_fill(&a, 3, 8);
            a[0] = 5;
            mem_bit_set(&a, 0);
            bit = mem_bit_test(&a, 0);
            bits = mem_popcount(15);
            mem_copy(&b, &a, 8);
            same = mem_cmp(&a, &b, 8);
            mem_bit_clear(&a, 0);
            mem_bit_toggle(&a, 1);
            mem_swap(&a, &b);
        }
        """,
    )
    assert value(compiler, emu, "bit") == 1
    assert value(compiler, emu, "bits") == 4
    assert value(compiler, emu, "same") == 0
    # a[0]: 5 -> set bit0 (5) -> clear bit0 (4) -> toggle bit1 (6).
    # mem_swap then puts b's original copy back into a.
    a_base = compiler.globals["a"].address
    b_base = compiler.globals["b"].address
    assert a_base is not None and b_base is not None
    assert emu.ram[a_base] == 5
    assert emu.ram[b_base] == 6


def test_display_module(tmp_path: Path) -> None:
    compiler, emu = compile_source(
        tmp_path,
        """
        import "lib/display.badge";
        nibble screen[32];
        nibble corner;
        nibble empty;
        nibble bottom;
        nibble page_value;
        fn main() {
            clear_screen(&screen);
            pixel_set(&screen, 0, 0, 1);
            pixel_set(&screen, 7, 15, 1);
            corner = pixel_get(&screen, 0, 0);
            empty = pixel_get(&screen, 1, 0);
            bottom = pixel_get(&screen, 7, 15);
            hline(&screen, 0, 7, 5, 1);
            display_fill(8, 5);
            page_value = display_peek(8, 3);
            display_clear(8);
        }
        """,
    )
    assert value(compiler, emu, "corner") == 1
    assert value(compiler, emu, "empty") == 0
    assert value(compiler, emu, "bottom") == 1
    assert value(compiler, emu, "page_value") == 5

    base = compiler.globals["screen"].address
    assert base is not None
    # Row 5 occupies nibbles 10 and 11; hline set all eight pixels.
    assert emu.ram[base + 10] == 15
    assert emu.ram[base + 11] == 15
    # display_clear cleared page 8.
    assert emu.ram[0x80] == 0


def test_key_names_and_clock(tmp_path: Path) -> None:
    compiler, emu = compile_source(
        tmp_path,
        """
        import "lib/key.badge";
        import "lib/time.badge";
        import "lib/uart.badge";
        nibble clock;
        fn main() {
            uart_route(1);
            uart_init(3);
            uart_puts(key_name(key_op8()));
            uart_nl();
            time_clock_set(5);
            clock = time_clock_get();
        }
        """,
    )
    assert bytes(emu.uart_tx) == b"OPCODE 8\n"
    assert value(compiler, emu, "clock") == 5


def test_uart_read_line(tmp_path: Path) -> None:
    compiler, emu = compile_source(
        tmp_path,
        """
        import "lib/uart.badge";
        char buf[8];
        nibble count;
        fn main() {
            uart_route(1);
            uart_init(3);
            count = uart_read_line(&buf, 4);
            uart_print_dec8(count);
            uart_putc(':');
            uart_print_str(&buf);
        }
        """,
        rx=list(b"abc\n"),
    )
    assert value(compiler, emu, "count") == 3
    assert bytes(emu.uart_tx) == b"3:abc"
