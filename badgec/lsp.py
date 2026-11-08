"""Language Server Protocol implementation for BadgeC.

Run with::

    python3 -m badgec.lsp --stdio

The server reuses the compiler front end through :mod:`badgec.analysis`.  It
supports diagnostics, document symbols, hover, completion,
go-to-definition, find-all-references, and rename, including links between
``extern fn`` declarations and imported assembly entry points.
"""

from __future__ import annotations

import argparse
import asyncio
import logging
from pathlib import Path
from typing import Optional
from urllib.parse import unquote, urlparse

try:
    from lsprotocol import types
    from pygls.lsp.server import LanguageServer
except ImportError as exc:  # pragma: no cover - exercised when the extra is absent
    raise ImportError(
        "badgec.lsp requires the optional LSP dependencies. "
        'Install them with: pip install -e ".[lsp]"'
    ) from exc

from .analysis import Analysis, Diagnostic, Symbol, analyze_asm

LOGGER = logging.getLogger(__name__)
DEBOUNCE_SECONDS = 0.25

ASM_KEYWORDS = [
    "ADD", "ADC", "SUB", "SBB", "OR", "AND", "XOR", "MOV",
    "CP", "INC", "DEC", "DSZ", "EXR", "BIT", "BSET", "BCLR", "BTG",
    "RRC", "RET", "SKIP", "JR",
]
ASM_PSEUDO_OPS = ["GOTO", "GOSUB", "NOP", "CPL", "NEG", "LSR", "SL", "RLC"]
ASM_DIRECTIVES = ["EQU", "ORG", "BYTE", "ASCII", "NIBBLE"]
ASM_CONDITIONS = ["C", "NC", "Z", "NZ", "GTE", "LT", "EQ", "NE"]
ASM_REGISTERS = [f"R{index}" for index in range(16)] + [
    "OUT", "OUTB", "IN", "INB", "JSR", "PCL", "PCM", "PCH",
    "PAGE", "CLOCK", "SYNC", "WRFLAGS", "RDFLAGS", "SERCTRL",
    "SERLOW", "SERHIGH", "RECEIVED", "AUTOOFF", "KEYSTATUS",
    "KEYREG", "DIMMER", "RANDOM",
]
BADGEC_KEYWORDS = [
    "fn", "nibble", "char", "word", "dword", "flashptr", "void",
    "const", "if", "else", "while", "for", "return", "break",
    "continue", "import", "extern", "true", "false",
]


def uri_to_path(uri: str) -> Path:
    parsed = urlparse(uri)
    if parsed.scheme not in ("", "file"):
        raise ValueError(f"unsupported URI scheme: {uri}")
    path = unquote(parsed.path)
    return Path(path).expanduser().resolve()


def path_to_uri(path: str | Path) -> str:
    return Path(path).resolve().as_uri()


def _range(line: int, column: int, length: int = 1) -> types.Range:
    """Build a single-line LSP range from 1-based source coordinates."""

    start_line = max(0, line - 1)
    start_character = max(0, column - 1)
    return types.Range(
        start=types.Position(line=start_line, character=start_character),
        end=types.Position(
            line=start_line,
            character=start_character + max(1, length),
        ),
    )


def _lsp_diagnostic(diagnostic: Diagnostic) -> types.Diagnostic:
    return types.Diagnostic(
        range=_range(diagnostic.line, diagnostic.column, 1),
        message=diagnostic.message,
        severity=(
            types.DiagnosticSeverity.Error
            if diagnostic.severity == "error"
            else types.DiagnosticSeverity.Warning
        ),
        source="badgec",
    )


def _symbol_kind(symbol: Symbol) -> types.SymbolKind:
    if symbol.kind == "function":
        return types.SymbolKind.Function
    if symbol.kind == "constant":
        return types.SymbolKind.Constant
    return types.SymbolKind.Variable


def _lsp_symbol(symbol: Symbol) -> types.DocumentSymbol:
    return types.DocumentSymbol(
        name=symbol.name,
        detail=symbol.detail,
        kind=_symbol_kind(symbol),
        range=_range(symbol.line, symbol.column, max(1, len(symbol.name))),
        selection_range=_range(
            symbol.line, symbol.column, max(1, len(symbol.name))
        ),
        children=[_lsp_symbol(child) for child in symbol.children],
    )


def _lsp_location(definition) -> types.Location:
    return types.Location(
        uri=path_to_uri(definition.file),
        range=_range(
            definition.line,
            definition.column,
            max(1, len(definition.name)),
        ),
    )


def _lsp_occurrence_location(occurrence) -> types.Location:
    return types.Location(
        uri=path_to_uri(occurrence.file),
        range=_range(
            occurrence.line,
            occurrence.column,
            max(1, occurrence.length),
        ),
    )


def _completion_kind(kind: str) -> types.CompletionItemKind:
    if kind in ("function", "asm_function"):
        return types.CompletionItemKind.Function
    if kind in ("constant", "asm_label"):
        return types.CompletionItemKind.Constant
    if kind in ("param", "local", "global", "variable"):
        return types.CompletionItemKind.Variable
    if kind == "runtime":
        return types.CompletionItemKind.Module
    return types.CompletionItemKind.Text


def create_server() -> LanguageServer:
    server = LanguageServer(
        "badgec-lsp",
        "0.1.0",
        text_document_sync_kind=types.TextDocumentSyncKind.Full,
    )
    documents: dict[str, str] = {}
    tasks: dict[str, asyncio.Task] = {}
    include_paths: list[str] = []
    reported: dict[str, set[str]] = {}
    analysis_cache: dict[str, Analysis] = {}

    def clear_analysis_cache() -> None:
        analysis_cache.clear()

    def overrides_for(entry_uri: str) -> dict[str, str]:
        # The analysis API wants filesystem keys, not URIs.
        result: dict[str, str] = {}
        for uri, text in documents.items():
            try:
                result[str(uri_to_path(uri))] = text
            except ValueError:
                continue
        return result

    def project_uri_for(entry_uri: str) -> Optional[str]:
        path = uri_to_path(entry_uri)
        if path.suffix.lower() != ".asm":
            return entry_uri
        target = str(path)
        for candidate in documents:
            candidate_path = uri_to_path(candidate)
            if candidate_path.suffix.lower() != ".badge":
                continue
            try:
                analysis = cached_analysis(
                    candidate,
                    uri_to_path(candidate),
                    extra_asm=None,
                )
            except Exception:
                continue
            if analysis.program is None:
                continue
            if any(
                str(Path(source.path).resolve()) == target
                for source in analysis.program.asm_sources
            ):
                return candidate
        return None

    def cached_analysis(
        cache_key: str,
        path: Path,
        extra_asm: dict[str, str] | None,
    ) -> Analysis:
        cached = analysis_cache.get(cache_key)
        if cached is not None:
            return cached
        analysis = Analysis(
            path,
            source_overrides=overrides_for(cache_key),
            search_paths=include_paths or None,
            extra_asm=extra_asm,
        )
        analysis_cache[cache_key] = analysis
        return analysis

    def analysis_for(entry_uri: str) -> Analysis:
        project_uri = project_uri_for(entry_uri)
        if project_uri is not None:
            return cached_analysis(
                project_uri,
                uri_to_path(project_uri),
                extra_asm=None,
            )
        path = uri_to_path(entry_uri)
        text = documents.get(entry_uri)
        if text is None:
            text = path.read_text()
        return cached_analysis(
            entry_uri,
            path,
            extra_asm={str(path): text},
        )

    def publish(uri: str) -> None:
        path = uri_to_path(uri)
        if path.suffix.lower() == ".asm":
            text = documents.get(uri)
            if text is None:
                text = path.read_text()
            diagnostics = analyze_asm(path, text)
        else:
            diagnostics = analysis_for(uri).diagnostics()

        by_file: dict[str, list[Diagnostic]] = {}
        for diagnostic in diagnostics:
            by_file.setdefault(diagnostic.file, []).append(diagnostic)

        # Publish for the open document first, then any other files the
        # analysis touched.  Clear diagnostics from files that no longer
        # have errors in this pass.
        def publish_topic(target_uri: str, items: list[types.Diagnostic]) -> None:
            server.text_document_publish_diagnostics(
                types.PublishDiagnosticsParams(
                    uri=target_uri,
                    diagnostics=items,
                    version=None,
                )
            )

        current: set[str] = set()
        targets = {str(path)} | set(by_file)
        for target in targets:
            target_uri = path_to_uri(target)
            current.add(target_uri)
            publish_topic(
                target_uri,
                [_lsp_diagnostic(item) for item in by_file.get(target, [])],
            )

        for stale in reported.get(uri, set()) - current:
            publish_topic(stale, [])
        reported[uri] = current

    def schedule(uri: str) -> None:
        previous = tasks.get(uri)
        if previous is not None:
            previous.cancel()

        async def run() -> None:
            try:
                await asyncio.sleep(DEBOUNCE_SECONDS)
                publish(uri)
            except asyncio.CancelledError:
                raise
            except Exception:  # pragma: no cover - surfaced in the log
                LOGGER.exception("analysis failed for %s", uri)

        tasks[uri] = asyncio.create_task(run())

    @server.feature(types.WORKSPACE_DID_CHANGE_CONFIGURATION)
    def configuration_changed(params: types.DidChangeConfigurationParams) -> None:
        settings = params.settings or {}
        if not isinstance(settings, dict):
            return
        badgec = settings.get("badgec", {})
        if not isinstance(badgec, dict):
            return
        paths = badgec.get("includePaths") or []
        if isinstance(paths, list):
            include_paths[:] = [str(item) for item in paths]
        clear_analysis_cache()
        for uri in documents:
            schedule(uri)

    @server.feature(types.TEXT_DOCUMENT_DID_OPEN)
    def did_open(params: types.DidOpenTextDocumentParams) -> None:
        document = params.text_document
        documents[document.uri] = document.text
        clear_analysis_cache()
        schedule(document.uri)

    @server.feature(types.TEXT_DOCUMENT_DID_CHANGE)
    def did_change(params: types.DidChangeTextDocumentParams) -> None:
        changes = params.content_changes
        if not changes:
            return
        # The extension registers full-document synchronization.
        documents[params.text_document.uri] = changes[-1].text
        clear_analysis_cache()
        schedule(params.text_document.uri)

    @server.feature(types.TEXT_DOCUMENT_DID_SAVE)
    def did_save(params: types.DidSaveTextDocumentParams) -> None:
        if params.text is not None:
            documents[params.text_document.uri] = params.text
        clear_analysis_cache()
        schedule(params.text_document.uri)

    @server.feature(types.TEXT_DOCUMENT_DID_CLOSE)
    def did_close(params: types.DidCloseTextDocumentParams) -> None:
        uri = params.text_document.uri
        documents.pop(uri, None)
        clear_analysis_cache()
        task = tasks.pop(uri, None)
        if task is not None:
            task.cancel()
        for stale in reported.pop(uri, set()):
            server.text_document_publish_diagnostics(
                types.PublishDiagnosticsParams(
                    uri=stale,
                    diagnostics=[],
                    version=None,
                )
            )

    @server.feature(types.TEXT_DOCUMENT_DOCUMENT_SYMBOL)
    def document_symbols(
        params: types.DocumentSymbolParams,
    ) -> list[types.DocumentSymbol]:
        uri = params.text_document.uri
        try:
            analysis = analysis_for(uri)
            symbols = analysis.document_symbols(uri_to_path(uri))
        except Exception:
            LOGGER.exception("document symbols failed for %s", uri)
            return []
        return [_lsp_symbol(symbol) for symbol in symbols]

    @server.feature(types.TEXT_DOCUMENT_HOVER)
    def hover(params: types.HoverParams) -> Optional[types.Hover]:
        uri = params.text_document.uri
        try:
            text = analysis_for(uri).hover(
                uri_to_path(uri),
                params.position.line + 1,
                params.position.character + 1,
            )
        except Exception:
            LOGGER.exception("hover failed for %s", uri)
            return None
        if not text:
            return None
        return types.Hover(
            contents=types.MarkupContent(
                kind=types.MarkupKind.Markdown,
                value=text,
            )
        )

    @server.feature(types.TEXT_DOCUMENT_DEFINITION)
    def definition(params: types.DefinitionParams) -> Optional[types.Location]:
        uri = params.text_document.uri
        try:
            target = analysis_for(uri).definition(
                uri_to_path(uri),
                params.position.line + 1,
                params.position.character + 1,
            )
        except Exception:
            LOGGER.exception("definition failed for %s", uri)
            return None
        if target is None or not target.file:
            return None
        return _lsp_location(target)

    @server.feature(types.TEXT_DOCUMENT_REFERENCES)
    def references(params: types.ReferenceParams) -> list[types.Location]:
        uri = params.text_document.uri
        try:
            occurrences = analysis_for(uri).references(
                uri_to_path(uri),
                params.position.line + 1,
                params.position.character + 1,
            )
        except Exception:
            LOGGER.exception("references failed for %s", uri)
            return []
        if not params.context.include_declaration:
            occurrences = [
                occurrence
                for occurrence in occurrences
                if occurrence.kind != "declaration"
            ]
        return [
            _lsp_occurrence_location(occurrence)
            for occurrence in occurrences
        ]

    @server.feature(types.TEXT_DOCUMENT_RENAME)
    def rename(params: types.RenameParams) -> Optional[types.WorkspaceEdit]:
        uri = params.text_document.uri
        try:
            edits = analysis_for(uri).rename(
                uri_to_path(uri),
                params.position.line + 1,
                params.position.character + 1,
                params.new_name,
            )
        except Exception:
            LOGGER.exception("rename failed for %s", uri)
            return None
        changes: dict[str, list[types.TextEdit]] = {}
        for edit in edits:
            changes.setdefault(path_to_uri(edit.file), []).append(
                types.TextEdit(
                    range=_range(edit.line, edit.column, edit.length),
                    new_text=edit.new_text,
                )
            )
        return types.WorkspaceEdit(changes=changes) if changes else None

    @server.feature(types.TEXT_DOCUMENT_COMPLETION)
    def completion(params: types.CompletionParams) -> types.CompletionList:
        uri = params.text_document.uri
        path = uri_to_path(uri)
        items: list[types.CompletionItem] = []
        seen: set[str] = set()

        def add(
            label: str,
            kind: types.CompletionItemKind,
            detail: str = "",
        ) -> None:
            if label in seen:
                return
            seen.add(label)
            items.append(
                types.CompletionItem(
                    label=label,
                    kind=kind,
                    detail=detail,
                    insert_text=label,
                    sort_text=label,
                )
            )

        try:
            analysis = analysis_for(uri)
            if path.suffix.lower() == ".asm":
                for word in ASM_KEYWORDS:
                    add(word, types.CompletionItemKind.Keyword, "Voja4 instruction")
                for word in ASM_PSEUDO_OPS:
                    add(word, types.CompletionItemKind.Keyword, "Voja4 pseudo-op")
                for word in ASM_DIRECTIVES:
                    add(word, types.CompletionItemKind.Keyword, "assembler directive")
                for word in ASM_CONDITIONS:
                    add(word, types.CompletionItemKind.Constant, "skip condition")
                for word in ASM_REGISTERS:
                    add(word, types.CompletionItemKind.Variable, "register")
                for label in analysis.asm_labels(path):
                    add(label.name, _completion_kind(label.kind), label.detail)
                for item in analysis.completions(
                    path,
                    params.position.line + 1,
                    params.position.character + 1,
                ):
                    if item.kind in ("runtime", "builtin"):
                        add(item.name, _completion_kind(item.kind), item.detail)
            else:
                for word in BADGEC_KEYWORDS:
                    add(word, types.CompletionItemKind.Keyword, "BadgeC keyword")
                for item in analysis.completions(
                    path,
                    params.position.line + 1,
                    params.position.character + 1,
                ):
                    if item.kind == "runtime":
                        continue
                    add(item.name, _completion_kind(item.kind), item.detail)
        except Exception:
            LOGGER.exception("completion failed for %s", uri)

        return types.CompletionList(is_incomplete=False, items=items)

    return server


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(prog="badgec-lsp")
    parser.add_argument(
        "--stdio",
        action="store_true",
        help="use stdio transport (the only supported transport)",
    )
    parser.add_argument("--debug", action="store_true", help="enable debug logging")
    args = parser.parse_args(argv)

    logging.basicConfig(
        level=logging.DEBUG if args.debug else logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    create_server().start_io()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
