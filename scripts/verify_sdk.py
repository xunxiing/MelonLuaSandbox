#!/usr/bin/env python3
"""SDK alignment smoke test (catalog + spawn by objectId)."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from melon_lua import (  # noqa: E402
    MelonScriptRunner,
    WorldContext,
    catalog_stats,
    get_profile_by_object_id,
    object_id_for_name,
    resolve_spawn_name,
)


def main() -> int:
    st = catalog_stats()
    assert st.get("with_size", 0) >= 400, st

    assert object_id_for_name("ResizablePlastic") == 202
    assert resolve_spawn_name("202") == "ResizablePlastic"

    p = get_profile_by_object_id(202)
    assert p and p.get("name") == "ResizablePlastic"
    assert p.get("aabbWidth") or (p.get("aabb") or {}).get("width")

    w = WorldContext()
    e = w.spawn_entity("202", 0, 5, dynamic=True)
    assert e.name == "ResizablePlastic"
    assert e.object_id == 202
    assert e.base_size_x > 0 and e.base_size_y > 0

    src = """
function OnInit()
    outputs.num.req = spawn.create("202", 0, 3)
end
function OnSpawned(req, ents)
    outputs.num.spawned = ents[1]:getId()
    outputs.string.pname = ents[1]:getName()
end
"""
    r = MelonScriptRunner(tps=20, world=WorldContext(), quiet=True)
    assert r.compile(src)
    r.call_on_init()
    outs = r.get_outputs()
    assert outs.get("num", {}).get("spawned"), outs
    assert outs.get("string", {}).get("pname") == "ResizablePlastic"

    print("SDK OK:", st)
    print("  plastic objectId=202 size", e.base_size_x, e.base_size_y)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())