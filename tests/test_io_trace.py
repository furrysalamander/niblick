"""I/O-port tracing and fake input-port helpers."""

from __future__ import annotations

from pathlib import Path

from badgec.assembler import assemble_file
from badgec.cli import main
from badgec.compiler import Compiler
from badgec.emulator import Emulator
from badgec.parser import parse


def build(tmp_path: Path, source: str, name: str = "io") -> Path:
    path = tmp_path / f"{name}.badge"
    path.write_text(source)
    compiler = Compiler(parse(source, str(path)), str(path))
    asm_path = tmp_path / f"{name}.asm"
    asm_path.write_text(compiler.compile())
    hex_path = tmp_path / f"{name}.hex"
    assemble_file(asm_path, hex_path)
    return hex_path


def test_trace_records_port_writes_and_bit_operations(tmp_path: Path) -> None:
    hex_path = build(
        tmp_path,
        """
        nibble r;
        fn main() {
            gpio_write(5);
            gpio_set(1);
            gpio_clear(2);
            gpio_toggle(4);
            r = gpio_test(8);
        }
        """,
    )
    emu = Emulator()
    emu.load_hex(hex_path)
    emu.trace_io()
    emu.run(1000)

    events = emu.io_trace
    assert events is not None
    kinds = [event.kind for event in events]
    assert kinds == ["write", "bit", "bit", "bit", "read"]
    assert events[0].address == 0x0A
    assert (events[0].before, events[0].after) == (0, 5)
    assert events[1].bit == 0
    assert (events[1].before, events[1].after) == (5, 5)
    assert events[2].bit == 1
    assert (events[2].before, events[2].after) == (5, 5)
    assert events[3].bit == 2
    assert (events[3].before, events[3].after) == (5, 1)
    assert events[4].address == 0x0B
    assert events[4].bit == 3


def test_trace_honors_iopos_and_fake_input(tmp_path: Path) -> None:
    hex_path = build(
        tmp_path,
        """
        nibble r;
        fn main() {
            gpio_set(1);
            r = gpio_test(4);
        }
        """,
    )
    emu = Emulator()
    emu.load_hex(hex_path)
    emu.ram[0xF3] = 2  # WrFlags.IOPos = 1
    emu.set_input(4, bank=1)
    emu.trace_io()
    emu.run(1000)

    events = emu.io_trace or []
    assert events[0].kind == "bit"
    assert events[0].address == 0xFA
    assert events[1].kind == "read"
    assert events[1].address == 0xFB
    assert events[1].after == 4


def test_set_input_writes_both_banks_by_default() -> None:
    emu = Emulator()
    emu.set_input(7)
    assert emu.ram[0x0B] == 7
    assert emu.ram[0xFB] == 7
    emu.set_input(2, bank=0)
    assert emu.ram[0x0B] == 2
    assert emu.ram[0xFB] == 7
    emu.set_input(3, bank=1)
    assert emu.ram[0x0B] == 2
    assert emu.ram[0xFB] == 3


def test_trace_limit_keeps_total_count(tmp_path: Path) -> None:
    hex_path = build(
        tmp_path,
        """
        fn main() {
            gpio_set(1);
            gpio_clear(1);
            gpio_toggle(1);
            gpio_set(2);
        }
        """,
        "limit",
    )
    emu = Emulator()
    emu.load_hex(hex_path)
    emu.trace_io(limit=2)
    emu.run(1000)
    assert emu.io_trace is not None
    assert len(emu.io_trace) == 2
    assert emu.io_trace_total == 4


def test_trace_is_disabled_by_default(tmp_path: Path) -> None:
    hex_path = build(tmp_path, "fn main() { gpio_set(1); }", "off")
    emu = Emulator()
    emu.load_hex(hex_path)
    emu.run(1000)
    assert emu.io_trace is None


def test_cli_trace_io_output(tmp_path: Path, capsys) -> None:
    source = tmp_path / "trace.badge"
    source.write_text(
        """
        fn main() {
            gpio_write(5);
            gpio_set(1);
        }
        """
    )
    assert main([str(source), "--trace-io", "--io-trace-limit", "10"]) == 0
    out = capsys.readouterr().out
    assert "I/O trace:" in out
    assert "write 0x0A" in out
    assert "bit   0x0A" in out
