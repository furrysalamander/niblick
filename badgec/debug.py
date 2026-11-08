"""Small JSON-lines debug service around the BadgeC emulator.

The VS Code DAP adapter is a thin translation layer on top of this service.
Keeping execution and source mapping in Python means the debugger uses the
same emulator and debug map as the rest of the toolchain.
"""

from __future__ import annotations

import ast as pyast
import json
import re
import sys
from pathlib import Path
from typing import Any, Optional

from .emulator import Emulator


class DebugSession:
    def __init__(self, hex_path: str | Path, debug_map: dict[str, Any]) -> None:
        self.emulator = Emulator()
        self.emulator.load_hex(hex_path)
        self.debug_map = debug_map
        self.breakpoints: set[int] = set()
        self.uart_sent = 0
        self._pc_source = {
            int(pc): tuple(source)
            for pc, source in debug_map.get("pc_source", {}).items()
        }

    # ------------------------------------------------------------------
    # Source helpers
    # ------------------------------------------------------------------

    def source_for_pc(self, pc: int) -> Optional[tuple[str, int]]:
        if pc in self._pc_source:
            return self._pc_source[pc]  # type: ignore[return-value]
        best = None
        for address, source in self._pc_source.items():
            if address <= pc and (best is None or address > best[0]):
                best = (address, source)
        return best[1] if best is not None else None

    def function_for_pc(self, pc: int) -> Optional[str]:
        for name, data in self.debug_map.get("functions", {}).items():
            if data["start_pc"] <= pc < max(
                data.get("end_pc", data["start_pc"] + 1),
                data["start_pc"] + 1,
            ):
                return name
        return None

    def _function_data(self, pc: int) -> Optional[dict]:
        name = self.function_for_pc(pc)
        if name is None:
            return None
        return self.debug_map.get("functions", {}).get(name)

    def _line_for_pc(self, pc: int) -> Optional[int]:
        source = self.source_for_pc(pc)
        return source[1] if source is not None else None

    def _uart_delta(self) -> list[int]:
        data = self.emulator.uart_tx[self.uart_sent :]
        self.uart_sent = len(self.emulator.uart_tx)
        return data

    def _state(self, reason: str) -> dict[str, Any]:
        pc = self.emulator.pc
        source = self.source_for_pc(pc)
        return {
            "reason": reason,
            "pc": pc,
            "source": list(source) if source is not None else None,
            "file": source[0] if source is not None else None,
            "line": source[1] if source is not None else None,
            "function": self.function_for_pc(pc),
            "halted": self.emulator.halted,
            "sp": self.emulator.sp,
            "registers": [self.emulator.ram[i] for i in range(10)],
            "flags": {
                "C": self.emulator.C,
                "Z": self.emulator.Z,
                "V": self.emulator.V,
            },
            "uart": self._uart_delta(),
            "steps": self.emulator.instruction_count,
        }

    # ------------------------------------------------------------------
    # Execution controls
    # ------------------------------------------------------------------

    def set_breakpoints(self, requested: list[dict]) -> list[dict]:
        source_to_pcs = self.debug_map.get("source", {})
        result = []
        pcs: set[int] = set()
        for item in requested:
            file = str(Path(item["file"]).expanduser().resolve())
            line = int(item["line"])
            addresses = [
                int(address)
                for address in source_to_pcs.get(file, {}).get(str(line), [])
            ]
            pcs.update(addresses)
            result.append(
                {
                    "file": file,
                    "line": line,
                    "verified": bool(addresses),
                    "pcs": addresses,
                }
            )
        self.breakpoints = pcs
        return result

    def continue_execution(self, max_steps: int = 5_000_000) -> dict:
        if self.emulator.halted:
            return self._state("exited")
        steps = 0
        first = True
        while steps < max_steps and not self.emulator.halted:
            if not first and self.emulator.pc in self.breakpoints:
                return self._state("breakpoint")
            first = False
            self.emulator.step()
            steps += 1
        if self.emulator.halted:
            return self._state("exited")
        return self._state("limit")

    def step(self, kind: str) -> dict:
        if self.emulator.halted:
            return self._state("exited")
        start_depth = self.emulator.sp
        start_line = self._line_for_pc(self.emulator.pc)
        steps = 0
        while steps < 2_000_000 and not self.emulator.halted:
            self.emulator.step()
            steps += 1
            line = self._line_for_pc(self.emulator.pc)
            if kind == "out":
                if self.emulator.sp < start_depth and line is not None:
                    return self._state("step")
            elif kind == "over":
                if (
                    self.emulator.sp <= start_depth
                    and line is not None
                    and line != start_line
                ):
                    return self._state("step")
            else:
                if line is not None and line != start_line:
                    return self._state("step")
        return self._state("exited" if self.emulator.halted else "limit")

    # ------------------------------------------------------------------
    # Inspection
    # ------------------------------------------------------------------

    def registers(self) -> list[dict]:
        names = [f"R{i}" for i in range(10)]
        return [
            {
                "name": names[index],
                "value": self.emulator.ram[index],
                "type": "nibble",
            }
            for index in range(10)
        ]

    def flags(self) -> list[dict]:
        return [
            {"name": name, "value": getattr(self.emulator, name), "type": "nibble"}
            for name in ("C", "Z", "V")
        ]

    def _read_global(self, data: dict) -> Any:
        address = data.get("address")
        if address is None:
            return data.get("value")
        typ = data.get("type", "nibble")
        size = {
            "nibble": 1,
            "char": 2,
            "word": 4,
            "dword": 8,
            "flashptr": 3,
        }.get(typ, 1)
        value = 0
        for index in range(size):
            value |= self.emulator.ram[(address + index) & 0xFF] << (4 * index)
        return value

    def _symbol_data(self, name: str) -> Optional[dict]:
        function = self._function_data(self.emulator.pc)
        if function is not None:
            for group in ("params", "locals"):
                for item in function.get(group, []):
                    if item.get("name") == name:
                        return item
        return self.debug_map.get("globals", {}).get(name)

    def locals(self) -> list[dict]:
        function = self._function_data(self.emulator.pc)
        if function is None:
            return []
        result = []
        for group in ("params", "locals"):
            for data in function.get(group, []):
                address = data.get("address")
                if data.get("array_len") is not None:
                    value = (
                        f"<{data.get('type')}[{data['array_len']}] @ {address}>"
                    )
                else:
                    value = self._read_global(data)
                result.append(
                    {
                        "name": data.get("name"),
                        "value": value,
                        "type": data.get("type", ""),
                        "address": address,
                    }
                )
        return result

    def globals(self) -> list[dict]:
        result = []
        for name, data in sorted(self.debug_map.get("globals", {}).items()):
            address = data.get("address")
            if data.get("array_len") is not None:
                value = f"<{data.get('type')}[{data['array_len']}] @ {address}>"
            else:
                value = self._read_global(data)
            result.append(
                {
                    "name": name,
                    "value": value,
                    "type": data.get("type", ""),
                    "address": address,
                }
            )
        return result

    def stack_frames(self) -> list[dict]:
        frames = []
        pc = self.emulator.pc
        source = self.source_for_pc(pc)
        frames.append(
            {
                "pc": pc,
                "name": self.function_for_pc(pc) or "current",
                "file": source[0] if source else None,
                "line": source[1] if source else None,
            }
        )
        for index in range(self.emulator.sp - 1, -1, -1):
            base = 0x10 + index * 3
            address = (
                self.emulator.ram[base]
                | (self.emulator.ram[base + 1] << 4)
                | (self.emulator.ram[base + 2] << 8)
            )
            source = self.source_for_pc(address)
            frames.append(
                {
                    "pc": address,
                    "name": self.function_for_pc(address) or "caller",
                    "file": source[0] if source else None,
                    "line": source[1] if source else None,
                }
            )
        return frames

    def _symbol_value(self, data: dict) -> Any:
        if data.get("array_len") is not None:
            address = data.get("address")
            return f"<{data.get('type')}[{data['array_len']}] @ {address}>"
        return self._read_global(data)

    def _read_element(self, data: dict, index: int) -> Any:
        address = data.get("address")
        if address is None:
            return data.get("value")
        stride = {
            "nibble": 1,
            "char": 2,
            "word": 4,
            "dword": 8,
            "flashptr": 3,
        }.get(data.get("type"), 1)
        element = {
            "type": data.get("type", "nibble"),
            "address": (address + index * stride) & 0xFF,
        }
        return self._read_global(element)

    def _eval_node(self, node: pyast.AST) -> tuple[Any, str]:
        if isinstance(node, pyast.Constant):
            value = node.value
            return value, "number"
        if isinstance(node, pyast.Name):
            name = node.id
            match = re.fullmatch(r"R([0-9])", name, re.IGNORECASE)
            if match is not None:
                return self.emulator.ram[int(match.group(1))], "nibble"
            if name.lower() == "pc":
                return self.emulator.pc, "nibble"
            if name.lower() == "sp":
                return self.emulator.sp, "nibble"
            data = self._symbol_data(name)
            if data is None:
                raise KeyError(name)
            return self._symbol_value(data), data.get("type", "")
        if isinstance(node, pyast.Subscript):
            if not isinstance(node.value, pyast.Name):
                raise ValueError("subscript base must be a name")
            data = self._symbol_data(node.value.id)
            if data is None:
                raise KeyError(node.value.id)
            index, _ = self._eval_node(node.slice)
            return self._read_element(data, int(index)), data.get("type", "")
        if isinstance(node, pyast.BinOp):
            left, _ = self._eval_node(node.left)
            right, _ = self._eval_node(node.right)
            operations = {
                pyast.Add: lambda a, b: a + b,
                pyast.Sub: lambda a, b: a - b,
                pyast.Mult: lambda a, b: a * b,
                pyast.Div: lambda a, b: a // b,
                pyast.FloorDiv: lambda a, b: a // b,
                pyast.Mod: lambda a, b: a % b,
                pyast.LShift: lambda a, b: a << b,
                pyast.RShift: lambda a, b: a >> b,
                pyast.BitOr: lambda a, b: a | b,
                pyast.BitAnd: lambda a, b: a & b,
                pyast.BitXor: lambda a, b: a ^ b,
            }
            operation = operations.get(type(node.op))
            if operation is None:
                raise ValueError("unsupported operator")
            return operation(int(left), int(right)), "number"
        if isinstance(node, pyast.UnaryOp):
            value, _ = self._eval_node(node.operand)
            if isinstance(node.op, pyast.USub):
                return -int(value), "number"
            if isinstance(node.op, pyast.Invert):
                return ~int(value), "number"
            if isinstance(node.op, pyast.Not):
                return (0 if value else 1), "nibble"
            raise ValueError("unsupported unary operator")
        if isinstance(node, pyast.BoolOp):
            values = [self._eval_node(item)[0] for item in node.values]
            if isinstance(node.op, pyast.And):
                return (1 if all(values) else 0), "nibble"
            return (1 if any(values) else 0), "nibble"
        if isinstance(node, pyast.Compare):
            left, _ = self._eval_node(node.left)
            for op, comparator in zip(node.ops, node.comparators):
                right, _ = self._eval_node(comparator)
                if isinstance(op, pyast.Eq):
                    result = left == right
                elif isinstance(op, pyast.NotEq):
                    result = left != right
                elif isinstance(op, pyast.Lt):
                    result = left < right
                elif isinstance(op, pyast.LtE):
                    result = left <= right
                elif isinstance(op, pyast.Gt):
                    result = left > right
                elif isinstance(op, pyast.GtE):
                    result = left >= right
                else:
                    raise ValueError("unsupported comparison")
                if not result:
                    return 0, "nibble"
                left = right
            return 1, "nibble"
        if isinstance(node, pyast.Call):
            if not isinstance(node.func, pyast.Name):
                raise ValueError("unsupported call")
            name = node.func.id
            args = [self._eval_node(arg)[0] for arg in node.args]
            if name == "peek" and len(args) == 1:
                return self.emulator.ram[int(args[0]) & 0xFF], "nibble"
            if name == "high_nibble" and len(args) == 1:
                return (int(args[0]) >> 4) & 0xF, "nibble"
            if name == "low_nibble" and len(args) == 1:
                return int(args[0]) & 0xF, "nibble"
            raise ValueError(f"unsupported function {name}")
        raise ValueError("unsupported expression")

    def evaluate(self, expression: str) -> dict:
        text = expression.strip()
        text = re.sub(r"\btrue\b", "True", text, flags=re.IGNORECASE)
        text = re.sub(r"\bfalse\b", "False", text, flags=re.IGNORECASE)
        text = text.replace("&&", " and ").replace("||", " or ")
        try:
            tree = pyast.parse(text, mode="eval")
            value, type_name = self._eval_node(tree.body)
            return {"result": value, "type": type_name or "number"}
        except Exception:
            return {
                "result": f"unknown expression: {expression}",
                "type": "error",
            }


class DebugService:
    def __init__(self) -> None:
        self.session: Optional[DebugSession] = None

    def dispatch(self, command: str, args: dict) -> Any:
        if command == "load":
            debug_map = args.get("map")
            if isinstance(debug_map, str):
                debug_map = json.loads(Path(debug_map).read_text())
            if debug_map is None:
                debug_map = {}
            self.session = DebugSession(args["hex"], debug_map)
            return self.session._state("entry")
        if self.session is None:
            raise RuntimeError("no program loaded")
        if command == "setBreakpoints":
            return self.session.set_breakpoints(args.get("breakpoints", []))
        if command == "continue":
            return self.session.continue_execution(
                int(args.get("maxSteps", 5_000_000))
            )
        if command == "step":
            return self.session.step(str(args.get("kind", "into")))
        if command == "state":
            return self.session._state("state")
        if command == "variables":
            scope = args.get("scope")
            if scope == "registers":
                return self.session.registers()
            if scope == "flags":
                return self.session.flags()
            if scope == "globals":
                return self.session.globals()
            if scope == "locals":
                return self.session.locals()
            return []
        if command == "stackTrace":
            return self.session.stack_frames()
        if command == "evaluate":
            return self.session.evaluate(str(args.get("expression", "")))
        if command == "reset":
            self.session.emulator.reset()
            return self.session._state("entry")
        if command == "shutdown":
            return {"ok": True}
        raise RuntimeError(f"unknown command {command!r}")


def main() -> int:
    service = DebugService()
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            request = json.loads(line)
            result = service.dispatch(
                str(request.get("command", "")),
                request.get("args") or {},
            )
            response = {
                "id": request.get("id"),
                "ok": True,
                "result": result,
            }
        except Exception as exc:
            response = {
                "id": request.get("id") if "request" in locals() else None,
                "ok": False,
                "error": str(exc),
            }
        sys.stdout.write(json.dumps(response) + "\n")
        sys.stdout.flush()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
