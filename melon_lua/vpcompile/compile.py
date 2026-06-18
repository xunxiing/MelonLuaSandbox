"""Public compile entry."""
from __future__ import annotations

from typing import Any

from .codegen import generate_lua
from .graph import parse_chip_graph


def compile_vp_graph(
    graph: dict[str, Any],
    *,
    tps: int = 20,
    max_gate_iter: int = 32,
    chip_meta: dict[str, Any] | None = None,
) -> str:
    ir = parse_chip_graph(graph)
    meta = dict(chip_meta or {})
    meta.setdefault("tps", tps)
    return generate_lua(ir, max_gate_iter=max_gate_iter, chip_meta=meta)