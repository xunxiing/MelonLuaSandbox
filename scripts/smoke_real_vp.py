#!/usr/bin/env python3
"""Smoke test to compile all VPchips in jixiebi.melsave and run them in MelonScriptRunner."""
import json
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from melon_lua.vpcompile import compile_vp_graph
from melon_lua.runner import MelonScriptRunner

def main():
    melsave_path = ROOT / "temp" / "jixiebi.melsave"
    if not melsave_path.is_file():
        print(f"jixiebi.melsave not found at {melsave_path}")
        return 1

    with zipfile.ZipFile(melsave_path) as z:
        data = json.loads(z.read("Data").decode("utf-8"))

    vpchips = []
    for c in data.get("saveObjectContainers") or []:
        so = c.get("saveObjects") or {}
        if int(so.get("objectId", 0)) == 248:
            vpchips.append(so)

    print(f"Found {len(vpchips)} VPchips in jixiebi.melsave")
    for so in vpchips:
        inst_id = so.get("instanceId")
        tps = 20
        graph = None
        for m in so.get("saveMetaDatas") or []:
            if m.get("key") == "chip_tps":
                tps = int(m.get("intValue") or 20)
            if m.get("key") == "chip_graph":
                graph = json.loads(m.get("stringValue"))
        
        if not graph:
            print(f"No chip_graph found for instance {inst_id}")
            continue

        print(f"Compiling instance {inst_id} with {len(graph.get('Nodes', []))} nodes at {tps} TPS...")
        try:
            lua_src = compile_vp_graph(graph, tps=tps, chip_meta={"instanceId": inst_id, "tps": tps})
        except Exception as e:
            print(f"Compilation error for instance {inst_id}: {e}")
            return 1

        runner = MelonScriptRunner(tps=tps, quiet=True)
        # Setup basic mock outputs / inputs
        runner.set_inputs({"num": {"a": 1, "b": 2, "x": 3, "y": 4}})
        
        if not runner.compile(lua_src, chunk_name=f"@vp_{inst_id}.lua"):
            print(f"Lua compilation failed for instance {inst_id}: {runner.last_error}")
            return 1
        
        print("Running 10 ticks...")
        runner.run_loop(ticks=10)
        if runner.last_error:
            print(f"Execution failed for instance {inst_id}: {runner.last_error}")
            return 1
        print(f"Instance {inst_id} ran successfully! Outputs: {runner.get_outputs()}")

    print("All VP chips from jixiebi.melsave compiled and executed successfully!")
    return 0

if __name__ == "__main__":
    sys.exit(main())
