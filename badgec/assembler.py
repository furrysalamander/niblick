"""Thin wrapper around the vendored Supercon.6 assembler."""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

from .errors import BadgeCompileError

ROOT = Path(__file__).resolve().parent.parent
ASSEMBLER = ROOT / "vendor" / "2022-Supercon6-Badge-Tools" / "assembler" / "assemble.py"

_SOURCE_MARKER_RE = re.compile(
    r";\s*@badgec-src\s+(?P<file>.+):(?P<line>\d+)\s*$"
)
_ASSEMBLER_LINE_RE = re.compile(r"Line\s+(\d+):")


def _assembler_error(
    asm_path: Path, output: str
) -> BadgeCompileError:
    lines = [line.strip() for line in output.splitlines() if line.strip()]
    message = "assembler failed"
    for index, line in enumerate(lines):
        if not line.startswith("E::"):
            continue
        parts: list[str] = []
        for detail in lines[index:]:
            if _ASSEMBLER_LINE_RE.search(detail):
                break
            if detail.startswith("E::"):
                detail = detail[3:].strip()
            if detail:
                parts.append(detail)
        message = ": ".join(parts) or "assembler failed"
        break
    else:
        if lines:
            message = lines[0]

    line_match = _ASSEMBLER_LINE_RE.search(output)
    if line_match is not None:
        index = int(line_match.group(1))
        try:
            generated = asm_path.read_text().splitlines()
        except OSError:
            generated = []
        if 0 <= index < len(generated):
            source_match = _SOURCE_MARKER_RE.search(generated[index])
            if source_match is not None:
                return BadgeCompileError(
                    message,
                    file=source_match.group("file").strip(),
                    line=int(source_match.group("line")),
                    column=1,
                )
            message = (
                f"{message} (generated assembly line {index + 1}: "
                f"{generated[index].strip()})"
            )
    return BadgeCompileError(message)


def assemble_file(asm_path: str | Path, hex_path: str | Path | None = None) -> Path:
    """Assemble *asm_path* and return the generated .hex path.

    The upstream assembler derives the output name by replacing the source
    extension with .hex.  If *hex_path* is given, the file is moved there.
    """
    asm_path = Path(asm_path).resolve()
    if not asm_path.exists():
        raise BadgeCompileError(f"assembly file not found: {asm_path}")
    if not ASSEMBLER.exists():
        raise BadgeCompileError(
            f"vendored assembler not found at {ASSEMBLER}; "
            "expected vendor/2022-Supercon6-Badge-Tools/"
        )

    expected = asm_path.with_suffix(".hex")
    if expected.exists():
        expected.unlink()

    proc = subprocess.run(
        [sys.executable, str(ASSEMBLER), "-q", str(asm_path)],
        cwd=str(asm_path.parent),
        capture_output=True,
        text=True,
    )
    output = (proc.stdout or "") + (proc.stderr or "")
    if proc.returncode != 0 or not expected.exists():
        raise _assembler_error(asm_path, output)

    if hex_path is not None:
        hex_path = Path(hex_path)
        if hex_path.resolve() != expected.resolve():
            hex_path.write_bytes(expected.read_bytes())
            expected.unlink()
            return hex_path
    return expected


def code_words(hex_path: str | Path) -> int:
    """Return the number of 12-bit program words in an assembler .hex file."""
    data = Path(hex_path).read_bytes()
    if len(data) < 10:
        raise BadgeCompileError(f"{hex_path}: file is too short to be a badge hex file")
    return data[6] | (data[7] << 8)
