"""Structured diagnostics shared by the CLI, LSP, and assembler wrapper."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class Diagnostic:
    file: str
    line: int
    column: int = 1
    message: str = ""
    severity: str = "error"
    end_line: Optional[int] = None
    end_column: Optional[int] = None
    code: Optional[str] = None

    def to_dict(self) -> dict:
        data = {
            "file": self.file,
            "line": self.line,
            "column": self.column,
            "severity": self.severity,
            "message": self.message,
        }
        if self.end_line is not None:
            data["end_line"] = self.end_line
        if self.end_column is not None:
            data["end_column"] = self.end_column
        if self.code is not None:
            data["code"] = self.code
        return data
