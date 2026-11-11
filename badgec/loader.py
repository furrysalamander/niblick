"""Source loading with ``import`` support.

An import is resolved relative to the importing file first, then relative to
each search root (the repository root plus any ``BADGEC_PATH`` entries).
Every file is loaded once; the resulting declarations are merged into a
single ``ast.Program`` for the compiler.
"""

from __future__ import annotations

import os
import site
import sys
from pathlib import Path

from . import ast_nodes as ast
from .errors import BadgeCompileError
from .parser import parse

REPO_ROOT = Path(__file__).resolve().parent.parent


def _search_roots(extra: list[str | Path] | None) -> list[Path]:
    roots = [REPO_ROOT]
    bases = [Path(sys.prefix)]
    if site.USER_BASE:
        bases.append(Path(site.USER_BASE))
    for base in bases:
        data_root = base / "share" / "badgec"
        if data_root.is_dir():
            roots.append(data_root)
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
    loaded_asm: set[Path],
    roots: list[Path],
    source_overrides: dict[Path, str] | None = None,
) -> ast.Program:
    if path in stack:
        chain = " -> ".join(str(item) for item in stack + [path])
        raise BadgeCompileError(f"import cycle: {chain}")
    if path in loaded:
        return ast.Program()

    text = source_overrides.get(path) if source_overrides else None
    if not path.is_file() and text is None:
        raise BadgeCompileError(f"source file not found: {path}")

    if text is None:
        text = path.read_text()
    parsed = parse(text, str(path))
    stack.append(path)

    merged = ast.Program()
    for declaration in parsed.imports:
        target = _resolve_import(path, declaration.path, roots)
        if target.suffix.lower() == ".asm":
            if target not in loaded_asm:
                loaded_asm.add(target)
                asm_text = source_overrides.get(target) if source_overrides else None
                if asm_text is None:
                    asm_text = target.read_text()
                merged.asm_sources.append(ast.AsmSource(str(target), asm_text))
            continue
        imported = _load(target, stack, loaded, loaded_asm, roots, source_overrides)
        merged.globals.extend(imported.globals)
        merged.functions.extend(imported.functions)
        merged.asm_sources.extend(imported.asm_sources)

    stack.pop()
    merged.globals.extend(parsed.globals)
    merged.functions.extend(parsed.functions)
    loaded.add(path)
    return merged


def load_program(
    path: str | Path,
    search_paths: list[str | Path] | None = None,
    source_overrides: dict[str | Path, str] | None = None,
) -> ast.Program:
    """Parse *path* and every file it imports into one program.

    ``source_overrides`` maps resolved paths to in-memory text, allowing an
    editor to analyze unsaved buffers without writing them to disk.
    """

    entry = Path(path).expanduser().resolve()
    overrides: dict[Path, str] | None = None
    if source_overrides:
        overrides = {
            Path(key).expanduser().resolve(): value
            for key, value in source_overrides.items()
        }
    return _load(entry, [], set(), set(), _search_roots(search_paths), overrides)


def load_source(
    source: str,
    filename: str = "<input>",
    search_paths: list[str | Path] | None = None,
    source_overrides: dict[str | Path, str] | None = None,
) -> ast.Program:
    """Parse in-memory source, resolving imports relative to *filename*."""

    parsed = parse(source, filename)
    base = Path(filename)
    roots = _search_roots(search_paths)
    loaded: set[Path] = set()
    loaded_asm: set[Path] = set()
    overrides: dict[Path, str] | None = None
    if source_overrides:
        overrides = {
            Path(key).expanduser().resolve(): value
            for key, value in source_overrides.items()
        }
    merged = ast.Program()
    for declaration in parsed.imports:
        target = _resolve_import(base, declaration.path, roots)
        if target.suffix.lower() == ".asm":
            if target not in loaded_asm:
                loaded_asm.add(target)
                asm_text = overrides.get(target) if overrides else None
                if asm_text is None:
                    asm_text = target.read_text()
                merged.asm_sources.append(ast.AsmSource(str(target), asm_text))
            continue
        imported = _load(target, [], loaded, loaded_asm, roots, overrides)
        merged.globals.extend(imported.globals)
        merged.functions.extend(imported.functions)
        merged.asm_sources.extend(imported.asm_sources)
    merged.globals.extend(parsed.globals)
    merged.functions.extend(parsed.functions)
    return merged
