"""Tests for GPIO, SFR helpers, and RAM-array runtime routines."""

from __future__ import annotations

from pathlib import Path

from badgec.assembler import assemble_file
from badgec.compiler import Compiler
from badgec.emulator import Emulator
from badgec.parser import parse


def build(tmp_path: Path, source: str) -> tuple[Compiler, Path]:
    source_path = tmp_path / "prog.badge"
    source_path.write_text(source)
    compiler = Compiler(parse(source, str(source_path)), str(source_path))
    asm_path = tmp_path / "prog.asm"
    asm_path.write_text(compiler.compile())
    hex_path = tmp_path / "prog.hex"
    assemble_file(asm_path, hex_path)
    return compiler, hex_path


def run(hex_path: Path, steps: int = 100000, input_value: int | None = None) -> Emulator:
    emu = Emulator()
    emu.load_hex(hex_path)
    if input_value is not None:
        emu.ram[0x0B] = input_value
    emu.run(steps)
    return emu


def addr(compiler: Compiler, name: str) -> int:
    symbol = compiler.globals[name]
    assert symbol.address is not None
    return symbol.address


def test_gpio_output_set_clear_toggle_and_test(tmp_path: Path) -> None:
    compiler, hex_path = build(
        tmp_path,
        """
        nibble readback;
        nibble bit;
        fn main() {
            gpio_write(5);
            readback = gpio_read();
            gpio_set(2);
            gpio_clear(1);
            gpio_toggle(8);
            bit = gpio_test(8);
        }
        """,
    )
    emu = run(hex_path, input_value=9)
    assert emu.ram[addr(compiler, "readback")] == 9
    assert emu.ram[addr(compiler, "bit")] == 1
    # 5 -> 7 -> 6 -> 14
    assert emu.ram[0x0A] == 14


def test_display_page_and_poke_peek(tmp_path: Path) -> None:
    compiler, hex_path = build(
        tmp_path,
        """
        nibble value;
        fn main() {
            display_page(8);
            display_poke(8, 0, 15);
            value = display_peek(8, 0);
        }
        """,
    )
    emu = run(hex_path)
    assert emu.ram[0xF0] == 8
    assert emu.ram[0x80] == 15
    assert emu.ram[addr(compiler, "value")] == 15


def test_memset_and_uart_write(tmp_path: Path) -> None:
    compiler, hex_path = build(
        tmp_path,
        """
        char buf[4];
        fn main() {
            memset(buf, 65, 4);
            uart_write(buf, 4);
        }
        """,
    )
    emu = run(hex_path)
    base = addr(compiler, "buf")
    assert [emu.ram[base + i] for i in range(8)] == [1, 4, 1, 4, 1, 4, 1, 4]
    assert emu.uart_tx == [65, 65, 65, 65]


def test_nibble_memset_and_system_sfr_helpers(tmp_path: Path) -> None:
    compiler, hex_path = build(
        tmp_path,
        """
        nibble buf[4];
        nibble rnd;
        nibble ks;
        nibble kc;
        nibble any;
        fn main() {
            memset(buf, 9, 4);
            seed(3);
            rnd = random();
            dimmer(7);
            ks = key_status();
            kc = key_code();
            any = key_any();
        }
        """,
    )
    emu = run(hex_path)
    base = addr(compiler, "buf")
    assert [emu.ram[base + i] for i in range(4)] == [9, 9, 9, 9]
    assert emu.ram[addr(compiler, "rnd")] == 3  # emulator stores the seed value
    assert emu.ram[0xFE] == 7
    assert emu.ram[addr(compiler, "ks")] == 0
    assert emu.ram[addr(compiler, "kc")] == 0
    assert emu.ram[addr(compiler, "any")] == 0


def test_gpio_honors_iopos_alternate_registers(tmp_path: Path) -> None:
    compiler, hex_path = build(
        tmp_path,
        """
        nibble readback;
        fn main() {
            readback = gpio_read();
            gpio_write(5);
            gpio_set(2);
        }
        """,
    )
    emu = Emulator()
    emu.load_hex(hex_path)
    emu.ram[0xF3] = 2      # IOPos=1: use InB/OutB
    emu.ram[0xFB] = 7
    emu.run(100000)
    assert emu.ram[addr(compiler, "readback")] == 7
    assert emu.ram[0xFA] == 7  # 5 -> 7
    assert emu.ram[0x0A] == 0  # OUT is R10 when IOPos=1


def test_memcpy_for_nibble_and_char_arrays(tmp_path: Path) -> None:
    compiler, hex_path = build(
        tmp_path,
        """
        nibble a[4];
        nibble b[4];
        char c[4];
        char d[4];
        fn main() {
            memset(a, 3, 4);
            memcpy(b, a, 4);
            memset(c, 65, 4);
            memcpy(d, c, 4);
        }
        """,
    )
    emu = run(hex_path)
    a = addr(compiler, "a")
    b = addr(compiler, "b")
    c = addr(compiler, "c")
    d = addr(compiler, "d")
    assert [emu.ram[a + i] for i in range(4)] == [3, 3, 3, 3]
    assert [emu.ram[b + i] for i in range(4)] == [3, 3, 3, 3]
    assert [emu.ram[c + i] for i in range(8)] == [1, 4, 1, 4, 1, 4, 1, 4]
    assert [emu.ram[d + i] for i in range(8)] == [1, 4, 1, 4, 1, 4, 1, 4]


def test_wrflags_helpers_preserve_other_bits(tmp_path: Path) -> None:
    compiler, hex_path = build(
        tmp_path,
        """
        fn main() {
            uart_route(1);
            gpio_alt(1);
            leds_enable(1);
            matrix_enable(1);
            dimmer(15);
        }
        """,
    )
    emu = run(hex_path)
    assert emu.ram[0xF3] == 0b0011  # uart_route + gpio_alt
    # Now clear them again.
    source = """
        fn main() {
            uart_route(0);
            gpio_alt(0);
            leds_enable(0);
            matrix_enable(0);
        }
    """
    clear_dir = tmp_path / "clear"
    clear_dir.mkdir()
    _, hex_path2 = build(clear_dir, source)
    emu2 = Emulator()
    emu2.load_hex(hex_path2)
    emu2.ram[0xF3] = 0b0011
    emu2.run(100000)
    assert emu2.ram[0xF3] == 0b1100  # leds/matrix disabled bits set
