"""Shard G: flow / IO / time nodes (Root, Exit, constants, state)."""
from __future__ import annotations

import json
import math

from ..save_data import constant_value
from ..ir import VPNode
from ._base import NodeEmitter


def _assign(uid: str, expr: str) -> list[str]:
    return [f'    G["{uid}"] = {expr}']


def _g(i: int, ins: list[str], default: str = "0") -> str:
    return ins[i] if i < len(ins) else default


def _save_data_obj(node: VPNode) -> dict:
    sd = node.save_data
    if not sd:
        return {}
    try:
        obj = json.loads(sd)
        return obj if isinstance(obj, dict) else {}
    except (json.JSONDecodeError, TypeError):
        return {}


def _gate_name_from_save(node: VPNode, fallback: str) -> str:
    obj = _save_data_obj(node)
    for key in ("DataName", "MechanicInputId", "MechanicOutputId", "Name"):
        v = obj.get(key)
        if v is not None and str(v).strip():
            return _lua_ident(str(v).strip(), fallback)
    return fallback


def _lua_ident(name: str, fallback: str) -> str:
    s = "".join(c if c.isalnum() or c == "_" else "_" for c in name)
    if not s or s[0].isdigit():
        return fallback
    return s


def emit_constant(uid: str, _ins: list[str], n: VPNode) -> list[str]:
    v = constant_value(n)
    if v == int(v):
        return _assign(uid, str(int(v)))
    return _assign(uid, str(v))


def emit_pi(uid: str, _ins: list[str], _n: VPNode) -> list[str]:
    return _assign(uid, str(math.pi))


def emit_e(uid: str, _ins: list[str], _n: VPNode) -> list[str]:
    return _assign(uid, str(math.e))


def emit_identity(uid: str, ins: list[str], _n: VPNode) -> list[str]:
    return _assign(uid, _g(0, ins))


def emit_root(uid: str, ins: list[str], n: VPNode) -> list[str]:
    gate = _gate_name_from_save(n, "a")
    obj = _save_data_obj(n)
    ent = obj.get("EntityId") or obj.get("entityId")
    lines = [f"    -- Root {uid}: entity/input gate"]
    if ent is not None:
        lines.append(f'    G["{uid}"] = {int(ent)}')
    elif ins:
        lines.append(f'    G["{uid}"] = {ins[0]}')
    else:
        lines.append(f'    G["{uid}"] = (inputs.num and inputs.num.{gate}) or 1')
    for i, _inp in enumerate(n.inputs):
        if i == 0 and ins:
            continue
        lines.append(f'    G["{uid}_in{i}"] = (inputs.num and inputs.num.{gate}) or 0')
    return lines


def emit_exit(uid: str, ins: list[str], n: VPNode) -> list[str]:
    if not ins:
        return [f"    -- Exit {uid}: no wired input"]
    gate = _gate_name_from_save(n, "out")
    return [f"    outputs.num.{gate} = {ins[0]}"]


def emit_variable(uid: str, ins: list[str], n: VPNode) -> list[str]:
    init = constant_value(n)
    init_s = str(int(init)) if init == int(init) else str(init)
    lines = []
    if len(ins) >= 2:
        lines.append(
            f"    if ({ins[1]}) ~= 0 then G[\"{uid}\"] = {ins[0]} end"
        )
    lines.append(f'    G["{uid}"] = G["{uid}"] or {init_s}')
    return lines


def emit_counter(uid: str, ins: list[str], _n: VPNode) -> list[str]:
    mem = f'["_cnt_{uid}"]'
    num = _g(0, ins)
    inc = _g(1, ins, "0")
    dec = _g(2, ins, "0")
    rst = _g(3, ins, "0")
    return [
        f"    G{mem} = G{mem} or {num}",
        f"    if ({rst}) ~= 0 then G{mem} = {num} end",
        f"    G{mem} = G{mem} + ({inc}) - ({dec})",
        f'    G["{uid}"] = G{mem}',
    ]


def emit_delay(uid: str, ins: list[str], _n: VPNode) -> list[str]:
    tmem = f'["_delay_{uid}"]'
    arm = f'["_delay_arm_{uid}"]'
    delay = _g(1, ins, "0")
    enable = _g(2, ins, "0")
    rst = _g(3, ins, "0")
    hold = _g(4, ins, "0")
    return [
        f"    G{tmem} = G{tmem} or 0",
        f"    G{arm} = G{arm} or false",
        f"    if ({rst}) ~= 0 then G{tmem} = 0 G{arm} = false end",
        f"    if ({enable}) ~= 0 and not G{arm} then G{arm} = true G{tmem} = 0 end",
        f"    if G{arm} then G{tmem} = G{tmem} + (1 / math.max(1, chip_tps or 20)) end",
        f"    local _dready = G{arm} and G{tmem} >= ({delay})",
        f'    G["{uid}"] = (_dready and ({hold}) ~= 0) and 1 or 0',
    ]


def emit_trigger(uid: str, ins: list[str], _n: VPNode) -> list[str]:
    prev = f'["_trg_{uid}"]'
    cur = _g(0, ins)
    return [
        f"    G{prev} = G{prev} or 0",
        f'    G["{uid}"] = (({cur}) ~= 0 and G{prev} == 0) and 1 or 0',
        f"    G{prev} = ({cur}) ~= 0 and 1 or 0",
    ]


def emit_time(uid: str, _ins: list[str], n: VPNode) -> list[str]:
    outs = n.outputs or []
    lines = [f"    -- Time {uid}: sandbox tick time stub"]
    keys = ("time", "delta", "frame", "unscaled")
    for i in range(min(4, max(1, len(outs)))):
        key = f"{uid}_o{i}"
        if i == 0:
            lines.append(f'    G["{key}"] = (G._vp_tick or 0) / math.max(1, chip_tps or 20)')
        elif i == 1:
            lines.append(f'    G["{key}"] = 1 / math.max(1, chip_tps or 20)')
        else:
            lines.append(f'    G["{key}"] = G._vp_tick or 0')
        lines.append(f'    G["{uid}_{keys[i]}"] = G["{key}"]')
    if not outs:
        lines.append(
            f'    G["{uid}"] = (G._vp_tick or 0) / math.max(1, chip_tps or 20)'
        )
    return lines


def emit_random(uid: str, ins: list[str], _n: VPNode) -> list[str]:
    lo = _g(0, ins, "0")
    hi = _g(1, ins, "1")
    return [
        f"    local _rlo, _rhi = ({lo}), ({hi})",
        f"    if _rlo > _rhi then _rlo, _rhi = _rhi, _rlo end",
        f'    G["{uid}"] = _rlo + math.random() * (_rhi - _rlo)',
    ]


def emit_sticker(uid: str, _ins: list[str], _n: VPNode) -> list[str]:
    return [f"    -- Sticker {uid}: editor-only (no runtime)"]


FLOW_EMITTERS: dict[str, NodeEmitter] = {
    "Root": emit_root,
    "Exit": emit_exit,
    "Constant": emit_constant,
    "Variable": emit_variable,
    "Counter": emit_counter,
    "Delay": emit_delay,
    "Trigger": emit_trigger,
    "Identity": emit_identity,
    "Sticker": emit_sticker,
    "Pi": emit_pi,
    "E": emit_e,
    "Time": emit_time,
    "Random": emit_random,
}