"""Keep the checked-in examples compiling."""

from __future__ import annotations

from pathlib import Path

import pytest

from badgec.assembler import assemble_file, code_words
from badgec.compiler import Compiler
from badgec.parser import parse

EXAMPLES = sorted((Path(__file__).resolve().parent.parent / "examples").glob("*.badge"))


@pytest.mark.parametrize("example", EXAMPLES, ids=lambda p: p.name)
def test_example_compiles(tmp_path: Path, example: Path) -> None:
    source = example.read_text()
    program = parse(source, str(example))
    compiler = Compiler(program, str(example))
    asm = compiler.compile()
    asm_path = tmp_path / (example.stem + ".asm")
    asm_path.write_text(asm)
    hex_path = tmp_path / (example.stem + ".hex")
    assemble_file(asm_path, hex_path)
    assert 0 < code_words(hex_path) <= 4096
    assert compiler.mem.used() <= 208
