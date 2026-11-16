"""Tests for the browser-facing JSON helpers."""

from __future__ import annotations

import base64
import json
from pathlib import Path

from niblick.web import (
    compile_source_json,
    emulator_load_json,
    emulator_state_json,
    emulator_step_json,
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
