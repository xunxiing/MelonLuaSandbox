"""Shard A: basic scalar math NodeOperationType emitters."""
from __future__ import annotations

from ..ir import VPNode
from ._base import NodeEmitter


def _assign(uid: str, expr: str) -> list[str]:
    return [f'    G["{uid}"] = {expr}']


def _g(i: int, ins: list[str], default: str = "0") -> str:
    return ins[i] if i < len(ins) else default


def _is_vector(n: VPNode) -> bool:
    """Check if node operates on vector data."""
    gdt = n.raw.get("GateDataType")
    if isinstance(gdt, str) and gdt.strip() == "Vector":
        return True
    for inp in n.inputs:
        dt = inp.get("DataType")
        if isinstance(dt, str) and dt.strip() == "Vector":
            return True
    return False


def _vector_binop(uid: str, a: str, b: str, op: str) -> list[str]:
    """Emit vector binary operation (a op b) component-wise."""
    op_map = {"+": " + ", "-": " - ", "*": " * ", "/": " / "}
    op_str = op_map.get(op, op)
    return [
        f"    local _va, _vb = {a}, {b}",
        f"    local _vax = type(_va) == 'table' and (_va.x or _va[1] or 0) or _va",
        f"    local _vay = type(_va) == 'table' and (_va.y or _va[2] or 0) or 0",
        f"    local _vaz = type(_va) == 'table' and (_va.z or _va[3] or 0) or 0",
        f"    local _vaw = type(_va) == 'table' and (_va.w or _va[4] or 0) or 0",
        f"    local _vbx = type(_vb) == 'table' and (_vb.x or _vb[1] or 0) or _vb",
        f"    local _vby = type(_vb) == 'table' and (_vb.y or _vb[2] or 0) or 0",
        f"    local _vbz = type(_vb) == 'table' and (_vb.z or _vb[3] or 0) or 0",
        f"    local _vbw = type(_vb) == 'table' and (_vb.w or _vb[4] or 0) or 0",
        f'    G["{uid}"] = {{x = _vax {op_str} _vbx, y = _vay {op_str} _vby, z = _vaz {op_str} _vbz, w = _vaw {op_str} _vbw}}',
    ]


def emit_add(uid: str, ins: list[str], n: VPNode) -> list[str]:
    if _is_vector(n):
        a, b = _g(0, ins, "{x=0,y=0,z=0,w=0}"), _g(1, ins, "{x=0,y=0,z=0,w=0}")
        return _vector_binop(uid, a, b, "+")
    if len(ins) >= 2:
        return _assign(uid, f"({ins[0]}) + ({ins[1]})")
    if len(ins) == 1:
        return _assign(uid, f"({ins[0]}) + 0")
    return _assign(uid, "0")


def emit_subtract(uid: str, ins: list[str], n: VPNode) -> list[str]:
    if _is_vector(n):
        a, b = _g(0, ins, "{x=0,y=0,z=0,w=0}"), _g(1, ins, "{x=0,y=0,z=0,w=0}")
        return _vector_binop(uid, a, b, "-")
    if len(ins) >= 2:
        return _assign(uid, f"({ins[0]}) - ({ins[1]})")
    return _assign(uid, "0")


def emit_multiply(uid: str, ins: list[str], n: VPNode) -> list[str]:
    if _is_vector(n):
        a, b = _g(0, ins, "{x=0,y=0,z=0,w=0}"), _g(1, ins, "{x=0,y=0,z=0,w=0}")
        return _vector_binop(uid, a, b, "*")
    if len(ins) >= 2:
        return _assign(uid, f"({ins[0]}) * ({ins[1]})")
    return _assign(uid, "0")


def emit_divide(uid: str, ins: list[str], n: VPNode) -> list[str]:
    if _is_vector(n):
        a, b = _g(0, ins, "{x=0,y=0,z=0,w=0}"), _g(1, ins, "{x=0,y=0,z=0,w=0}")
        return [
            f"    local _va, _vb = {a}, {b}",
            f"    local _vax = type(_va) == 'table' and (_va.x or _va[1] or 0) or _va",
            f"    local _vay = type(_va) == 'table' and (_va.y or _va[2] or 0) or 0",
            f"    local _vaz = type(_va) == 'table' and (_va.z or _va[3] or 0) or 0",
            f"    local _vaw = type(_va) == 'table' and (_va.w or _va[4] or 0) or 0",
            f"    local _vbx = type(_vb) == 'table' and (_vb.x or _vb[1] or 0) or _vb",
            f"    local _vby = type(_vb) == 'table' and (_vb.y or _vb[2] or 0) or 0",
            f"    local _vbz = type(_vb) == 'table' and (_vb.z or _vb[3] or 0) or 0",
            f"    local _vbw = type(_vb) == 'table' and (_vb.w or _vb[4] or 0) or 0",
            f'    G["{uid}"] = {{x = _vbx ~= 0 and _vax / _vbx or 0, y = _vby ~= 0 and _vay / _vby or 0, z = _vbz ~= 0 and _vaz / _vbz or 0, w = _vbw ~= 0 and _vaw / _vbw or 0}}',
        ]
    if len(ins) >= 2:
        return _assign(uid, f"(({ins[1]}) ~= 0 and ({ins[0]}) / ({ins[1]}) or 0)")
    return _assign(uid, "0")


def emit_negate(uid: str, ins: list[str], n: VPNode) -> list[str]:
    if _is_vector(n):
        v = _g(0, ins, "{x=0,y=0,z=0,w=0}")
        return [
            f"    local _nv = {v}",
            f"    local _nvx = type(_nv) == 'table' and (_nv.x or _nv[1] or 0) or _nv",
            f"    local _nvy = type(_nv) == 'table' and (_nv.y or _nv[2] or 0) or 0",
            f"    local _nvz = type(_nv) == 'table' and (_nv.z or _nv[3] or 0) or 0",
            f"    local _nvw = type(_nv) == 'table' and (_nv.w or _nv[4] or 0) or 0",
            f'    G["{uid}"] = {{x = -_nvx, y = -_nvy, z = -_nvz, w = -_nvw}}',
        ]
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