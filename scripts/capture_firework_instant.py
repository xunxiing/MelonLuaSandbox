#!/usr/bin/env python3
"""
Generate a clean, high-resolution snapshot of the EXACT moment the firework explodes
and the spark ring appears. No extra bodies, tight crop around the burst, high PPM.
This is the "烟花爆炸时候的瞬间的火花图" the user asked for.
"""
from pathlib import Path
from melon_lua import WorldContext, MelonScriptRunner, render_world

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "samples" / "firework_at_2_2.lua"
OUT = ROOT / "firework_explosion_instant_hires.png"

def main():
    world = WorldContext()
    runner = MelonScriptRunner(tps=20, world=world, quiet=True)
    src = SRC.read_text(encoding="utf-8")

    if not runner.compile(src, "@firework_at_2_2.lua"):
        print("COMPILE FAIL:", runner.last_error)
        return

    done = False
    burst_xy = None

    def cb(i, dt, res):
        nonlocal done, burst_xy
        if done:
            return
        st = runner.get_outputs().get("string", {}).get("status", "")
        if st == "bursting":
            n = runner.get_outputs().get("num", {})
            bx = float(n.get("x", 2.0))
            by = float(n.get("y", 2.0))
            burst_xy = (bx, by)
            # High-res, clean, centered tightly on the burst cloud
            render_world(
                world,
                OUT,
                width=960,
                height=640,
                ppm=140,
                center_x=bx,
                center_y=by + 0.3,
                target_x=bx,
                target_y=by
            )
            live = len(world.entities)
            print(f"EXPLOSION INSTANT captured at tick {i}")
            print(f"Burst center: ({bx:.2f}, {by:.2f})")
            print(f"Live entities (sparks + rocket remnants): {live}")
            print(f"Saved to: {OUT}")
            done = True

    runner.run_loop(ticks=60, tick_callback=cb)

    if burst_xy:
        print("\nThis is the pure '烟花爆炸瞬间火花图' — the ring of sparks right at detonation.")
    else:
        print("No burst detected in this run.")

if __name__ == "__main__":
    main()
