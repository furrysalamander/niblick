"""Tests for imported .asm modules and extern function declarations."""

from __future__ import annotations

from pathlib import Path

import pytest

from badgec.assembler import assemble_file, code_words
from badgec.compiler import Compiler
from badgec.emulator import Emulator
from badgec.errors import BadgeCompileError
from badgec.loader import load_program, load_source


def build(tmp_path: Path, source: str, asm: dict[str, str], name: str = "main"):
    for filename, text in asm.items():
        path = tmp_path / filename
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text)

    entry = tmp_path / f"{name}.badge"
    entry.write_text(source)
    compiler = Compiler(load_program(entry), str(entry))
    asm_text = compiler.compile()
    asm_path = tmp_path / f"{name}.asm"
    asm_path.write_text(asm_text)
    hex_path = tmp_path / f"{name}.hex"
    assemble_file(asm_path, hex_path)
    return compiler, asm_text, hex_path


def run(hex_path: Path, steps: int = 10000) -> Emulator:
    emu = Emulator()
    emu.load_hex(hex_path)
    emu.run(max_steps=steps)
    return emu


def test_extern_function_runs_and_reads_parameter(tmp_path: Path) -> None:
    compiler, _, hex_path = build(
        tmp_path,
        """
        import "add.asm";
        extern fn nibble add3(nibble x);
        nibble result;
        fn main() {
            result = add3(4);
            while (1) { }
        }
        """,
        {
            "add.asm": """
            ; nibble add3(nibble x)
            fn_add3:
                MOV R0, [${x}]
                ADD R0, 3
                MOV R1, R0
                RET R0, 0
            """
        },
    )
    emu = run(hex_path)
    address = compiler.globals["result"].address
    assert address is not None
    assert emu.ram[address] == 7
    assert "fn_add3:" in compiler.asm_text
    assert compiler.functions["add3"].decl.is_extern


def test_char_parameter_uses_two_nibbles(tmp_path: Path) -> None:
    compiler, _, hex_path = build(
        tmp_path,
        """
        import "high.asm";
        extern fn nibble high_nibble_of(char value);
        nibble result;
        fn main() {
            result = high_nibble_of(0xA5);
            while (1) { }
        }
        """,
        {
            "high.asm": """
            fn_high_nibble_of:
                MOV R0, [${value+1}]
                MOV R1, R0
                RET R0, 0
            """
        },
    )
    emu = run(hex_path)
    address = compiler.globals["result"].address
    assert address is not None
    assert emu.ram[address] == 0xA


def test_asm_runtime_call_is_linked_and_emits_uart(tmp_path: Path) -> None:
    compiler, _, hex_path = build(
        tmp_path,
        """
        import "emit.asm";
        import "lib/uart.badge";
        extern fn void emit(char value);
        fn main() {
            uart_init(3);
            emit('A');
            while (1) { }
        }
        """,
        {
            "emit.asm": """
            fn_emit:
                MOV R0, [${value}]
                MOV R1, R0
                MOV R0, [${value+1}]
                MOV R2, R0
                GOSUB __bc_uart_putc
                RET R0, 0
            """
        },
    )
    emu = run(hex_path)
    assert b"A" in bytes(emu.uart_tx)
    assert "__bc_uart_putc" in compiler.linked_runtime


def test_asm_can_call_c_function_and_dce_keeps_it(tmp_path: Path) -> None:
    compiler, asm_text, hex_path = build(
        tmp_path,
        """
        import "call.asm";
        extern fn void call_helper();
        nibble result;
        fn void helper() {
            result = 9;
        }
        fn main() {
            call_helper();
            while (1) { }
        }
        """,
        {
            "call.asm": """
            fn_call_helper:
                GOSUB fn_helper
                RET R0, 0
            """
        },
    )
    assert "helper" in compiler.functions
    assert "fn_helper:" in asm_text
    emu = run(hex_path)
    address = compiler.globals["result"].address
    assert address is not None
    assert emu.ram[address] == 9


def test_global_placeholder_keeps_global_alive(tmp_path: Path) -> None:
    compiler, _, hex_path = build(
        tmp_path,
        """
        import "store.asm";
        extern fn void store(nibble value);
        nibble target;
        fn main() {
            store(6);
            while (1) { }
        }
        """,
        {
            "store.asm": """
            fn_store:
                MOV R0, [${value}]
                MOV [${target}], R0
                RET R0, 0
            """
        },
    )
    assert "target" in compiler.globals
    emu = run(hex_path)
    address = compiler.globals["target"].address
    assert address is not None
    assert emu.ram[address] == 6


def test_const_array_placeholder_uses_flash_label(tmp_path: Path) -> None:
    _, _, hex_path = build(
        tmp_path,
        """
        import "print.asm";
        import "lib/uart.badge";
        const char msg[] = "Hi";
        extern fn void print_msg();
        fn main() {
            uart_init(3);
            print_msg();
            while (1) { }
        }
        """,
        {
            "print.asm": """
            fn_print_msg:
                MOV R1, LOW ${msg}
                MOV R2, MID ${msg}
                MOV R3, HIGH ${msg}
                GOSUB __bc_flash_read_char
                GOSUB __bc_uart_putc
                RET R0, 0
            """
        },
    )
    emu = run(hex_path)
    assert b"H" in bytes(emu.uart_tx)


def test_qualified_placeholder_addresses_another_function_param(tmp_path: Path) -> None:
    compiler, _, hex_path = build(
        tmp_path,
        """
        import "call.asm";
        extern fn void call_helper(nibble x);
        nibble result;
        fn void helper(nibble value) {
            result = value + 1;
        }
        fn main() {
            call_helper(5);
            while (1) { }
        }
        """,
        {
            "call.asm": """
            fn_call_helper:
                MOV R0, [${x}]
                MOV [${helper.value}], R0
                GOSUB fn_helper
                RET R0, 0
            """
        },
    )
    emu = run(hex_path)
    address = compiler.globals["result"].address
    assert address is not None
    assert emu.ram[address] == 6


def test_missing_asm_entry_point_is_reported(tmp_path: Path) -> None:
    entry = tmp_path / "main.badge"
    entry.write_text(
        """
        import "empty.asm";
        extern fn void missing();
        fn main() { missing(); }
        """
    )
    (tmp_path / "empty.asm").write_text("; no functions here\n")
    compiler = Compiler(load_program(entry), str(entry))
    with pytest.raises(BadgeCompileError, match="has no fn_missing"):
        compiler.compile()


def test_asm_entry_without_extern_is_reported(tmp_path: Path) -> None:
    entry = tmp_path / "main.badge"
    entry.write_text(
        """
        import "extra.asm";
        fn main() { while (1) { } }
        """
    )
    (tmp_path / "extra.asm").write_text(
        "fn_extra:\n    RET R0, 0\n"
    )
    compiler = Compiler(load_program(entry), str(entry))
    with pytest.raises(BadgeCompileError, match="no extern fn extra"):
        compiler.compile()


def test_unknown_placeholder_is_reported(tmp_path: Path) -> None:
    entry = tmp_path / "main.badge"
    entry.write_text(
        """
        import "bad.asm";
        extern fn void bad();
        fn main() { bad(); }
        """
    )
    (tmp_path / "bad.asm").write_text(
        "fn_bad:\n    MOV R0, [${nope}]\n    RET R0, 0\n"
    )
    compiler = Compiler(load_program(entry), str(entry))
    with pytest.raises(BadgeCompileError, match="unknown asm placeholder"):
        compiler.compile()


def test_raw_pc_write_is_rejected(tmp_path: Path) -> None:
    entry = tmp_path / "main.badge"
    entry.write_text(
        """
        import "bad.asm";
        extern fn void bad();
        fn main() { bad(); }
        """
    )
    (tmp_path / "bad.asm").write_text(
        "fn_bad:\n    MOV JSR, R1\n    RET R0, 0\n"
    )
    compiler = Compiler(load_program(entry), str(entry))
    with pytest.raises(BadgeCompileError, match="raw MOV JSR"):
        compiler.compile()


def test_same_asm_file_is_loaded_once(tmp_path: Path) -> None:
    lib = tmp_path / "lib"
    lib.mkdir()
    (lib / "one.badge").write_text('import "shared.asm";\nextern fn nibble one();\n')
    (lib / "two.badge").write_text('import "shared.asm";\nextern fn nibble two();\n')
    (lib / "shared.asm").write_text(
        """
        fn_one:
            MOV R1, 1
            RET R0, 0
        fn_two:
            MOV R1, 2
            RET R0, 0
        """
    )
    entry = tmp_path / "main.badge"
    entry.write_text(
        """
        import "lib/one.badge";
        import "lib/two.badge";
        nibble a;
        nibble b;
        fn main() {
            a = one();
            b = two();
            while (1) { }
        }
        """
    )
    compiler = Compiler(load_program(entry), str(entry))
    asm = compiler.compile()
    assert asm.count("fn_one:") == 1
    assert len(compiler.program.asm_sources) == 1


def test_file_level_no_optimize_marker_preserves_text(tmp_path: Path) -> None:
    _, asm_text, _ = build(
        tmp_path,
        """
        import "keep.asm";
        extern fn void keep();
        fn main() { keep(); while (1) { } }
        """,
        {
            "keep.asm": """
            ; @badgec: no-optimize
            fn_keep:
                MOV R1, R1
                RET R0, 0
            """
        },
    )
    assert "MOV R1, R1" in asm_text


def test_region_no_optimize_marker_preserves_region(tmp_path: Path) -> None:
    _, asm_text, _ = build(
        tmp_path,
        """
        import "keep.asm";
        extern fn void keep();
        fn main() { keep(); while (1) { } }
        """,
        {
            "keep.asm": """
            fn_keep:
            ; @badgec: no-optimize-begin
                MOV R1, R1
            ; @badgec: no-optimize-end
                MOV R2, R2
                RET R0, 0
            """
        },
    )
    assert "MOV R1, R1" in asm_text
    assert "MOV R2, R2" not in asm_text


def test_w5500_tx_pointer_moved_to_library(tmp_path: Path) -> None:
    entry = tmp_path / "caller.badge"
    entry.write_text(
        """
        import "lib/drivers/w5500.badge";
        word pointer;
        fn main() {
            pointer = w5500_tx_pointer();
            while (1) { }
        }
        """
    )
    compiler = Compiler(load_program(entry), str(entry))
    asm = compiler.compile()
    assert "fn_w5500_tx_pointer:" in asm
    assert "__bc_w5500_tx_pointer:" not in asm
    assert "GOSUB __bc_w5500_spi_xfer_fast" in asm

    asm_path = tmp_path / "caller.asm"
    asm_path.write_text(asm)
    hex_path = tmp_path / "caller.hex"
    assemble_file(asm_path, hex_path)
    assert code_words(hex_path) <= 4096


def test_unused_asm_entry_point_is_stripped(tmp_path: Path) -> None:
    source = Path(__file__).resolve().parent.parent / "examples" / "w5500_probe.badge"
    compiler = Compiler(load_program(source), str(source))
    asm = compiler.compile()
    assert "w5500_tx_pointer" not in compiler.functions
    assert "fn_w5500_tx_pointer:" not in asm


def test_unused_asm_routine_does_not_link_runtime(tmp_path: Path) -> None:
    compiler, asm_text, _ = build(
        tmp_path,
        """
        import "two.asm";
        extern fn void dead();
        extern fn void used();
        fn main() { used(); while (1) { } }
        """,
        {
            "two.asm": """
            fn_dead:
                GOSUB __bc_uart_putc
                RET R0, 0
            fn_used:
                MOV R1, 1
                RET R0, 0
            """
        },
    )
    assert "fn_dead:" not in asm_text
    assert "fn_used:" in asm_text
    assert "__bc_uart_putc" not in compiler.linked_runtime


def test_asm_error_keeps_original_line_number(tmp_path: Path) -> None:
    entry = tmp_path / "main.badge"
    entry.write_text(
        """
        import "lines.asm";
        extern fn void dead();
        extern fn void used();
        fn main() { used(); }
        """
    )
    (tmp_path / "lines.asm").write_text(
        "fn_dead:\n"
        "    RET R0, 0\n"
        "\n"
        "fn_used:\n"
        "    MOV R0, [${bad}]\n"
        "    RET R0, 0\n"
    )
    compiler = Compiler(load_program(entry), str(entry))
    with pytest.raises(BadgeCompileError, match=r"lines\.asm:5: unknown asm placeholder"):
        compiler.compile()
