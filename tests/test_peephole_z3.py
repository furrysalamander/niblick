"""Symbolic checks for small peephole and address-lowering identities."""

from __future__ import annotations

import pytest

z3 = pytest.importorskip("z3")
from z3 import (  # noqa: E402
    Array,
    BitVec,
    BitVecSort,
    BitVecVal,
    Concat,
    Extract,
    If,
    Not,
    Select,
    Solver,
    Store,
    unsat,
)


def test_poke8_increment_wraps_to_byte_address() -> None:
    addr = BitVec("addr", 8)
    lo = Extract(3, 0, addr)
    hi = Extract(7, 4, addr)
    carry = If(lo == BitVecVal(15, 4), BitVecVal(1, 4), BitVecVal(0, 4))
    next_addr = Concat(hi + carry, lo + 1)

    solver = Solver()
    solver.add(next_addr != addr + 1)
    assert solver.check() == unsat


def test_constant_address_poke_matches_indirect_store() -> None:
    mem = Array("mem", BitVecSort(8), BitVecSort(4))
    hi, lo, addr, value = (
        BitVec("hi", 4),
        BitVec("lo", 4),
        BitVec("addr", 8),
        BitVec("value", 4),
    )
    solver = Solver()
    solver.add(Concat(hi, lo) == addr)
    solver.add(Store(mem, Concat(hi, lo), value) != Store(mem, addr, value))
    assert solver.check() == unsat


def test_constant_address_peek_matches_indirect_load() -> None:
    mem = Array("mem", BitVecSort(8), BitVecSort(4))
    hi, lo, addr = BitVec("hi", 4), BitVec("lo", 4), BitVec("addr", 8)
    solver = Solver()
    solver.add(Concat(hi, lo) == addr)
    solver.add(Select(mem, Concat(hi, lo)) != Select(mem, addr))
    assert solver.check() == unsat


def test_redundant_duplicate_move_is_identity() -> None:
    regs = Array("regs", BitVecSort(4), BitVecSort(4))
    rd, rs = BitVec("rd", 4), BitVec("rs", 4)
    once = Store(regs, rd, Select(regs, rs))
    twice = Store(once, rd, Select(once, rs))

    solver = Solver()
    solver.add(twice != once)
    assert solver.check() == unsat


def test_direct_peek_preserves_result_register() -> None:
    mem = Array("mem", BitVecSort(8), BitVecSort(4))
    hi, lo, addr = BitVec("hi", 4), BitVec("lo", 4), BitVec("addr", 8)
    indirect_r0 = Select(mem, Concat(hi, lo))
    indirect_r1 = indirect_r0
    direct_r0 = Select(mem, addr)
    direct_r1 = direct_r0

    solver = Solver()
    solver.add(Concat(hi, lo) == addr)
    solver.add(Not(indirect_r1 == direct_r1))
    assert solver.check() == unsat
