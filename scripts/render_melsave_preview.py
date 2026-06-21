#!/usr/bin/env python3
"""Load .melsave into WorldContext, optional melmod dir, render PNG."""
from __future__ import annotations

import argparse
import json
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from melon_lua import WorldContext, render_world
from melon_lua.melsave import read_melsave, spawn_document_into_world
from melon_lua.melmod import load_melmod_pack


def melmod_overrides_from_save(path: Path) -> dict[int, str]:
    with zipfile.ZipFile(path) as z:
        data = json.loads(z.read("Data").decode("utf-8"))
    out: dict[int, str] = {}
    for c in data.get("saveObjectContainers") or []:
        for obj in [c.get("saveObjects")] + (c.get("saveObjectChildren") or []):
            if not obj:
                continue
            iid = obj.get("instanceId")
            mo = obj.get("modedObjectId")
            if iid is not None and mo:
                out[int(iid)] = str(mo)
    return out


def tank_focus_bbox(doc, *, exclude_human: bool = True) -> tuple[float, float, float, float]:
    xs, ys = [], []
    for o in doc.objects:
        if exclude_human and o.object_id == 62:
            continue
        if exclude_human and (o.y > 25 or o.y < -25 or o.x > 18):
            continue
        xs.append(o.x)
        ys.append(o.y)
    if not xs:
        xs = [o.x for o in doc.objects]
        ys = [o.y for o in doc.objects]
    pad = 0.5
    return min(xs) - pad, min(ys) - pad, max(xs) + pad, max(ys) + pad


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("melsave", type=Path)
    ap.add_argument("-o", "--output", type=Path, required=True)
    ap.add_argument("--melmod-dir", type=Path, default=None)
    ap.add_argument("--scale", type=float, default=8.0)
    ap.add_argument("--no-melmod", action="store_true")
    args = ap.parse_args()

    if args.melmod_dir and args.melmod_dir.is_dir() and not args.no_melmod:
        load_melmod_pack(args.melmod_dir)

    doc = read_melsave(args.melsave)
    overrides = melmod_overrides_from_save(args.melsave) if not args.no_melmod else {}
    world = WorldContext()
    spawn_document_into_world(doc, world, melmod_overrides=overrides or None)
    x0, y0, x1, y1 = tank_focus_bbox(doc)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    render_world(
        world,
        str(args.output),
        focus_rect=(x0, y0, x1, y1),
        content_padding=1.0,
        show_labels=False,
        show_grid=False,
        scale=args.scale,
        min_ppm=12.0,
    )
    print(args.output)
    print(f"objects={doc.object_count} melmod_mapped={len(overrides)} focus=({x0:.2f},{y0:.2f})-({x1:.2f},{y1:.2f})")


if __name__ == "__main__":
    main()