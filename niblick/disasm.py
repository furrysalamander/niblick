"""Minimal 12-bit Voja4 instruction decoder for tracing and diagnostics."""

from __future__ import annotations


def decode(word: int) -> str:
    word &= 0xFFF
    op = (word >> 8) & 0xF
    x = (word >> 4) & 0xF
    y = word & 0xF

    if op != 0:
        if op == 0x1:
            return f"ADD R{x}, R{y}"
        if op == 0x2:
            return f"ADC R{x}, R{y}"
        if op == 0x3:
            return f"SUB R{x}, R{y}"
        if op == 0x4:
            return f"SBB R{x}, R{y}"
        if op == 0x5:
            return f"OR R{x}, R{y}"
        if op == 0x6:
            return f"AND R{x}, R{y}"
        if op == 0x7:
            return f"XOR R{x}, R{y}"
        if op == 0x8:
            return f"MOV R{x}, R{y}"
        if op == 0x9:
            return f"MOV R{x}, {y}"
        if op == 0xA:
            return f"MOV [R{x}:R{y}], R0"
        if op == 0xB:
            return f"MOV R0, [R{x}:R{y}]"
        if op == 0xC:
            return f"MOV [0x{x << 4 | y:02X}], R0"
        if op == 0xD:
            return f"MOV R0, [0x{x << 4 | y:02X}]"
        if op == 0xE:
            return f"MOV PC, 0x{x << 4 | y:02X}"
        if op == 0xF:
            offset = (x << 4) | y
            if offset & 0x80:
                offset -= 0x100
            return f"JR {offset:+d}"

    if x == 0x0:
        return f"CP R0, {y}"
    if x == 0x1:
        return f"ADD R0, {y}"
    if x == 0x2:
        return f"INC R{y}"
    if x == 0x3:
        return f"DEC R{y}"
    if x == 0x4:
        return f"DSZ R{y}"
    if x == 0x5:
        return f"OR R0, {y}"
    if x == 0x6:
        return f"AND R0, {y}"
    if x == 0x7:
        return f"XOR R0, {y}"
    if x == 0x8:
        return f"EXR {y}"
    if x == 0x9:
        return f"BIT R{(y >> 2) & 3}, {y & 3}"
    if x == 0xA:
        return f"BSET R{(y >> 2) & 3}, {y & 3}"
    if x == 0xB:
        return f"BCLR R{(y >> 2) & 3}, {y & 3}"
    if x == 0xC:
        return f"BTG R{(y >> 2) & 3}, {y & 3}"
    if x == 0xD:
        return f"RRC R{y}"
    if x == 0xE:
        return f"RET R0, {y}"
    if x == 0xF:
        condition = {0: "C", 1: "NC", 2: "Z", 3: "NZ"}[(y >> 2) & 3]
        count = (y & 3) or 4
        return f"SKIP {condition}, {count}"

    return f".word 0x{word:03X}"
