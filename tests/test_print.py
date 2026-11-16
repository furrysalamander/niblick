"""Compile-time ``print`` formatting tests."""

from __future__ import annotations

from pathlib import Path

import pytest

from niblick.assembler import assemble_file
from niblick.compiler import Compiler
from niblick.errors import NiblickCompileError, NiblickTypeError
from niblick.emulator import Emulator
from niblick.format import PlaceholderPart, TextPart, parse_format
from niblick.loader import load_source


def compile_source(tmp_path: Path, source: str) -> tuple[Compiler, Emulator, str]:
    filename = tmp_path / "print.nbl"
    program = load_source(source, filename=str(filename))
    compiler = Compiler(program, str(filename))
    asm = compiler.compile()
    asm_path = tmp_path / "print.asm"
    asm_path.write_text(asm)
    hex_path = tmp_path / "print.hex"
    assemble_file(asm_path, hex_path)

    emu = Emulator()
    emu.load_hex(hex_path)
    emu.run(500000)
    return compiler, emu, asm


def compile_error(tmp_path: Path, source: str, error_type) -> None:
    filename = tmp_path / "print.nbl"
    program = load_source(source, filename=str(filename))
    compiler = Compiler(program, str(filename))
    with pytest.raises(error_type):
        compiler.compile()


def test_format_parser() -> None:
    assert parse_format("plain", "<test>", 1) == [TextPart("plain")]
    assert parse_format("a{}b{:x}c", "<test>", 1) == [
        TextPart("a"),
        PlaceholderPart("", 2),
        TextPart("b"),
        PlaceholderPart("x", 5),
        TextPart("c"),
    ]
    assert parse_format("{{x}}", "<test>", 1) == [TextPart("{x}")]


def test_format_parser_errors() -> None:
    with pytest.raises(NiblickCompileError):
        parse_format("unclosed {", "<test>", 1)
    with pytest.raises(NiblickCompileError):
        parse_format("stray }", "<test>", 1)
    with pytest.raises(NiblickCompileError):
        parse_format("{:q}", "<test>", 1)


def test_print_core_formats(tmp_path: Path) -> None:
    _, emu, _ = compile_source(
        tmp_path,
        """
        import "lib/uart.nbl";
        import "lib/string.nbl";

        nibble n;
        char c;
        uint16_t w;
        uint32_t d;
        char buf[8];

        fn main() {
            uart_route(1);
            uart_init(3);
            n = 5;
            c = 65;
            w = 1234;
            d = 123456;
            str_copy_flash(&buf, "ram");
            print("n={} c={:c} w={:x} d={:x}\\n", n, c, w, d);
            print("b={:b} {:b} {:b}\\n", n, w, d);
            print("ram={:s} flash={}\\n", &buf, "hello");
            print("lit {{ok}}\\n");
        }
        """,
    )
    assert bytes(emu.uart_tx) == (
        b"n=5 c=A w=04D2 d=0001E240\n"
        b"b=0101 0000010011010010 00000000000000011110001001000000\n"
        b"ram=ram flash=hello\n"
        b"lit {ok}\n"
    )


def test_print_decimal_widths(tmp_path: Path) -> None:
    _, emu, asm = compile_source(
        tmp_path,
        """
        import "lib/uart.nbl";

        nibble n;
        char c;
        uint16_t w;
        uint32_t d;

        fn main() {
            uart_route(1);
            uart_init(3);
            n = 5;
            c = 255;
            w = 65535;
            d = 4294967295;
            print("{} {} {} {}\\n", n, c, w, d);
        }
        """,
    )
    assert bytes(emu.uart_tx) == b"5 255 65535 4294967295\n"
    assert "fn_uart_print_dec16" in asm
    assert "fn_uart_print_dec32" in asm


def test_print_links_only_used_formatters(tmp_path: Path) -> None:
    _, emu, asm = compile_source(
        tmp_path,
        """
        import "lib/uart.nbl";

        nibble n;

        fn main() {
            uart_route(1);
            uart_init(3);
            n = 5;
            print("n={}\\n", n);
        }
        """,
    )
    assert bytes(emu.uart_tx) == b"n=5\n"
    assert "fn_uart_print_dec16" not in asm
    assert "fn_uart_print_dec32" not in asm


def test_print_literal_only(tmp_path: Path) -> None:
    _, emu, _ = compile_source(
        tmp_path,
        """
        import "lib/uart.nbl";

        fn main() {
            uart_route(1);
            uart_init(3);
            print("hello\\n");
        }
        """,
    )
    assert bytes(emu.uart_tx) == b"hello\n"


def test_print_requires_uart_import(tmp_path: Path) -> None:
    compile_error(
        tmp_path,
        """
        fn main() {
            print("hello\\n");
        }
        """,
        NiblickCompileError,
    )


def test_print_rejects_dynamic_format(tmp_path: Path) -> None:
    compile_error(
        tmp_path,
        """
        import "lib/uart.nbl";

        char fmt;

        fn main() {
            print(fmt);
        }
        """,
        NiblickCompileError,
    )


def test_print_placeholder_count(tmp_path: Path) -> None:
    compile_error(
        tmp_path,
        """
        import "lib/uart.nbl";

        fn main() {
            print("{}");
        }
        """,
        NiblickTypeError,
    )
    compile_error(
        tmp_path,
        """
        import "lib/uart.nbl";

        fn main() {
            print("x", 1);
        }
        """,
        NiblickTypeError,
    )


def test_print_rejects_bad_types(tmp_path: Path) -> None:
    compile_error(
        tmp_path,
        """
        import "lib/uart.nbl";

        fn main() {
            print("{:x}", "text");
        }
        """,
        NiblickTypeError,
    )
    compile_error(
        tmp_path,
        """
        import "lib/uart.nbl";

        fn main() {
            print("{:c}", 300);
        }
        """,
        NiblickTypeError,
    )


def test_print_is_statement_only(tmp_path: Path) -> None:
    compile_error(
        tmp_path,
        """
        import "lib/uart.nbl";

        nibble value;

        fn main() {
            value = print("x");
        }
        """,
        NiblickCompileError,
    )


def test_print_is_reserved(tmp_path: Path) -> None:
    compile_error(
        tmp_path,
        """
        fn void print() {
        }
        """,
        NiblickCompileError,
    )


def test_print_signed_and_bool_types(tmp_path: Path) -> None:
    _, emu, _ = compile_source(
        tmp_path,
        """
        import "lib/uart.nbl";
        int8_t a;
        int16_t b;
        int32_t c;
        bool flag;
        fn main() {
            uart_route(1);
            uart_init(3);
            a = -7;
            b = -20000;
            c = -100000;
            flag = 2;
            print("{} {} {} {} {}\\n", a, b, c, flag, b < a);
        }
        """,
    )
    emu.run(4_000_000)
    assert bytes(emu.uart_tx) == b"-7 -20000 -100000 1 1\n"
