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

from .asm_text import NO_OPTIMIZE, NO_OPTIMIZE_BEGIN, NO_OPTIMIZE_END

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
    return bool(_LABEL_RE.match(_code(line).strip()))


def _opaque_mask(lines: list[str]) -> list[bool]:
    """Mark lines inside a ``; @niblick: no-optimize`` region."""

    mask = [False] * len(lines)
    depth = 0
    file_opaque = False
    begin = NO_OPTIMIZE_BEGIN.lower()
    end = NO_OPTIMIZE_END.lower()
    file_marker = NO_OPTIMIZE.lower()
    for index, line in enumerate(lines):
        stripped = line.strip().lower()
        if stripped == file_marker:
            file_opaque = True
            mask[index] = True
            continue
        if file_opaque:
            mask[index] = True
            continue
        if stripped == begin:
            depth += 1
            mask[index] = True
            continue
        if stripped == end:
            mask[index] = True
            if depth > 0:
                depth -= 1
            continue
        if depth > 0:
            mask[index] = True
    return mask


def _mov(line: str):
    match = _MOV_RE.match(_code(line))
    if not match:
        return None
    return match.group(1).upper(), match.group(2).upper()


def peephole(lines: list[str]) -> list[str]:
    out: list[str] = []
    opaque = _opaque_mask(lines)
    for index, line in enumerate(lines):
        if opaque[index]:
            out.append(line)
            continue
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
    opaque = _opaque_mask(lines)

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

    for index, line in enumerate(lines):
        if opaque[index]:
            known.clear()
            out.append(line)
            continue
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


_ALL_REGS = {f"R{index}" for index in range(10)}


def _register_effects(code: str):
    """Return ``(reads, writes)`` for a register-level instruction.

    ``None`` means the effect is unknown; callers must treat the instruction
    as a control-flow boundary.
    """

    parts = code.split(None, 1)
    if not parts:
        return None
    op = parts[0].upper()
    args = [item.strip() for item in parts[1].split(",")] if len(parts) > 1 else []

    if op == "MOV":
        if len(args) != 2:
            return None
        dst, src = args
        dst_reg = _register(dst)
        src_reg = _register(src)
        if dst_reg and src_reg:
            return {src_reg}, {dst_reg}
        if dst_reg and _IMM_RE.match(src):
            return set(), {dst_reg}
        if dst_reg and src.startswith("["):
            reads = set()
            if "R4" in src:
                reads.add("R4")
            if "R5" in src:
                reads.add("R5")
            return reads, {dst_reg}
        if dst.startswith("[") and src_reg:
            reads = {src_reg}
            if "R4" in dst:
                reads.add("R4")
            if "R5" in dst:
                reads.add("R5")
            return reads, set()
        return None

    if op in ("ADD", "ADC", "SUB", "SBB", "OR", "AND", "XOR"):
        if len(args) == 2 and _register(args[0]) and _register(args[1]):
            return {args[0], args[1]}, {args[0]}
        return None

    if op == "CP":
        return {arg for arg in args if _register(arg)}, set()

    if op in ("INC", "DEC"):
        if args and _register(args[0]):
            return {args[0]}, {args[0]}
        return None

    if op == "CPL":
        if args and _register(args[0]):
            reads = {arg for arg in args if _register(arg)}
            return reads, {args[0]}
        return None

    if op in ("BSET", "BCLR", "BTG"):
        if args and _register(args[0]) and _register(args[0]) != "R3":
            return {args[0]}, {args[0]}
        return None

    if op == "BIT":
        if args and _register(args[0]) and _register(args[0]) != "R3":
            return {args[0]}, set()
        return None

    if op in ("RRC", "LSR"):
        if args and _register(args[0]):
            return {args[0]}, {args[0]}
        return None

    if op in ("SL", "NEG", "RLC"):
        if len(args) == 2 and _register(args[0]) and _register(args[1]):
            return {args[1]}, {args[0]}
        return None

    return None


def _is_pure_register_move(code: str) -> bool:
    parts = code.split(None, 1)
    if not parts or parts[0].upper() != "MOV" or len(parts) < 2:
        return False
    args = [item.strip() for item in parts[1].split(",")]
    if len(args) != 2 or not _register(args[0]):
        return False
    # Memory loads can touch SFRs (reading KeyStatus clears JustPress), so
    # only register-to-register and immediate moves are removed.
    return bool(_register(args[1]) or _IMM_RE.match(args[1]))


def _skip_protected_lines(lines: list[str]) -> set[int]:
    """Indices of instructions inside the word window of a SKIP.

    Removing one of them would change how far the SKIP jumps.
    """

    protected: set[int] = set()
    for index, line in enumerate(lines):
        match = _SKIP_RE.match(_code(line))
        if not match:
            continue
        remaining = int(match.group(2))
        cursor = index + 1
        while cursor < len(lines) and remaining > 0:
            if _code(lines[cursor]) and not _is_label(lines[cursor]):
                protected.add(cursor)
                remaining -= _word_size(lines[cursor])
            cursor += 1
    return protected


def dead_register_writes(lines: list[str]) -> list[str]:
    """Remove register writes whose value is never read in the same block."""

    protected = _skip_protected_lines(lines)
    opaque = _opaque_mask(lines)
    remove: set[int] = set()
    segment: list[int] = []

    def flush() -> None:
        live = set(_ALL_REGS)
        for index in reversed(segment):
            code = _code(lines[index])
            if not code:
                continue
            effects = _register_effects(code)
            if effects is None:
                live = set(_ALL_REGS)
                continue
            reads, writes = effects
            if (
                index not in protected
                and len(writes) == 1
                and not (writes & live)
                and _is_pure_register_move(code)
            ):
                remove.add(index)
                continue
            live = (live - writes) | reads

    for index, line in enumerate(lines):
        if opaque[index]:
            flush()
            segment = []
            continue
        code = _code(line)
        barrier = (
            not code
            or _is_label(line)
            or _register_effects(code) is None
            or code.split(None, 1)[0].upper() in _BARRIER_OPS
        )
        if barrier:
            flush()
            segment = []
        else:
            segment.append(index)
    flush()

    return [line for index, line in enumerate(lines) if index not in remove]


def _word_size(line: str) -> int:
    code = _code(line)
    if not code or _is_label(line):
        return 0
    upper = code.upper()
    parts = upper.split(None, 1)
    op = parts[0]
    args = parts[1] if len(parts) > 1 else ""

    if re.match(r"^[A-Za-z_.][A-Za-z0-9_.]*\s+EQU\b", upper):
        return 0
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
    if op == "CPL":
        return 1 if len([item for item in args.split(",") if item.strip()]) == 1 else 2
    if op in ("NEG", "SL", "RLC", "LSR"):
        return 2
    return 1


def asm_word_count(asm: str) -> int:
    """Return the number of words the assembler will emit for *asm*."""
    return sum(_word_size(line) for line in asm.splitlines())


def word_sizes(
    asm: str,
    labels: set[str],
    total_words: int | None = None,
) -> dict[str, int]:
    """Return the word size of each entry label in *labels*.

    Entry labels must be emitted in source order and must not overlap.  The
    size of an entry runs up to the next entry label (or the end of the
    program).  Internal labels inside a routine stay in that routine.
    """

    lines = asm.splitlines()
    addresses = _addresses(lines)
    if total_words is None:
        total_words = sum(_word_size(line) for line in lines)

    present = sorted(
        (addresses[label], label) for label in set(labels) if label in addresses
    )
    sizes: dict[str, int] = {}
    for index, (address, label) in enumerate(present):
        end = present[index + 1][0] if index + 1 < len(present) else total_words
        sizes[label] = max(0, end - address)
    return sizes


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
    opaque = _opaque_mask(lines)
    changed = False
    out: list[str] = []

    for index, line in enumerate(lines):
        if opaque[index]:
            out.append(line)
            continue
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
        if skip_index >= 0 and not _is_label(out[skip_index]) and not opaque[skip_index]:
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
        lines = dead_register_writes(lines)
    if relax_enabled:
        lines = relax_branches(lines)
    return "\n".join(lines).rstrip() + "\n"
