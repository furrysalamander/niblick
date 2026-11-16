"""Tests for the browser-facing JSON helpers."""

from __future__ import annotations

import base64
import json
from pathlib import Path

from niblick.web import (
    compile_source_json,
    completions_json,
    emulator_alt_json,
    emulator_key_json,
    list_examples_json,
    emulator_load_json,
    emulator_state_json,
    emulator_step_json,
    read_example_json,
)

ROOT = Path(__file__).resolve().parent.parent


def test_compile_source_json_returns_asm_and_hex(tmp_path: Path) -> None:
    source = (ROOT / "examples" / "hello.nbl").read_text()
    payload = json.loads(
        compile_source_json(
            source,
            filename=str(tmp_path / "hello.nbl"),
            search_paths=[str(ROOT)],
        )
    )
    assert payload["ok"] is True
    assert payload["words"] > 0
    assert payload["ram"] > 0
    assert "fn_main" in payload["asm"]
    data = base64.b64decode(payload["hex"])
    assert data[:6] == bytes((0x00, 0xFF, 0x00, 0xFF, 0xA5, 0xC3))
    assert payload["hex_size"] == len(data)
    assert payload["asm_map"]
    assert any(
        item["file"].endswith("hello.nbl") and item["source_line"] == 7
        for item in payload["asm_map"]
    )
    assert any(
        item["file"].endswith("lib/uart.nbl")
        for item in payload["asm_map"]
    )
    assert any(path.endswith("hello.nbl") for path in payload["sources"])
    assert any(path.endswith("lib/uart.nbl") for path in payload["sources"])


def test_compile_source_json_reports_diagnostics(tmp_path: Path) -> None:
    payload = json.loads(
        compile_source_json(
            "nibble x = ;\nfn main() { }\n",
            filename=str(tmp_path / "bad.nbl"),
            search_paths=[str(ROOT)],
        )
    )
    assert payload["ok"] is False
    diagnostic = payload["diagnostics"][0]
    assert diagnostic["line"] == 1
    assert "expected" in diagnostic["message"]


def test_completions_include_imported_functions(tmp_path: Path) -> None:
    source = (
        'import "lib/uart.nbl";\n'
        "fn main() {\n"
        "    uart_init(0);\n"
        "}\n"
    )
    payload = json.loads(
        completions_json(
            source,
            filename=str(tmp_path / "main.nbl"),
            line=3,
            column=5,
            search_paths=[str(ROOT)],
        )
    )
    assert payload["ok"] is True
    names = {item["name"] for item in payload["items"]}
    assert "uart_init" in names
    assert "uart_puts" in names
    assert "main" in names
    assert "peek" in names


def test_emulator_load_and_step(tmp_path: Path) -> None:
    source = (ROOT / "examples" / "hello.nbl").read_text()
    compiled = json.loads(
        compile_source_json(
            source,
            filename=str(tmp_path / "hello.nbl"),
            search_paths=[str(ROOT)],
        )
    )
    loaded = json.loads(emulator_load_json(compiled["hex"]))
    assert loaded["ok"] is True
    state = loaded["state"]
    assert state["pc"] == 0
    assert len(state["ram"]) == 256
    assert len(state["display_left"]) == 16

    stepped = json.loads(emulator_step_json(1000))
    assert stepped["ok"] is True
    assert stepped["state"]["instructions"] >= 1
    assert "uart_tx" in stepped["state"]

    current = json.loads(emulator_state_json())
    assert current["ok"] is True
    assert current["state"]["pc"] == stepped["state"]["pc"]

    keyed = json.loads(emulator_key_json(1, True))
    assert keyed["ok"] is True
    assert 1 in keyed["state"]["keys_down"]
    released = json.loads(emulator_key_json(1, False))
    assert 1 not in released["state"]["keys_down"]
    alt = json.loads(emulator_alt_json(True))
    assert alt["state"]["alt_down"] is True
    alt = json.loads(emulator_alt_json(False))
    assert alt["state"]["alt_down"] is False


def test_example_fallbacks(tmp_path: Path) -> None:
    examples = tmp_path / "examples"
    examples.mkdir()
    (examples / "hello.nbl").write_text("fn main() { }\n")
    listed = json.loads(list_examples_json(str(tmp_path)))
    assert listed["ok"] is True
    assert listed["items"] == [{"name": "hello", "path": "hello.nbl"}]
    read = json.loads(read_example_json("hello.nbl", str(tmp_path)))
    assert read["ok"] is True
    assert "fn main" in read["source"]
