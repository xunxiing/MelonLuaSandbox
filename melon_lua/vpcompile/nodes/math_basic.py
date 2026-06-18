"""Shard A: basic scalar math NodeOperationType emitters."""
from __future__ import annotations

from ..ir import VPNode
from ._base import NodeEmitter


def _assign(uid: str, expr: str) -> list[str]:
    return [f'    G["{uid}"] = {expr}']


def _g(i: int, ins: list[str], default: str = "0") -> str:
    return ins[i] if i < len(ins) else default


def emit_add(uid: str, ins: list[str], _n: VPNode) -> list[str]:
    if len(ins) >= 2:
        return _assign(uid, f"({ins[0]}) + ({ins[1]})")
    if len(ins) == 1:
        return _assign(uid, f"({ins[0]}) + 0")
    return _assign(uid, "0")


def emit_subtract(uid: str, ins: list[str], _n: VPNode) -> list[str]:
    if len(ins) >= 2:
        return _assign(uid, f"({ins[0]}) - ({ins[1]})")
    return _assign(uid, "0")


def emit_multiply(uid: str, ins: list[str], _n: VPNode) -> list[str]:
    if len(ins) >= 2:
        return _assign(uid, f"({ins[0]}) * ({ins[1]})")
    return _assign(uid, "0")


def emit_divide(uid: str, ins: list[str], _n: VPNode) -> list[str]:
    if len(ins) >= 2:
        return _assign(uid, f"(({ins[1]}) ~= 0 and ({ins[0]}) / ({ins[1]}) or 0)")
    return _assign(uid, "0")


def emit_negate(uid: str, ins: list[str], _n: VPNode) -> list[str]:
    return _assign(uid, f"-({_g(0, ins)})")


def emit_abs(uid: str, ins: list[str], _n: VPNode) -> list[str]:
    return _assign(uid, f"math.abs({_g(0, ins)})")


def emit_min(uid: str, ins: list[str], _n: VPNode) -> list[str]:
    if len(ins) >= 2:
        return _assign(uid, f"math.min(({ins[0]}), ({ins[1]}))")
    return _assign(uid, _g(0, ins))


def emit_max(uid: str, ins: list[str], _n: VPNode) -> list[str]:
    if len(ins) >= 2:
        return _assign(uid, f"math.max(({ins[0]}), ({ins[1]}))")
    return _assign(uid, _g(0, ins))


def emit_clamp(uid: str, ins: list[str], _n: VPNode) -> list[str]:
    v, lo, hi = _g(0, ins), _g(1, ins), _g(2, ins)
    return _assign(uid, f"math.max(({lo}), math.min(({hi}), ({v})))")


def emit_clamp01(uid: str, ins: list[str], _n: VPNode) -> list[str]:
    v = _g(0, ins)
    return _assign(uid, f"math.max(0, math.min(1, ({v})))")


def emit_sqr(uid: str, ins: list[str], _n: VPNode) -> list[str]:
    x = _g(0, ins)
    return _assign(uid, f"({x}) * ({x})")


def emit_sqrt(uid: str, ins: list[str], _n: VPNode) -> list[str]:
    return _assign(uid, f"math.sqrt(math.max(0, ({_g(0, ins)})))")


def emit_pow(uid: str, ins: list[str], _n: VPNode) -> list[str]:
    if len(ins) >= 2:
        return _assign(uid, f"math.pow(({ins[0]}), ({ins[1]}))")
    return _assign(uid, "1")


def emit_mod(uid: str, ins: list[str], _n: VPNode) -> list[str]:
    if len(ins) >= 2:
        return _assign(uid, f"math.fmod(({ins[0]}), ({ins[1]}))")
    return _assign(uid, "0")


def emit_lerp(uid: str, ins: list[str], _n: VPNode) -> list[str]:
    a, b, t = _g(0, ins), _g(1, ins), _g(2, ins)
    return _assign(uid, f"({a}) + (({b}) - ({a})) * ({t})")


def emit_floor(uid: str, ins: list[str], _n: VPNode) -> list[str]:
    return _assign(uid, f"math.floor({_g(0, ins)})")


def emit_ceil(uid: str, ins: list[str], _n: VPNode) -> list[str]:
    return _assign(uid, f"math.ceil({_g(0, ins)})")


def emit_round(uid: str, ins: list[str], _n: VPNode) -> list[str]:
    return _assign(uid, f"math.floor(({_g(0, ins)}) + 0.5)")


def emit_sign(uid: str, ins: list[str], _n: VPNode) -> list[str]:
    x = _g(0, ins)
    return _assign(
        uid,
        f"(({x}) > 0 and 1 or (({x}) < 0 and -1 or 0))",
    )


def emit_inverse(uid: str, ins: list[str], _n: VPNode) -> list[str]:
    x = _g(0, ins)
    return _assign(uid, f"(({x}) ~= 0 and 1 / ({x}) or 0)")


def emit_percent(uid: str, ins: list[str], _n: VPNode) -> list[str]:
    if len(ins) >= 2:
        return _assign(
            uid,
            f"(({ins[1]}) ~= 0 and (({ins[0]}) / ({ins[1]})) * 100 or 0)",
        )
    return _assign(uid, "0")


def emit_average(uid: str, ins: list[str], _n: VPNode) -> list[str]:
    if len(ins) >= 2:
        return _assign(uid, f"(({ins[0]}) + ({ins[1]})) / 2")
    return _assign(uid, _g(0, ins))


def emit_exp(uid: str, ins: list[str], _n: VPNode) -> list[str]:
    return _assign(uid, f"math.exp({_g(0, ins)})")


def emit_log(uid: str, ins: list[str], _n: VPNode) -> list[str]:
    x = _g(0, ins)
    return _assign(uid, f"(({x}) > 0 and math.log({x}) or 0)")


MATH_BASIC_EMITTERS: dict[str, NodeEmitter] = {
    "Add": emit_add,
    "Subtract": emit_subtract,
    "Multiply": emit_multiply,
    "Divide": emit_divide,
    "Negate": emit_negate,
    "Abs": emit_abs,
    "Min": emit_min,
    "Max": emit_max,
    "Clamp": emit_clamp,
    "Clamp01": emit_clamp01,
    "Sqr": emit_sqr,
    "Sqrt": emit_sqrt,
    "Pow": emit_pow,
    "Mod": emit_mod,
    "Lerp": emit_lerp,
    "Floor": emit_floor,
    "Ceil": emit_ceil,
    "Round": emit_round,
    "Sign": emit_sign,
    "Inverse": emit_inverse,
    "Percent": emit_percent,
    "Average": emit_average,
    "Exp": emit_exp,
    "Log": emit_log,
}