"""Build a PC-to-source map for the BadgeC debugger."""

from __future__ import annotations

import re
from typing import Any

from .asm_opt import _word_size
from .asm_text import label_span

_SOURCE_RE = re.compile(r";\s*@badgec-src\s+(?P<file>.+):(?P<line>\d+)\s*$")
_SOURCE_END_RE = re.compile(r";\s*@badgec-src-end\s*$")


def build_debug_map(asm_text: str, compiler) -> dict[str, Any]:
    lines = asm_text.splitlines()
    labels: dict[str, int] = {}
    source_map: dict[str, dict[str, list[int]]] = {}
    pc_source: dict[str, list[Any]] = {}
    current_source: tuple[str, int] | None = None

    address = 0
    for line in lines:
        span = label_span(line)
        if span is not None:
            labels[span[0]] = address
        marker = _SOURCE_RE.search(line)
        if marker is not None:
            current_source = (
                marker.group("file").strip(),
                int(marker.group("line")),
            )
        elif _SOURCE_END_RE.search(line):
            current_source = None

        size = _word_size(line)
        if size > 0 and current_source is not None:
            file, source_line = current_source
            per_file = source_map.setdefault(file, {})
            addresses = per_file.setdefault(str(source_line), [])
            for offset in range(size):
                pc_source[str(address + offset)] = [file, source_line]
            addresses.append(address)
        address += size

    functions: dict[str, Any] = {}
    try:
        sizes = compiler.code_sizes()["functions"]
    except Exception:
        sizes = {}
    for name, fn in compiler.functions.items():
        start = labels.get(fn.label)
        if start is None:
            continue
        functions[name] = {
            "label": fn.label,
            "start_pc": start,
            "end_pc": start + sizes.get(name, 0),
            "params": [
                {
                    "name": param.name,
                    "type": str(param.type),
                    "address": param.address,
                }
                for param in fn.params
            ],
        }

    globals_map: dict[str, Any] = {}
    for name, symbol in compiler.globals.items():
        globals_map[name] = {
            "type": str(symbol.type),
            "address": symbol.address,
            "array_len": symbol.array_len,
            "const": symbol.is_const,
            "value": symbol.const_value,
            "flash_label": symbol.flash_label,
        }

    return {
        "source": source_map,
        "pc_source": pc_source,
        "functions": functions,
        "globals": globals_map,
        "labels": labels,
        "total_words": address,
    }
