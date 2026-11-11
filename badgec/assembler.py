"""Thin wrapper around the ``supercon6-assembler`` package."""

from __future__ import annotations

import contextlib
import io
import re
from pathlib import Path

from .errors import BadgeCompileError

try:
    import assemble as _assemble
except ImportError:  # pragma: no cover - exercised only when the dependency is missing
    _assemble = None

_SOURCE_MARKER_RE = re.compile(
    r";\s*@badgec-src\s+(?P<file>.+):(?P<line>\d+)\s*$"
)
_ASSEMBLER_LINE_RE = re.compile(r"Line\s+(\d+):")

_ASSEMBLER_HINT = (
    "install the supercon6-assembler package, for example: "
    "pip install 'supercon6-assembler @ "
    "git+https://github.com/furrysalamander/2022-Supercon6-Badge-Tools.git"
    "#subdirectory=assembler'"
)


def _assembler_module():
    if _assemble is None:
        raise BadgeCompileError(f"the assembler is not installed; {_ASSEMBLER_HINT}")
    return _assemble


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

    The assembler derives the output name by replacing the source extension
    with .hex.  If *hex_path* is given, the file is moved there.
    """
    asm_path = Path(asm_path).resolve()
    if not asm_path.exists():
        raise BadgeCompileError(f"assembly file not found: {asm_path}")

    assembler = _assembler_module()
    expected = asm_path.with_suffix(".hex")
    if expected.exists():
        expected.unlink()

    # The upstream assembler prints both normal output and errors to stdout.
    # Keep it quiet, then use the captured text for diagnostics.
    assembler.options.show_output = False
    assembler.options.show_verbose = False
    assembler.options.show_wordspace = False
    assembler.options.show_linenums = False
    assembler.options.show_comments = False
    assembler.options.show_assembly = False

    output = io.StringIO()
    with contextlib.redirect_stdout(output):
        result = assembler.parse_asm(
            asm_path.read_text(), hexfile_out=str(expected)
        )

    text = output.getvalue()
    if result is not True or not expected.exists():
        raise _assembler_error(asm_path, text)

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
