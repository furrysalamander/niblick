"""CLI and assembler-wrapper smoke tests."""

from __future__ import annotations

from pathlib import Path

from niblick.assembler import code_words
from niblick.cli import main


def test_cli_compiles_and_runs_from_any_working_directory(tmp_path: Path) -> None:
    source = tmp_path / "hello.nbl"
    source.write_text(
        """
        import "lib/uart.nbl";
        const char msg[] = "Hi";
        fn main() {
            uart_init(3);
            uart_puts(msg);
        }
        """
    )
    result = main([str(source), "--run", "--max-steps", "2000"])
    assert result == 0
    assert (tmp_path / "hello.asm").exists()
    hex_path = tmp_path / "hello.hex"
    assert hex_path.exists()
    assert 0 < code_words(hex_path) <= 4096


def test_cli_reports_errors_without_traceback(tmp_path: Path, capsys) -> None:
    source = tmp_path / "bad.nbl"
    source.write_text("fn main() { unknown(); }")
    result = main([str(source)])
    captured = capsys.readouterr()
    assert result == 1
    assert "unknown function" in captured.err
    assert "Traceback" not in captured.err


def test_cli_map_json_trace_and_dumps(tmp_path: Path, capsys) -> None:
    source = tmp_path / "hello.nbl"
    source.write_text(
        """
        import "lib/uart.nbl";
        const char msg[] = "Hi";
        nibble x;
        fn main() {
            x = 1 + 2;
            uart_init(3);
            uart_puts(msg);
        }
        """
    )
    map_path = tmp_path / "hello.map.json"
    result = main(
        [
            str(source),
            "--run",
            "--trace",
            "--trace-limit",
            "5",
            "--map-json",
            str(map_path),
            "--symbols",
            "--callgraph",
            "--dump-uart",
            "--dump-sfr",
        ]
    )
    assert result == 0
    assert map_path.exists()
    data = map_path.read_text()
    assert '"functions"' in data
    assert '"uart_puts"' in data  # uart_puts is a library function now
    captured = capsys.readouterr()
    assert "pc=0" in captured.out
    assert "UART TX" in captured.out
    assert "SFRs" in captured.out
