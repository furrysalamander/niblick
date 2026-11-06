"""Small, conservative assembly optimizations.

The peephole pass removes redundant moves (MOV does not affect flags on this
CPU).  Copy propagation removes ``MOV Rd,Rs`` when ``Rd`` already holds the
value in ``Rs`` inside the same straight-line block.  The branch pass turns
two-word GOTO pseudo-ops into one-word JR when the target is in range,
adjusting a directly preceding SKIP count so the conditional-branch idiom
remains correct.
"""

from __future__ import annotations

import re

_LABEL_RE = re.compile(r"^[A-Za-z_.][A-Za-z0-9_.]*:\s*$")
_SKIP_RE = re.compile(r"^SKIP\s+([A-Za-z]+)\s*,\s*(\d+)\s*$", re.IGNORECASE)
_MOV_RE = re.compile(r"^MOV\s+([A-Za-z0-9]+)\s*,\s*([A-Za-z0-9]+)\s*$", re.IGNORECASE)
_REG_RE = re.compile(r"^R([0-9])$", re.IGNORECASE)
_IMM_RE = re.compile(r"^#?[0-9]+$")

# Control transfers and instructions with non-obvious register effects end a
# straight-line block.  Clearing the whole map is cheap and conservative.
_BARRIER_OPS = {"GOTO", "GOSUB", "JR", "RET", "SKIP", "DSZ", "EXR"}
# These read registers but write none.
_READ_ONLY_OPS = {"CP", "BIT"}
# These write their first register operand.
_WRITE_FIRST_OPS = {
    "ADD",
    "ADC",
    "SUB",
    "SBB",
    "OR",
    "AND",
    "XOR",
    "INC",
    "DEC",
    "CPL",
    "SL",
    "NEG",
    "LSR",
    "RRC",
    "RLC",
    "BSET",
    "BCLR",
    "BTG",
}


def _code(line: str) -> str:
    return line.split(";", 1)[0].strip()


def _is_label(line: str) -> bool:
    return bool(_LABEL_RE.match(line.strip()))


def _mov(line: str):
    match = _MOV_RE.match(_code(line))
    if not match:
        return None
    return match.group(1).upper(), match.group(2).upper()


def peephole(lines: list[str]) -> list[str]:
    out: list[str] = []
    for line in lines:
        code = _code(line)
        if not code:
            out.append(line)
            continue
        mov = _mov(line)
        if mov is not None:
            dst, src = mov
            if dst == src:
                continue
            # A redundant copy-back immediately after MOV R0,Rx.
            if (
                dst == "R1"
                and src == "R0"
                and out
                and _mov(out[-1]) == ("R0", "R1")
            ):
                continue
            # Consecutive writes to the same destination: the first is dead.
            if out and _mov(out[-1]) is not None:
                prev_dst, _ = _mov(out[-1])
                if prev_dst == dst:
                    out[-1] = line
                    continue
            # Immediate duplicate instruction.
            if out and _code(out[-1]).upper() == code.upper():
                continue
        out.append(line)
    return out


def _register(name: str) -> str | None:
    name = name.strip().upper()
    return name if _REG_RE.match(name) else None


def copy_propagate(lines: list[str]) -> list[str]:
    """Drop ``MOV Rd,Rs`` when ``Rd`` is known to already equal ``Rs``.

    Values are tracked by identity inside a basic block.  Labels, branches,
    skips and anything with unknown register effects clear the map, so the
    pass never reasons across a control-flow edge.
    """

    known: dict[str, int] = {}
    next_value = 0
    out: list[str] = []

    def value_of(reg: str) -> int:
        # At a block boundary a register has an arbitrary value.  Give it a
        # private id on first use; a later MOV can still prove that two
        # registers hold that same (unknown) value.
        nonlocal next_value
        if reg not in known:
            next_value += 1
            known[reg] = next_value
        return known[reg]

    def fresh(reg: str) -> None:
        nonlocal next_value
        next_value += 1
        known[reg] = next_value

    for line in lines:
        stripped = line.strip()
        if _is_label(stripped):
            known.clear()
            out.append(line)
            continue

        code = _code(line)
        if not code:
            out.append(line)
            continue

        parts = code.split(None, 1)
        op = parts[0].upper()
        args = parts[1].strip() if len(parts) > 1 else ""

        if op in _BARRIER_OPS:
            known.clear()
            out.append(line)
            continue

        if op == "MOV":
            operands = [item.strip() for item in args.split(",", 1)]
            if len(operands) != 2:
                known.clear()
                out.append(line)
                continue
            dst_text, src_text = operands
            dst = _register(dst_text)
            src = _register(src_text)

            if dst is None and dst_text.strip().upper() in ("PC", "PCL", "PCH", "PCM", "JSR"):
                # Writing the program counter ends the block.
                known.clear()
                out.append(line)
                continue

            if dst is not None and src is not None:
                if known.get(dst) is not None and known.get(dst) == value_of(src):
                    continue
                known[dst] = value_of(src)
            elif dst is not None:
                # Immediate or memory load into a register: the old value is
                # gone, and the new one has no known relationship to another
                # register.
                fresh(dst)

            out.append(line)
            continue

        if op in _READ_ONLY_OPS:
            out.append(line)
            continue

        if op in _WRITE_FIRST_OPS and args:
            first_text = args.split(",", 1)[0].strip()
            first = _register(first_text)
            if first is not None:
                # BSET/BCLR/BTG on R3 address the I/O port, not a register.
                if op in ("BSET", "BCLR", "BTG") and first == "R3":
                    known.clear()
                else:
                    fresh(first)
            out.append(line)
            continue

        # Unknown mnemonic or directive: be conservative.
        known.clear()
        out.append(line)

    return out


def _word_size(line: str) -> int:
    code = _code(line)
    if not code or _is_label(line):
        return 0
    upper = code.upper()
    if upper.startswith("GOTO ") or upper.startswith("GOSUB "):
        return 2
    if upper.startswith("BYTE "):
        return 2
    if upper.startswith("NIBBLE "):
        return 1
    if upper.startswith("ASCII "):
        # Count characters between the quotes.
        match = re.search(r'"(.*)"', code)
        return 2 * len(match.group(1)) if match else 2
    return 1


def _addresses(lines: list[str]) -> dict[str, int]:
    addresses: dict[str, int] = {}
    address = 0
    for line in lines:
        if _is_label(line):
            addresses[line.strip()[:-1]] = address
        else:
            address += _word_size(line)
    return addresses


def _relax_once(lines: list[str]) -> tuple[list[str], bool]:
    addresses = _addresses(lines)
    changed = False
    out: list[str] = []

    for index, line in enumerate(lines):
        code = _code(line)
        upper = code.upper()
        if not upper.startswith("GOTO "):
            out.append(line)
            continue

        target = code.split(None, 1)[1].strip()
        if target not in addresses:
            out.append(line)
            continue

        address = sum(_word_size(item) for item in lines[:index])
        offset = addresses[target] - (address + 1)
        if offset == 0 or not (-128 <= offset <= 126):
            out.append(line)
            continue

        # If a SKIP immediately precedes this GOTO, it is intentionally
        # skipping the two GOTO words.  Shrink the count by one along with
        # the branch, otherwise it would skip into the next instruction.
        skip_index = len(out) - 1
        while skip_index >= 0 and not _code(out[skip_index]):
            skip_index -= 1
        if skip_index >= 0 and not _is_label(out[skip_index]):
            skip_match = _SKIP_RE.match(_code(out[skip_index]))
            if skip_match:
                count = int(skip_match.group(2))
                if count <= 1:
                    out.append(line)
                    continue
                condition = skip_match.group(1)
                out[skip_index] = f"SKIP {condition}, {count - 1}"

        comment = ""
        if ";" in line:
            comment = " ;" + line.split(";", 1)[1]
        out.append(f"JR {target}{comment}")
        changed = True

    return out, changed


def relax_branches(lines: list[str]) -> list[str]:
    for _ in range(1000):
        lines, changed = _relax_once(lines)
        if not changed:
            return lines
    return lines


def optimize_asm(text: str, peephole_enabled: bool = True, relax_enabled: bool = True) -> str:
    lines = text.splitlines()
    if peephole_enabled:
        lines = peephole(lines)
        lines = copy_propagate(lines)
    if relax_enabled:
        lines = relax_branches(lines)
    return "\n".join(lines).rstrip() + "\n"
