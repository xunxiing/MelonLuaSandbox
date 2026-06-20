"""Shard F: vector scalars (Magnitude etc.) + Split/Combine/Normalize."""
from __future__ import annotations

import math

from ..ir import VPNode
from ._base import NodeEmitter


def _assign(uid: str, expr: str) -> list[str]:
    return [f'    G["{uid}"] = {expr}']


def _g(i: int, ins: list[str], default: str = "0") -> str:
    return ins[i] if i < len(ins) else default


def emit_magnitude(uid: str, ins: list[str], _n: VPNode) -> list[str]:
    """Magnitude: Vector -> Number (sqrt(x^2+y^2+z^2+w^2), usually 2D)."""
    v = _g(0, ins)
    # Assume vector is {x, y, z, w} table; magnitude uses x,y for 2D
    return [
        f"    local _vmag = {v}",
        f"    local _vx = type(_vmag) == 'table' and (_vmag.x or _vmag[1] or 0) or _vmag",
        f"    local _vy = type(_vmag) == 'table' and (_vmag.y or _vmag[2] or 0) or 0",
        f'    G["{uid}"] = math.sqrt(_vx * _vx + _vy * _vy)',
    ]


def emit_sqr_magnitude(uid: str, ins: list[str], _n: VPNode) -> list[str]:
    v = _g(0, ins)
    return [
        f"    local _vsm = {v}",
        f"    local _vx = type(_vsm) == 'table' and (_vsm.x or _vsm[1] or 0) or _vsm",
        f"    local _vy = type(_vsm) == 'table' and (_vsm.y or _vsm[2] or 0) or 0",
        f'    G["{uid}"] = _vx * _vx + _vy * _vy',
    ]


def emit_split(uid: str, ins: list[str], n: VPNode) -> list[str]:
    """Split: Vector -> 4 Numbers (x, y, z, w)."""
    v = _g(0, ins, "{x=0,y=0,z=0,w=0}")
    outs = n.outputs or []
    lines = [
        f"    local _spl = {v}",
        f"    local _splx = type(_spl) == 'table' and (_spl.x or _spl[1] or 0) or _spl",
        f"    local _spy = type(_spl) == 'table' and (_spl.y or _spl[2] or 0) or 0",
        f"    local _splz = type(_spl) == 'table' and (_spl.z or _spl[3] or 0) or 0",
        f"    local _splw = type(_spl) == 'table' and (_spl.w or _spl[4] or 0) or 0",
    ]
    # Emit outputs based on how many outputs the node has
    for i in range(min(4, max(1, len(outs)))):
        comp = ("_splx", "_spy", "_splz", "_splw")[i]
        lines.append(f'    G["{uid}_o{i}"] = {comp}')
    # Primary output is x (first component)
    lines.append(f'    G["{uid}"] = _splx')
    return lines


def emit_combine(uid: str, ins: list[str], n: VPNode) -> list[str]:
    """Combine: 4 Numbers (x,y,z,w) -> Vector."""
    x = _g(0, ins, "0")
    y = _g(1, ins, "0")
    z = _g(2, ins, "0")
    w = _g(3, ins, "0")
    # Use local variables to avoid field access on literals (0.x is syntax error)
    return [
        f"    local _cxv = {x}",
        f"    local _cyv = {y}",
        f"    local _czv = {z}",
        f"    local _cwv = {w}",
        f"    local _cx = type(_cxv) == 'table' and (_cxv.x or _cxv[1] or 0) or _cxv",
        f"    local _cy = type(_cyv) == 'table' and (_cyv.y or _cyv[2] or 0) or _cyv",
        f"    local _cz = type(_czv) == 'table' and (_czv.z or _czv[3] or 0) or _czv",
        f"    local _cw = type(_cwv) == 'table' and (_cwv.w or _cwv[4] or 0) or _cwv",
        f'    G["{uid}"] = {{x = _cx, y = _cy, z = _cz, w = _cw}}',
    ]


def emit_normalize(uid: str, ins: list[str], n: VPNode) -> list[str]:
    """Normalize: Vector -> Vector (unit vector)."""
    v = _g(0, ins, "{x=0,y=0,z=0,w=0}")
    return [
        f"    local _norm = {v}",
        f"    local _nx = type(_norm) == 'table' and (_norm.x or _norm[1] or 0) or _norm",
        f"    local _ny = type(_norm) == 'table' and (_norm.y or _norm[2] or 0) or 0",
        f"    local _nz = type(_norm) == 'table' and (_norm.z or _norm[3] or 0) or 0",
        f"    local _nw = type(_norm) == 'table' and (_norm.w or _norm[4] or 0) or 0",
        f"    local _len = math.sqrt(_nx * _nx + _ny * _ny)",
        f"    local _flen = math.max(1e-6, _len)",
        f'    G["{uid}"] = {{x = _nx / _flen, y = _ny / _flen, z = _nz / _flen, w = _nw / _flen}}',
    ]


VECTOR_EMITTERS: dict[str, NodeEmitter] = {
    "Magnitude": emit_magnitude,
    "SqrMagnitude": emit_sqr_magnitude,
    "Split": emit_split,
    "Combine": emit_combine,
    "Normalize": emit_normalize,
}