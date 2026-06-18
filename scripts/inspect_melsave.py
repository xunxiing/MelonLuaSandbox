#!/usr/bin/env python3
"""Parse a .melsave and print / write MelonLuaSandbox.melsave.v1 JSON."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from melon_lua.melsave import document_to_dict, read_melsave


def main() -> None:
    ap = argparse.ArgumentParser(description="Inspect Melon .melsave archive")
    ap.add_argument("melsave", type=Path, help="Path to .melsave file")
    ap.add_argument("-o", "--output", type=Path, help="Write JSON summary here")
    ap.add_argument("--raw", action="store_true", help="Include full saveObjects in JSON")
    ap.add_argument("--table", action="store_true", help="Print human table to stdout")
    args = ap.parse_args()

    doc = read_melsave(args.melsave)
    payload = document_to_dict(doc, include_raw=args.raw)

    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        print(args.output)

    if args.table or not args.output:
        print(f"save: {doc.save_name!r} category={doc.category!r} app={doc.app_version}")
        print(f"objects: {doc.object_count} (unique objectIds: {payload['stats']['uniqueObjectIds']})")
        print(f"counts: {payload['stats']['countsByObjectId']}")
        print("-" * 72)
        for o in doc.objects:
            print(
                f"#{o.index:3d} oid={o.object_id:4d} {o.name:20s} "
                f"pos=({o.x:8.4f},{o.y:8.4f}) rotZ={o.rotation_z:7.2f} "
                f"scale=({o.scale_x:.2f},{o.scale_y:.2f}) parent={o.parent_id}"
            )


if __name__ == "__main__":
    main()