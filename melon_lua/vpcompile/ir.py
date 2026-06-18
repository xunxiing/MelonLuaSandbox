"""Intermediate representation for VPchip graphs."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional


@dataclass
class VPEdge:
    from_node: str
    to_node: str
    from_port: str = ""
    to_port: str = ""


@dataclass
class VPNode:
    uid: str
    name: str
    operation_type: int
    full_id: str
    inputs: list[dict[str, Any]] = field(default_factory=list)
    outputs: list[dict[str, Any]] = field(default_factory=list)
    save_data: Optional[str] = None
    raw: dict[str, Any] = field(default_factory=dict, repr=False)


@dataclass
class MelonGraph:
    validation_state: int
    nodes: dict[str, VPNode]
    edges: list[VPEdge]
    topo_order: list[str] = field(default_factory=list)