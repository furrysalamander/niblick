"""Struct declaration, layout, and field-access tests."""

from __future__ import annotations

from pathlib import Path

import pytest

from badgec.assembler import assemble_file
from badgec.compiler import Compiler
from badgec.errors import BadgeCompileError, BadgeSyntaxError, BadgeTypeError
from badgec.emulator import Emulator
from badgec.loader import load_source


def compile_source(tmp_path: Path, source: str) -> tuple[Compiler, Emulator]:
    filename = tmp_path / "structs.badge"
    program = load_source(source, filename=str(filename))
    compiler = Compiler(program, str(filename))
    asm = compiler.compile()
    asm_path = tmp_path / "structs.asm"
    asm_path.write_text(asm)
    hex_path = tmp_path / "structs.hex"
    assemble_file(asm_path, hex_path)

    emu = Emulator()
    emu.load_hex(hex_path)
    emu.run(100000)
    return compiler, emu


def compile_error(tmp_path: Path, source: str, error_type) -> None:
    filename = tmp_path / "structs.badge"
    with pytest.raises(error_type):
        program = load_source(source, filename=str(filename))
        compiler = Compiler(program, str(filename))
        compiler.compile()


def test_struct_layout_and_field_access(tmp_path: Path) -> None:
    compiler, emu = compile_source(
        tmp_path,
        """
        import "lib/uart.badge";

        struct Point {
            nibble x;
            nibble y;
        };

        struct Mixed {
            char a;
            nibble b;
            word c;
        };

        Point origin;
        Point points[3];
        Mixed mixed;
        nibble out[4];

        fn main() {
            uart_route(1);
            uart_init(3);

            origin.x = 3;
            origin.y = 4;

            points[0].x = 1;
            points[0].y = 2;
            points[1].x = 5;
            points[1].y = 6;
            points[2].x = 7;
            points[2].y = 8;

            mixed.a = 0xAB;
            mixed.b = 9;
            mixed.c = 0x1234;

            out[0] = origin.x;
            out[1] = points[2].y;
            out[2] = mixed.b;
            out[3] = (nibble)mixed.c;

            print("p=({},{}) ps2=({},{}) mixed={:x},{},c={:x}\\n",
                  origin.x, origin.y, points[2].x, points[2].y,
                  mixed.a, mixed.b, mixed.c);
        }
        """,
    )
    origin = compiler.globals["origin"]
    points = compiler.globals["points"]
    mixed = compiler.globals["mixed"]
    assert origin.type.ram_size == 2
    assert points.type.ram_size == 2
    assert mixed.type.ram_size == 8
    assert [field.offset for field in mixed.type.fields] == [0, 2, 3]

    assert origin.address is not None
    assert points.address is not None
    assert mixed.address is not None
    assert [emu.ram[origin.address + index] for index in range(2)] == [3, 4]
    assert [
        emu.ram[points.address + index] for index in range(6)
    ] == [1, 2, 5, 6, 7, 8]
    assert [
        emu.ram[mixed.address + index] for index in range(8)
    ] == [11, 10, 9, 4, 3, 2, 1, 0]

    out = compiler.globals["out"]
    assert out.address is not None
    assert [emu.ram[out.address + index] for index in range(4)] == [3, 8, 9, 4]
    assert bytes(emu.uart_tx) == b"p=(3,4) ps2=(7,8) mixed=AB,9,c=1234\n"


def test_local_struct_and_array(tmp_path: Path) -> None:
    compiler, emu = compile_source(
        tmp_path,
        """
        struct Pair {
            char value;
            nibble flag;
        };

        nibble out[2];

        fn main() {
            Pair local;
            Pair items[2];
            local.value = 0x42;
            local.flag = 1;
            items[0].value = 0x10;
            items[0].flag = 0;
            items[1].value = 0x20;
            items[1].flag = 1;
            out[0] = local.flag;
            out[1] = items[1].flag;
        }
        """,
    )
    out = compiler.globals["out"]
    assert out.address is not None
    assert [emu.ram[out.address + index] for index in range(2)] == [1, 1]


def test_struct_error_cases(tmp_path: Path) -> None:
    compile_error(
        tmp_path,
        """
        struct Point { nibble x; nibble y; };
        Point p;
        fn main() {
            p.z = 1;
        }
        """,
        BadgeTypeError,
    )
    compile_error(
        tmp_path,
        """
        struct Point { nibble x; nibble y; };
        Point a;
        Point b;
        fn main() {
            a = b;
        }
        """,
        BadgeTypeError,
    )
    compile_error(
        tmp_path,
        """
        struct Point { nibble x; nibble y; };
        Point value;
        fn void take(Point p) {
        }
        fn main() {
            take(value);
        }
        """,
        BadgeTypeError,
    )
    compile_error(
        tmp_path,
        """
        struct Point { nibble x; nibble y; };
        fn Point make() {
            Point p;
            return p;
        }
        fn main() {
            make();
        }
        """,
        BadgeTypeError,
    )
    compile_error(
        tmp_path,
        """
        struct Point { nibble x; nibble y; };
        Point p = 1;
        fn main() {
            p.x = 1;
        }
        """,
        BadgeCompileError,
    )
    compile_error(
        tmp_path,
        """
        struct Point { nibble x; nibble y; };
        const Point p = 0;
        fn main() {
            p.x = 1;
        }
        """,
        BadgeTypeError,
    )
    compile_error(
        tmp_path,
        """
        struct Point { nibble x; nibble x; };
        fn main() {
        }
        """,
        BadgeSyntaxError,
    )
