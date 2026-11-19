"""Documentation coverage and navigation checks."""

from __future__ import annotations

import re
from pathlib import Path

from niblick.compiler import BUILTINS

from tools.check_docs import main as check_docs_main

ROOT = Path(__file__).resolve().parent.parent
DOCS = ROOT / "docs"

LIB_PAGES = {
    "audio.nbl": "audio",
    "display.nbl": "display",
    "fixed.nbl": "fixed-point",
    "font.nbl": "font",
    "gpio.nbl": "gpio",
    "key.nbl": "keys",
    "math.nbl": "math",
    "mem.nbl": "memory",
    "pdm.nbl": "pdm",
    "power.nbl": "power",
    "random.nbl": "random",
    "spi.nbl": "spi",
    "string.nbl": "strings",
    "system.nbl": "system",
    "textscroll.nbl": "textscroll",
    "time.nbl": "time",
    "trig.nbl": "trig",
    "uart.nbl": "uart",
}


def test_docs_style_and_links() -> None:
    assert check_docs_main() == 0


def test_public_library_functions_are_documented() -> None:
    missing: list[str] = []
    for filename, page in LIB_PAGES.items():
        source = (ROOT / "lib" / filename).read_text(encoding="utf-8")
        documented = (DOCS / "standard-library" / f"{page}.md").read_text(
            encoding="utf-8"
        )
        for name in re.findall(r"(?m)^fn\s+\w+\s+(\w+)\s*\(", source):
            if name.startswith("__"):
                continue
            if f"`{name}(" not in documented:
                missing.append(f"{filename}: {name}")
    assert not missing, "Undocumented library functions:\n" + "\n".join(missing)


def test_public_intrinsics_are_documented() -> None:
    documented = (DOCS / "standard-library" / "intrinsics.md").read_text(
        encoding="utf-8"
    )
    missing = [
        name
        for name in sorted(BUILTINS)
        if not name.startswith("__") and f"`{name}(" not in documented
    ]
    assert not missing, "Undocumented intrinsics:\n" + "\n".join(missing)


def test_cli_options_are_documented() -> None:
    source = (ROOT / "niblick" / "cli.py").read_text(encoding="utf-8")
    documented = (DOCS / "getting-started" / "cli.md").read_text(encoding="utf-8")
    options = set(re.findall(r'add_argument\(\s*\n?\s*"([^"]+)"', source))
    missing = [
        option
        for option in sorted(options)
        if option.startswith("--") and f"`{option}" not in documented
    ]
    assert not missing, "Undocumented CLI options:\n" + "\n".join(missing)
