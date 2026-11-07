"""Import resolution and dead-declaration tests."""

from __future__ import annotations

from pathlib import Path

import pytest

from badgec.assembler import assemble_file
from badgec.compiler import Compiler
from badgec.emulator import Emulator
from badgec.errors import BadgeCompileError
from badgec.loader import load_program, load_source


def build(tmp_path: Path, source: str, name: str = "main"):
    entry = tmp_path / f"{name}.badge"
    entry.write_text(source)
    program = load_program(entry)
    compiler = Compiler(program, str(entry))
    asm_path = tmp_path / f"{name}.asm"
    asm_path.write_text(compiler.compile())
    hex_path = tmp_path / f"{name}.hex"
    assemble_file(asm_path, hex_path)
    return compiler, hex_path


def test_import_merges_functions(tmp_path: Path) -> None:
    lib = tmp_path / "lib"
    lib.mkdir()
    (lib / "math.badge").write_text(
        """
        fn nibble twice(nibble n) {
            return n + n;
        }
        """
    )
    compiler, hex_path = build(
        tmp_path,
        """
        import "lib/math.badge";
        nibble result;
        fn main() {
            result = twice(3);
        }
        """,
    )
    emu = Emulator()
    emu.load_hex(hex_path)
    emu.run(10000)
    address = compiler.globals["result"].address
    assert address is not None
    assert emu.ram[address] == 6


def test_nested_imports_are_loaded_once(tmp_path: Path) -> None:
    lib = tmp_path / "lib"
    lib.mkdir()
    (lib / "base.badge").write_text(
        "fn nibble inc(nibble n) { return n + 1; }\n"
    )
    (lib / "first.badge").write_text(
        'import "base.badge";\n'
        "fn nibble twice_inc(nibble n) { return inc(inc(n)); }\n"
    )
    (lib / "second.badge").write_text(
        'import "base.badge";\n'
        "fn nibble plus_two(nibble n) { return inc(inc(n)); }\n"
    )
    compiler, hex_path = build(
        tmp_path,
        """
        import "lib/first.badge";
        import "lib/second.badge";
        nibble a;
        nibble b;
        fn main() {
            a = twice_inc(1);
            b = plus_two(2);
        }
        """,
    )
    emu = Emulator()
    emu.load_hex(hex_path)
    emu.run(10000)
    assert emu.ram[compiler.globals["a"].address] == 3
    assert emu.ram[compiler.globals["b"].address] == 4


def test_import_cycle_is_reported(tmp_path: Path) -> None:
    (tmp_path / "a.badge").write_text('import "b.badge";\nfn void a() { }\n')
    (tmp_path / "b.badge").write_text('import "a.badge";\nfn void b() { }\n')
    with pytest.raises(BadgeCompileError, match="import cycle"):
        load_program(tmp_path / "a.badge")


def test_missing_import_is_reported(tmp_path: Path) -> None:
    entry = tmp_path / "main.badge"
    entry.write_text('import "nope.badge";\nfn main() { }\n')
    with pytest.raises(BadgeCompileError, match="cannot find import"):
        load_program(entry)


def test_unused_imported_declarations_disappear(tmp_path: Path) -> None:
    lib = tmp_path / "lib"
    lib.mkdir()
    (lib / "help.badge").write_text(
        """
        const nibble unused_table[] = { 1, 2, 3 };
        nibble unused_global;
        fn void unused_function() {
            unused_global = 1;
        }
        fn nibble used(nibble n) {
            return n;
        }
        """
    )
    compiler, hex_path = build(
        tmp_path,
        """
        import "lib/help.badge";
        nibble result;
        fn main() {
            result = used(7);
        }
        """,
    )
    assert "unused_global" not in compiler.globals
    assert "unused_table" not in compiler.globals
    assert "unused_function" not in compiler.functions

    emu = Emulator()
    emu.load_hex(hex_path)
    emu.run(10000)
    assert emu.ram[compiler.globals["result"].address] == 7


def test_load_source_resolves_relative_imports(tmp_path: Path) -> None:
    lib = tmp_path / "lib"
    lib.mkdir()
    (lib / "inc.badge").write_text(
        "fn nibble inc(nibble n) {\n    nibble r;\n    r = n + 1;\n    return r;\n}\n"
    )
    program = load_source(
        'import "lib/inc.badge";\nnibble x;\nfn main() { x = inc(4); }\n',
        filename=str(tmp_path / "virtual.badge"),
    )
    compiler = Compiler(program, str(tmp_path / "virtual.badge"))
    compiler.compile()
    assert "inc" in compiler.functions
