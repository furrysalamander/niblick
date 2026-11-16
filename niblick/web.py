"""Browser-facing helpers for the Niblick web editor.

The functions return JSON strings so a Pyodide caller can pass the result to
JavaScript without keeping Python proxies alive.
"""

from __future__ import annotations

import base64
import json
import tempfile
from pathlib import Path
from typing import Optional

from .analysis import Analysis
from .asm_opt import asm_word_count
from .assembler import assemble_file
from .compiler import Compiler
from .emulator import Emulator
from .errors import NiblickError
from .loader import load_source

WORK_ROOT = "/work"


def _diagnostic(exc: Exception) -> dict:
    if isinstance(exc, NiblickError):
        return {
            "file": exc.file or "",
            "line": max(1, exc.line),
            "column": max(1, exc.column),
            "message": exc.message,
            "severity": exc.severity,
            "code": exc.code or "",
        }
    return {
        "file": "",
        "line": 1,
        "column": 1,
        "message": f"{type(exc).__name__}: {exc}",
        "severity": "error",
        "code": "",
    }


def compile_source_json(
    source: str,
    filename: str = f"{WORK_ROOT}/main.nbl",
    search_paths: Optional[list[str | Path]] = None,
    overrides_json: str = "{}",
) -> str:
    """Compile *source* and return assembly, hex, sizes, and diagnostics."""

    try:
        overrides: dict[str | Path, str] = {
            str(key): str(value)
            for key, value in json.loads(overrides_json or "{}").items()
        }
        program = load_source(
            source,
            filename=filename,
            search_paths=search_paths or [WORK_ROOT],
            source_overrides=overrides or None,
        )
        compiler = Compiler(program, filename)
        asm = compiler.compile()
        with tempfile.TemporaryDirectory(prefix="niblick-web-") as temp:
            asm_path = Path(temp) / "main.asm"
            asm_path.write_text(asm)
            hex_path = Path(temp) / "main.hex"
            assemble_file(asm_path, hex_path)
            hex_data = hex_path.read_bytes()
        payload = {
            "ok": True,
            "filename": filename,
            "asm": asm,
            "hex": base64.b64encode(hex_data).decode("ascii"),
            "hex_size": len(hex_data),
            "words": asm_word_count(asm),
            "ram": compiler.mem.used(),
            "diagnostics": [],
        }
    except Exception as exc:  # noqa: BLE001 - the browser needs a JSON error
        payload = {
            "ok": False,
            "filename": filename,
            "asm": "",
            "hex": "",
            "hex_size": 0,
            "words": 0,
            "ram": 0,
            "diagnostics": [_diagnostic(exc)],
        }
    return json.dumps(payload)


_analysis_cache: dict[tuple[str, tuple[str, ...], str], Analysis] = {}


def _analysis_for_completion(
    filename: str,
    source: str,
    search_paths: tuple[str, ...],
) -> Analysis:
    key = (filename, search_paths, source)
    analysis = _analysis_cache.get(key)
    if analysis is None:
        if len(_analysis_cache) >= 4:
            _analysis_cache.pop(next(iter(_analysis_cache)))
        analysis = Analysis(
            filename,
            source_overrides={filename: source},
            search_paths=list(search_paths),
        )
        _analysis_cache[key] = analysis
    return analysis


def completions_json(
    source: str,
    filename: str = f"{WORK_ROOT}/main.nbl",
    line: int = 1,
    column: int = 1,
    search_paths: Optional[list[str | Path]] = None,
) -> str:
    """Return editor completion symbols for *source* at *line*:*column*."""

    try:
        paths = tuple(str(item) for item in (search_paths or [WORK_ROOT]))
        analysis = _analysis_for_completion(filename, source, paths)
        items = analysis.completions(filename, int(line), int(column))
        payload = {
            "ok": True,
            "items": [
                {
                    "name": item.name,
                    "kind": item.kind,
                    "detail": item.detail,
                    "type": item.type,
                }
                for item in items
            ],
        }
    except Exception as exc:  # noqa: BLE001
        payload = {
            "ok": False,
            "items": [],
            "diagnostics": [_diagnostic(exc)],
        }
    return json.dumps(payload)


_emulator: Optional[Emulator] = None


def _emulator_instance() -> Emulator:
    global _emulator
    if _emulator is None:
        _emulator = Emulator()
    return _emulator


def _state_payload(extra: Optional[dict] = None) -> str:
    state = _emulator_instance().state()
    if extra:
        state.update(extra)
    return json.dumps({"ok": True, "state": state})


def emulator_load_json(hex_b64: str) -> str:
    global _emulator
    try:
        data = base64.b64decode(hex_b64)
        _emulator = Emulator()
        _emulator.load_bytes(data)
        return _state_payload()
    except Exception as exc:  # noqa: BLE001
        return json.dumps({"ok": False, "diagnostics": [_diagnostic(exc)]})


def emulator_step_json(count: int = 1) -> str:
    try:
        emulator = _emulator_instance()
        executed = emulator.run(max(0, int(count)))
        return _state_payload({"executed": executed})
    except Exception as exc:  # noqa: BLE001
        return json.dumps({"ok": False, "diagnostics": [_diagnostic(exc)]})


def emulator_key_json(key: int, down: bool) -> str:
    try:
        emulator = _emulator_instance()
        if down:
            emulator.press_key(int(key))
        else:
            emulator.release_key(int(key))
        return _state_payload()
    except Exception as exc:  # noqa: BLE001
        return json.dumps({"ok": False, "diagnostics": [_diagnostic(exc)]})


def emulator_alt_json(down: bool) -> str:
    try:
        emulator = _emulator_instance()
        if down:
            emulator.press_alt()
        else:
            emulator.release_alt()
        return _state_payload()
    except Exception as exc:  # noqa: BLE001
        return json.dumps({"ok": False, "diagnostics": [_diagnostic(exc)]})


def emulator_input_json(data_b64: str) -> str:
    try:
        data = base64.b64decode(data_b64)
        _emulator_instance().receive_uart(data)
        return _state_payload()
    except Exception as exc:  # noqa: BLE001
        return json.dumps({"ok": False, "diagnostics": [_diagnostic(exc)]})


def emulator_state_json() -> str:
    try:
        return _state_payload()
    except Exception as exc:  # noqa: BLE001
        return json.dumps({"ok": False, "diagnostics": [_diagnostic(exc)]})
