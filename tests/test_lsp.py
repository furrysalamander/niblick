"""Smoke tests for the optional pygls language server."""

from __future__ import annotations

import asyncio
from pathlib import Path

import pytest

pytest.importorskip("pygls")
pytest.importorskip("lsprotocol")

from lsprotocol import types

from badgec.lsp import DEBOUNCE_SECONDS, create_server


def position(source: str, needle: str) -> tuple[int, int]:
    index = source.index(needle)
    line = source.count("\n", 0, index)
    column = index - source.rfind("\n", 0, index) - 1
    return line, column


def test_server_registers_diagnostics_symbols_and_navigation() -> None:
    server = create_server()
    features = set(server.protocol.fm._features)
    assert "textDocument/didOpen" in features
    assert "textDocument/didChange" in features
    assert "textDocument/didSave" in features
    assert "textDocument/documentSymbol" in features
    assert "textDocument/hover" in features
    assert "textDocument/definition" in features
    assert "textDocument/references" in features
    assert "textDocument/completion" in features


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


def test_hover_definition_and_completion_handlers(tmp_path: Path) -> None:
    text = (
        "nibble g;\n"
        "fn nibble add(nibble a, nibble b) { return a + b; }\n"
        "fn main() { nibble x; x = add(g, 2); }\n"
    )
    source = tmp_path / "nav.badge"
    source.write_text(text)
    server = create_server()
    uri = source.as_uri()

    hover = server.protocol.fm._features["textDocument/hover"]
    line, character = position(text, "add(g")
    result = hover(
        types.HoverParams(
            text_document=types.TextDocumentIdentifier(uri=uri),
            position=types.Position(line=line, character=character),
        )
    )
    assert result is not None
    assert "nibble add(nibble a, nibble b)" in result.contents.value

    definition = server.protocol.fm._features["textDocument/definition"]
    result = definition(
        types.DefinitionParams(
            text_document=types.TextDocumentIdentifier(uri=uri),
            position=types.Position(line=line, character=character),
        )
    )
    assert result is not None
    assert result.uri == uri
    assert result.range.start.line == 1

    completion = server.protocol.fm._features["textDocument/completion"]
    line, character = position(text, "a + b")
    result = completion(
        types.CompletionParams(
            text_document=types.TextDocumentIdentifier(uri=uri),
            position=types.Position(line=line, character=character),
        )
    )
    labels = {item.label for item in result.items}
    assert {"a", "b", "g", "add", "fn"}.issubset(labels)


def test_asm_completion_handler(tmp_path: Path) -> None:
    source = tmp_path / "main.badge"
    source.write_text("fn main() { while (1) { } }\n")
    asm = tmp_path / "impl.asm"
    asm.write_text("fn_impl:\n    RET R0, 0\n")
    server = create_server()
    completion = server.protocol.fm._features["textDocument/completion"]
    result = completion(
        types.CompletionParams(
            text_document=types.TextDocumentIdentifier(uri=asm.as_uri()),
            position=types.Position(line=1, character=4),
        )
    )
    labels = {item.label for item in result.items}
    assert {"fn_impl", "MOV", "R1", "RET", "GOSUB"}.issubset(labels)


def test_references_handler(tmp_path: Path) -> None:
    text = (
        "nibble g;\n"
        "fn main() {\n"
        "    g = 1;\n"
        "    asm {\n"
        "        MOV R0, [${g}]\n"
        "    }\n"
        "}\n"
    )
    source = tmp_path / "refs.badge"
    source.write_text(text)
    server = create_server()
    references = server.protocol.fm._features["textDocument/references"]
    line, character = position(text, "g = 1")
    result = references(
        types.ReferenceParams(
            text_document=types.TextDocumentIdentifier(uri=source.as_uri()),
            position=types.Position(line=line, character=character),
            context=types.ReferenceContext(include_declaration=True),
        )
    )
    assert len(result) == 3
    assert all(item.uri == source.as_uri() for item in result)
