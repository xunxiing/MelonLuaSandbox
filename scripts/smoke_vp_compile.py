#!/usr/bin/env python3
"""Compile VP fixture graph and run in MelonScriptRunner."""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "tests" / "fixtures" / "vp_graph_minimal.json"


def main() -> int:
    if not FIXTURE.is_file():
        print(f"missing fixture: {FIXTURE}", file=sys.stderr)
        return 1

    graph = json.loads(FIXTURE.read_text(encoding="utf-8-sig"))
    from melon_lua.vpcompile import compile_vp_graph
    from melon_lua.runner import MelonScriptRunner

    lua_src = compile_vp_graph(graph, tps=20)
    runner = MelonScriptRunner(tps=20, quiet=True)
    runner.set_inputs({"num": {}})
    if not runner.compile(lua_src, chunk_name="@vp_smoke.lua"):
        print(f"compile failed: {runner.last_error}", file=sys.stderr)
        return 1
    runner.run_loop(ticks=5)
    if runner.last_error:
        print(f"run failed: {runner.last_error}", file=sys.stderr)
        return 1
    outs = runner.get_outputs()
    total = outs.get("num", {}).get("sum")
    print(f"ok nodes={len(graph.get('Nodes') or [])} outputs.num.sum={total}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())