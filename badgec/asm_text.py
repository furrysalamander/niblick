"""Small helpers for imported and inline assembly text.

The compiler treats assembly as text, but it still needs to find ``${...}``
placeholders, metadata markers, labels and call instructions.  Keeping those
scans here keeps code generation, dead-declaration elimination and the
optimizer from growing separate, slightly different parsers.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Iterator

PLACEHOLDER_RE = re.compile(r"\$\{([^}]*)\}")
IDENT_RE = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")
ASM_CALL_RE = re.compile(
    r"\b(?:GOSUB|GOTO)\s+(fn_[A-Za-z0-9_]+)", re.IGNORECASE
)
LABEL_RE = re.compile(r"^\s*([A-Za-z_.][A-Za-z0-9_.]*):\s*$")

NO_OPTIMIZE = "; @badgec: no-optimize"
NO_OPTIMIZE_BEGIN = "; @badgec: no-optimize-begin"
NO_OPTIMIZE_END = "; @badgec: no-optimize-end"


def code_part(line: str) -> str:
    """Return the instruction part of an assembly line (comments removed)."""

    return line.split(";", 1)[0]


@dataclass(frozen=True)
class Placeholder:
    line: int
    start: int
    end: int
    text: str


def iter_placeholders(text: str) -> Iterator[Placeholder]:
    """Yield placeholders from code, ignoring assembly comments."""

    for line_number, line in enumerate(text.splitlines(), 1):
        code = code_part(line)
        for match in PLACEHOLDER_RE.finditer(code):
            yield Placeholder(
                line=line_number,
                start=match.start(),
                end=match.end(),
                text=match.group(1).strip(),
            )


def placeholder_names(text: str) -> set[str]:
    """Return every identifier mentioned inside a placeholder.

    This is deliberately an over-approximation.  Dead-declaration
    elimination only uses it to decide which globals/functions must stay.
    """

    names: set[str] = set()
    for placeholder in iter_placeholders(text):
        names.update(IDENT_RE.findall(placeholder.text))
    return names


def asm_function_references(text: str) -> set[str]:
    """Return BadgeC function names called by ``GOSUB``/``GOTO``."""

    return {
        match.group(1)[3:]
        for line in text.splitlines()
        for match in ASM_CALL_RE.finditer(code_part(line))
    }


def has_file_marker(text: str, marker: str) -> bool:
    """True when *marker* appears on a line by itself."""

    wanted = marker.strip().lower()
    return any(line.strip().lower() == wanted for line in text.splitlines())


def label_name(line: str) -> str | None:
    span = label_span(line)
    return span[0] if span is not None else None


def label_span(line: str) -> tuple[str, int] | None:
    """Return the label name and its 1-based column."""

    match = LABEL_RE.match(code_part(line))
    if match is None:
        return None
    return match.group(1), match.start(1) + 1
