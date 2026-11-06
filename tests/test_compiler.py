"""End-to-end tests for BadgeC: source -> asm -> hex -> emulator."""

from __future__ import annotations

from pathlib import Path

import pytest

from badgec.assembler import assemble_file, code_words
from badgec.compiler import Compiler
from badgec.emulator import Emulator
from badgec.errors import BadgeCompileError, BadgeTypeError
from badgec.parser import parse


def build(tmp_path: Path, source: str, name: str = "prog") -> tuple[Compiler, Path]:
    source_path = tmp_path / f"{name}.badge"
    source_path.write_text(source)
    program = parse(source, str(source_path))
    compiler = Compiler(program, str(source_path))
    asm = compiler.compile()
    asm_path = tmp_path / f"{name}.asm"
    asm_path.write_text(asm)
    hex_path = tmp_path / f"{name}.hex"
    assemble_file(asm_path, hex_path)
    return compiler, hex_path


def run(hex_path: Path, steps: int = 20000, rx: list[int] | None = None) -> Emulator:
    emu = Emulator()
    emu.load_hex(hex_path)
    if rx:
        emu.uart_rx = list(rx)
    emu.run(steps)
    return emu


def ram_nibble(compiler: Compiler, name: str, offset: int = 0) -> int:
    symbol = compiler.globals[name]
    assert symbol.address is not None
    return symbol.address + offset


def test_nibble_loop_and_arithmetic(tmp_path: Path) -> None:
    compiler, hex_path = build(
        tmp_path,
        """
        nibble x;
        fn main() {
            x = 5;
            while (x != 0) {
                x = x - 1;
            }
        }
        """,
    )
    emu = run(hex_path)
    assert emu.ram[ram_nibble(compiler, "x")] == 0
    assert emu.sp == 0
    assert code_words(hex_path) < 4096


def test_char_array_and_char_arithmetic(tmp_path: Path) -> None:
    compiler, hex_path = build(
        tmp_path,
        """
        char buf[4];
        fn main() {
            buf[0] = 65;
            buf[1] = buf[0] + 1;
        }
        """,
    )
    emu = run(hex_path)
    base = ram_nibble(compiler, "buf")
    assert (emu.ram[base], emu.ram[base + 1]) == (1, 4)      # 0x41
    assert (emu.ram[base + 2], emu.ram[base + 3]) == (2, 4)  # 0x42


def test_char_binary_operands(tmp_path: Path) -> None:
    compiler, hex_path = build(
        tmp_path,
        """
        char a;
        char b;
        char add;
        char sub;
        char band;
        char bor;
        char bxor;
        char addc;
        char subc;
        fn main() {
            a = 71;
            b = 2;
            add = a + b;
            sub = a - b;
            band = a & b;
            bor = a | b;
            bxor = a ^ b;
            addc = a + 3;
            subc = a - 3;
        }
        """,
    )
    emu = run(hex_path)

    def value(name: str) -> int:
        base = ram_nibble(compiler, name)
        return emu.ram[base] | (emu.ram[base + 1] << 4)

    assert value("add") == 73
    assert value("sub") == 69
    assert value("band") == 2
    assert value("bor") == 71
    assert value("bxor") == 69
    assert value("addc") == 74
    assert value("subc") == 68


def test_functions_and_tail_recursion(tmp_path: Path) -> None:
    compiler, hex_path = build(
        tmp_path,
        """
        nibble result;
        nibble steps;

        fn nibble add(nibble a, nibble b) {
            return a + b;
        }

        fn nibble count(nibble n, nibble acc) {
            if (n == 0) {
                return acc;
            }
            return count(n - 1, acc + 1);
        }

        fn main() {
            result = add(2, 3);
            steps = count(10, 0);
        }
        """,
    )
    emu = run(hex_path, steps=50000)
    assert emu.ram[ram_nibble(compiler, "result")] == 5
    assert emu.ram[ram_nibble(compiler, "steps")] == 10
    assert emu.sp == 0


def test_non_tail_recursion_is_rejected(tmp_path: Path) -> None:
    source = """
    nibble f(nibble n) {
        if (n == 0) {
            return 1;
        }
        return 1 + f(n - 1);
    }
    fn main() {
        nibble x = f(3);
    }
    """
    source_path = tmp_path / "bad.badge"
    source_path.write_text(source)
    program = parse(source, str(source_path))
    compiler = Compiler(program, str(source_path))
    with pytest.raises(BadgeCompileError, match="non-tail recursion"):
        compiler.compile()


def test_flash_string_iteration(tmp_path: Path) -> None:
    compiler, hex_path = build(
        tmp_path,
        """
        const char msg[] = "ABC";
        flashptr p;
        char c;
        nibble count;

        fn main() {
            count = 0;
            p = msg;
            while (1) {
                c = flash_next(&p);
                if (c == 0xFF) {
                    break;
                }
                count = count + 1;
            }
        }
        """,
    )
    emu = run(hex_path, steps=50000)
    assert emu.ram[ram_nibble(compiler, "count")] == 3
    assert emu.ram[ram_nibble(compiler, "c")] == 0xF
    assert emu.ram[ram_nibble(compiler, "c", 1)] == 0xF


def test_uart_puts_and_echo(tmp_path: Path) -> None:
    compiler, hex_path = build(
        tmp_path,
        """
        char c;
        fn main() {
            uart_init(3);
            uart_puts("Hi");
            while (uart_available() == 0) {
            }
            c = uart_getc();
            uart_putc(c);
        }
        """,
    )
    emu = run(hex_path, steps=50000, rx=[0x41])
    assert emu.uart_tx == [0x48, 0x69, 0x41]
    assert emu.uart_rx == []
    assert emu.ram[0xF5] == 3  # 9600 baud index


def test_for_loop_and_break_continue(tmp_path: Path) -> None:
    compiler, hex_path = build(
        tmp_path,
        """
        nibble sum;
        nibble i;
        fn main() {
            sum = 0;
            for (i = 0; i < 10; i = i + 1) {
                if (i == 3) {
                    continue;
                }
                if (i == 8) {
                    break;
                }
                sum = sum + i;
            }
        }
        """,
    )
    emu = run(hex_path, steps=50000)
    # 0 + 1 + 2 + 4 + 5 + 6 + 7 = 25, but 4-bit arithmetic wraps: 25 & 0xF = 9.
    assert emu.ram[ram_nibble(compiler, "sum")] == 9
    assert emu.ram[ram_nibble(compiler, "i")] == 8


def test_type_errors_are_reported(tmp_path: Path) -> None:
    source = """
    nibble x;
    char c;
    fn main() {
        x = c;
    }
    """
    source_path = tmp_path / "badtype.badge"
    source_path.write_text(source)
    program = parse(source, str(source_path))
    compiler = Compiler(program, str(source_path))
    with pytest.raises(BadgeTypeError, match="cannot convert char to nibble"):
        compiler.compile()


def test_const_nibble_table_after_char_table(tmp_path: Path) -> None:
    """Regression test for the assembler's BYTE label-count bug.

    BadgeC emits flash char data as NIBBLE directives so a later label is
    resolved to the correct 12-bit address.
    """
    compiler, hex_path = build(
        tmp_path,
        """
        const char message[] = "ABC";
        const nibble digits[] = { 1, 2, 3, 4 };
        nibble value;
        fn main() {
            value = digits[2];
        }
        """,
    )
    emu = run(hex_path)
    assert emu.ram[ram_nibble(compiler, "value")] == 3


def test_peek_poke_and_out_in(tmp_path: Path) -> None:
    compiler, hex_path = build(
        tmp_path,
        """
        nibble value;
        nibble port;
        fn main() {
            poke(0x20, 9);
            value = peek(0x20);
            out(5);
            port = in();
        }
        """,
    )
    emu = run(hex_path)
    assert emu.ram[ram_nibble(compiler, "value")] == 9
    assert emu.ram[0x0A] == 5
    assert emu.ram[ram_nibble(compiler, "port")] == emu.ram[0x0B]


def test_program_size_is_reported_and_within_budget(tmp_path: Path) -> None:
    _, hex_path = build(
        tmp_path,
        """
        fn main() {
            nibble i = 0;
            while (i != 10) {
                i = i + 1;
            }
        }
        """,
    )
    assert 0 < code_words(hex_path) <= 4096


def test_constant_folding_reduces_code(tmp_path: Path) -> None:
    compiler, hex_path = build(
        tmp_path,
        """
        nibble x;
        nibble y;
        fn main() {
            x = 3 + 4;
            y = 10 < 5;
        }
        """,
    )
    asm = (tmp_path / "prog.asm").read_text()
    assert "MOV R1, 7" in asm
    assert "MOV R1, 0" in asm
    emu = run(hex_path)
    assert emu.ram[ram_nibble(compiler, "x")] == 7
    assert emu.ram[ram_nibble(compiler, "y")] == 0


def test_random_flash_reads(tmp_path: Path) -> None:
    compiler, hex_path = build(
        tmp_path,
        """
        const char msg[] = "Hi";
        const nibble nums[] = { 5, 6, 7 };
        char c;
        nibble n;
        fn main() {
            c = flash_read_char(msg);
            n = flash_read_nibble(nums);
        }
        """,
    )
    emu = run(hex_path)
    c_addr = ram_nibble(compiler, "c")
    assert (emu.ram[c_addr], emu.ram[c_addr + 1]) == (8, 4)  # 'H'
    assert emu.ram[ram_nibble(compiler, "n")] == 5


def test_flash_array_index_with_variable(tmp_path: Path) -> None:
    compiler, hex_path = build(
        tmp_path,
        """
        const char msg[] = "ABC";
        char c;
        nibble i;
        fn main() {
            i = 1;
            c = msg[i];
        }
        """,
    )
    emu = run(hex_path)
    c_addr = ram_nibble(compiler, "c")
    assert (emu.ram[c_addr], emu.ram[c_addr + 1]) == (2, 4)  # 'B'


def test_char_array_index_with_char_index(tmp_path: Path) -> None:
    compiler, hex_path = build(
        tmp_path,
        """
        char buf[32];
        char i;
        fn main() {
            i = 20;
            buf[i] = 65;
        }
        """,
    )
    emu = run(hex_path)
    base = ram_nibble(compiler, "buf")
    assert (emu.ram[base + 40], emu.ram[base + 41]) == (1, 4)  # buf[20] = 0x41


def test_small_return_function_is_inlined(tmp_path: Path) -> None:
    compiler, hex_path = build(
        tmp_path,
        """
        nibble result;
        fn nibble add(nibble a, nibble b) {
            return a + b;
        }
        fn main() {
            result = add(2, 3);
        }
        """,
    )
    asm = (tmp_path / "prog.asm").read_text()
    assert "fn_add" not in asm
    assert "fn_add" not in compiler.functions
    emu = run(hex_path)
    assert emu.ram[ram_nibble(compiler, "result")] == 5


def test_inliner_does_not_duplicate_side_effects(tmp_path: Path) -> None:
    # `twice(x)` uses its parameter twice, so a call argument with a side
    # effect must not be inlined.
    compiler, hex_path = build(
        tmp_path,
        """
        nibble calls;
        nibble result;

        fn nibble bump() {
            calls = calls + 1;
            return 1;
        }

        fn nibble twice(nibble x) {
            return x + x;
        }

        fn main() {
            calls = 0;
            result = twice(bump());
        }
        """,
    )
    emu = run(hex_path, steps=50000)
    assert emu.ram[ram_nibble(compiler, "calls")] == 1
    assert emu.ram[ram_nibble(compiler, "result")] == 2
