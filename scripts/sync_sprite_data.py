#!/usr/bin/env python3
"""Copy lua-triage/object_sprites_by_id into melon_lua/data for packaging."""
import json
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT.parent / "lua-triage" / "object_sprites_by_id"
DST = ROOT / "melon_lua" / "data" / "sprites_pack"


def main() -> int:
    if not SRC.is_dir():
        print("missing", SRC)
        return 1
    if DST.exists():
        shutil.rmtree(DST)
    shutil.copytree(SRC, DST)
    idx = DST / "sprites_by_object_id.json"
    n = 0
    if idx.is_file():
        data = json.loads(idx.read_text(encoding="utf-8"))
        for row in data.get("sprites", []):
            sp = row.get("spritePath")
            if sp and sp.startswith("images/"):
                row["spritePath"] = f"sprites_pack/{sp}"
        n = len(data.get("sprites", []))
        slim = ROOT / "melon_lua" / "data" / "sprites_by_object_id.json"
        slim.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    print("synced", DST, "entries", n)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())