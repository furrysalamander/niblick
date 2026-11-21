"""Struct declaration, layout, and field-access tests."""

from __future__ import annotations

from pathlib import Path

import pytest

from niblick.assembler import assemble_file
from niblick.compiler import Compiler
from niblick.errors import NiblickSyntaxError, NiblickTypeError
from niblick.emulator import Emulator
from niblick.loader import load_source


def compile_source(tmp_path: Path, source: str) -> tuple[Compiler, Emulator]:
    filename = tmp_path / "structs.nbl"
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
    filename = tmp_path / "structs.nbl"
    with pytest.raises(error_type):
        program = load_source(source, filename=str(filename))
        compiler = Compiler(program, str(filename))
        compiler.compile()


def test_struct_layout_and_field_access(tmp_path: Path) -> None:
    compiler, emu = compile_source(
        tmp_path,
        """
        import "lib/uart.nbl";

        struct Point {
            nibble x;
            nibble y;
        };

        struct Mixed {
            char a;
            nibble b;
            uint16_t c;
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
    assert mixed.type.ram_size == 7
    assert [field.offset for field in mixed.type.fields] == [0, 2, 3]

    assert origin.address is not None
    assert points.address is not None
    assert mixed.address is not None
    assert [emu.ram[origin.address + index] for index in range(2)] == [3, 4]
    assert [
        emu.ram[points.address + index] for index in range(6)
    ] == [1, 2, 5, 6, 7, 8]
    assert [
        emu.ram[mixed.address + index] for index in range(7)
    ] == [11, 10, 9, 4, 3, 2, 1]

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
        NiblickTypeError,
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
        NiblickTypeError,
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
        NiblickTypeError,
    )
    compile_error(
        tmp_path,
        """
        struct Point { nibble x; nibble x; };
        fn main() {
        }
        """,
        NiblickSyntaxError,
    )


def test_struct_assignment_parameters_and_returns(tmp_path: Path) -> None:
    compiler, emu = compile_source(
        tmp_path,
        """
        struct Point {
            nibble x;
            nibble y;
        };

        Point original;
        Point copy;
        Point made;
        Point items[2];
        nibble out[4];

        fn void clobber(Point p) {
            p.x = 5;
            p.y = 6;
        }

        fn Point make() {
            Point p;
            p.x = 7;
            p.y = 8;
            return p;
        }

        fn main() {
            original.x = 1;
            original.y = 2;
            copy = original;
            clobber(original);
            made = make();
            items[0] = make();
            items[1] = copy;
            Point local = items[1];
            out[0] = made.x;
            out[1] = make().y;
            out[2] = items[0].x;
            out[3] = local.y;
        }
        """,
    )

    def ram(name: str) -> list[int]:
        symbol = compiler.globals[name]
        assert symbol.address is not None
        size = symbol.type.ram_size * (symbol.array_len or 1)
        return [emu.ram[symbol.address + index] for index in range(size)]

    assert ram("original") == [1, 2]
    assert ram("copy") == [1, 2]
    assert ram("made") == [7, 8]
    assert ram("items") == [7, 8, 1, 2]
    assert ram("out") == [7, 8, 7, 2]


def test_struct_float_field(tmp_path: Path) -> None:
    compiler, emu = compile_source(
        tmp_path,
        """
        struct Sample {
            float value;
            nibble tag;
        };

        Sample sample;
        float out;

        fn main() {
            sample.value = 1.5;
            sample.tag = 7;
            out = sample.value;
        }
        """,
    )
    out = compiler.globals["out"]
    assert out.address is not None
    bits = sum(emu.ram[out.address + index] << (4 * index) for index in range(8))
    assert bits == 0x3FC00000


def test_struct_array_fields_and_exact_layout(tmp_path: Path) -> None:
    compiler, emu = compile_source(
        tmp_path,
        """
        struct Packet {
            nibble header;
            char payload[4];
            nibble tail;
        };

        Packet packet;
        char out[5];

        fn main() {
            packet.header = 1;
            packet.payload[0] = 'A';
            packet.payload[1] = 'B';
            nibble index = 2;
            packet.payload[index] = 'C';
            packet.tail = 9;
            out[0] = packet.header;
            out[1] = packet.payload[0];
            out[2] = packet.payload[index];
            out[3] = packet.tail;
            out[4] = packet.payload[3];
        }
        """,
    )
    packet = compiler.globals["packet"]
    assert packet.type.ram_size == 10
    assert [field.offset for field in packet.type.fields] == [0, 1, 9]
    assert packet.address is not None
    assert emu.ram[packet.address + 1] == ord("A") & 0xF
    assert emu.ram[packet.address + 2] == ord("A") >> 4
    assert emu.ram[packet.address + 5] == ord("C") & 0xF
    assert emu.ram[packet.address + 6] == ord("C") >> 4
    out = compiler.globals["out"]
    assert out.address is not None
    assert [
        emu.ram[out.address + index * 2]
        | (emu.ram[out.address + index * 2 + 1] << 4)
        for index in range(5)
    ] == [1, 0x41, 0x43, 9, 0]


def test_nested_structs_and_initializers(tmp_path: Path) -> None:
    compiler, emu = compile_source(
        tmp_path,
        """
        struct Inner {
            nibble a;
            nibble b;
        };

        struct Outer {
            nibble head;
            Inner inner;
            nibble tail;
        };

        Outer outer = { 1, { 2, 3 }, 4 };
        Outer empty = {};
        nibble out[6];

        fn main() {
            out[0] = outer.head;
            out[1] = outer.inner.a;
            out[2] = outer.inner.b;
            out[3] = outer.tail;
            out[4] = empty.inner.b;
            out[5] = empty.tail;
        }
        """,
    )
    outer = compiler.globals["outer"]
    assert outer.type.ram_size == 4
    assert [field.offset for field in outer.type.fields] == [0, 1, 3]
    assert outer.address is not None
    assert [emu.ram[outer.address + index] for index in range(4)] == [1, 2, 3, 4]
    out = compiler.globals["out"]
    assert out.address is not None
    assert [emu.ram[out.address + index] for index in range(6)] == [1, 2, 3, 4, 0, 0]


def test_struct_comparison(tmp_path: Path) -> None:
    compiler, emu = compile_source(
        tmp_path,
        """
        struct Point {
            nibble x;
            nibble y;
        };

        Point a;
        Point b;
        nibble out[4];

        fn main() {
            a.x = 1;
            a.y = 2;
            b = a;
            out[0] = a == b;
            out[1] = a != b;
            b.y = 3;
            out[2] = a == b;
            out[3] = a != b;
        }
        """,
    )
    out = compiler.globals["out"]
    assert out.address is not None
    assert [emu.ram[out.address + index] for index in range(4)] == [1, 0, 0, 1]


def test_struct_names_are_global_across_imports(tmp_path: Path) -> None:
    (tmp_path / "types.nbl").write_text(
        """
        struct Point {
            nibble x;
            nibble y;
        };
        """
    )
    source = """
        import "types.nbl";
        Point point;
        nibble out[2];
        fn main() {
            point.x = 3;
            point.y = 4;
            out[0] = point.x;
            out[1] = point.y;
        }
        """
    filename = tmp_path / "main.nbl"
    program = load_source(source, filename=str(filename))
    compiler = Compiler(program, str(filename))
    asm = compiler.compile()
    asm_path = tmp_path / "main.asm"
    asm_path.write_text(asm)
    hex_path = tmp_path / "main.hex"
    assemble_file(asm_path, hex_path)
    emu = Emulator()
    emu.load_hex(hex_path)
    emu.run(100000)
    out = compiler.globals["out"]
    assert out.address is not None
    assert [emu.ram[out.address + index] for index in range(2)] == [3, 4]


def test_const_structs_in_flash_and_value_copies(tmp_path: Path) -> None:
    compiler, emu = compile_source(
        tmp_path,
        """
        struct Point {
            nibble x;
            nibble y;
        };

        struct Config {
            nibble id;
            char name[3];
        };

        const Point origin = { 3, 4 };
        const Config config = { 5, "AB" };
        Point copy;
        Config config_copy;
        char out[4];

        fn nibble sum(Point p) {
            return p.x + p.y;
        }

        fn Point make() {
            return origin;
        }

        fn main() {
            copy = origin;
            config_copy = config;
            out[0] = origin.x;
            out[1] = config.name[1];
            out[2] = sum(origin);
            out[3] = make().y;
            copy.x = config_copy.id;
        }
        """,
    )
    out = compiler.globals["out"]
    assert out.address is not None
    assert [
        emu.ram[out.address + index * 2]
        | (emu.ram[out.address + index * 2 + 1] << 4)
        for index in range(4)
    ] == [3, 0x42, 7, 4]
    copy = compiler.globals["copy"]
    assert copy.address is not None
    assert [emu.ram[copy.address + index] for index in range(2)] == [5, 4]
    config_copy = compiler.globals["config_copy"]
    assert config_copy.address is not None
    assert [emu.ram[config_copy.address + index] for index in range(7)] == [
        5,
        0x41 & 0xF,
        0x41 >> 4,
        0x42 & 0xF,
        0x42 >> 4,
        0,
        0,
    ]


def test_exact_size_struct_array_indexing(tmp_path: Path) -> None:
    compiler, emu = compile_source(
        tmp_path,
        """
        struct Triple {
            nibble a;
            nibble b;
            nibble c;
        };

        Triple items[4];
        nibble out[4];

        fn main() {
            nibble index = 2;
            items[0].b = 1;
            items[1].b = 2;
            items[index].b = 3;
            items[3].b = 4;
            out[0] = items[0].b;
            out[1] = items[1].b;
            out[2] = items[index].b;
            out[3] = items[3].b;
        }
        """,
    )
    items = compiler.globals["items"]
    assert items.type.ram_size == 3
    assert items.address is not None
    assert [emu.ram[items.address + index] for index in range(3)] == [0, 1, 0]
    out = compiler.globals["out"]
    assert out.address is not None
    assert [emu.ram[out.address + index] for index in range(4)] == [1, 2, 3, 4]


def test_const_nested_struct_and_comparison(tmp_path: Path) -> None:
    compiler, emu = compile_source(
        tmp_path,
        """
        struct Inner {
            nibble a;
            nibble b;
        };

        struct Outer {
            Inner inner;
            nibble tail;
        };

        const Outer first = { { 1, 2 }, 3 };
        const Outer second = { { 1, 2 }, 3 };
        nibble out[3];

        fn main() {
            out[0] = first.inner.b;
            out[1] = first == second;
            out[2] = first != second;
        }
        """,
    )
    out = compiler.globals["out"]
    assert out.address is not None
    assert [emu.ram[out.address + index] for index in range(3)] == [2, 1, 0]


def test_const_struct_array_in_flash(tmp_path: Path) -> None:
    compiler, emu = compile_source(
        tmp_path,
        """
        struct Point {
            nibble x;
            nibble y;
        };

        const Point points[2] = { { 1, 2 }, { 3, 4 } };
        nibble out[2];

        fn nibble sum(Point p) {
            return p.x + p.y;
        }

        fn main() {
            out[0] = points[1].x;
            out[1] = sum(points[0]);
        }
        """,
    )
    out = compiler.globals["out"]
    assert out.address is not None
    assert [emu.ram[out.address + index] for index in range(2)] == [3, 3]


def test_struct_error_cases_extended(tmp_path: Path) -> None:
    compile_error(
        tmp_path,
        """
        struct Point { nibble x; nibble y; };
        const Point origin = { 1, 2 };
        fn main() {
            origin.x = 3;
        }
        """,
        NiblickTypeError,
    )
    compile_error(
        tmp_path,
        """
        struct Point { nibble x; nibble y; };
        const Point points[2] = { { 1, 2 }, { 3, 4 } };
        fn main() {
            points[0] = points[1];
        }
        """,
        NiblickTypeError,
    )
    compile_error(
        tmp_path,
        """
        struct Point { nibble x; nibble y; };
        fn main() {
            const Point origin = { 1, 2 };
        }
        """,
        NiblickTypeError,
    )
    compile_error(
        tmp_path,
        """
        struct Point { nibble x; nibble y; };
        struct Holder { Point points[2]; };
        fn main() {
        }
        """,
        NiblickSyntaxError,
    )


def test_duplicate_struct_names_across_imports(tmp_path: Path) -> None:
    (tmp_path / "types.nbl").write_text(
        """
        struct Point {
            nibble x;
            nibble y;
        };
        """
    )
    source = """
        import "types.nbl";
        struct Point {
            nibble x;
        };
        fn main() {
        }
        """
    with pytest.raises(NiblickSyntaxError):
        load_source(source, filename=str(tmp_path / "main.nbl"))


def test_array_field_index_with_call(tmp_path: Path) -> None:
    compiler, emu = compile_source(
        tmp_path,
        """
        struct Packet {
            nibble header;
            char payload[4];
            nibble tail;
        };

        Packet packet;
        char out[2];

        fn nibble index() {
            return 2;
        }

        fn main() {
            packet.header = 1;
            packet.payload[index()] = 'C';
            packet.tail = 9;
            out[0] = packet.payload[index()];
            out[1] = packet.tail;
        }
        """,
    )
    packet = compiler.globals["packet"]
    assert packet.address is not None
    assert emu.ram[packet.address + 5] == ord("C") & 0xF
    assert emu.ram[packet.address + 6] == ord("C") >> 4
    out = compiler.globals["out"]
    assert out.address is not None
    assert [
        emu.ram[out.address + index * 2]
        | (emu.ram[out.address + index * 2 + 1] << 4)
        for index in range(2)
    ] == [0x43, 9]
