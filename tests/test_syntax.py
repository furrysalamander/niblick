"""Tests for the 1.0 syntax additions."""

from __future__ import annotations

from pathlib import Path

import pytest

from badgec.assembler import assemble_file
from badgec.compiler import Compiler
from badgec.emulator import Emulator
from badgec.errors import BadgeCompileError, BadgeSyntaxError, BadgeTypeError
from badgec.loader import load_source
from badgec.parser import parse


def build(tmp_path: Path, source: str, *, steps: int = 500_000):
    filename = str(tmp_path / "syntax.badge")
    compiler = Compiler(load_source(source, filename=filename), filename)
    asm_path = tmp_path / "syntax.asm"
    asm_path.write_text(compiler.compile())
    hex_path = tmp_path / "syntax.hex"
    assemble_file(asm_path, hex_path)
    emu = Emulator()
    emu.load_hex(hex_path)
    emu.run(steps)
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


def local(compiler: Compiler, function: str, name: str):
    for symbol in compiler.functions[function].locals:
        if symbol.name == name:
            return symbol
    raise KeyError(name)


def ram_byte(emu: Emulator, address: int) -> int:
    return emu.ram[address] | (emu.ram[address + 1] << 4)


def local_value(compiler: Compiler, emu: Emulator, function: str, name: str) -> int:
    symbol = local(compiler, function, name)
    assert symbol.address is not None
    width = symbol.type.ram_size
    bits = sum(emu.ram[symbol.address + index] << (4 * index) for index in range(width))
    if symbol.type.signed:
        sign = 1 << (4 * width - 1)
        if bits & sign:
            bits -= 1 << (4 * width)
    return bits


def test_ternary_selects_one_branch_and_is_lazy(tmp_path: Path) -> None:
    compiler, emu = build(
        tmp_path,
        """
        nibble a;
        nibble b;
        nibble x;
        nibble y;

        fn nibble bump_a() {
            a = a + 1;
            return 1;
        }

        fn nibble bump_b() {
            b = b + 1;
            return 2;
        }

        fn main() {
            x = 1 ? bump_a() : bump_b();
            y = 0 ? bump_a() : bump_b();
        }
        """,
    )
    assert value(compiler, emu, "a") == 1
    assert value(compiler, emu, "b") == 1
    assert value(compiler, emu, "x") == 1
    assert value(compiler, emu, "y") == 2


def test_ternary_type_width_and_nesting(tmp_path: Path) -> None:
    compiler, emu = build(
        tmp_path,
        """
        uint16_t wide;
        nibble nested;

        fn main() {
            wide = 1 ? 400 : 500;
            nested = 0 ? 2 : 0 ? 4 : 5;
            nested = 1 ? 2 : 3 ? 4 : 5;
        }
        """,
    )
    assert value(compiler, emu, "wide") == 400
    assert value(compiler, emu, "nested") == 2


def test_ternary_in_print_argument(tmp_path: Path) -> None:
    _, emu = build(
        tmp_path,
        """
        import "lib/uart.badge";

        fn main() {
            uart_route(1);
            uart_init(3);
            print("{} {} {}\\n", 1 ? 2 : 3, 0 ? 4 : 5, 1 ? 6 : 7);
        }
        """,
    )
    assert bytes(emu.uart_tx) == b"2 5 6\n"


def test_ternary_float_result(tmp_path: Path) -> None:
    compiler, emu = build(
        tmp_path,
        """
        float value;
        nibble ok;

        fn main() {
            value = 1 ? 1.5 : 2.5;
            ok = value == 1.5 ? 1 : 0;
        }
        """,
    )
    assert value(compiler, emu, "ok") == 1


def test_ternary_constant_folds_in_array_length(tmp_path: Path) -> None:
    compiler, _ = build(
        tmp_path,
        """
        const nibble N = 1 ? 4 : 8;
        nibble values[N];

        fn main() {
            values[0] = 1;
        }
        """,
    )
    assert compiler.globals["values"].array_len == 4


def test_ternary_rejects_void_and_struct_branches(tmp_path: Path) -> None:
    with pytest.raises(BadgeTypeError, match="must produce a value"):
        Compiler(
            load_source(
                """
                fn void f() { }
                fn main() {
                    nibble x = 1 ? f() : 2;
                }
                """,
                filename=str(tmp_path / "ternary.badge"),
            ),
            str(tmp_path / "ternary.badge"),
        ).compile()

    with pytest.raises(BadgeTypeError, match="struct values"):
        Compiler(
            load_source(
                """
                struct P { nibble x; };
                P a;
                P b;
                P c;
                fn main() {
                    c = 1 ? a : b;
                }
                """,
                filename=str(tmp_path / "ternary.badge"),
            ),
            str(tmp_path / "ternary.badge"),
        ).compile()


def test_compound_assignment_and_increment(tmp_path: Path) -> None:
    compiler, emu = build(
        tmp_path,
        """
        nibble x;
        nibble a[3];
        struct P { nibble v; };
        P p;

        fn main() {
            x = 1;
            x += 2;
            x <<= 1;
            x |= 1;
            a[1] = 2;
            a[1] += 3;
            p.v = 4;
            p.v++;
            ++x;
            x--;
            for (p.v = 0; p.v < 3; p.v++) {
            }
        }
        """,
    )
    assert value(compiler, emu, "x") == 7
    assert emu.ram[compiler.globals["a"].address + 1] == 5
    assert emu.ram[compiler.globals["p"].address] == 3


def test_array_length_constant_expressions(tmp_path: Path) -> None:
    compiler, emu = build(
        tmp_path,
        """
        const nibble N = 3;
        nibble a[N + 1];
        const nibble M = 0 ? 1 : 5;
        nibble b[M];

        fn main() {
            nibble local[N];
            local[0] = 9;
            a[0] = 1;
            b[0] = 2;
        }
        """,
    )
    assert compiler.globals["a"].array_len == 4
    assert compiler.globals["b"].array_len == 5
    assert local(compiler, "main", "local").array_len == 3
    assert local_value(compiler, emu, "main", "local") == 9


def test_global_and_local_aggregate_initializers(tmp_path: Path) -> None:
    compiler, emu = build(
        tmp_path,
        """
        nibble g[4] = {1, 2};
        char text[] = "hi";
        struct P { nibble x; nibble y; };
        P gp = {3, 4};
        nibble sink;
        char csink;

        fn main() {
            nibble l[3] = {5, 6, 7};
            char lbuf[4] = "ab";
            P lp = {8, 9};
            sink = g[0];
            sink = gp.x;
            csink = text[0];
            sink = l[0];
            csink = lbuf[0];
            sink = lp.x;
        }
        """,
    )
    g = compiler.globals["g"]
    assert g.address is not None
    assert [emu.ram[g.address + i] for i in range(4)] == [1, 2, 0, 0]

    text = compiler.globals["text"]
    assert text.address is not None
    assert [ram_byte(emu, text.address + 2 * i) for i in range(3)] == [
        ord("h"),
        ord("i"),
        0,
    ]

    gp = compiler.globals["gp"]
    assert gp.address is not None
    assert [emu.ram[gp.address + i] for i in range(2)] == [3, 4]

    loc = local(compiler, "main", "l")
    assert loc.address is not None
    assert [emu.ram[loc.address + i] for i in range(3)] == [5, 6, 7]

    lbuf = local(compiler, "main", "lbuf")
    assert lbuf.address is not None
    assert [ram_byte(emu, lbuf.address + 2 * i) for i in range(4)] == [
        ord("a"),
        ord("b"),
        0,
        0,
    ]

    lp = local(compiler, "main", "lp")
    assert lp.address is not None
    assert [emu.ram[lp.address + i] for i in range(2)] == [8, 9]


def test_string_terminator_is_nul(tmp_path: Path) -> None:
    compiler, _ = build(
        tmp_path,
        """
        const char msg[] = "AB";
        char sink;

        fn main() {
            sink = msg[0];
        }
        """,
    )
    item = next(item for item in compiler.flash if item.string_value == "AB")
    assert item.values == [ord("A"), ord("B"), 0]
    assert compiler.globals["msg"].array_len == 3


def test_literal_forms(tmp_path: Path) -> None:
    compiler, emu = build(
        tmp_path,
        """
        uint16_t a;
        uint16_t b;
        char c;
        char d;
        nibble e;
        char f;
        uint16_t g;
        uint16_t dot;

        fn main() {
            a = 0o17;
            b = 1_0;
            c = 0b1010_1010;
            d = '\\101';
            e = (nibble)('\\x41' - 60);
            f = 0xFF;
            g = 0xFF_FF;
            dot = .5 > 0 ? 1 : 0;
            dot = 1. > 0 ? dot + 1 : dot;
        }
        """,
    )
    assert value(compiler, emu, "a") == 15
    assert value(compiler, emu, "b") == 10
    assert value(compiler, emu, "c") == 170
    assert value(compiler, emu, "d") == 65
    assert value(compiler, emu, "e") == 5
    assert value(compiler, emu, "f") == 255
    assert value(compiler, emu, "g") == 65535
    assert value(compiler, emu, "dot") == 2


def test_string_concatenation_and_escapes(tmp_path: Path) -> None:
    compiler, _ = build(
        tmp_path,
        """
        const char msg[] = "a" "b" "\\n";
        const char ctl[] = "\\a\\b\\f\\v";
        char sink;

        fn main() {
            sink = msg[0];
            sink = ctl[0];
        }
        """,
    )
    item = next(item for item in compiler.flash if item.string_value == "ab\n")
    assert item.values == [ord("a"), ord("b"), ord("\n"), 0]
    ctl = next(item for item in compiler.flash if item.string_value == "\a\b\f\v")
    assert ctl.values == [7, 8, 12, 11, 0]


def test_rejected_literals_and_identifiers(tmp_path: Path) -> None:
    for source in (
        "nibble x = 012;",
        "nibble x = 1__0;",
        "nibble x = 0b102;",
        "nibble x = 0o8;",
        "nibble int;",
        "nibble café;",
    ):
        with pytest.raises(BadgeSyntaxError):
            parse(source + "\nfn main() { }\n", "bad.badge")

    with pytest.raises(BadgeSyntaxError, match="newline in string literal"):
        parse('const char s[] = "a\nb";\nfn main() { }\n', "bad.badge")

    with pytest.raises(BadgeSyntaxError, match="NUL is not allowed"):
        parse('const char s[] = "a\\0b";\nfn main() { }\n', "bad.badge")


def test_byte_alias_and_trailing_commas(tmp_path: Path) -> None:
    compiler, emu = build(
        tmp_path,
        """
        byte b;

        fn nibble add(nibble a, nibble b,) {
            return a + b;
        }

        fn main() {
            b = add(1, 2,);
        }
        """,
    )
    assert value(compiler, emu, "b") == 3


def test_inline_asm_comment_with_brace(tmp_path: Path) -> None:
    program = parse(
        """
        fn main() {
            nibble x;
            asm {
                ; a comment with } and ${x}
                MOV R1, 1
            }
        }
        """,
        "asm.badge",
    )
    inline = program.functions[0].body.statements[1]
    assert "a comment with }" in inline.text
    assert "MOV R1, 1" in inline.text


def test_unary_plus(tmp_path: Path) -> None:
    compiler, emu = build(
        tmp_path,
        """
        nibble a;
        uint16_t b;

        fn main() {
            a = +1;
            b = +(1 << 8);
        }
        """,
    )
    assert value(compiler, emu, "a") == 1
    assert value(compiler, emu, "b") == 256


def test_rejects_local_const_arrays(tmp_path: Path) -> None:
    with pytest.raises(BadgeTypeError, match="local const array"):
        Compiler(
            load_source(
                """
                fn main() {
                    const nibble values[2] = {1, 2};
                }
                """,
                filename=str(tmp_path / "const.badge"),
            ),
            str(tmp_path / "const.badge"),
        ).compile()


def test_rejects_nonconstant_array_length(tmp_path: Path) -> None:
    with pytest.raises(BadgeCompileError, match="compile-time integer constant"):
        Compiler(
            load_source(
                """
                nibble n;
                nibble values[n];
                nibble sink;
                fn main() {
                    sink = values[0];
                }
                """,
                filename=str(tmp_path / "len.badge"),
            ),
            str(tmp_path / "len.badge"),
        ).compile()


def test_rejects_oversized_string_initializer(tmp_path: Path) -> None:
    with pytest.raises(BadgeCompileError, match="does not fit"):
        Compiler(
            load_source(
                """
                fn main() {
                    char text[2] = "hi";
                }
                """,
                filename=str(tmp_path / "str.badge"),
            ),
            str(tmp_path / "str.badge"),
        ).compile()
