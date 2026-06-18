"""Emit Lua from MelonGraph (C1 math subset)."""
from __future__ import annotations

from typing import Any

from .ir import MelonGraph, VPNode
from .nodes import REGISTRY



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


def generate_lua(
    graph: MelonGraph,
    *,
    max_gate_iter: int = 32,
    chip_meta: dict[str, Any] | None = None,
) -> str:
    meta = chip_meta or {}
    wires = _wire_inputs(graph)
    lines: list[str] = [
        "-- @vp_generated Melon 36.x VPchip subset (C1)",
        f"-- nodes={len(graph.nodes)} edges={len(graph.edges)} iter={max_gate_iter}",
    ]
    if meta.get("instanceId"):
        lines.append(f"-- instanceId={meta['instanceId']}")
    lines.extend(
        [
            "local G = {}",
            f"local MAX_GATE_ITER = {int(max_gate_iter)}",
            f"local chip_tps = {int(meta.get('tps', 20))}",
            "",
            "function OnInit()",
            "end",
            "",
            "function OnTick()",
            "  G._vp_tick = (G._vp_tick or 0) + 1",
            "  for _iter = 1, MAX_GATE_ITER do",
        ]
    )

    unimplemented: set[str] = set()

    for uid in graph.topo_order:
        n = graph.nodes[uid]
        gkey = f'["{uid}"]'
        if emitter := REGISTRY.get(n.name):
            ins = _input_exprs(n, uid, wires, graph)
            lines.extend(emitter(uid, ins, n))
        else:
            unimplemented.add(n.name)
            lines.append(f"    -- TODO VP node {n.name} op={n.operation_type} uid={uid}")

    lines.extend(["  end", "end", ""])
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
) -> list[str]:
    wired = wires.get(uid, {})
    exprs: list[str] = []
    for i, inp in enumerate(n.inputs):
        if i in wired:
            exprs.append(f'G["{wired[i]}"]')
        else:
            exprs.append("(inputs.num and inputs.num.a) or 0" if i == 1 else "0")
    return exprs