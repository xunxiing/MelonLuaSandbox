#!/usr/bin/env python3
"""Render the full tank including base layers and custom melmods."""
from __future__ import annotations
import json
import zipfile
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from melon_lua import WorldContext, render_world
from melon_lua.melsave import read_melsave, spawn_document_into_world
from melon_lua.melmod import load_melmod_pack

def main():
    melsave_path = Path("temp/ztz99b 5.melsave")
    melmod_dir = Path("temp/99bketi")
    
    # 1. Load melmods
    load_melmod_pack(melmod_dir)
    
    # 2. Get overrides mapping
    with zipfile.ZipFile(melsave_path) as z:
        data = json.loads(z.read("Data").decode("utf-8"))
    overrides: dict[int, str] = {}
    for c in data.get("saveObjectContainers") or []:
        for obj in [c.get("saveObjects")] + (c.get("saveObjectChildren") or []):
            if not obj:
                continue
            iid = obj.get("instanceId")
            mo = obj.get("modedObjectId")
            if iid is not None and mo:
                overrides[int(iid)] = str(mo)
                
    # 3. Read & Spawn
    doc = read_melsave(melsave_path)
    world = WorldContext()
    spawn_document_into_world(doc, world, melmod_overrides=overrides)
    
    # 4. Render main tank focus area (x: -5 to 5, y: -4 to 4 to capture the chassis + body)
    # The custom range is (-3.1 to 2.8, -2.0 to 1.9), so this captures the entire vehicle body
    output_path = "temp/ztz99b5_full_with_textures.png"
    render_world(
        world,
        output_path,
        focus_rect=(-5.0, -4.0, 5.0, 4.0),
        content_padding=0.5,
        show_labels=False,
        show_grid=False,
        scale=12.0, # high quality 12x
        min_ppm=10.0,
    )
    print(f"Rendered: {output_path}")

if __name__ == "__main__":
    main()