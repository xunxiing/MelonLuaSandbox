"""Parse chip_graph JSON from VPchip saveMetaDatas."""
from __future__ import annotations

import re
from typing import Any

from .ir import MelonGraph, VPEdge, VPNode
from .ops import op_name

_UUID_RE = re.compile(
    r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}",
    re.I,
)


def _short_uid(full_id: str) -> str:
    m = _UUID_RE.search(full_id or "")
    if m:
        return m.group(0)[:8]
    return re.sub(r"[^a-zA-Z0-9_]", "_", (full_id or "n")[:32])


def parse_chip_graph(graph: dict[str, Any]) -> MelonGraph:
    nodes: dict[str, VPNode] = {}
    edges: list[VPEdge] = []
    full_to_uid: dict[str, str] = {}

    for raw_n in graph.get("Nodes") or []:
        full_id = str(raw_n.get("Id") or "")
        op = int(raw_n.get("OperationType", 0))
        name = op_name(op, full_id)
        uid = f"{name}_{_short_uid(full_id)}"
        full_to_uid[full_id] = uid
        nodes[uid] = VPNode(
            uid=uid,
            name=name,
            operation_type=op,
            full_id=full_id,
            inputs=list(raw_n.get("Inputs") or []),
            outputs=list(raw_n.get("Outputs") or []),
            save_data=raw_n.get("SaveData"),
            raw=raw_n,
        )

    for raw_n in graph.get("Nodes") or []:
        to_full = str(raw_n.get("Id") or "")
        to_uid = full_to_uid.get(to_full)
        if not to_uid:
            continue
        to_name = nodes[to_uid].name
        for inp in raw_n.get("Inputs") or []:
            co = inp.get("connectedOutputIdModel")
            if not co:
                continue
            from_full = str(co.get("NodeId") or "")
            from_uid = full_to_uid.get(from_full)
            if from_uid:
                edges.append(
                    VPEdge(
                        from_node=from_uid,
                        to_node=to_uid,
                        from_port=str(co.get("Id") or "")[:48],
                        to_port=str(inp.get("Id") or "")[:48],
                    )
                )

    topo = _topo_sort(nodes, edges)
    return MelonGraph(
        validation_state=int(graph.get("ValidationState", 0)),
        nodes=nodes,
        edges=edges,
        topo_order=topo,
    )


def _topo_sort(nodes: dict[str, VPNode], edges: list[VPEdge]) -> list[str]:
    indeg = {uid: 0 for uid in nodes}
    adj: dict[str, list[str]] = {uid: [] for uid in nodes}
    for e in edges:
        if e.from_node in indeg and e.to_node in indeg:
            adj[e.from_node].append(e.to_node)
            indeg[e.to_node] += 1
    q = [u for u, d in indeg.items() if d == 0]
    order: list[str] = []
    while q:
        u = q.pop(0)
        order.append(u)
        for v in adj.get(u, []):
            indeg[v] -= 1
            if indeg[v] == 0:
                q.append(v)
    for u in nodes:
        if u not in order:
            order.append(u)
    return order


from .save_data import constant_value  # noqa: F401 — re-export