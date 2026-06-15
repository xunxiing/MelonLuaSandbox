#!/usr/bin/env python3
"""Full flow: spawn plastic block (objectId 202) at (0, 1) and save preview PNG."""
from pathlib import Path

from melon_lua import MelonScriptRunner, WorldContext
from melon_lua.preview import render_world

ROOT = Path(__file__).resolve().parents[1]
LUA = ROOT / "samples" / "plastic_at_0_1.lua"
OUT = ROOT / "plastic_preview.png"


def main() -> int:
    source = LUA.read_text(encoding="utf-8")
    world = WorldContext()
    runner = MelonScriptRunner(tps=20, world=world, quiet=True)
    if not runner.compile(source, chunk_name="@plastic_at_0_1.lua"):
        print("compile failed:", runner.last_error)
        return 1
    runner.call_on_init()
    runner.run_tick()
    outs = runner.get_outputs()
    print("outputs:", outs)
    for e in world.entities.values():
        if e.alive:
            print(
                f"entity id={e.entity_id} oid={e.object_id} name={e.name} "
                f"pos=({e.position_x},{e.position_y}) size={e.real_size()} "
                f"sprite={e.sprite_path}"
            )
    render_world(world, OUT, center_x=0.0, center_y=1.0, ppm=128)
    print("screenshot:", OUT.resolve())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())