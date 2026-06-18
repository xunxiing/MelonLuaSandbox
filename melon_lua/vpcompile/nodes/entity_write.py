"""Shard E: entity write NodeOperationType emitters (Entity API side effects)."""
from __future__ import annotations

from ..ir import VPNode
from ._base import NodeEmitter


def _g(i: int, ins: list[str], default: str = "0") -> str:
    return ins[i] if i < len(ins) else default


def _ent(ins: list[str], idx: int = 0) -> str:
    if idx < len(ins):
        return f"Entity(({_g(idx, ins)}))"
    return "Entity(1)"


def _truthy(expr: str) -> str:
    return f"(({expr}) ~= 0 and ({expr}) ~= nil)"


def _vec2(ins: list[str], idx: int) -> tuple[str, str]:
    if idx >= len(ins):
        return "0", "0"
    base = ins[idx]
    if base.startswith('G["') and base.endswith('"]'):
        key = base[3:-2]
        return base, f'G["{key}_o1"]'
    return f"({base})", "0"


def emit_add_force(uid: str, ins: list[str], _n: VPNode) -> list[str]:
    e = _ent(ins, 0)
    fx, fy = _vec2(ins, 1)
    return [f"    {e}:addForce({fx}, {fy})"]


def emit_add_angular_force(uid: str, ins: list[str], _n: VPNode) -> list[str]:
    e = _ent(ins, 0)
    t = _g(1, ins)
    return [f"    {e}:addTorque(({t}))"]


def emit_add_force_at_position(uid: str, ins: list[str], _n: VPNode) -> list[str]:
    e = _ent(ins, 0)
    fx, fy = _vec2(ins, 1)
    px, py = _vec2(ins, 2)
    return [f"    {e}:addForceAtPosition({fx}, {fy}, {px}, {py})"]


def emit_activate(uid: str, ins: list[str], _n: VPNode) -> list[str]:
    e = _ent(ins, 0)
    flag = _g(1, ins)
    lines = [
        f"    if {_truthy(flag)} then",
        f"      {e}:activate(1)",
        "    else",
        f"      {e}:activate(0)",
        "    end",
        f'    G["{uid}"] = {e}:getActivationInput()',
    ]
    return lines


def emit_freeze(uid: str, ins: list[str], _n: VPNode) -> list[str]:
    e = _ent(ins, 0)
    flag = _g(1, ins)
    lines = [
        f"    if {_truthy(flag)} then",
        f"      {e}:freeze(1)",
        "    else",
        f"      {e}:freeze(0)",
        "    end",
        f'    G["{uid}"] = {e}:isFrozen()',
    ]
    return lines


def emit_ignite(uid: str, ins: list[str], _n: VPNode) -> list[str]:
    e = _ent(ins, 0)
    flag = _g(1, ins)
    lines = [
        f"    if {_truthy(flag)} then",
        f"      {e}:ignite()",
        "    end",
        f'    G["{uid}"] = {e}:isOnFire()',
    ]
    return lines


def emit_extinguish(uid: str, ins: list[str], _n: VPNode) -> list[str]:
    e = _ent(ins, 0)
    flag = _g(1, ins)
    lines = [
        f"    if {_truthy(flag)} then",
        f"      {e}:extinguish()",
        "    end",
    ]
    return lines


def emit_delete(uid: str, ins: list[str], _n: VPNode) -> list[str]:
    e = _ent(ins, 0)
    flag = _g(1, ins)
    return [
        f"    if {_truthy(flag)} then",
        f"      {e}:delete()",
        "    end",
    ]


def emit_look_at(uid: str, ins: list[str], _n: VPNode) -> list[str]:
    e = _ent(ins, 0)
    rate = _g(2, ins, "360")
    return [f"    {e}:lookAt(({_g(1, ins)}), ({rate}))"]


def emit_draggable(uid: str, ins: list[str], _n: VPNode) -> list[str]:
    e = _ent(ins, 0)
    flag = _g(1, ins)
    lines = [
        f"    if {_truthy(flag)} then",
        f"      {e}:setDraggable(1)",
        "    else",
        f"      {e}:setDraggable(0)",
        "    end",
        f'    G["{uid}"] = {e}:isDraggable()',
    ]
    return lines


def emit_gravity(uid: str, ins: list[str], _n: VPNode) -> list[str]:
    e = _ent(ins, 0)
    scale = _g(1, ins)
    lines = [
        f"    {e}:setGravityScale(({scale}))",
        f'    G["{uid}"] = {e}:getGravityScale()',
    ]
    return lines


def emit_follow(uid: str, ins: list[str], _n: VPNode) -> list[str]:
    on = _g(1, ins)
    off = _g(2, ins)
    ent_id = _g(0, ins)
    lines = [
        f"    if {_truthy(on)} then",
        f"      if camera and camera.follow then camera.follow(({ent_id})) end",
        f"    elseif {_truthy(off)} then",
        "      if camera and camera.unfollow then camera.unfollow() end",
        "    end",
        f'    G["{uid}"] = (camera and camera.isFollowing and camera.isFollowing()) or 0',
    ]
    return lines


ENTITY_WRITE_EMITTERS: dict[str, NodeEmitter] = {
    "AddForce": emit_add_force,
    "AddAngularForce": emit_add_angular_force,
    "AddForceAtPosition": emit_add_force_at_position,
    "Activate": emit_activate,
    "Freeze": emit_freeze,
    "Ignite": emit_ignite,
    "Extinguish": emit_extinguish,
    "Delete": emit_delete,
    "LookAt": emit_look_at,
    "Draggable": emit_draggable,
    "Gravity": emit_gravity,
    "Follow": emit_follow,
}