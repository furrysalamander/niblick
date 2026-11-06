"""Compiler errors with source locations."""

from __future__ import annotations


class BadgeError(Exception):
    """Base class for user-facing BadgeC errors."""


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
