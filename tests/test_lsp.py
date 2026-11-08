"""Smoke tests for the optional pygls language server."""

from __future__ import annotations

import asyncio
from pathlib import Path

import pytest

pytest.importorskip("pygls")
pytest.importorskip("lsprotocol")

from lsprotocol import types

from badgec.lsp import DEBOUNCE_SECONDS, create_server


def test_server_registers_diagnostics_and_symbol_features() -> None:
    server = create_server()
    features = set(server.protocol.fm._features)
    assert "textDocument/didOpen" in features
    assert "textDocument/didChange" in features
    assert "textDocument/didSave" in features
    assert "textDocument/documentSymbol" in features


def test_document_symbol_handler(tmp_path: Path) -> None:
    source = tmp_path / "main.badge"
    source.write_text(
        "nibble result;\n"
        "fn main() { result = 1; }\n"
    )
    server = create_server()
    handler = server.protocol.fm._features["textDocument/documentSymbol"]
    symbols = handler(
        types.DocumentSymbolParams(
            text_document=types.TextDocumentIdentifier(uri=source.as_uri())
        )
    )
    assert [symbol.name for symbol in symbols] == ["result", "main"]


def test_open_publishes_diagnostics(tmp_path: Path) -> None:
    source = tmp_path / "bad.badge"
    source.write_text("fn main() { }\n")
    server = create_server()
    published: list[types.PublishDiagnosticsParams] = []

    def capture(params: types.PublishDiagnosticsParams) -> None:
        published.append(params)

    server.text_document_publish_diagnostics = capture  # type: ignore[method-assign]
    handler = server.protocol.fm._features["textDocument/didOpen"]

    async def run() -> None:
        handler(
            types.DidOpenTextDocumentParams(
                text_document=types.TextDocumentItem(
                    uri=source.as_uri(),
                    language_id="badgec",
                    version=1,
                    text="nibble x;\nfn main() { x = 300; }\n",
                )
            )
        )
        await asyncio.sleep(DEBOUNCE_SECONDS + 0.15)

    asyncio.run(run())
    assert published
    diagnostic_sets = [item for item in published if item.uri == source.as_uri()]
    assert diagnostic_sets
    assert any(
        "cannot convert" in diagnostic.message
        for item in diagnostic_sets
        for diagnostic in item.diagnostics
    )
