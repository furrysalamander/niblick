"""Editor-facing analysis helpers.

The LSP server should not scrape the CLI's human-readable output.  This module
loads a Niblick project, runs the compiler's semantic checks, and exposes
structured diagnostics and document symbols.  It deliberately avoids full
code generation where possible.
"""

from __future__ import annotations

import copy
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from .asm_link import scan_asm
from .assembler import assemble_file
from .compiler import Compiler
from .diagnostics import Diagnostic
from .errors import NiblickError
from .loader import load_program
from .runtime_linker import ROUTINE_LABELS
from .symbols import Definition, ProgramIndex


@dataclass(frozen=True)
class Location:
    file: str
    line: int
    column: int = 1


@dataclass
class Symbol:
    name: str
    kind: str
    detail: str
    file: str
    line: int
    column: int = 1
    children: list["Symbol"] = field(default_factory=list)


def _normalise(path: str | Path) -> str:
    return str(Path(path).expanduser().resolve())


def _override_map(
    source_overrides: dict[str | Path, str] | None,
) -> dict[str, str] | None:
    if not source_overrides:
        return None
    return {_normalise(key): value for key, value in source_overrides.items()}


def _diagnostic_from_error(
    exc: NiblickError, fallback_file: str
) -> Diagnostic:
    if exc.file:
        return Diagnostic(
            file=_normalise(exc.file),
            line=max(1, exc.line),
            column=max(1, exc.column),
            message=exc.message,
            severity=exc.severity,
            end_line=exc.end_line,
            end_column=exc.end_column,
            code=exc.code,
        )
    return Diagnostic(
        file=fallback_file,
        line=1,
        column=1,
        message=str(exc),
    )


def analyze_asm(path: str | Path, text: str) -> list[Diagnostic]:
    """Return diagnostics for a standalone assembly document."""

    target = _normalise(path)
    try:
        scan_asm(text, target)
    except NiblickError as exc:
        return [_diagnostic_from_error(exc, target)]
    return []


class Analysis:
    """A loaded project plus editor-oriented queries."""

    def __init__(
        self,
        entry: str | Path,
        source_overrides: dict[str | Path, str] | None = None,
        search_paths: list[str | Path] | None = None,
        extra_asm: dict[str | Path, str] | None = None,
    ) -> None:
        self.entry = Path(entry).expanduser().resolve()
        self.overrides = _override_map(source_overrides)
        self.search_paths = search_paths
        self.extra_asm = _override_map(extra_asm)
        self.program = None
        self.load_error: Optional[NiblickError] = None
        self._index: Optional[ProgramIndex] = None
        self._load()

    def _load(self) -> None:
        try:
            self.program = load_program(
                self.entry,
                search_paths=self.search_paths,
                source_overrides=self.overrides,
            )
        except NiblickError as exc:
            self.load_error = exc

    def diagnostics(self) -> list[Diagnostic]:
        if self.load_error is not None:
            return [
                _diagnostic_from_error(self.load_error, _normalise(self.entry))
            ]

        assert self.program is not None
        has_main = any(fn.name == "main" for fn in self.program.functions)
        program = copy.deepcopy(self.program) if has_main else self.program
        if has_main:
            try:
                asm = Compiler(program, _normalise(self.entry)).compile()
                with tempfile.TemporaryDirectory(prefix="niblick-lsp-") as temp:
                    asm_path = Path(temp) / "program.asm"
                    asm_path.write_text(asm)
                    assemble_file(asm_path, Path(temp) / "program.hex")
            except NiblickError as exc:
                return [
                    _diagnostic_from_error(exc, _normalise(self.entry))
                ]
            return []

        try:
            Compiler(program, _normalise(self.entry)).check(prune=False)
        except NiblickError as exc:
            return [_diagnostic_from_error(exc, _normalise(self.entry))]        # The compiler's check path intentionally does not scan imported
        # assembly; surface asm syntax/call errors and validate the extern
        # declarations against the imported entry points here.
        scans = []
        for source in self.program.asm_sources:
            try:
                scans.append(scan_asm(source.text, source.path))
            except NiblickError as exc:
                return [_diagnostic_from_error(exc, source.path)]

        locations: dict[str, tuple[str, int]] = {}
        for scan in scans:
            for label, line in scan.labels.items():
                if label in locations:
                    path, first_line = locations[label]
                    return [
                        Diagnostic(
                            file=_normalise(scan.path),
                            line=line,
                            column=1,
                            message=(
                                f"duplicate assembly label {label!r} "
                                f"(already defined at {path}:{first_line})"
                            ),
                        )
                    ]
                locations[label] = (scan.path, line)

        declarations = {fn.name: fn for fn in self.program.functions}
        for scan in scans:
            for call in scan.runtime_calls:
                if call.target_label not in ROUTINE_LABELS:
                    return [
                        Diagnostic(
                            file=_normalise(scan.path),
                            line=call.line,
                            column=1,
                            message=(
                                f"unknown runtime routine "
                                f"{call.target_label!r}"
                            ),
                        )
                    ]
            for call in scan.calls:
                target = call.target_label[3:]
                if target not in declarations:
                    return [
                        Diagnostic(
                            file=_normalise(scan.path),
                            line=call.line,
                            column=1,
                            message=(
                                f"call to undeclared function "
                                f"{call.target_label!r}; add an extern fn declaration"
                            ),
                        )
                    ]
        for label, (path, line) in locations.items():
            if not label.startswith("fn_"):
                continue
            name = label[3:]
            declaration = declarations.get(name)
            if declaration is None:
                return [
                    Diagnostic(
                        file=_normalise(path),
                        line=line,
                        column=1,
                        message=(
                            f"assembly defines {label!r} but there is no "
                            f"extern fn {name}() declaration"
                        ),
                    )
                ]
            if not declaration.is_extern:
                return [
                    Diagnostic(
                        file=_normalise(path),
                        line=line,
                        column=1,
                        message=f"assembly redefines Niblick function {name!r}",
                    )
                ]

        for fn in program.functions:
            if not fn.is_extern:
                continue
            if f"fn_{fn.name}" not in locations:
                return [
                    Diagnostic(
                        file=_normalise(fn.file or self.entry),
                        line=fn.name_line or fn.line,
                        column=fn.name_column or fn.column or 1,
                        message=(
                            f"extern function {fn.name!r} has no "
                            f"fn_{fn.name}: definition in imported assembly"
                        ),
                    )
                ]
        return []

    def _ensure_index(self) -> ProgramIndex:
        if self._index is None:
            self._index = ProgramIndex(
                self.program,
                self.entry,
                self.overrides,
                self.extra_asm,
            )
        return self._index

    def definition(
        self, file: str | Path, line: int, column: int
    ) -> Optional[Definition]:
        return self._ensure_index().definition_at(file, line, column)

    def hover(self, file: str | Path, line: int, column: int) -> Optional[str]:
        return self._ensure_index().hover_at(file, line, column)

    def references(
        self, file: str | Path, line: int, column: int
    ) -> list:
        return self._ensure_index().references_at(file, line, column)

    def rename(
        self,
        file: str | Path,
        line: int,
        column: int,
        new_name: str,
    ) -> list:
        return self._ensure_index().rename_at(file, line, column, new_name)

    def completions(
        self, file: str | Path, line: int, column: int
    ) -> list[Definition]:
        return self._ensure_index().completions_at(file, line, column)

    def asm_labels(self, file: str | Path) -> list[Definition]:
        return self._ensure_index().asm_labels_for(file)

    def inline_asm_at(self, file: str | Path, line: int):
        return self._ensure_index().inline_asm_at(file, line)

    def document_symbols(self, file: str | Path) -> list[Symbol]:
        target = _normalise(file)
        if target.lower().endswith(".asm"):
            text = (
                self.overrides.get(target) if self.overrides else None
            )
            if text is None:
                path = Path(target)
                if not path.is_file():
                    return []
                text = path.read_text()
            try:
                scan = scan_asm(text, target)
            except NiblickError:
                return []
            symbols: list[Symbol] = []
            for label, line in sorted(scan.labels.items(), key=lambda item: item[1]):
                if label.startswith("."):
                    continue
                kind = "function" if label.startswith("fn_") else "variable"
                detail = "asm entry point" if kind == "function" else "asm label"
                symbols.append(
                    Symbol(
                        name=label,
                        kind=kind,
                        detail=detail,
                        file=target,
                        line=line,
                        column=1,
                    )
                )
            return symbols

        if self.program is None:
            return []

        symbols: list[Symbol] = []
        for fn in self.program.functions:
            if fn.file != target:
                continue
            params = ", ".join(
                f"{param.type} {param.name}" for param in fn.params
            )
            prefix = "extern " if fn.is_extern else ""
            symbols.append(
                Symbol(
                    name=fn.name,
                    kind="function",
                    detail=f"{prefix}{fn.return_type} {fn.name}({params})",
                    file=target,
                    line=fn.name_line or fn.line,
                    column=fn.name_column or fn.column or 1,
                    children=[
                        Symbol(
                            name=param.name,
                            kind="variable",
                            detail=str(param.type),
                            file=target,
                            line=param.line,
                            column=param.column or 1,
                        )
                        for param in fn.params
                    ],
                )
            )

        for decl in self.program.globals:
            if decl.file != target:
                continue
            kind = "constant" if decl.is_const else "variable"
            array = f"[{decl.array_len}]" if decl.array_len is not None else ""
            symbols.append(
                Symbol(
                    name=decl.name,
                    kind=kind,
                    detail=f"{decl.type}{array}",
                    file=target,
                    line=decl.line,
                    column=decl.column or 1,
                )
            )

        symbols.sort(key=lambda item: (item.line, item.column, item.name))
        return symbols
