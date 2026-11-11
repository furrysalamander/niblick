"""Tests for the assembler's data pseudo-ops."""

from __future__ import annotations

from pathlib import Path

from badgec.assembler import assemble_file


def assemble(tmp_path: Path, name: str, source: str) -> bytes:
    asm = tmp_path / f"{name}.asm"
    asm.write_text(source)
    hex_path = tmp_path / f"{name}.hex"
    assemble_file(asm, hex_path)
    return hex_path.read_bytes()


def test_byte_counts_as_two_words_for_later_labels(tmp_path: Path) -> None:
    with_byte = assemble(
        tmp_path,
        "with_byte",
        """
        ORG 0
        GOTO start
        BYTE 0x12
        start:
        GOTO start
        """,
    )
    with_nibbles = assemble(
        tmp_path,
        "with_nibbles",
        """
        ORG 0
        GOTO start
        NIBBLE 2
        NIBBLE 1
        start:
        GOTO start
        """,
    )
    assert with_byte == with_nibbles


def test_ascii_counts_two_words_per_character(tmp_path: Path) -> None:
    with_ascii = assemble(
        tmp_path,
        "with_ascii",
        """
        ORG 0
        GOTO start
        ASCII "AB"
        start:
        GOTO start
        """,
    )
    with_nibbles = assemble(
        tmp_path,
        "ascii_nibbles",
        """
        ORG 0
        GOTO start
        NIBBLE 1
        NIBBLE 4
        NIBBLE 2
        NIBBLE 4
        start:
        GOTO start
        """,
    )
    assert with_ascii == with_nibbles
