"""Shard C: logic, compare, branch, and select node emitters."""
from __future__ import annotations

from ..ir import VPNode
from ._base import NodeEmitter


def _assign(uid: str, expr: str) -> list[str]:
    return [f'    G["{uid}"] = {expr}']


def _g(i: int, ins: list[str], default: str = "0") -> str:
    return ins[i] if i < len(ins) else default


def emit_and(uid: str, ins: list[str], _n: VPNode) -> list[str]:
    a, b = _g(0, ins), _g(1, ins)
    return _assign(uid, f"(({a}) ~= 0 and ({b}) ~= 0) and 1 or 0")


def emit_or(uid: str, ins: list[str], _n: VPNode) -> list[str]:
    a, b = _g(0, ins), _g(1, ins)
    return _assign(uid, f"(({a}) ~= 0 or ({b}) ~= 0) and 1 or 0")


def emit_not(uid: str, ins: list[str], _n: VPNode) -> list[str]:
    a = _g(0, ins)
    return _assign(uid, f"(({a}) ~= 0) and 0 or 1")


def emit_nand(uid: str, ins: list[str], _n: VPNode) -> list[str]:
    a, b = _g(0, ins), _g(1, ins)
    return _assign(uid, f"(({a}) ~= 0 and ({b}) ~= 0) and 0 or 1")


def emit_nor(uid: str, ins: list[str], _n: VPNode) -> list[str]:
    a, b = _g(0, ins), _g(1, ins)
    return _assign(uid, f"(({a}) ~= 0 or ({b}) ~= 0) and 0 or 1")


def emit_xor(uid: str, ins: list[str], _n: VPNode) -> list[str]:
    a, b = _g(0, ins), _g(1, ins)
    return _assign(
        uid,
        f"((({a}) ~= 0) ~= (({b}) ~= 0)) and 1 or 0",
    )


def emit_branch(uid: str, ins: list[str], _n: VPNode) -> list[str]:
    cond = _g(0, ins)
    true_v = _g(1, ins)
    false_v = _g(2, ins)
    return [
        f'    G["{uid}_o0"] = ({true_v})',
        f'    G["{uid}_o1"] = ({false_v})',
        f'    G["{uid}"] = (({cond}) > 0 and ({true_v}) or ({false_v}))',
    ]


def emit_select(uid: str, ins: list[str], _n: VPNode) -> list[str]:
    idx = _g(0, ins)
    arms = ", ".join(f"({_g(i, ins)})" for i in range(1, 11))
    return [
        f"    local _seli = math.floor(({idx}))",
        f"    local _selarms = {{{arms}}}",
        f'    G["{uid}"] = _selarms[_seli + 1] or 0',
    ]


def emit_equal(uid: str, ins: list[str], _n: VPNode) -> list[str]:
    a, b = _g(0, ins), _g(1, ins)
    return _assign(uid, f"(({a}) == ({b})) and 1 or 0")


def emit_not_equal(uid: str, ins: list[str], _n: VPNode) -> list[str]:
    a, b = _g(0, ins), _g(1, ins)
    return _assign(uid, f"(({a}) ~= ({b})) and 1 or 0")


def emit_greater(uid: str, ins: list[str], _n: VPNode) -> list[str]:
    a, b = _g(0, ins), _g(1, ins)
    return _assign(uid, f"(({a}) > ({b})) and 1 or 0")


def emit_less(uid: str, ins: list[str], _n: VPNode) -> list[str]:
    a, b = _g(0, ins), _g(1, ins)
    return _assign(uid, f"(({a}) < ({b})) and 1 or 0")


def emit_greater_or_equal(uid: str, ins: list[str], _n: VPNode) -> list[str]:
    a, b = _g(0, ins), _g(1, ins)
    return _assign(uid, f"(({a}) >= ({b})) and 1 or 0")


def emit_less_or_equal(uid: str, ins: list[str], _n: VPNode) -> list[str]:
    a, b = _g(0, ins), _g(1, ins)
    return _assign(uid, f"(({a}) <= ({b})) and 1 or 0")


def emit_in_range_inclusive(uid: str, ins: list[str], _n: VPNode) -> list[str]:
    v, a, b = _g(0, ins), _g(1, ins), _g(2, ins)
    return [
        f"    local _rv, _rlo, _rhi = ({v}), ({a}), ({b})",
        f"    if _rlo > _rhi then _rlo, _rhi = _rhi, _rlo end",
        f'    G["{uid}"] = (_rv >= _rlo and _rv <= _rhi) and 1 or 0',
    ]


def emit_nxor(uid: str, ins: list[str], _n: VPNode) -> list[str]:
    a, b = _g(0, ins), _g(1, ins)
    return _assign(uid, f"((({a}) ~= 0) == (({b}) ~= 0)) and 1 or 0")


LOGIC_EMITTERS: dict[str, NodeEmitter] = {
    "And": emit_and,
    "Or": emit_or,
    "Not": emit_not,
    "Nand": emit_nand,
    "Nor": emit_nor,
    "Xor": emit_xor,
    "Branch": emit_branch,
    "Select": emit_select,
    "Equal": emit_equal,
    "NotEqual": emit_not_equal,
    "Greater": emit_greater,
    "Less": emit_less,
    "GreaterOrEqual": emit_greater_or_equal,
    "LessOrEqual": emit_less_or_equal,
    "InRangeInclusive": emit_in_range_inclusive,
    "Nxor": emit_nxor,
}