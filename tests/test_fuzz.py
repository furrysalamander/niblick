"""Deterministic fuzz/property tests for the parser, compiler, and emulator."""

from __future__ import annotations

import ast as pyast
import random
import re
from pathlib import Path

from badgec.assembler import assemble_file
from badgec.compiler import Compiler
from badgec.emulator import Emulator, EmulatorError
from badgec.errors import BadgeError
from badgec.parser import parse


def _nibble(value: int) -> int:
    return value & 0xF


def _eval(expr: str, env: dict[str, int]) -> int:
    """Evaluate the generated expression with BadgeC's nibble semantics."""
    py_expr = expr.replace("&&", " and ").replace("||", " or ")
    py_expr = re.sub(r"!(?!=)", " not ", py_expr)
    tree = pyast.parse(py_expr, mode="eval")

    def visit(node):
        if isinstance(node, pyast.Expression):
            return visit(node.body)
        if isinstance(node, pyast.Constant):
            return int(node.value) & 0xF
        if isinstance(node, pyast.Name):
            return int(env[node.id]) & 0xF
        if isinstance(node, pyast.BinOp):
            left = visit(node.left)
            right = visit(node.right)
            if isinstance(node.op, pyast.Add):
                return (left + right) & 0xF
            if isinstance(node.op, pyast.Sub):
                return (left - right) & 0xF
            if isinstance(node.op, pyast.BitAnd):
                return (left & right) & 0xF
            if isinstance(node.op, pyast.BitOr):
                return (left | right) & 0xF
            if isinstance(node.op, pyast.BitXor):
                return (left ^ right) & 0xF
        if isinstance(node, pyast.UnaryOp) and isinstance(node.op, pyast.Not):
            return 0 if visit(node.operand) else 1
        if isinstance(node, pyast.BoolOp):
            if isinstance(node.op, pyast.And):
                return 0 if any(not visit(value) for value in node.values) else 1
            return 1 if any(visit(value) for value in node.values) else 0
        if isinstance(node, pyast.Compare):
            left = visit(node.left)
            right = visit(node.comparators[0])
            op = node.ops[0]
            if isinstance(op, pyast.Eq):
                return int(left == right)
            if isinstance(op, pyast.NotEq):
                return int(left != right)
            if isinstance(op, pyast.Lt):
                return int(left < right)
            if isinstance(op, pyast.LtE):
                return int(left <= right)
            if isinstance(op, pyast.Gt):
                return int(left > right)
            if isinstance(op, pyast.GtE):
                return int(left >= right)
        raise AssertionError(f"unsupported fuzz AST node: {pyast.dump(node)}")

    return visit(tree)


def _gen_expr(rng: random.Random, depth: int = 0) -> str:
    leaves = ["x", "y", "3", "7", "0", "15"]
    if depth >= 3 or rng.random() < 0.35:
        return rng.choice(leaves)
    choice = rng.random()
    if choice < 0.55:
        op = rng.choice(["+", "-", "&", "|", "^"])
        return f"({_gen_expr(rng, depth + 1)} {op} {_gen_expr(rng, depth + 1)})"
    if choice < 0.75:
        op = rng.choice(["==", "!=", "<", "<=", ">", ">="])
        return f"({_gen_expr(rng, depth + 1)} {op} {_gen_expr(rng, depth + 1)})"
    if choice < 0.88:
        op = rng.choice(["&&", "||"])
        return f"({_gen_expr(rng, depth + 1)} {op} {_gen_expr(rng, depth + 1)})"
    return f"(!{_gen_expr(rng, depth + 1)})"


def test_arithmetic_fuzz_matches_reference(tmp_path: Path) -> None:
    rng = random.Random(1234)
    expressions = [_gen_expr(rng) for _ in range(8)]
    x = rng.randrange(16)
    y = rng.randrange(16)

    lines = ["nibble x;", "nibble y;"] + [f"nibble r{i};" for i in range(len(expressions))]
    lines.append("fn main() {")
    lines.append(f"    x = {x};")
    lines.append(f"    y = {y};")
    for index, expr in enumerate(expressions):
        lines.append(f"    r{index} = {expr};")
    lines.append("}")
    source = "\n".join(lines)

    compiler = Compiler(parse(source, "fuzz.badge"), "fuzz.badge")
    asm_path = tmp_path / "fuzz.asm"
    asm_path.write_text(compiler.compile())
    hex_path = tmp_path / "fuzz.hex"
    assemble_file(asm_path, hex_path)

    emu = Emulator()
    emu.load_hex(hex_path)
    emu.run(200000)

    env = {"x": x, "y": y}
    for index, expr in enumerate(expressions):
        symbol = compiler.globals[f"r{index}"]
        assert symbol.address is not None
        expected = _eval(expr, env)
        actual = emu.ram[symbol.address]
        assert actual == expected, f"expr {expr!r}: got {actual}, expected {expected}"


def test_parser_fuzz_never_raises_internal_exceptions() -> None:
    rng = random.Random(5678)
    fragments = [
        "fn",
        "nibble",
        "char",
        "main",
        "(",
        ")",
        "{",
        "}",
        ";",
        "=",
        "+",
        "-",
        "if",
        "while",
        "return",
        "0",
        "15",
        "0xFF",
        '"hi"',
        ",",
        "[",
        "]",
    ]
    for _ in range(200):
        text = " ".join(rng.choice(fragments) for _ in range(rng.randrange(1, 20)))
        try:
            parse(text, "fuzz.badge")
        except BadgeError:
            pass
        except Exception as exc:  # noqa: BLE001 - the point is to catch internal failures
            raise AssertionError(f"parser crashed on {text!r}: {type(exc).__name__}: {exc}") from exc


def test_emulator_fuzz_handles_random_programs() -> None:
    rng = random.Random(9012)
    for _ in range(50):
        words = [rng.randrange(0x1000) for _ in range(32)]
        emu = Emulator()
        emu.load_words(words)
        try:
            emu.run(200)
        except EmulatorError:
            pass
        except Exception as exc:  # noqa: BLE001
            raise AssertionError(f"emulator crashed on {words!r}: {type(exc).__name__}: {exc}") from exc
