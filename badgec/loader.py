"""Source loading with ``import`` support.

An import is resolved relative to the importing file first, then relative to
each search root (the repository root plus any ``BADGEC_PATH`` entries).
Every file is loaded once; the resulting declarations are merged into a
single ``ast.Program`` for the compiler.
"""

from __future__ import annotations

import os
from pathlib import Path

from . import ast_nodes as ast
from .errors import BadgeCompileError
from .parser import parse

REPO_ROOT = Path(__file__).resolve().parent.parent


def _search_roots(extra: list[str | Path] | None) -> list[Path]:
    roots = [REPO_ROOT]
    if extra:
        roots.extend(Path(item).expanduser() for item in extra)
    env = os.environ.get("BADGEC_PATH")
    if env:
        roots.extend(Path(item).expanduser() for item in env.split(os.pathsep) if item)
    return roots


def _resolve_import(
    importer: Path, import_path: str, roots: list[Path]
) -> Path:
    requested = Path(import_path)
    candidates: list[Path] = []
    if requested.is_absolute():
        candidates.append(requested)
    else:
        candidates.append(importer.parent / requested)
        candidates.extend(root / requested for root in roots)
    for candidate in candidates:
        if candidate.is_file():
            return candidate.resolve()
    raise BadgeCompileError(
        f"{importer}: cannot find import {import_path!r} "
        f"(tried {', '.join(str(c) for c in candidates)})"
    )


def _load(
    path: Path,
    stack: list[Path],
    loaded: set[Path],
    roots: list[Path],
) -> ast.Program:
    if path in stack:
        chain = " -> ".join(str(item) for item in stack + [path])
        raise BadgeCompileError(f"import cycle: {chain}")
    if path in loaded:
        return ast.Program()

    if not path.is_file():
        raise BadgeCompileError(f"source file not found: {path}")

    parsed = parse(path.read_text(), str(path))
    stack.append(path)

    merged = ast.Program()
    for declaration in parsed.imports:
        target = _resolve_import(path, declaration.path, roots)
        imported = _load(target, stack, loaded, roots)
        merged.globals.extend(imported.globals)
        merged.functions.extend(imported.functions)

    stack.pop()
    merged.globals.extend(parsed.globals)
    merged.functions.extend(parsed.functions)
    loaded.add(path)
    return merged


def load_program(
    path: str | Path, search_paths: list[str | Path] | None = None
) -> ast.Program:
    """Parse *path* and every file it imports into one program."""

    entry = Path(path).expanduser().resolve()
    return _load(entry, [], set(), _search_roots(search_paths))


def load_source(
    source: str,
    filename: str = "<input>",
    search_paths: list[str | Path] | None = None,
) -> ast.Program:
    """Parse in-memory source, resolving imports relative to *filename*."""

    parsed = parse(source, filename)
    base = Path(filename)
    roots = _search_roots(search_paths)
    loaded: set[Path] = set()
    merged = ast.Program()
    for declaration in parsed.imports:
        target = _resolve_import(base, declaration.path, roots)
        imported = _load(target, [], loaded, roots)
        merged.globals.extend(imported.globals)
        merged.functions.extend(imported.functions)
    merged.globals.extend(parsed.globals)
    merged.functions.extend(parsed.functions)
    return merged
