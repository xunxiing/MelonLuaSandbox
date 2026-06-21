"""Emit Lua from MelonGraph (C1 math subset)."""
from __future__ import annotations

import json
from typing import Any

from .ir import MelonGraph, VPNode
from .nodes import REGISTRY
from .nodes.flow import set_chip_variables



def _slot_key(to_node: str, input_index: int) -> str:
    return f"_in_{to_node}_{input_index}"


def _wire_inputs(graph: MelonGraph) -> dict[str, dict[int, str]]:
    """Map to_node -> input_index -> from_node uid."""
    by_to: dict[str, dict[int, str]] = {}
    for uid, n in graph.nodes.items():
        for i, inp in enumerate(n.inputs):
            co = inp.get("connectedOutputIdModel")
            if not co:
                continue
            from_full = str(co.get("NodeId") or "")
            for fu, fn in graph.nodes.items():
                if fn.full_id == from_full:
                    by_to.setdefault(uid, {})[i] = fu
                    break
    return by_to


def _is_vector_node(n: VPNode) -> bool:
    """Check if a node operates on vector data (GateDataType or input DataType)."""
    gdt = n.raw.get("GateDataType")
    if isinstance(gdt, str) and gdt.strip() == "Vector":
        return True
    for inp in n.inputs:
        dt = inp.get("DataType")
        if isinstance(dt, str) and dt.strip() == "Vector":
            return True
    return False


def _build_var_uid_map(graph: MelonGraph) -> dict[str, str]:
    """Map Variable node uid -> shared G key (MechanicConnectionId).

    Variable nodes with the same MechanicConnectionId share state. Other nodes
    reference a variable by uid; this map lets _input_exprs redirect those
    references to the shared key so readers always see writer-updated state.
    """
    mapping: dict[str, str] = {}
    for uid, n in graph.nodes.items():
        if n.name == "Variable":
            mci = n.raw.get("MechanicConnectionId")
            if mci:
                mapping[uid] = mci
    return mapping


def _parse_chip_variables(raw: str | list | None) -> dict[str, float]:
    """Parse chip_variables JSON into a Key -> Value dict."""
    if not raw:
        return {}
    try:
        if isinstance(raw, str):
            items = json.loads(raw)
        else:
            items = raw
    except (json.JSONDecodeError, TypeError):
        return {}
    result: dict[str, float] = {}
    for item in items:
        key = item.get("Key")
        if not key:
            continue
        sv = item.get("SerializedValue")
        try:
            sv_obj = json.loads(sv) if isinstance(sv, str) else (sv or {})
            val = sv_obj.get("Value", 0.0)
            result[key] = float(val) if val is not None else 0.0
        except (json.JSONDecodeError, TypeError, ValueError):
            result[key] = 0.0
    return result


def generate_lua(
    graph: MelonGraph,
    *,
    max_gate_iter: int = 32,
    chip_meta: dict[str, Any] | None = None,
) -> str:
    meta = chip_meta or {}
    # Inject chip_variables so emit_variable can look up user-set values
    set_chip_variables(_parse_chip_variables(meta.get("chip_variables")))
    wires = _wire_inputs(graph)
    var_uid_map = _build_var_uid_map(graph)
    lines: list[str] = [
        "-- @vp_generated Melon 36.x VPchip subset (C1)",
        f"-- nodes={len(graph.nodes)} edges={len(graph.edges)}",
    ]
    if meta.get("instanceId"):
        lines.append(f"-- instanceId={meta['instanceId']}")
    lines.extend(
        [
            "local G = {}",
            f"local chip_tps = {int(meta.get('tps', 20))}",
            "",
            "function OnInit()",
            "end",
            "",
            "function OnTick()",
            "  G._vp_tick = (G._vp_tick or 0) + 1",
        ]
    )

    unimplemented: set[str] = set()

    for uid in graph.topo_order:
        n = graph.nodes[uid]
        if emitter := REGISTRY.get(n.name):
            ins = _input_exprs(n, uid, wires, graph, var_uid_map)
            lines.extend(emitter(uid, ins, n))
        else:
            unimplemented.add(n.name)
            lines.append(f"  -- TODO VP node {n.name} op={n.operation_type} uid={uid}")

    lines.extend(["end", ""])
    if unimplemented:
        lines.insert(
            2,
            "-- TODO unimplemented: " + ", ".join(sorted(unimplemented)),
        )
    return "\n".join(lines)


def _input_exprs(
    n: VPNode,
    uid: str,
    wires: dict[str, dict[int, str]],
    graph: MelonGraph,
    var_uid_map: dict[str, str] | None = None,
) -> list[str]:
    wired = wires.get(uid, {})
    # If this node consumes vectors, prefer _vec suffix from entity_read nodes
    want_vec = _is_vector_node(n)
    exprs: list[str] = []
    for i, inp in enumerate(n.inputs):
        if i in wired:
            from_uid = wired[i]
            # Redirect Variable node references to their shared key
            if var_uid_map and from_uid in var_uid_map:
                shared_key = var_uid_map[from_uid]
                exprs.append(f'G["{shared_key}"]')
                continue
            from_node = graph.nodes.get(from_uid)
            if want_vec and from_node and from_node.name in ("Position", "Velocity", "Elevation"):
                exprs.append(f'G["{from_uid}_vec"]')
            else:
                exprs.append(f'G["{from_uid}"]')
        else:
            exprs.append("0")
    return exprs