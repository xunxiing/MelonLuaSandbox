#!/usr/bin/env python3
"""Inventory VPchip OperationTypes used in .melsave files (temp/*.melsave)."""
from __future__ import annotations

import json
import sys
import zipfile
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from melon_lua.vpcompile.ops import OP_NAME, op_name  # noqa: E402


def inventory(path: Path) -> Counter:
    c: Counter = Counter()
    with zipfile.ZipFile(path) as z:
        data = json.loads(z.read("Data").decode("utf-8"))
    for container in data.get("saveObjectContainers") or []:
        so = container.get("saveObjects") or {}
        if int(so.get("objectId", 0)) != 248:
            continue
        graph_raw = None
        for m in so.get("saveMetaDatas") or []:
            if m.get("key") == "chip_graph":
                graph_raw = m.get("stringValue")
                break
        if not graph_raw:
            continue
        g = json.loads(graph_raw)
        inst = so.get("instanceId")
        for n in g.get("Nodes") or []:
            op_val = n.get("OperationType", 0)
            if isinstance(op_val, str):
                if op_val.isdigit():
                    op = int(op_val)
                else:
                    from melon_lua.vpcompile.ops import NAME_TO_OP
                    op = NAME_TO_OP.get(op_val, 0)
            else:
                op = int(op_val)
            name = op_name(op, str(n.get("Id") or ""))
            c[(op, name, inst)] += 1
    return c


def main() -> int:
    if len(sys.argv) > 1:
        paths = [Path(p) for p in sys.argv[1:]]
    else:
        temp = ROOT / "temp"
        paths = list(temp.glob("*.melsave")) if temp.is_dir() else []
    if not paths:
        print("No .melsave in temp/ or argv")
        return 1
    global_ops: Counter = Counter()
    for p in paths:
        print(f"\n=== {p.name} ===")
        per = inventory(p)
        by_op: Counter = Counter()
        for (op, name, inst), cnt in per.items():
            by_op[(op, name)] += cnt
            global_ops[(op, name)] += cnt
        for (op, name), cnt in sorted(by_op.items(), key=lambda x: (-x[1], x[0][0])):
            known = "ok" if op in OP_NAME else "??"
            print(f"  {op:5} {name:28} x{cnt}  [{known}]")
    print("\n=== UNION (all saves) ===")
    for (op, name), cnt in sorted(global_ops.items(), key=lambda x: (-x[1], x[0][0])):
        print(f"  {op:5} {name:28} x{cnt}")
    print(f"\nEnum size: {len(OP_NAME)}  union distinct ops: {len(global_ops)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())