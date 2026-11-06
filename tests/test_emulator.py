"""Tests for the headless Supercon.6 / Voja4 emulator.

Run from the repository root with::

    python -m pytest
"""

from __future__ import annotations

import pytest

from badgec.emulator import Emulator, EmulatorStackError


# ---------------------------------------------------------------------------
# Instruction-encoding helpers
# ---------------------------------------------------------------------------
def word(opcode: int, x: int = 0, y: int = 0) -> int:
    """Build a 12-bit instruction word using the manual's nibble layout."""
    return ((opcode & 0xF) << 8) | ((x & 0xF) << 4) | (y & 0xF)


def op8(opcode: int, operand: int) -> int:
    """Build an instruction with the 8-bit opcode form (high nibble zero)."""
    return word(0, opcode, operand)


def make_hex(words: list[int]) -> bytes:
    """Create a valid assembler .hex image for the given instruction words."""
    payload = b"".join(
        bytes((instruction & 0xFF, (instruction >> 8) & 0xFF))
        for instruction in words
    )
    body = bytes((len(words) & 0xFF, (len(words) >> 8) & 0xFF)) + payload
    checksum = 0
    for index in range(0, len(body), 2):
        checksum = (checksum + body[index] + (body[index + 1] << 8)) & 0xFFFF
    return (
        Emulator.HEX_HEADER
        + body
        + bytes((checksum & 0xFF, (checksum >> 8) & 0xFF))
    )


# ---------------------------------------------------------------------------
# Arithmetic and flags
# ---------------------------------------------------------------------------
def test_add_and_adc_flags():
    cpu = Emulator()
    cpu.load_words([word(0x1, 0, 1)])
    cpu.ram[0] = 11
    cpu.ram[1] = 7
    cpu.step()
    assert cpu.ram[0] == 2
    assert (cpu.C, cpu.Z, cpu.V) == (1, 0, 0)  # unsigned carry, signed ok

    cpu.load_words([word(0x1, 2, 3)])
    cpu.ram[2] = 8
    cpu.ram[3] = 8
    cpu.step()
    assert cpu.ram[2] == 0
    assert (cpu.C, cpu.Z, cpu.V) == (1, 1, 1)  # -8 + -8 overflows signed

    cpu.load_words([word(0x2, 0, 1)])
    cpu.ram[0] = 7
    cpu.ram[1] = 1
    cpu.C = 1
    cpu.step()
    assert cpu.ram[0] == 9
    assert (cpu.C, cpu.Z, cpu.V) == (0, 0, 1)  # 7 + 1 + 1 = 9 signed overflow

    cpu.load_words([word(0x2, 0, 1)])
    cpu.ram[0] = 4
    cpu.ram[1] = 11
    cpu.C = 1
    cpu.step()
    assert cpu.ram[0] == 0
    assert (cpu.C, cpu.Z, cpu.V) == (1, 1, 0)  # 4 + 11 + 1 = 16


def test_sub_and_sbb_flags_and_borrow_direction():
    cpu = Emulator()

    # SUB 15 - 9 = 6, no borrow.
    cpu.load_words([word(0x3, 0, 1)])
    cpu.ram[0] = 15
    cpu.ram[1] = 9
    cpu.step()
    assert cpu.ram[0] == 6
    assert (cpu.C, cpu.Z, cpu.V) == (1, 0, 0)

    # SUB 3 - 6 = 13 with borrow.
    cpu.load_words([word(0x3, 0, 1)])
    cpu.ram[0] = 3
    cpu.ram[1] = 6
    cpu.step()
    assert cpu.ram[0] == 13
    assert (cpu.C, cpu.Z, cpu.V) == (0, 0, 0)

    # SUB 7 - 15 = 8: borrow, and signed 7 - (-1) overflows.
    cpu.load_words([word(0x3, 0, 1)])
    cpu.ram[0] = 7
    cpu.ram[1] = 15
    cpu.step()
    assert cpu.ram[0] == 8
    assert (cpu.C, cpu.Z, cpu.V) == (0, 0, 1)

    # Manual SBB example 1: 14 - 3 - 1 (because C=0) = 10.
    cpu.load_words([word(0x4, 0, 1)])
    cpu.ram[0] = 14
    cpu.ram[1] = 3
    cpu.C = 0
    cpu.step()
    assert cpu.ram[0] == 10
    assert (cpu.C, cpu.Z, cpu.V) == (1, 0, 0)

    # Manual SBB example 2: 6 - 14 - 0 (because C=1) = 8.
    cpu.load_words([word(0x4, 0, 1)])
    cpu.ram[0] = 6
    cpu.ram[1] = 14
    cpu.C = 1
    cpu.step()
    assert cpu.ram[0] == 8
    assert (cpu.C, cpu.Z, cpu.V) == (0, 0, 1)

    # 4 - 3 - 1 = 0.
    cpu.load_words([word(0x4, 0, 1)])
    cpu.ram[0] = 4
    cpu.ram[1] = 3
    cpu.C = 0
    cpu.step()
    assert cpu.ram[0] == 0
    assert (cpu.C, cpu.Z, cpu.V) == (1, 1, 0)


def test_cp_inc_and_dec_flags():
    cpu = Emulator()
    cpu.load_words([op8(0x0, 5)])
    cpu.ram[0] = 5
    cpu.step()
    assert (cpu.C, cpu.Z) == (1, 1)

    cpu.load_words([op8(0x0, 5)])
    cpu.ram[0] = 4
    cpu.step()
    assert (cpu.C, cpu.Z) == (0, 0)

    cpu.load_words([op8(0x0, 5)])
    cpu.ram[0] = 6
    cpu.step()
    assert (cpu.C, cpu.Z) == (1, 0)

    cpu.load_words([op8(0x2, 3)])
    cpu.ram[3] = 15
    cpu.step()
    assert cpu.ram[3] == 0
    assert (cpu.C, cpu.Z) == (1, 1)

    cpu.load_words([op8(0x2, 3)])
    cpu.ram[3] = 4
    cpu.step()
    assert cpu.ram[3] == 5
    assert (cpu.C, cpu.Z) == (0, 0)

    cpu.load_words([op8(0x3, 3)])
    cpu.ram[3] = 0
    cpu.step()
    assert cpu.ram[3] == 15
    assert (cpu.C, cpu.Z) == (0, 0)

    cpu.load_words([op8(0x3, 3)])
    cpu.ram[3] = 1
    cpu.step()
    assert cpu.ram[3] == 0
    assert (cpu.C, cpu.Z) == (1, 1)

    cpu.load_words([op8(0x3, 3)])
    cpu.ram[3] = 3
    cpu.step()
    assert cpu.ram[3] == 2
    assert (cpu.C, cpu.Z) == (1, 0)


# ---------------------------------------------------------------------------
# Memory addressing and MOV
# ---------------------------------------------------------------------------
def test_direct_and_indirect_memory_addressing():
    cpu = Emulator()
    cpu.load_words(
        [
            word(0x9, 0, 0xA),      # MOV R0,10
            word(0xC, 4, 2),        # MOV [0x42],R0
            word(0x9, 0, 0),        # MOV R0,0
            word(0xD, 4, 2),        # MOV R0,[0x42]
        ]
    )
    for _ in range(4):
        cpu.step()
    assert cpu.ram[0x42] == 0xA
    assert cpu.ram[0] == 0xA

    # Indirect addressing uses the *contents* of RX and RY as the address.
    cpu.load_words(
        [
            word(0x9, 1, 3),        # MOV R1,3
            word(0x9, 2, 4),        # MOV R2,4
            word(0x9, 0, 0xB),      # MOV R0,11
            word(0xA, 1, 2),        # MOV [R1:R2],R0 -> [0x34]
            word(0x9, 0, 0),        # MOV R0,0
            word(0xB, 1, 2),        # MOV R0,[R1:R2]
        ]
    )
    for _ in range(6):
        cpu.step()
    assert cpu.ram[0x34] == 0xB
    assert cpu.ram[0] == 0xB


def test_mov_pc_sets_pcm_pch_and_pcl_causes_jump():
    cpu = Emulator()
    cpu.load_words(
        [
            word(0xE, 3, 1),        # MOV PC,0x31 -> PCM=1, PCH=3
            word(0x9, 0, 0),        # MOV R0,0
            word(0x8, 0xD, 0),      # MOV PCL,R0 -> jump to PCH:PCM:PCL
        ]
    )
    cpu.step()
    assert cpu.pc == 1
    assert cpu.ram[0x0E] == 1
    assert cpu.ram[0x0F] == 3

    cpu.step()
    cpu.step()
    assert cpu.pc == 0x310


# ---------------------------------------------------------------------------
# Relative jumps, skip, and DSZ
# ---------------------------------------------------------------------------
def test_jr_is_relative_to_next_instruction_and_supports_backward_jumps():
    cpu = Emulator()
    cpu.load_words(
        [
            word(0xF, 0, 1),        # JR +1 (from address 1 to address 2)
            word(0x9, 0, 1),        # should be skipped
            word(0x9, 0, 5),        # MOV R0,5
        ]
    )
    cpu.step()
    assert cpu.pc == 2
    cpu.step()
    assert cpu.ram[0] == 5

    # JR -1 is an intentional infinite loop.  It is not auto-halted.
    cpu.load_words([word(0xF, 0xF, 0xF)])
    assert cpu.run(max_steps=7) == 7
    assert cpu.pc == 0
    assert cpu.halted is False


def test_skip_conditions_and_counts():
    cpu = Emulator()
    cpu.load_words(
        [
            op8(0xF, (0 << 2) | 2),  # SKIP C,2
            word(0x9, 0, 1),
            word(0x9, 0, 2),
            word(0x9, 0, 3),
        ]
    )
    cpu.C = 1
    cpu.step()
    assert cpu.pc == 3
    cpu.step()
    assert cpu.ram[0] == 3

    # M=0 means skip four instructions (addresses 1..4 after the SKIP).
    cpu.load_words([op8(0xF, 0)])
    cpu.C = 1
    cpu.step()
    assert cpu.pc == 5

    # NC is not taken when C=1.
    cpu.load_words([op8(0xF, (1 << 2) | 2)])
    cpu.C = 1
    cpu.step()
    assert cpu.pc == 1

    # Z and NZ conditions.
    cpu.load_words([op8(0xF, (2 << 2) | 1)])
    cpu.Z = 1
    cpu.step()
    assert cpu.pc == 2

    cpu.load_words([op8(0xF, (3 << 2) | 1)])
    cpu.Z = 0
    cpu.step()
    assert cpu.pc == 2


def test_dsz_decrements_and_skips_only_at_zero_without_touching_flags():
    cpu = Emulator()
    cpu.load_words(
        [
            op8(0x4, 3),            # DSZ R3
            word(0xF, 0xF, 0xF),    # JR -1 (skipped when R3 reaches 0)
            word(0x9, 2, 13),       # MOV R2,13
        ]
    )
    cpu.ram[3] = 1
    cpu.C = 1
    cpu.Z = 1
    cpu.step()
    assert cpu.ram[3] == 0
    assert cpu.pc == 2  # skipped the JR
    assert (cpu.C, cpu.Z, cpu.V) == (1, 1, 0)
    cpu.step()
    assert cpu.ram[2] == 13

    cpu.load_words([op8(0x4, 3), word(0x9, 0, 7)])
    cpu.ram[3] = 2
    cpu.step()
    assert cpu.ram[3] == 1
    assert cpu.pc == 1


# ---------------------------------------------------------------------------
# RRC, EXR, and bit operations
# ---------------------------------------------------------------------------
def test_rrc_uses_old_carry_and_old_bit_zero():
    cpu = Emulator()
    cpu.load_words([op8(0xD, 4)])
    cpu.ram[4] = 0b0100
    cpu.C = 1
    cpu.step()
    assert cpu.ram[4] == 0b1010
    assert (cpu.C, cpu.Z) == (0, 0)

    cpu.load_words([op8(0xD, 4)])
    cpu.ram[4] = 0b0001
    cpu.C = 0
    cpu.step()
    assert cpu.ram[4] == 0
    assert (cpu.C, cpu.Z) == (1, 1)

    # V is unaffected.
    cpu.load_words([op8(0xD, 4)])
    cpu.ram[4] = 0b0010
    cpu.V = 1
    cpu.C = 0
    cpu.step()
    assert cpu.ram[4] == 0b0001
    assert (cpu.C, cpu.V) == (0, 1)


def test_exr_swaps_main_and_alternate_register_banks():
    cpu = Emulator()
    cpu.load_words([op8(0x8, 2)])
    cpu.ram[0] = 1
    cpu.ram[1] = 2
    cpu.ram[0xE0] = 3
    cpu.ram[0xE1] = 4
    cpu.step()
    assert (cpu.ram[0], cpu.ram[1]) == (3, 4)
    assert (cpu.ram[0xE0], cpu.ram[0xE1]) == (1, 2)

    # N=0 is the special case meaning all 16 registers.
    cpu.load_words([op8(0x8, 0)])
    for index in range(16):
        cpu.ram[index] = index
        cpu.ram[0xE0 + index] = 15 - index
    cpu.step()
    assert cpu.ram[0] == 15
    assert cpu.ram[15] == 0
    assert cpu.ram[0xE0] == 0
    assert cpu.ram[0xEF] == 15


def test_bit_bset_bclr_btg():
    cpu = Emulator()
    cpu.load_words(
        [
            op8(0x9, (2 << 2) | 1),  # BIT R2,1
            op8(0x9, (2 << 2) | 0),  # BIT R2,0
            op8(0xA, (1 << 2) | 2),  # BSET R1,2
            op8(0xB, (1 << 2) | 2),  # BCLR R1,2
            op8(0xC, (1 << 2) | 2),  # BTG R1,2
        ]
    )
    cpu.ram[2] = 0b1010
    cpu.step()
    assert cpu.Z == 0  # bit 1 is set
    cpu.step()
    assert cpu.Z == 1  # bit 0 is clear

    cpu.ram[1] = 0
    cpu.step()
    assert cpu.ram[1] == 0b0100
    cpu.step()
    assert cpu.ram[1] == 0
    cpu.step()
    assert cpu.ram[1] == 0b0100

    # G=3 reads IN and writes OUT, with IOPos selecting the alternate bank.
    cpu.load_words(
        [
            op8(0x9, (3 << 2) | 3),  # BIT IN,3
            op8(0xA, (3 << 2) | 0),  # BSET OUT,0
        ]
    )
    cpu.ram[0xF3] = 0  # IOPos=0 -> IN=0x0B, OUT=0x0A
    cpu.ram[0x0B] = 0b1000
    cpu.step()
    assert cpu.Z == 0
    cpu.step()
    assert cpu.ram[0x0A] == 0b0001


# ---------------------------------------------------------------------------
# Calls, returns, and flash RET tables
# ---------------------------------------------------------------------------
def test_call_and_ret_push_and_pop_return_address():
    cpu = Emulator()
    program = [0] * Emulator.PROGRAM_SIZE
    program[0] = word(0xE, 0, 2)    # MOV PC,0x02 -> PCM=2, PCH=0
    program[1] = word(0x9, 0xC, 0)  # MOV JSR,0 -> call 0x020
    program[2] = word(0x9, 0, 0xA)  # MOV R0,10 (after return)
    program[0x20] = op8(0xE, 5)     # RET R0,5
    cpu.load_words(program)

    cpu.step()
    cpu.step()
    assert cpu.pc == 0x20
    assert cpu.sp == 1
    assert cpu.ram[0x10] == 2  # return PC low nibble
    assert cpu.ram[0x11] == 0  # return PC middle nibble
    assert cpu.ram[0x12] == 0  # return PC high nibble

    cpu.step()
    assert cpu.ram[0] == 5
    assert cpu.pc == 2
    assert cpu.sp == 0

    cpu.step()
    assert cpu.ram[0] == 0xA
    assert cpu.pc == 3


def test_flash_ret_table_reads():
    """Calling RET R0,N entries in program memory is the idiom used for tables."""
    cpu = Emulator()
    program = [0] * Emulator.PROGRAM_SIZE
    program[0] = word(0xE, 1, 0)    # MOV PC,0x10 -> PCH=1, PCM=0
    program[1] = word(0x9, 0xC, 0)  # MOV JSR,0 -> call 0x100
    program[2] = word(0x9, 0xC, 1)  # MOV JSR,1 -> call 0x101
    program[3] = word(0x8, 0, 0)    # MOV R0,R0 (park)
    program[0x100] = op8(0xE, 0xC)  # table entry: RET R0,12
    program[0x101] = op8(0xE, 0x1)  # table entry: RET R0,1
    cpu.load_words(program)

    cpu.step()  # MOV PC
    cpu.step()  # call entry 0
    assert cpu.pc == 0x100
    cpu.step()  # RET
    assert cpu.ram[0] == 0xC
    assert cpu.pc == 2
    assert cpu.sp == 0

    cpu.step()  # call entry 1
    assert cpu.pc == 0x101
    cpu.step()  # RET
    assert cpu.ram[0] == 0x1
    assert cpu.pc == 3
    assert cpu.sp == 0


def test_inc_pcl_jumps_and_ret_without_call_errors():
    cpu = Emulator()
    cpu.load_words([op8(0x2, 0xD)])  # INC PCL
    cpu.ram[0xD] = 4
    cpu.step()
    assert cpu.pc == 5

    cpu.load_words([op8(0xE, 0)])  # RET without a call
    with pytest.raises(EmulatorStackError):
        cpu.step()


# ---------------------------------------------------------------------------
# Loading formats and state
# ---------------------------------------------------------------------------
def test_load_hex_and_load_bytes(tmp_path):
    words = [word(0x9, 0, 5), op8(0xE, 0)]
    hex_path = tmp_path / "program.hex"
    hex_path.write_bytes(make_hex(words))

    cpu = Emulator()
    cpu.load_hex(hex_path)
    assert cpu.program[0] == words[0]
    assert cpu.program[1] == words[1]
    assert cpu.pc == 0
    assert cpu.run(max_steps=1) == 1
    assert cpu.ram[0] == 5

    # load_bytes accepts both complete .hex images and raw word streams.
    cpu.load_bytes(make_hex(words))
    assert cpu.program[0] == words[0]

    cpu.load_bytes(bytes((words[0] & 0xFF, (words[0] >> 8) & 0xFF)))
    assert cpu.program[0] == words[0]


def test_invalid_hex_checksum_is_rejected(tmp_path):
    image = bytearray(make_hex([word(0x9, 0, 5)]))
    image[-1] ^= 0xFF
    path = tmp_path / "bad.hex"
    path.write_bytes(image)
    with pytest.raises(ValueError):
        Emulator().load_hex(path)


def test_state_snapshot_is_independent_copy():
    cpu = Emulator()
    cpu.load_words([word(0x9, 0, 3)])
    cpu.step()
    snapshot = cpu.state()
    assert snapshot["pc"] == 1
    assert snapshot["sp"] == 0
    assert (snapshot["C"], snapshot["Z"], snapshot["V"]) == (0, 0, 0)
    assert snapshot["registers"][0] == 3
    assert len(snapshot["ram"]) == 256

    snapshot["ram"][0] = 0
    snapshot["registers"][0] = 0
    assert cpu.ram[0] == 3
