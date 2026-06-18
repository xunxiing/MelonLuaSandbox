#!/usr/bin/env python3
"""Compile VPchip graph from .melsave to generated.lua."""
from __future__ import annotations

import argparse
import json
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from melon_lua.vpcompile import compile_vp_graph  # noqa: E402


def load_graph(melsave: Path, instance_id: int) -> tuple[dict, dict]:
    with zipfile.ZipFile(melsave) as z:
        data = json.loads(z.read("Data").decode("utf-8"))
    for c in data.get("saveObjectContainers") or []:
        so = c.get("saveObjects") or {}
        if int(so.get("instanceId", 0)) != instance_id:
            continue
        if int(so.get("objectId", 0)) != 248:
            raise ValueError(f"instance {instance_id} is not VPchip (248)")
        tps = 20
        for m in so.get("saveMetaDatas") or []:
            if m.get("key") == "chip_tps":
                tps = int(m.get("intValue") or 20)
            if m.get("key") == "chip_graph":
                g = json.loads(m["stringValue"])
                return g, {"instanceId": instance_id, "tps": tps}
    raise ValueError(f"instance {instance_id} not found in {melsave}")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("melsave", type=Path)
    ap.add_argument("--instance", type=int, required=True)
    ap.add_argument("-o", "--output", type=Path, required=True)
    args = ap.parse_args()
    graph, meta = load_graph(args.melsave, args.instance)
    lua = compile_vp_graph(graph, tps=meta["tps"], chip_meta=meta)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(lua, encoding="utf-8")
    print(args.output, "nodes", len(graph.get("Nodes") or []))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())