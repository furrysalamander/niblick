"""Function-slot overlay tests."""

from __future__ import annotations

from pathlib import Path

from niblick.compiler import Compiler
from niblick.loader import load_source


def compile_source(tmp_path: Path, source: str) -> Compiler:
    path = tmp_path / "overlay.nbl"
    path.write_text(source)
    compiler = Compiler(load_source(source, filename=str(path)), str(path))
    compiler.compile()
    return compiler


def test_independent_leaf_functions_share_slots(tmp_path: Path) -> None:
    compiler = compile_source(
        tmp_path,
        """
        nibble out;
        fn void a() { nibble x[4]; x[0] = 1; out = x[0]; }
        fn void b() { nibble x[4]; x[0] = 2; out = x[0]; }
        fn main() { a(); b(); }
        """,
    )
    assert compiler.functions["a"].ram_base == compiler.functions["b"].ram_base


def test_ancestor_and_callee_do_not_share_slots(tmp_path: Path) -> None:
    compiler = compile_source(
        tmp_path,
        """
        nibble out;
        fn void child() { nibble y[2]; y[0] = 1; out = y[0]; }
        fn void parent() { child(); nibble z[2]; z[0] = 2; out = z[0]; }
        fn main() { parent(); }
        """,
    )
    assert compiler.functions["parent"].ram_base != compiler.functions["child"].ram_base


def test_argument_callee_does_not_share_target_slots(tmp_path: Path) -> None:
    compiler = compile_source(
        tmp_path,
        """
        nibble out;
        fn nibble helper() { nibble x; x = 1; return x; }
        fn void target(nibble v) { nibble y; y = v; out = y; }
        fn main() { target(helper()); }
        """,
    )
    assert compiler.functions["helper"].ram_base != compiler.functions["target"].ram_base
