"""Tests for the emulator's SFR, input, display, and timing models."""

from __future__ import annotations

from badgec.emulator import Emulator


def test_key_status_and_key_reg() -> None:
    emu = Emulator()
    assert emu.read_nibble(0xFC) == 0

    emu.press_key(5)
    status = emu.read_nibble(0xFC)
    assert status & 0x4  # AnyPress
    assert status & 0x2  # LastPress
    assert status & 0x1  # JustPress
    assert emu.read_nibble(0xFD) == 5

    # Reading KeyStatus clears JustPress.
    assert (emu.read_nibble(0xFC) & 0x1) == 0
    emu.release_key(5)
    assert (emu.read_nibble(0xFC) & 0x2) == 0

    emu.press_alt()
    assert emu.read_nibble(0xFC) & 0x8


def test_random_seed_and_advance() -> None:
    emu = Emulator()
    emu.write_nibble(0xFF, 3)
    first = emu.read_nibble(0xFF)
    second = emu.read_nibble(0xFF)
    assert first == 3
    assert 0 <= second <= 15


def test_user_sync_flag_is_set_and_cleared() -> None:
    emu = Emulator()
    emu.write_nibble(0xF2, 0)
    emu.run(16)
    flags = emu.read_nibble(0xF4)
    assert flags & 0x1
    assert (emu.read_nibble(0xF4) & 0x1) == 0


def test_display_pages_map_ram() -> None:
    emu = Emulator()
    emu.write_nibble(0xF0, 4)
    emu.ram[0x40] = 1
    emu.ram[0x50] = 2
    left, right = emu.display_pages()
    assert right[0] == 1  # page 4 -> 0x40
    assert left[0] == 2   # page 5 -> 0x50


def test_uart_fifo_and_received() -> None:
    emu = Emulator()
    emu.receive_uart([0x41, 0x42])
    assert emu.read_nibble(0xF8) == 2
    assert emu.read_nibble(0xF7) == 4
    assert emu.read_nibble(0xF6) == 1
    assert emu.read_nibble(0xF8) == 1
    assert emu.read_nibble(0xF7) == 4
    assert emu.read_nibble(0xF6) == 2
    assert emu.read_nibble(0xF8) == 0


def test_instruction_and_cycle_counts() -> None:
    emu = Emulator()
    emu.load_words([0x000])  # CP R0,0
    emu.run(10)
    assert emu.instruction_count == 10
    assert emu.cycle_count == 20
    assert emu.clock_hz == 250e3
