"""Language Server Protocol implementation for BadgeC.

Run with::

    python3 -m badgec.lsp --stdio

The server reuses the compiler front end through :mod:`badgec.analysis`.  It
supports diagnostics and document symbols in this first version; navigation
and completion build on the same analysis layer.
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

    def overrides_for(entry_uri: str) -> dict[str, str]:
        # The analysis API wants filesystem keys, not URIs.
        result: dict[str, str] = {}
        for uri, text in documents.items():
            try:
                result[str(uri_to_path(uri))] = text
            except ValueError:
                continue
        return result

    def analysis_for(entry_uri: str) -> Analysis:
        return Analysis(
            uri_to_path(entry_uri),
            source_overrides=overrides_for(entry_uri),
            search_paths=include_paths or None,
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
        for uri in documents:
            schedule(uri)

    @server.feature(types.TEXT_DOCUMENT_DID_OPEN)
    def did_open(params: types.DidOpenTextDocumentParams) -> None:
        document = params.text_document
        documents[document.uri] = document.text
        schedule(document.uri)

    @server.feature(types.TEXT_DOCUMENT_DID_CHANGE)
    def did_change(params: types.DidChangeTextDocumentParams) -> None:
        changes = params.content_changes
        if not changes:
            return
        # The extension registers full-document synchronization.
        documents[params.text_document.uri] = changes[-1].text
        schedule(params.text_document.uri)

    @server.feature(types.TEXT_DOCUMENT_DID_SAVE)
    def did_save(params: types.DidSaveTextDocumentParams) -> None:
        if params.text is not None:
            documents[params.text_document.uri] = params.text
        schedule(params.text_document.uri)

    @server.feature(types.TEXT_DOCUMENT_DID_CLOSE)
    def did_close(params: types.DidCloseTextDocumentParams) -> None:
        uri = params.text_document.uri
        documents.pop(uri, None)
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
