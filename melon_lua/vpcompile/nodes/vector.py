"""Shard F: vector scalars (Magnitude etc.)."""
from __future__ import annotations

from ..ir import VPNode
from ._base import NodeEmitter


def _assign(uid: str, expr: str) -> list[str]:
    return [f'    G["{uid}"] = {expr}']


def emit_magnitude(uid: str, ins: list[str], _n: VPNode) -> list[str]:
    if len(ins) >= 2:
        return _assign(uid, f"math.sqrt(({ins[0]})^2 + ({ins[1]})^2)")
    if len(ins) == 1:
        return _assign(uid, f"math.abs({ins[0]})")
    return _assign(uid, "0")


def emit_sqr_magnitude(uid: str, ins: list[str], _n: VPNode) -> list[str]:
    if len(ins) >= 2:
        return _assign(uid, f"({ins[0]})^2 + ({ins[1]})^2")
    return _assign(uid, "0")


VECTOR_EMITTERS: dict[str, NodeEmitter] = {
    "Magnitude": emit_magnitude,
    "SqrMagnitude": emit_sqr_magnitude,
}