"""Scan imported assembly for symbols, calls and forbidden constructs.

The generated program still goes through the vendored assembler, so this is
not a full assembler parser.  It only needs the parts that affect the
compiler: labels, ``GOSUB``/``GOTO`` targets, placeholders, and the set
of constructs that would bypass the call-graph or stack model.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from .asm_text import PLACEHOLDER_RE, Placeholder, code_part, label_span
from .errors import NiblickCompileError, location


@dataclass(frozen=True)
class AsmCall:
    caller_label: str
    target_label: str
    tail: bool
    line: int
    column: int = 1


@dataclass(frozen=True)
class AsmRuntimeCall:
    caller_label: str
    target_label: str
    line: int
    column: int = 1


@dataclass
class AsmScan:
    path: str
    labels: dict[str, int] = field(default_factory=dict)
    label_columns: dict[str, int] = field(default_factory=dict)
    function_labels: list[str] = field(default_factory=list)
    calls: list[AsmCall] = field(default_factory=list)
    runtime_calls: list[AsmRuntimeCall] = field(default_factory=list)
    placeholders: list[tuple[str | None, Placeholder]] = field(default_factory=list)


def _error(path: str, line: int, message: str) -> NiblickCompileError:
    return NiblickCompileError(f"{location(path, line)}: {message}")


def _target_kind(target: str) -> str:
    if target.startswith("."):
        return "local"
    if target.startswith("fn_"):
        return "function"
    if target.startswith("__nib_"):
        return "runtime"
    return "unknown"


def scan_asm(text: str, path: str) -> AsmScan:
    """Return the call/label structure of an imported assembly file."""

    scan = AsmScan(path=path)
    current_function: str | None = None
    current_global: str | None = None
    local_labels: set[str] = set()

    for line_number, line in enumerate(text.splitlines(), 1):
        raw_code = code_part(line)
        code = raw_code.strip()
        if not code:
            continue
        leading = len(raw_code) - len(raw_code.lstrip())

        label = label_span(line)
        if label is not None:
            label, label_column = label
            if label.startswith("."):
                scoped = (current_global or "") + label
                if scoped in local_labels:
                    raise _error(path, line_number, f"duplicate label {label!r}")
                local_labels.add(scoped)
                continue

            if label in scan.labels:
                raise _error(path, line_number, f"duplicate label {label!r}")
            scan.labels[label] = line_number
            scan.label_columns[label] = label_column
            current_global = label
            if label.startswith("__nib_"):
                raise _error(
                    path,
                    line_number,
                    f"{label!r} is reserved for the compiler runtime; "
                    "use a fn_* entry point for library assembly",
                )
            if label.startswith("fn_"):
                current_function = label
                scan.function_labels.append(label)
            else:
                # A non-local label other than fn_* is data or a helper and
                # does not carry the previous function's placeholder scope.
                current_function = None
            continue

        for match in PLACEHOLDER_RE.finditer(code):
            scan.placeholders.append(
                (
                    current_function,
                    Placeholder(
                        line=line_number,
                        start=match.start() + leading,
                        end=match.end() + leading,
                        text=match.group(1).strip(),
                    ),
                )
            )

        parts = code.split(None, 1)
        op = parts[0].upper()
        args = parts[1].strip() if len(parts) > 1 else ""

        if op in ("GOSUB", "GOTO"):
            if not args:
                raise _error(path, line_number, f"{op} requires a target")
            target = args.split()[0]
            target_column = code.find(target, len(op))
            target_column = (
                target_column + 1 + leading if target_column >= 0 else 1
            )
            kind = _target_kind(target)
            tail = op == "GOTO"

            if kind == "local":
                if op == "GOSUB":
                    raise _error(
                        path,
                        line_number,
                        "GOSUB to a local label is not supported; use GOTO loops "
                        "or call a declared extern function",
                    )
                continue

            if kind == "runtime":
                if tail:
                    raise _error(
                        path,
                        line_number,
                        "GOTO to a runtime routine is not supported; use GOSUB",
                    )
                if current_function is None:
                    raise _error(
                        path,
                        line_number,
                        "runtime calls must appear inside a fn_* function",
                    )
                scan.runtime_calls.append(
                    AsmRuntimeCall(
                        current_function, target, line_number, target_column
                    )
                )
                continue

            if kind == "function":
                if current_function is None:
                    raise _error(
                        path,
                        line_number,
                        "function calls must appear inside a fn_* function",
                    )
                scan.calls.append(
                    AsmCall(
                        current_function,
                        target,
                        tail,
                        line_number,
                        target_column,
                    )
                )
                continue

            raise _error(
                path,
                line_number,
                f"unsupported {op} target {target!r}; "
                "use a fn_* or __nib_* label",
            )

        if op == "MOV":
            destination = args.split(",", 1)[0].strip().upper()
            if destination in {"PC", "PCL", "PCM", "PCH", "JSR"}:
                raise _error(
                    path,
                    line_number,
                    f"raw MOV {destination} bypasses the compiler call model; "
                    "use GOTO/GOSUB",
                )

        if op in ("ORG", "BYTE", "ASCII"):
            raise _error(
                path,
                line_number,
                f"{op} is not supported in imported assembly; "
                "use NIBBLE tables or declare flash data in Niblick",
            )

        if op == "EXR":
            value = args.split(",", 1)[0].strip()
            try:
                count = int(value, 0)
            except ValueError:
                raise _error(path, line_number, "EXR requires a numeric operand") from None
            if count == 0 or count > 10:
                raise _error(
                    path,
                    line_number,
                    "EXR with 0 or more than 10 registers would touch "
                    "compiler/runtime state",
                )

    return scan
