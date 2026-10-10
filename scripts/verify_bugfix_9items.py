"""Self-test for the 9 user-reported bugs (run: python scripts/verify_bugfix_9items.py).

1  catalog_search missing (ImportError)
2  add_lua_chip missing 'color' gate type
3  debug inputs silently overridden by scene wires
4  debug_run does not reset world between runs (spawn pollution)
5  spawn.create bad alias fails silently (no reason)
6  frames/tick phase contract (documented + frames[i].tick == i)
7  Radar default detection box 1x1
8  UI same-name elements silently cross-wire (no warning)
9  spawn.create dual naming (objectId auto-fallback + device warning)
"""
from __future__ import annotations

import sys
import warnings
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from melon_lua import MelsaveSession, UIControllerBuilder, catalog_search
from melon_lua.mechanics.radar import parse_radar_config, RADAR_DEFAULT_SIZE

PASS, FAIL = [], []


def check(num: int, name: str, ok: bool, detail: str = ""):
    (PASS if ok else FAIL).append(num)
    print(f"  [{'PASS' if ok else 'FAIL'}] bug {num}: {name}"
          + (f" — {detail}" if detail else ""))


print("=== verify_bugfix_9items ===")

# ---- bug 1: catalog_search exists and finds things -------------------------
try:
    r = catalog_search("crate")
    check(1, "catalog_search importable + 'crate' found", "alias: crate" in r and "oid=23" in r, r.splitlines()[0])
except ImportError as e:
    check(1, "catalog_search importable", False, str(e))

# ---- bug 7: radar default size ---------------------------------------------
cfg = parse_radar_config({})  # no gates, no mechanicData
check(7, "radar default 10x10", cfg["width"] == RADAR_DEFAULT_SIZE and cfg["height"] == RADAR_DEFAULT_SIZE,
      f"{cfg['width']}x{cfg['height']}")

# ---- bug 2/3/4/5/6/9: session-level checks ---------------------------------
with MelsaveSession() as s:
    # bug 2: color gate on a chip (gate Type = Vector-family, LuaValue.Type = 5 color)
    src = """
local last_tint = nil
function OnTick()
  last_tint = outputs.color.tint
  outputs.num.value = inputs.num.enable
end
"""
    chip_idx = s.add_lua_chip(
        src, inputs=[{"name": "enable", "type": "number", "value": 0}],
        outputs=[{"name": "tint", "type": "color"},
                 {"name": "value", "type": "number"}],
    )
    so = s.get_container(chip_idx)
    outs_meta = [m for m in so.get("saveMetaDatas", []) if m.get("key") == "lua_chip_outputs"]
    import json as _json
    tint_gate = None
    if outs_meta:
        arr = _json.loads(outs_meta[0].get("stringValue") or "[]")
        tint_gate = next((g for g in arr if g.get("Name") == "tint"), None)
    check(2, "chip color gate written (LuaValue.Type=5 color)",
          tint_gate is not None
          and int((tint_gate.get("LuaValue") or {}).get("Type", 0)) == 5,
          f"tint gate LuaValue.Type={(tint_gate or {}).get('LuaValue', {}).get('Type')}")

    # bug 3: wire btn->enable writes 0; flat injection {"enable":1} must win
    btn_idx = s.add_item(202, x=5, y=5)  # any item as wire source
    s.load()
    s._world.gate_wires.connect(btn_idx, "out", chip_idx, "enable")
    s._world.gate_output_values[btn_idx] = {"out": 0.0}
    res = s.debug_run(src, ticks=3, inputs={"enable": 1}, container_idx=chip_idx)
    saw_one = any((fr["outputs"].get("num", {}) or {}).get("value") == 1.0 for fr in res["frames"])
    check(3, "flat injected input beats scene wire", saw_one and not res.get("error"),
          f"outputs={[(fr['outputs'].get('num') or {}).get('value') for fr in res['frames']]}")

    # bug 4: reset_world wipes spawned entities between debug runs.
    # Spawn in OnTick (OnInit only runs once per runner lifetime) so each
    # run re-spawns: no-reset runs accumulate, reset runs stay stable.
    spawn_src = """
spawned = false
function OnTick()
  if not spawned then
    spawn.create("plastic_plate", 1, 5)
    spawned = true
  end
end
"""
    r1 = s.debug_run(spawn_src, ticks=2, container_idx=chip_idx)
    c1 = r1["frames"][-1]["entity_count"]
    r2 = s.debug_run(spawn_src, ticks=2, container_idx=chip_idx)  # no reset
    c2 = r2["frames"][-1]["entity_count"]
    r3 = s.debug_run(spawn_src, ticks=2, container_idx=chip_idx, reset_world=True)
    c3 = r3["frames"][-1]["entity_count"]
    r4 = s.debug_run(spawn_src, ticks=2, container_idx=chip_idx, reset_world=True)
    c4 = r4["frames"][-1]["entity_count"]
    plates2 = sum(1 for e in s._world.entities.values()
                  if e.alive and round(e.position_x) == 1 and round(e.position_y) == 5)
    check(4, "reset_world=True stops spawn accumulation",
          c2 > c1 and c4 == c3
          and not (r3.get("error") or r4.get("error")),
          f"counts {c1}->{c2} (no reset grows) | {c3}->{c4} (reset stable)")
    check(4, "reset leaves exactly one chip-spawned plate", plates2 == 1,
          f"plates at (1,5) after 4th run: {plates2}")

    # bug 5: bad alias reports a reason via OnSpawned(reqId, nil, reason)
    bad_src = """
reason_seen = nil
function OnTick()
  spawn.create("definitely_not_an_alias_xyz", 0, 0)
end
function OnSpawned(reqId, entities, reason)
  if reason then reason_seen = tostring(reason) end
  variables.Set("reason", reason and 1 or 0)
end
"""
    r3 = s.debug_run(bad_src, ticks=2, container_idx=chip_idx, reset_world=True)
    reason_flag = (r3["frames"][-1]["variables"] or {}).get("reason")
    check(5, "bad alias OnSpawned carries reason", reason_flag == 1.0 and not r3.get("error"),
          f"variables={r3['frames'][-1]['variables']}")

    # bug 6: frames/tick contract
    r4 = s.debug_run(src, ticks=3, container_idx=chip_idx, reset_world=True,
                     inputs={"num": {"enable": 0}})
    ticks_ok = [fr["tick"] for fr in r4["frames"]] == [0, 1, 2]
    check(6, "frames[i].tick == i (0-based)", ticks_ok, str([fr["tick"] for fr in r4["frames"]]))

    # bug 9: objectId / catalog-name auto-fallback + device-safety warning
    oid_src = """
function OnTick()
  spawn.create("202", 3, 3)
  spawn.create("ResizablePlastic", 4, 4)
end
"""
    r5 = s.debug_run(oid_src, ticks=2, container_idx=chip_idx, reset_world=True)
    warned_device = any("REAL DEVICE" in str(m) for _, m in (r5.get("logs") or []))
    ents = [e for e in s._world.entities.values() if e.alive and e.object_id == 202]
    check(9, "objectId/catalog-name spawn auto-fallback works",
          len(ents) >= 2 and not r5.get("error"), f"oid-202 entities={len(ents)}")
    check(9, "device-safety warning surfaces in debug_run logs",
          warned_device, f"logs={ [m for _, m in (r5.get('logs') or [])][-2:] }")

# ---- bug 8: UI same-name cross-wire warning --------------------------------
with MelsaveSession() as s:
    chip_idx = s.add_lua_chip(
        "function OnTick() end",
        inputs=[{"name": "v", "type": "number", "value": 0}],
    )
    b = UIControllerBuilder()
    s1 = b.add_slider("Value", x=-100, y=100)
    s2 = b.add_slider("Value", x=100, y=100)
    ui_idx = s.add_ui_controller(b)
    # bare "Value" as OUTPUT side (sliders emit "Value") — ambiguous
    with warnings.catch_warnings(record=True) as wrec:
        warnings.simplefilter("always")
        s.connect(ui_idx, "Value", chip_idx, "v")
    warned = any("ambiguous" in str(w.message) for w in wrec)
    check(8, "same-name UI elements trigger ambiguity warning", warned,
          f"warnings={[str(w.message)[:60] for w in wrec]}")
    # pinned wire via ElementHandle group must NOT warn
    with warnings.catch_warnings(record=True) as wrec2:
        warnings.simplefilter("always")
        s.connect(ui_idx, "Value", chip_idx, "v", output_group=s1.group_id)
    warned2 = any("ambiguous" in str(w.message) for w in wrec2)
    check(8, "group-pinned wire does not warn", not warned2)
    # single slider (unique name) must NOT warn either
    b2 = UIControllerBuilder()
    b2.add_slider("Speed", x=0, y=100)
    ui2_idx = s.add_ui_controller(b2)
    with warnings.catch_warnings(record=True) as wrec3:
        warnings.simplefilter("always")
        s.connect(ui2_idx, "Speed", chip_idx, "v")
    check(8, "unique-name UI element does not warn",
          not any("ambiguous" in str(w.message) for w in wrec3))

print(f"\n=== {len(PASS)} passed, {len(FAIL)} failed (failed: {sorted(set(FAIL))}) ===")
sys.exit(1 if FAIL else 0)
