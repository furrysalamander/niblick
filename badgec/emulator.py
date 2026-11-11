"""Headless emulator for the Hackaday Supercon.6 (2022) "Voja4" 4-bit CPU.

The CPU has a 12-bit program counter, a 256 x 4-bit data memory, a small
stack in data memory, and three flags (C, Z, V).  This module intentionally
models only the CPU core.  The badge's LEDs, buttons, UART, timers, and
other SFR side effects are left as ordinary RAM locations.

Instruction encoding
--------------------
Each instruction is a 12-bit word.  With the word laid out as::

    bits 11..8   bits 7..4   bits 3..0
        op          X           Y

most arithmetic/logic instructions use a 4-bit opcode in ``op`` with two
nibbles of operands.  The remaining instructions use ``op == 0`` followed
by an 8-bit opcode split across ``X`` and ``Y``.

Memory layout
-------------
``ram[0x00:0x10]`` contains R0..R15 (R10=OUT, R11=IN, R12=JSR, R13=PCL,
R14=PCM, R15=PCH).  ``ram[0x10:]`` is general data memory, with the
subroutine stack beginning at ``0x10 + sp * 3``.  A loaded program is
stored in ``program`` (4096 words, corresponding to flash).

The implementation follows the revision-4 manuals published with the
Hack-a-Day Supercon.6 badge tools.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

__all__ = ["Emulator", "EmulatorError", "EmulatorStackError", "IoTraceEvent"]


@dataclass(frozen=True)
class IoTraceEvent:
    """One logical I/O-port access recorded by :meth:`Emulator.trace_io`."""

    step: int
    pc: int
    kind: str  # "write", "bit", or "read"
    address: int  # OUT/OUTB/IN/INB data-memory address
    before: int
    after: int
    bit: int | None = None


class EmulatorError(RuntimeError):
    """Base exception raised by the emulator."""


class EmulatorStackError(EmulatorError):
    """Raised for a subroutine stack underflow or overflow."""


class Emulator:
    """A small, dependency-free emulator for the Supercon.6 4-bit CPU.

    Typical use::

        cpu = Emulator()
        cpu.load_hex("program.hex")
        steps = cpu.run(max_steps=10000)
        print(cpu.state())

    The emulator does not attempt to detect an intentional infinite loop
    (for example ``JR -1``).  Call :meth:`run` with a suitable
    ``max_steps`` limit instead.
    """

    PROGRAM_SIZE = 4096
    RAM_SIZE = 256

    #: Header used by the assembler's ``.hex`` output.
    HEX_HEADER = bytes((0x00, 0xFF, 0x00, 0xFF, 0xA5, 0xC3))

    # Data-memory addresses of the special registers on page 0.
    JSR = 0x0C
    PCL = 0x0D
    PCM = 0x0E
    PCH = 0x0F

    # Names of the primary registers, useful for debugging/state snapshots.
    REGISTER_NAMES = (
        "R0",
        "R1",
        "R2",
        "R3",
        "R4",
        "R5",
        "R6",
        "R7",
        "R8",
        "R9",
        "OUT",
        "IN",
        "JSR",
        "PCL",
        "PCM",
        "PCH",
    )

    def __init__(self) -> None:
        self.program: list[int] = [0] * self.PROGRAM_SIZE
        self.ram: list[int] = [0] * self.RAM_SIZE
        self.pc = 0
        self.sp = 0
        self.C = 0
        self.Z = 0
        self.V = 0
        self.halted = False
        self.sleeping = False

        # Minimal UART model used by BadgeC integration tests.
        self.uart_tx: list[int] = []
        self.uart_rx: list[int] = []
        self.uart_tx_high = 0
        self.uart_error = False

        # Timing / SFR helpers.
        self.instruction_count = 0
        self.cycle_count = 0
        self.sync_counter = 0
        self.user_sync = False
        self.random_state = 0xACE1

        # Button model.
        self.keys_down: set[int] = set()
        self.alt_down = False
        self.last_key = 0
        self.just_pressed = False

        # I/O tracing.  ``io_trace`` is None until trace_io() is called.
        self.io_trace: list[IoTraceEvent] | None = None
        self.io_trace_limit: int | None = None
        self.io_trace_total = 0
        self._pc_at_fetch = 0

    # ------------------------------------------------------------------
    # Loading and reset
    # ------------------------------------------------------------------
    def reset(self) -> None:
        """Reset CPU state, flags, and RAM (the loaded program is kept)."""
        self.ram = [0] * self.RAM_SIZE
        self.pc = 0
        self.sp = 0
        self.C = 0
        self.Z = 0
        self.V = 0
        self.halted = False
        self.sleeping = False
        self.uart_tx = []
        self.uart_rx = []
        self.uart_tx_high = 0
        self.uart_error = False
        self.instruction_count = 0
        self.cycle_count = 0
        self.sync_counter = 0
        self.user_sync = False
        self.random_state = 0xACE1
        self.keys_down = set()
        self.alt_down = False
        self.last_key = 0
        self.just_pressed = False
        if self.io_trace is not None:
            self.io_trace = []
            self.io_trace_total = 0
        self._pc_at_fetch = 0

    # ------------------------------------------------------------------
    # I/O tracing and input-port helpers
    # ------------------------------------------------------------------
    def trace_io(self, limit: int | None = 2000) -> None:
        """Start recording OUT/OUTB/IN/INB accesses.

        *limit* caps the number of stored events; ``None`` stores everything.
        ``io_trace_total`` keeps counting past the limit, so a caller can see
        how many events were dropped.
        """

        self.io_trace = []
        self.io_trace_limit = limit
        self.io_trace_total = 0

    def stop_io_trace(self) -> None:
        """Disable I/O tracing while keeping any recorded events."""

        self.io_trace_limit = 0

    def _record_io(
        self,
        kind: str,
        address: int,
        before: int,
        after: int,
        bit: int | None = None,
    ) -> None:
        if self.io_trace is None:
            return
        self.io_trace_total += 1
        if self.io_trace_limit is not None and len(self.io_trace) >= self.io_trace_limit:
            return
        self.io_trace.append(
            IoTraceEvent(
                step=self.instruction_count,
                pc=self._pc_at_fetch,
                kind=kind,
                address=address & 0xFF,
                before=before & 0xF,
                after=after & 0xF,
                bit=bit,
            )
        )

    def set_input(self, value: int, bank: int | None = None) -> None:
        """Set the 4-bit input port used by IN/INB tests.

        ``bank=None`` writes both bank 0 (0x0B) and bank 1 (0xFB), which is
        convenient when the program may change ``WrFlags.IOPos``.  Pass 0 or
        1 to target the bank selected by ``IOPos=0`` / ``IOPos=1``.
        """

        value &= 0xF
        if bank in (None, 0):
            self.ram[0x0B] = value
        if bank in (None, 1):
            self.ram[0xFB] = value

    def halt(self) -> None:
        """Request that :meth:`run` stop before its step limit."""
        self.halted = True

    def load_words(self, words: Iterable[int]) -> None:
        """Load an iterable of 12-bit instruction words into program memory.

        Loading also resets the CPU and clears data RAM.  Program memory is
        cleared first, so omitted trailing words read as ``CP R0,0``.
        """
        loaded = [int(word) for word in words]
        if len(loaded) > self.PROGRAM_SIZE:
            raise ValueError(
                f"program has {len(loaded)} words; maximum is {self.PROGRAM_SIZE}"
            )
        for index, word in enumerate(loaded):
            if not 0 <= word <= 0xFFF:
                raise ValueError(
                    f"instruction {index} is 0x{word:X}; expected a 12-bit word"
                )

        self.program = [0] * self.PROGRAM_SIZE
        self.program[: len(loaded)] = loaded
        self.reset()

    def load_bytes(self, data: bytes | bytearray | memoryview | Iterable[int]) -> None:
        """Load program bytes.

        If ``data`` starts with the assembler's 6-byte header it is parsed
        as a complete ``.hex`` file (header, length, payload, checksum).
        Otherwise it is treated as a raw stream of little-endian 12-bit
        instruction words (two bytes per instruction).
        """
        raw = bytes(data)
        if raw.startswith(self.HEX_HEADER):
            self._load_hex_bytes(raw)
            return

        if len(raw) % 2:
            raise ValueError("raw program data must contain an even number of bytes")
        words = [
            raw[index] | (raw[index + 1] << 8)
            for index in range(0, len(raw), 2)
        ]
        self.load_words(words)

    def load_hex(self, path: str | Path) -> None:
        """Load an assembler ``.hex`` file.

        The file format is::

            00 FF 00 FF A5 C3   header
            LL HH               number of 12-bit words, little-endian
            <2 bytes per word>  word low byte first
            CL CH               16-bit checksum, little-endian

        The checksum is the 16-bit sum of the little-endian words formed
        by the length field and the program payload.
        """
        raw = Path(path).read_bytes()
        self._load_hex_bytes(raw)

    def _load_hex_bytes(self, raw: bytes) -> None:
        """Parse and validate an in-memory assembler ``.hex`` image."""
        if len(raw) < 10:
            raise ValueError("hex file is too short to contain a header and checksum")
        if raw[:6] != self.HEX_HEADER:
            raise ValueError("hex file has an invalid header")

        word_count = raw[6] | (raw[7] << 8)
        payload = raw[8:-2]
        if len(payload) != word_count * 2:
            raise ValueError(
                "hex file length field says "
                f"{word_count} words, but payload contains "
                f"{len(payload) // 2} words"
            )

        checksum_data = raw[6:-2]
        checksum = 0
        for index in range(0, len(checksum_data), 2):
            checksum += checksum_data[index] | (checksum_data[index + 1] << 8)
            checksum &= 0xFFFF
        expected = raw[-2] | (raw[-1] << 8)
        if checksum != expected:
            raise ValueError(
                f"hex file checksum mismatch: calculated 0x{checksum:04X}, "
                f"file contains 0x{expected:04X}"
            )

        words = [
            payload[index] | (payload[index + 1] << 8)
            for index in range(0, len(payload), 2)
        ]
        self.load_words(words)

    # ------------------------------------------------------------------
    # Execution
    # ------------------------------------------------------------------
    def step(self) -> None:
        """Fetch and execute exactly one instruction."""
        if self.halted:
            return

        word = self.program[self.pc & 0xFFF]
        self._pc_at_fetch = self.pc
        # The PC points to the next instruction while the current one
        # executes.  This matches JR/SKIP/DSZ, which are documented relative
        # to the already-incremented PC.
        self.pc = (self.pc + 1) & 0xFFF
        self.instruction_count += 1
        self.cycle_count += 2
        self._tick_sync()
        self._execute(word)

    def run(self, max_steps: int = 100000) -> int:
        """Run until ``halted`` or ``max_steps`` instructions execute.

        Returns the number of instructions actually executed.  An intentional
        infinite loop such as ``JR -1`` is not auto-detected; the caller must
        supply a step limit.
        """
        if max_steps < 0:
            raise ValueError("max_steps must be non-negative")

        executed = 0
        while executed < max_steps and not self.halted:
            self.step()
            executed += 1
        return executed

    def _execute(self, word: int) -> None:
        """Decode and execute one 12-bit instruction word."""
        opcode = (word >> 8) & 0xF
        x = (word >> 4) & 0xF
        y = word & 0xF

        if opcode != 0:
            self._execute_4bit_opcode(opcode, x, y)
        else:
            self._execute_8bit_opcode(x, y)

    def _execute_4bit_opcode(self, opcode: int, x: int, y: int) -> None:
        """Execute instructions whose high nibble is a 4-bit opcode."""
        if opcode == 0x1:  # ADD RX,RY
            self._add(x, self.ram[y], carry_in=0)
        elif opcode == 0x2:  # ADC RX,RY
            self._add(x, self.ram[y], carry_in=self.C)
        elif opcode == 0x3:  # SUB RX,RY
            self._subtract(x, self.ram[y], borrow_in=0)
        elif opcode == 0x4:  # SBB RX,RY
            # The manual describes "- C", but its worked examples subtract
            # one when C=0 (borrow asserted).  C is inverse borrow.
            self._subtract(x, self.ram[y], borrow_in=1 if self.C == 0 else 0)
        elif opcode == 0x5:  # OR RX,RY
            self.ram[x] = self.ram[x] | self.ram[y]
            self._set_z(self.ram[x])
        elif opcode == 0x6:  # AND RX,RY
            self.ram[x] = self.ram[x] & self.ram[y]
            self._set_z(self.ram[x])
        elif opcode == 0x7:  # XOR RX,RY
            self.ram[x] = self.ram[x] ^ self.ram[y]
            self._set_z(self.ram[x])
        elif opcode == 0x8:  # MOV RX,RY
            before = self.ram[x]
            self.ram[x] = self.ram[y]
            if x in (0x0A, 0x0B):
                self._record_io("write", x, before, self.ram[x])
            if y == 0x0B and x != 0x0B:
                self._record_io("read", 0x0B, self.ram[y], self.ram[y])
            self._after_register_write(x)
        elif opcode == 0x9:  # MOV RX,N
            before = self.ram[x]
            self.ram[x] = y
            if x in (0x0A, 0x0B):
                self._record_io("write", x, before, self.ram[x])
            self._after_register_write(x)
        elif opcode == 0xA:  # MOV [XY],R0
            address = (self.ram[x] << 4) | self.ram[y]
            self._write_memory(address, self.ram[0])
        elif opcode == 0xB:  # MOV R0,[XY]
            address = (self.ram[x] << 4) | self.ram[y]
            self.ram[0] = self._read_memory(address)
        elif opcode == 0xC:  # MOV [NN],R0
            address = (x << 4) | y
            self._write_memory(address, self.ram[0])
        elif opcode == 0xD:  # MOV R0,[NN]
            address = (x << 4) | y
            self.ram[0] = self._read_memory(address)
        elif opcode == 0xE:  # MOV PC,NN -- sets PCM/PCH only
            self.ram[self.PCM] = y
            self.ram[self.PCH] = x
        elif opcode == 0xF:  # JR NN
            offset = (x << 4) | y
            if offset & 0x80:
                offset -= 0x100
            self.pc = (self.pc + offset) & 0xFFF
        else:  # pragma: no cover - all 16 opcodes are covered above
            raise EmulatorError(f"unimplemented opcode 0x{opcode:X}")

    def _execute_8bit_opcode(self, opcode: int, operand: int) -> None:
        """Execute instructions with high nibble zero and an 8-bit opcode."""
        if opcode == 0x0:  # CP R0,N
            value = self.ram[0]
            self.C = 1 if value >= operand else 0
            self.Z = 1 if value == operand else 0
        elif opcode == 0x1:  # ADD R0,N
            self._add(0, operand, carry_in=0)
        elif opcode == 0x2:  # INC RY
            result = (self.ram[operand] + 1) & 0xF
            self.ram[operand] = result
            if result == 0:
                self.Z = 1
                self.C = 1
            else:
                self.Z = 0
                self.C = 0
            self._after_register_write(operand)
        elif opcode == 0x3:  # DEC RY
            result = (self.ram[operand] - 1) & 0xF
            self.ram[operand] = result
            self.Z = 1 if result == 0 else 0
            # DEC clears C only for the 0 -> 15 underflow result.
            self.C = 0 if result == 0xF else 1
            self._after_register_write(operand)
        elif opcode == 0x4:  # DSZ RY
            result = (self.ram[operand] - 1) & 0xF
            self.ram[operand] = result
            # DSZ never changes flags, and it skips the next instruction
            # when the decremented value reaches zero.
            if result == 0:
                self.pc = (self.pc + 1) & 0xFFF
        elif opcode == 0x5:  # OR R0,N
            self.ram[0] = self.ram[0] | operand
            self._set_z(self.ram[0])
            self.C = 1
        elif opcode == 0x6:  # AND R0,N
            self.ram[0] = self.ram[0] & operand
            self._set_z(self.ram[0])
            self.C = 0
        elif opcode == 0x7:  # XOR R0,N
            self.ram[0] = self.ram[0] ^ operand
            self._set_z(self.ram[0])
            self.C = 1 - self.C  # XOR R0,N complements C
        elif opcode == 0x8:  # EXR N
            count = 16 if operand == 0 else operand
            for index in range(count):
                alt = 0xE0 + index
                self.ram[index], self.ram[alt] = self.ram[alt], self.ram[index]
        elif opcode == 0x9:  # BIT RG,M
            group = (operand >> 2) & 0x3
            bit = operand & 0x3
            address = self._bit_read_address(group)
            if group == 3:
                self._record_io(
                    "read", address, self.ram[address], self.ram[address], bit
                )
            self.Z = 0 if (self.ram[address] >> bit) & 1 else 1
        elif opcode == 0xA:  # BSET RG,M
            group = (operand >> 2) & 0x3
            bit = operand & 0x3
            address = self._bit_write_address(group)
            before = self.ram[address]
            self.ram[address] = (self.ram[address] | (1 << bit)) & 0xF
            if group == 3:
                self._record_io("bit", address, before, self.ram[address], bit)
        elif opcode == 0xB:  # BCLR RG,M
            group = (operand >> 2) & 0x3
            bit = operand & 0x3
            address = self._bit_write_address(group)
            before = self.ram[address]
            self.ram[address] = self.ram[address] & ~(1 << bit) & 0xF
            if group == 3:
                self._record_io("bit", address, before, self.ram[address], bit)
        elif opcode == 0xC:  # BTG RG,M
            group = (operand >> 2) & 0x3
            bit = operand & 0x3
            address = self._bit_write_address(group)
            before = self.ram[address]
            self.ram[address] = (self.ram[address] ^ (1 << bit)) & 0xF
            if group == 3:
                self._record_io("bit", address, before, self.ram[address], bit)
        elif opcode == 0xD:  # RRC RY
            value = self.ram[operand]
            old_carry = self.C
            self.C = value & 1
            result = ((old_carry & 1) << 3) | ((value >> 1) & 0x7)
            self.ram[operand] = result
            self.Z = 1 if result == 0 else 0
        elif opcode == 0xE:  # RET R0,N
            self.ram[0] = operand
            self._pop_return_address()
        elif opcode == 0xF:  # SKIP F,M
            condition = (operand >> 2) & 0x3
            count = operand & 0x3
            if count == 0:
                count = 4
            taken = (
                (condition == 0 and self.C)
                or (condition == 1 and not self.C)
                or (condition == 2 and self.Z)
                or (condition == 3 and not self.Z)
            )
            if taken:
                self.pc = (self.pc + count) & 0xFFF
        else:  # pragma: no cover - all 16 opcodes are covered above
            raise EmulatorError(f"unimplemented opcode 0x0{opcode:X}")

    # ------------------------------------------------------------------
    # Memory and UART model
    # ------------------------------------------------------------------
    def read_nibble(self, address: int) -> int:
        """Public SFR/RAM read used by tests and tooling."""
        return self._read_memory(address)

    def write_nibble(self, address: int, value: int) -> None:
        """Public SFR/RAM write used by tests and tooling."""
        self._write_memory(address, value)

    def _read_memory(self, address: int) -> int:
        """Read a nibble, modelling UART, PRNG, keys, and status SFRs."""
        address &= 0xFF
        if address == 0xF8:  # Received: number of queued bytes, saturating
            return min(len(self.uart_rx), 15)
        if address == 0xF7:  # SerHigh
            if self.uart_rx:
                return (self.uart_rx[0] >> 4) & 0xF
            return self.ram[0xF7]
        if address == 0xF6:  # SerLow (reading pops a byte)
            if self.uart_rx:
                byte = self.uart_rx.pop(0)
                self.ram[0xF6] = byte & 0xF
                self.ram[0xF7] = (byte >> 4) & 0xF
                return byte & 0xF
            return self.ram[0xF6]
        if address == 0xF5:  # SerCtrl: error + baud; reading clears error
            value = (0x8 if self.uart_error else 0) | (self.ram[0xF5] & 0x7)
            self.uart_error = False
            return value
        if address == 0xFC:  # KeyStatus; reading clears JustPress
            value = 0
            if self.alt_down:
                value |= 0x8
            if self.keys_down:
                value |= 0x4
            if self.last_key in self.keys_down:
                value |= 0x2
            if self.just_pressed:
                value |= 0x1
            self.just_pressed = False
            return value
        if address == 0xFD:  # KeyReg
            return self.last_key & 0xF
        if address == 0xFF:  # Random: return low nibble, then advance
            value = self.random_state & 0xF
            self.random_state = (self.random_state * 1103515245 + 12345) & 0xFFFF
            self.ram[0xFF] = value
            return value
        if address == 0xF4:  # RdFlags: V flag + UserSync, clears UserSync
            value = (1 if self.V else 0) << 1
            if self.user_sync:
                value |= 1
            self.user_sync = False
            return value
        value = self.ram[address]
        if address in (0x0B, 0xFB):
            self._record_io("read", address, value, value)
        return value

    def _write_memory(self, address: int, value: int) -> None:
        """Write a nibble, modelling UART, PRNG, and SFR side effects."""
        address &= 0xFF
        value &= 0xF
        if address == 0xF7:  # SerHigh
            self.uart_tx_high = value
            self.ram[0xF7] = value
            return
        if address == 0xF6:  # SerLow: writing starts a byte transmission
            self.ram[0xF6] = value
            self.uart_tx.append(((self.uart_tx_high & 0xF) << 4) | value)
            return
        if address == 0xFF:  # seed
            self.random_state = 0xACE1 if value == 15 else value
            self.ram[0xFF] = value
            return
        if address == 0xF9 and value == 0:  # AutoOff = 0 enters SLEEP
            self.ram[0xF9] = 0
            self.sleeping = True
            self.halted = True
            return
        if address in (0x0A, 0xFA):
            before = self.ram[address]
            self.ram[address] = value
            self._record_io("write", address, before, value)
            return
        self.ram[address] = value

    def _tick_sync(self) -> None:
        """Approximate the Sync divider / UserSync flag."""
        divider = self.ram[0xF2] & 0xF
        period = 16 << divider
        self.sync_counter += 1
        if self.sync_counter >= period:
            self.sync_counter = 0
            self.user_sync = True

    # ------------------------------------------------------------------
    # Input, display, and timing helpers
    # ------------------------------------------------------------------
    def press_key(self, key: int) -> None:
        """Press a key number (0..13)."""
        key &= 0xF
        self.keys_down.add(key)
        self.last_key = key
        self.just_pressed = True

    def release_key(self, key: int) -> None:
        self.keys_down.discard(key & 0xF)

    def press_alt(self) -> None:
        self.alt_down = True

    def release_alt(self) -> None:
        self.alt_down = False

    def display_pages(self) -> tuple[list[int], list[int]]:
        """Return the 16 nibbles shown on the left (Page+1) and right (Page)."""
        page = self.ram[0xF0] & 0xF
        left = [self.ram[(((page + 1) & 0xF) * 16 + index) & 0xFF] for index in range(16)]
        right = [self.ram[(page * 16 + index) & 0xFF] for index in range(16)]
        return left, right

    @property
    def clock_hz(self) -> float:
        speeds = [250e3, 100e3, 30e3, 10e3, 3e3, 1e3, 500, 200, 100, 50, 20, 10, 5, 2, 1, 0.5]
        return speeds[self.ram[0xF1] & 0xF]

    @property
    def elapsed_seconds(self) -> float:
        return self.cycle_count / max(self.clock_hz, 0.001)

    def receive_uart(self, data: bytes | bytearray | list[int]) -> None:
        """Queue bytes for the program to read."""
        for byte in data:
            if len(self.uart_rx) >= 257:
                self.uart_error = True
            else:
                self.uart_rx.append(int(byte) & 0xFF)

    # ------------------------------------------------------------------
    # ALU helpers
    # ------------------------------------------------------------------
    @staticmethod
    def _signed4(value: int) -> int:
        """Interpret a nibble as a signed two's-complement value."""
        return value - 16 if value & 0x8 else value

    def _set_z(self, value: int) -> None:
        self.Z = 1 if (value & 0xF) == 0 else 0

    def _add(self, destination: int, source_value: int, carry_in: int) -> None:
        """Add into ``ram[destination]`` and update C/Z/V."""
        left = self.ram[destination]
        total = left + source_value + (1 if carry_in else 0)
        result = total & 0xF
        self.ram[destination] = result

        self.C = 1 if total > 15 else 0
        self.Z = 1 if result == 0 else 0
        signed_total = self._signed4(left) + self._signed4(source_value)
        signed_total += 1 if carry_in else 0
        self.V = 0 if -8 <= signed_total <= 7 else 1

    def _subtract(self, destination: int, source_value: int, borrow_in: int) -> None:
        """Subtract from ``ram[destination]`` and update C/Z/V.

        ``C`` is inverse borrow: after the operation C=1 means no borrow
        (the full difference is non-negative), C=0 means borrow.
        """
        left = self.ram[destination]
        difference = left - source_value - (1 if borrow_in else 0)
        result = difference & 0xF
        self.ram[destination] = result

        self.C = 1 if difference >= 0 else 0
        self.Z = 1 if result == 0 else 0
        signed_difference = self._signed4(left) - self._signed4(source_value)
        signed_difference -= 1 if borrow_in else 0
        self.V = 0 if -8 <= signed_difference <= 7 else 1

    # ------------------------------------------------------------------
    # Jumps, calls, and stack
    # ------------------------------------------------------------------
    def _after_register_write(self, register: int) -> None:
        """Handle the side effects of MOV/INC/DEC on JSR and PCL.

        Only MOV RX,RY, MOV RX,N, INC RY and DEC RY trigger these effects.
        Writes through memory-addressing instructions do not.
        """
        if register == self.JSR:
            self._call_subroutine()
        elif register == self.PCL:
            self._jump_to_pcl()

    def _jump_to_pcl(self) -> None:
        self.pc = (
            self.ram[self.PCL]
            | (self.ram[self.PCM] << 4)
            | (self.ram[self.PCH] << 8)
        ) & 0xFFF

    def _call_subroutine(self) -> None:
        """Push the already-incremented PC, then jump through JSR/PCM/PCH."""
        self._push_return_address()
        self.pc = (
            self.ram[self.JSR]
            | (self.ram[self.PCM] << 4)
            | (self.ram[self.PCH] << 8)
        ) & 0xFFF

    def _push_return_address(self) -> None:
        base = 0x10 + self.sp * 3
        if base + 2 >= self.RAM_SIZE:
            raise EmulatorStackError("subroutine stack overflow")
        return_pc = self.pc & 0xFFF
        self.ram[base] = return_pc & 0xF
        self.ram[base + 1] = (return_pc >> 4) & 0xF
        self.ram[base + 2] = (return_pc >> 8) & 0xF
        self.sp += 1

    def _pop_return_address(self) -> None:
        if self.sp <= 0:
            raise EmulatorStackError("subroutine stack underflow")
        self.sp -= 1
        base = 0x10 + self.sp * 3
        self.pc = (
            self.ram[base]
            | (self.ram[base + 1] << 4)
            | (self.ram[base + 2] << 8)
        ) & 0xFFF

    # ------------------------------------------------------------------
    # BIT/BSET/BCLR/BTG helpers
    # ------------------------------------------------------------------
    def _io_position(self) -> int:
        """Return WrFlags.IOPos (SFR 0xF3, bit 1)."""
        return (self.ram[0xF3] >> 1) & 1

    def _bit_read_address(self, group: int) -> int:
        """Map a BIT group to R0/R1/R2 or the active IN register."""
        if group < 3:
            return group
        # G=3 reads IN (0x0B) or InB (0xFB), selected by WrFlags.IOPos.
        return 0xFB if self._io_position() else 0x0B

    def _bit_write_address(self, group: int) -> int:
        """Map a BSET/BCLR/BTG group to R0/R1/R2 or the active OUT register."""
        if group < 3:
            return group
        # G=3 writes OUT (0x0A) or OutB (0xFA), selected by WrFlags.IOPos.
        return 0xFA if self._io_position() else 0x0A

    # ------------------------------------------------------------------
    # State inspection
    # ------------------------------------------------------------------
    def state(self) -> dict:
        """Return a snapshot of the machine state.

        The returned lists are copies, so mutating them will not change the
        emulator.  ``registers`` is the first 16 data-memory locations
        (R0..PCH); ``ram`` is the complete 256-nibble data memory.
        """
        return {
            "pc": self.pc,
            "sp": self.sp,
            "C": self.C,
            "Z": self.Z,
            "V": self.V,
            "flags": {"C": self.C, "Z": self.Z, "V": self.V},
            "registers": list(self.ram[:16]),
            "ram": list(self.ram),
            "halted": self.halted,
            "instructions": self.instruction_count,
            "cycles": self.cycle_count,
            "clock_hz": self.clock_hz,
            "uart_tx": list(self.uart_tx),
            "uart_rx": list(self.uart_rx),
            "keys_down": sorted(self.keys_down),
            "alt_down": self.alt_down,
            "last_key": self.last_key,
            "display_left": self.display_pages()[0],
            "display_right": self.display_pages()[1],
        }
