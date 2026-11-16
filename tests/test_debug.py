"""Tests for the emulator debug service and debug map."""

from __future__ import annotations

from pathlib import Path

from niblick.assembler import assemble_file
from niblick.compiler import Compiler
from niblick.debug import DebugService, DebugSession
from niblick.loader import load_program


def build(tmp_path: Path):
    entry = tmp_path / "main.nbl"
    entry.write_text(
        "nibble x;\n"
        "fn main() {\n"
        "    nibble local;\n"
        "    local = 5;\n"
        "    x = 1;\n"
        "    x = 2;\n"
        "    while (1) { }\n"
        "}\n"
    )
    compiler = Compiler(load_program(entry), str(entry))
    asm = compiler.compile()
    asm_path = tmp_path / "main.asm"
    asm_path.write_text(asm)
    hex_path = tmp_path / "main.hex"
    assemble_file(asm_path, hex_path)
    debug_map = compiler.debug_map()
    return entry, hex_path, debug_map


def test_breakpoint_stops_on_source_line(tmp_path: Path) -> None:
    entry, hex_path, debug_map = build(tmp_path)
    session = DebugSession(hex_path, debug_map)
    verified = session.set_breakpoints(
        [{"file": str(entry.resolve()), "line": 6}]
    )
    assert verified[0]["verified"]
    state = session.continue_execution()
    assert state["reason"] == "breakpoint"
    assert state["line"] == 6


def test_debug_variables_and_evaluate(tmp_path: Path) -> None:
    entry, hex_path, debug_map = build(tmp_path)
    session = DebugSession(hex_path, debug_map)
    session.set_breakpoints([{"file": str(entry.resolve()), "line": 6}])
    session.continue_execution()
    globals_list = session.globals()
    value = next(item for item in globals_list if item["name"] == "x")
    assert value["value"] == 1
    locals_list = session.locals()
    local = next(item for item in locals_list if item["name"] == "local")
    assert local["value"] == 5
    assert session.evaluate("x")["result"] == 1
    assert session.evaluate("local")["result"] == 5
    assert session.evaluate("local + 1")["result"] == 6
    assert session.evaluate("R1")["result"] in range(16)


def test_frame_contains_current_source(tmp_path: Path) -> None:
    entry, hex_path, debug_map = build(tmp_path)
    session = DebugSession(hex_path, debug_map)
    session.set_breakpoints([{"file": str(entry.resolve()), "line": 6}])
    session.continue_execution()
    frames = session.stack_frames()
    assert frames[0]["name"] == "main"
    assert frames[0]["line"] == 6


def test_debug_service_json_dispatch(tmp_path: Path) -> None:
    entry, hex_path, debug_map = build(tmp_path)
    service = DebugService()
    state = service.dispatch(
        "load", {"hex": str(hex_path), "map": debug_map}
    )
    assert state["reason"] == "entry"
    service.dispatch(
        "setBreakpoints",
        {"breakpoints": [{"file": str(entry), "line": 6}]},
    )
    state = service.dispatch("continue", {})
    assert state["reason"] == "breakpoint"
    assert service.dispatch("evaluate", {"expression": "x"})["result"] == 1
    assert service.dispatch("evaluate", {"expression": "local + 2"})["result"] == 7
