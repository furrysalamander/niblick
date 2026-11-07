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

# First label of each independently-linkable runtime routine.  Internal labels
# (loop targets, retry labels, ...) deliberately do not appear here.
ROUTINE_LABELS = {
    "__bc_uart_init",
    "__bc_uart_putc",
    "__bc_uart_getc",
    "__bc_uart_available",
    "__bc_flash_read_nibble_ptr",
    "__bc_flash_read_char_ptr",
    "__bc_flash_read_char",
    "__bc_flash_read_nibble",
    "__bc_flash_read_word",
    "__bc_uart_puts",
    "__bc_gpio_read",
    "__bc_gpio_read_out",
    "__bc_gpio_write",
    "__bc_gpio_set",
    "__bc_gpio_clear",
    "__bc_gpio_toggle",
    "__bc_gpio_test",
    "__bc_random",
    "__bc_seed",
    "__bc_dimmer",
    "__bc_key_status",
    "__bc_key_code",
    "__bc_key_any",
    "__bc_key_alt",
    "__bc_key_just",
    "__bc_key_last",
    "__bc_uart_write",
    "__bc_memset_nibbles",
    "__bc_memset_chars",
    "__bc_delay",
    "__bc_memcpy_nibbles",
    "__bc_memcpy_chars",
    "__bc_gpio_alt",
    "__bc_uart_route",
    "__bc_leds_enable",
    "__bc_matrix_enable",
    "__bc_mul4",
    "__bc_mul8",
    "__bc_mul16",
    "__bc_divmod8",
    "__bc_divmod16",
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
