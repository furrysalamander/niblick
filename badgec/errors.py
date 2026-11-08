"""Compiler errors with source locations."""

from __future__ import annotations

import re
from typing import Optional

from .diagnostics import Diagnostic

_LOCATION_RE = re.compile(
    r"^(?P<file>.+?):(?P<line>\d+)(?::(?P<column>\d+))?:\s*(?P<message>.*)$",
    re.DOTALL,
)


class BadgeError(Exception):
    """Base class for user-facing BadgeC errors.

    Existing raise sites may pass a preformatted ``file:line:column:``
    message.  The constructor extracts those fields so callers can consume a
    structured diagnostic without scraping strings.
    """

    def __init__(
        self,
        message: str,
        *,
        file: Optional[str] = None,
        line: int = 0,
        column: int = 1,
        end_line: Optional[int] = None,
        end_column: Optional[int] = None,
        severity: str = "error",
        code: Optional[str] = None,
    ) -> None:
        self.file = file
        self.line = line
        self.column = column
        self.end_line = end_line
        self.end_column = end_column
        self.severity = severity
        self.code = code
        self.message = message

        if self.file is None:
            match = _LOCATION_RE.match(message)
            if match is not None:
                self.file = match.group("file")
                self.line = int(match.group("line"))
                self.column = int(match.group("column") or 1)
                self.message = match.group("message")

        super().__init__(str(self))

    def __str__(self) -> str:
        if self.file and self.line > 0:
            if self.column > 1:
                return f"{self.file}:{self.line}:{self.column}: {self.message}"
            return f"{self.file}:{self.line}: {self.message}"
        return self.message

    def diagnostic(self) -> Diagnostic:
        return Diagnostic(
            file=self.file or "",
            line=max(1, self.line),
            column=max(1, self.column),
            message=self.message,
            severity=self.severity,
            end_line=self.end_line,
            end_column=self.end_column,
            code=self.code,
        )


class BadgeSyntaxError(BadgeError):
    pass


class BadgeTypeError(BadgeError):
    pass


class BadgeCompileError(BadgeError):
    pass


def location(filename: str, line: int, column: int | None = None) -> str:
    if column is None:
        return f"{filename}:{line}"
    return f"{filename}:{line}:{column}"
