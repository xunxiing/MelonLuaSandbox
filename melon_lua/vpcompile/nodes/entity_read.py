"""Shard D: entity read NodeOperationType emitters (Entity(1) placeholder)."""
from __future__ import annotations

from ..ir import VPNode
from ._base import NodeEmitter


def _assign(uid: str, expr: str) -> list[str]:
    return [f'    G["{uid}"] = {expr}']


def _g(i: int, ins: list[str], default: str = "0") -> str:
    return ins[i] if i < len(ins) else default


def _ent(ins: list[str], idx: int = 0) -> str:
    if idx < len(ins):
        return f"Entity(({_g(idx, ins)}))"
    return "Entity(1)"


def _emit_multi_xy(
    uid: str,
    ins: list[str],
    n: VPNode,
    *,
    call: str,
    ent_idx: int = 0,
) -> list[str]:
    e = _ent(ins, ent_idx)
    outs = n.outputs or []
    lines = [f"    local _vx, _vy = {call}"]
    if len(outs) >= 2:
        lines.append(f'    G["{uid}_o0"] = _vx')
        lines.append(f'    G["{uid}_o1"] = _vy')
    lines.append(f'    G["{uid}"] = _vx')
    return lines


def emit_position(uid: str, ins: list[str], n: VPNode) -> list[str]:
    e = _ent(ins, 0)
    return _emit_multi_xy(uid, ins, n, call=f"{e}:getPosition()")


def emit_velocity(uid: str, ins: list[str], n: VPNode) -> list[str]:
    e = _ent(ins, 0)
    return _emit_multi_xy(uid, ins, n, call=f"{e}:getVelocity()")


def emit_angular_velocity(uid: str, ins: list[str], n: VPNode) -> list[str]:
    e = _ent(ins, 0)
    return _assign(uid, f"{e}:getAngularVelocity()")


def emit_entity_angle(uid: str, ins: list[str], n: VPNode) -> list[str]:
    e = _ent(ins, 0)
    return _assign(uid, f"{e}:getAngle()")


def emit_elevation(uid: str, ins: list[str], n: VPNode) -> list[str]:
    e = _ent(ins, 0)
    tx, ty = _g(1, ins), _g(2, ins)
    return _assign(uid, f"{e}:getElevation(({tx}), ({ty}))")


def emit_mass(uid: str, ins: list[str], _n: VPNode) -> list[str]:
    e = _ent(ins, 0)
    return _assign(uid, f"{e}:getMass()")


def emit_size(uid: str, ins: list[str], n: VPNode) -> list[str]:
    e = _ent(ins, 0)
    return _emit_multi_xy(uid, ins, n, call=f"{e}:getSize()")


def emit_entity_id(uid: str, ins: list[str], _n: VPNode) -> list[str]:
    e = _ent(ins, 0)
    return _assign(uid, f"{e}:getId()")


def emit_color(uid: str, ins: list[str], n: VPNode) -> list[str]:
    e = _ent(ins, 0)
    outs = n.outputs or []
    lines = [f"    local _cr, _cg, _cb, _ca = {e}:getColor()"]
    keys = ("r", "g", "b", "a")
    for i in range(min(4, max(1, len(outs)))):
        var = ("_cr", "_cg", "_cb", "_ca")[i]
        lines.append(f'    G["{uid}_o{i}"] = {var}')
        lines.append(f'    G["{uid}_{keys[i]}"] = {var}')
    if not outs:
        lines.append(f'    G["{uid}"] = _cr')
    return lines


def emit_temperature(uid: str, ins: list[str], _n: VPNode) -> list[str]:
    e = _ent(ins, 0)
    return _assign(uid, f"{e}:getTemperature()")


def emit_voltage(uid: str, ins: list[str], _n: VPNode) -> list[str]:
    e = _ent(ins, 0)
    return _assign(uid, f"{e}:getVoltage()")


def emit_entity_name(uid: str, ins: list[str], _n: VPNode) -> list[str]:
    e = _ent(ins, 0)
    return _assign(uid, f'{e}:getName() or ""')


def emit_mass_center(uid: str, ins: list[str], n: VPNode) -> list[str]:
    e = _ent(ins, 0)
    return _emit_multi_xy(uid, ins, n, call=f"{e}:getCenterOfMass()")


def emit_velocity_at_position(uid: str, ins: list[str], n: VPNode) -> list[str]:
    e = _ent(ins, 0)
    px, py = _g(1, ins), _g(2, ins)
    call = f"{e}:getVelocityAtPoint(({px}), ({py}))"
    return _emit_multi_xy(uid, ins, n, call=call)


def emit_gravity(uid: str, ins: list[str], _n: VPNode) -> list[str]:
    e = _ent(ins, 0)
    return _assign(uid, f"{e}:getGravityScale()")


def emit_can_be_activated(uid: str, ins: list[str], _n: VPNode) -> list[str]:
    e = _ent(ins, 0)
    return _assign(uid, f"{e}:canBeActivated()")


def emit_collision(uid: str, ins: list[str], _n: VPNode) -> list[str]:
    e = _ent(ins, 0)
    return [
        f"    -- Collision {uid}: read stub (collision state not exposed on Entity API)",
        f'    G["{uid}"] = 0',
        f"    -- entity {e} collision queries need subscribeCollision* at runtime",
    ]


ENTITY_READ_EMITTERS: dict[str, NodeEmitter] = {
    "Position": emit_position,
    "Velocity": emit_velocity,
    "AngularVelocity": emit_angular_velocity,
    "EntityAngle": emit_entity_angle,
    "Elevation": emit_elevation,
    "Mass": emit_mass,
    "Size": emit_size,
    "EntityID": emit_entity_id,
    "Color": emit_color,
    "Temperature": emit_temperature,
    "Voltage": emit_voltage,
    "EntityName": emit_entity_name,
    "MassCenter": emit_mass_center,
    "VelocityAtPosition": emit_velocity_at_position,
    "CanBeActivated": emit_can_be_activated,
    "Collision": emit_collision,
}