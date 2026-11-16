"""Link only the runtime assembly routines a program actually uses.

The runtime file is split into routines at well-known entry labels.  Internal
loop labels stay in the same routine group.  A routine may reference another
routine with GOTO/GOSUB/JR; we walk that graph from the entry points used by
the compiler and emit only the reachable groups in their original order.
"""

from __future__ import annotations

import re

LABEL_RE = re.compile(r"^(__bc_[A-Za-z0-9_]+):\s*$")
REF_RE = re.compile(r"\b(__bc_[A-Za-z0-9_]+)\b")
GOSUB_RE = re.compile(r"\bGOSUB\s+(__bc_[A-Za-z0-9_]+)\b", re.IGNORECASE)
JSR_RE = re.compile(r"\bMOV\s+JSR\b", re.IGNORECASE)

# First label of each independently-linkable runtime routine.  Internal labels
# (loop targets, retry labels, ...) deliberately do not appear here.
ROUTINE_LABELS = {
    "__bc_uart_putc",
    "__bc_uart_getc",
    "__bc_flash_read_nibble_ptr",
    "__bc_flash_read_char_ptr",
    "__bc_flash_read_char",
    "__bc_flash_read_nibble",
    "__bc_flash_read_word",
    "__bc_flash_read_dword",
    "__bc_gpio_read",
    "__bc_gpio_read_out",
    "__bc_gpio_write",
    "__bc_gpio_set",
    "__bc_gpio_clear",
    "__bc_gpio_toggle",
    "__bc_gpio_test",
    "__bc_w5500_spi_tx_fast",
    "__bc_w5500_spi_xfer_fast",
    "__bc_delay",
    "__bc_mul4",
    "__bc_mul8",
    "__bc_mul16",
    "__bc_divmod8",
    "__bc_divmod16",
    "__bc_sdivmod8",
    "__bc_sdivmod16",
    "__bc_mul32",
    "__bc_divmod32",
}


def _parse(text: str):
    preamble: list[str] = []
    blocks: dict[str, list[str]] = {}
    order: list[str] = []
    current: str | None = None

    for line in text.splitlines():
        match = LABEL_RE.match(line.strip())
        if match:
            current = match.group(1)
            blocks[current] = [line]
            order.append(current)
        elif current is None:
            preamble.append(line)
        else:
            blocks[current].append(line)

    groups: dict[str, list[str]] = {}
    group_order: list[str] = []
    label_to_group: dict[str, str] = {}
    current_group: str | None = None

    for label in order:
        if label in ROUTINE_LABELS or current_group is None:
            current_group = label
            group_order.append(label)
            groups[current_group] = []
        groups[current_group].extend(blocks[label])
        label_to_group[label] = current_group

    deps: dict[str, set[str]] = {group: set() for group in groups}
    for label in order:
        group = label_to_group[label]
        for line in blocks[label]:
            code = line.split(";", 1)[0]
            for ref in REF_RE.findall(code):
                ref_group = label_to_group.get(ref)
                if ref_group is not None and ref_group != group:
                    deps[group].add(ref_group)

    return preamble, group_order, groups, deps


def link_runtime(text: str, entries: set[str]) -> str:
    """Return only the runtime routines reachable from *entries*."""
    if not entries:
        return ""

    preamble, group_order, groups, deps = _parse(text)
    reachable: set[str] = set()
    stack = list(entries)
    while stack:
        label = stack.pop()
        if label in reachable or label not in groups:
            continue
        reachable.add(label)
        stack.extend(deps[label] - reachable)

    lines: list[str] = []
    lines.extend(preamble)
    for label in group_order:
        if label in reachable:
            lines.extend(groups[label])

    return "\n".join(lines).rstrip() + "\n"


def routine_labels(text: str) -> list[str]:
    """Return every independently-linkable runtime entry label, in order."""
    return _parse(text)[1]


def runtime_stack_costs(text: str) -> dict[str, int]:
    """Return the worst-case hardware stack cost of each runtime routine.

    A call from user code costs one entry for the ``GOSUB``, then any nested
    ``GOSUB`` or flash-table ``MOV JSR`` inside the routine.  The values are
    therefore the number of stack entries used *including* the caller's
    ``GOSUB``.
    """

    _, group_order, groups, _ = _parse(text)

    label_to_group: dict[str, str] = {}
    current: str | None = None
    for line in text.splitlines():
        match = LABEL_RE.match(line.strip())
        if not match:
            continue
        label = match.group(1)
        if label in ROUTINE_LABELS or current is None:
            current = label
        label_to_group[label] = current

    calls: dict[str, set[str]] = {group: set() for group in group_order}
    has_jsr = {group: False for group in group_order}
    for group in group_order:
        for line in groups[group]:
            code = line.split(";", 1)[0]
            if JSR_RE.search(code):
                has_jsr[group] = True
            for ref in GOSUB_RE.findall(code):
                child = label_to_group.get(ref)
                if child is not None and child != group:
                    calls[group].add(child)

    memo: dict[str, int] = {}

    def depth(group: str, visiting: set[str]) -> int:
        if group in memo:
            return memo[group]
        if group in visiting:
            return 0
        visiting.add(group)
        best = 1 if has_jsr[group] else 0
        for child in calls[group]:
            best = max(best, 1 + depth(child, visiting))
        visiting.remove(group)
        memo[group] = best
        return best

    return {group: 1 + depth(group, set()) for group in group_order}


def reachable_labels(text: str, entries: set[str]) -> set[str]:
    """Return the set of runtime routine labels reachable from *entries*."""
    if not entries:
        return set()
    _, _, groups, deps = _parse(text)
    reachable: set[str] = set()
    stack = list(entries)
    while stack:
        label = stack.pop()
        if label in reachable or label not in groups:
            continue
        reachable.add(label)
        stack.extend(deps[label] - reachable)
    return reachable
