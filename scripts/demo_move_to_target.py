#!/usr/bin/env python3
"""
Full demo for "move to target using velocity" Lua chip.

- Robust Lua chip (persistent mover_id via OnSpawned, brake ramp, logs every 5 ticks).
- Python runner drives it with tunable speed/target/start.
- Captures PNG sequence (with red TARGET marker).
- Prints rich telemetry for speed tuning (from Lua prints + outputs).
- If ffmpeg is in PATH, auto-encodes to MP4 (you have it, so it will work).
- Final still frame + log file.

Usage examples (for tuning):
  python scripts/demo_move_to_target.py --speed 1.0 --target-x 5 --ticks 400
  python scripts/demo_move_to_target.py --speed 3.5 --target-x 4 --target-y 2.5 --frame-every 2

Outputs in MelonLuaSandbox/:
  frames/####.png          (sequence)
  move_to_target_demo.mp4  (if ffmpeg)
  final_frame.png
  move_to_target.log       (key prints for analysis)
"""
from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from pathlib import Path

from melon_lua import MelonScriptRunner, WorldContext, render_world

ROOT = Path(__file__).resolve().parents[1]
LUA = ROOT / "samples" / "move_to_target.lua"
FRAMES = ROOT / "frames"
VIDEO = ROOT / "move_to_target_demo.mp4"
FINAL = ROOT / "final_frame.png"
LOG = ROOT / "move_to_target.log"


def main() -> int:
    p = argparse.ArgumentParser(description="Velocity-based move-to-target Lua chip demo + video")
    p.add_argument("--ticks", type=int, default=240, help="max ticks to simulate")
    p.add_argument("--tps", type=int, default=20, help="simulation ticks per second (affects dt)")
    p.add_argument("--speed", type=float, default=2.0, help="max speed m/s (tune this)")
    p.add_argument("--target-x", type=float, default=4.0)
    p.add_argument("--target-y", type=float, default=2.5)
    p.add_argument("--start-x", type=float, default=-3.0)
    p.add_argument("--start-y", type=float, default=2.5)
    p.add_argument("--ppm", type=float, default=80.0, help="pixels per meter (zoom)")
    p.add_argument("--width", type=int, default=800)
    p.add_argument("--height", type=int, default=480)
    p.add_argument("--frame-every", type=int, default=2, help="capture every N ticks (1=every tick)")
    p.add_argument("--no-video", action="store_true", help="skip ffmpeg even if present")
    args = p.parse_args()

    FRAMES.mkdir(parents=True, exist_ok=True)
    for f in FRAMES.glob("*.png"):
        f.unlink(missing_ok=True)

    world = WorldContext()

    # Visual reference floor (static, long box) — not the mover
    world.spawn_entity("Box", 0.0, 1.0, dynamic=False, scale_x=14.0, scale_y=0.25)

    inputs = {
        "num": {
            "tx": args.target_x,
            "ty": args.target_y,
            "speed": args.speed,
        }
    }

    runner = MelonScriptRunner(tps=args.tps, world=world, quiet=True)

    source = LUA.read_text(encoding="utf-8")
    if not runner.compile(source, chunk_name="@move_to_target.lua"):
        print("Compile error:", runner.last_error)
        return 1

    # Initial frame (pre-movement)
    render_world(
        world,
        FRAMES / "0000.png",
        width=args.width,
        height=args.height,
        ppm=args.ppm,
        center_x=(args.start_x + args.target_x) * 0.5,
        center_y=args.target_y,
        target_x=args.target_x,
        target_y=args.target_y,
    )

    frame_count = 1
    log_lines: list[str] = []

    def on_tick(i: int, dt: float, result: dict) -> None:
        nonlocal frame_count
        outs = runner.get_outputs()
        num = outs.get("num", {})
        st = outs.get("string", {}).get("status", "")
        dist = num.get("dist", 0.0)
        cur = num.get("cur_speed", num.get("max_speed", 0.0))

        # Telemetry for tuning (printed + logged)
        if i % 5 == 0 or st == "arrived":
            line = (f"tick={i:3d} pos=({num.get('x',0):6.2f},{num.get('y',0):6.2f}) "
                    f"dist={dist:6.3f} status={st:8s} max={args.speed:.2f} cur={cur:.2f}")
            print(line)
            log_lines.append(line)

        # Capture frames (with target marker)
        if (i % max(1, args.frame_every)) == 0:
            render_world(
                world,
                FRAMES / f"{frame_count:04d}.png",
                width=args.width,
                height=args.height,
                ppm=args.ppm,
                center_x=(args.start_x + args.target_x) * 0.5,
                center_y=args.target_y,
                target_x=args.target_x,
                target_y=args.target_y,
            )
            frame_count += 1

    # This is the correct way: run_loop does world.tick(dt) + run_tick internally → physics moves
    runner.run_loop(ticks=args.ticks, tick_callback=on_tick, inputs_provider=lambda i: inputs)

    # Final still
    render_world(
        world,
        FINAL,
        width=960,
        height=540,
        ppm=96,
        center_x=(args.start_x + args.target_x) * 0.5,
        center_y=args.target_y,
        target_x=args.target_x,
        target_y=args.target_y,
    )
    print(f"Final frame: {FINAL}")

    # Write tuning log
    LOG.write_text("\n".join(log_lines) + "\n", encoding="utf-8")
    print(f"Log: {LOG}")

    # Video (you said you have ffmpeg)
    if not args.no_video:
        ff = shutil.which("ffmpeg")
        if ff and frame_count > 2:
            print("Encoding video...")
            cmd = [
                "ffmpeg", "-y",
                "-framerate", "20",
                "-i", str(FRAMES / "%04d.png"),
                "-vf", "pad=ceil(iw/2)*2:ceil(ih/2)*2",
                "-c:v", "libx264",
                "-pix_fmt", "yuv420p",
                "-crf", "16",
                "-preset", "slow",
                str(VIDEO),
            ]
            try:
                subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                print(f"Video ready: {VIDEO}")
            except subprocess.CalledProcessError as ex:
                print("ffmpeg error (non-fatal):", ex)
        elif not ff:
            print("ffmpeg not found in PATH this time — you can encode manually:")
            print(f"  ffmpeg -framerate 20 -i frames/%04d.png -c:v libx264 -pix_fmt yuv420p -crf 16 {VIDEO.name}")
        else:
            print("Too few frames for video.")

    print(f"Frames captured: {frame_count-1}")
    print("Done. Use --speed / --target-x etc to tune and re-run for new video/logs.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
