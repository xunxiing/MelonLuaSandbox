"""Melmod loader for Melon Playground custom texture mods (.melmod).

.melmod is a ZIP with:
- MetaData: JSON { uniqueId, category, type, Icon, ... }
- Data: JSON { parts: [ { mainTexture: {AssetId}, pixelsPerUnit, collidersJson, ... } ] }
- Part_<guid>: raw PNG bytes for the main texture
- Icon: PNG

This module extracts and provides:
- list of parts with png path, ppu, pixel size
- ability to resolve by uniqueId or assetId
- physical size = pixel_size / ppu (in meters, matching game sprite import)
"""
from __future__ import annotations

import json
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass
class MelmodPart:
    unique_id: str
    asset_id: str
    png_path: str
    ppu: float
    pixel_w: int
    pixel_h: int
    # physical size in meters (width, height)
    phys_w: float
    phys_h: float


@dataclass
class MelmodEntry:
    file: str
    unique_id: str
    category: str | None
    type: str | None
    icon_png: str | None
    parts: list[MelmodPart]


def _extract_png(zf: zipfile.ZipFile, entry: str, out_path: Path) -> None:
    raw = zf.read(entry)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    tmp = out_path.with_suffix(".tmp.bin")
    tmp.write_bytes(raw)
    # Pillow will validate on open; we just move after
    tmp.replace(out_path)


def load_melmod_pack(pack_dir: str | Path, extract_dir: str | Path | None = None) -> list[MelmodEntry]:
    """Load all .melmod from a directory.

    If extract_dir is given, PNGs are extracted there (idempotent).
    Returns list of MelmodEntry with resolved PNG paths and computed physical sizes.
    """
    pack_dir = Path(pack_dir)
    if extract_dir is None:
        extract_dir = pack_dir.parent / (pack_dir.name + "_extracted")
    extract_dir = Path(extract_dir)
    extract_dir.mkdir(parents=True, exist_ok=True)

    manifest_path = extract_dir / "manifest.json"
    entries: list[MelmodEntry] = []

    for mf in sorted(pack_dir.glob("*.melmod")):
        with zipfile.ZipFile(mf) as z:
            meta = json.loads(z.read("MetaData").decode("utf-8", errors="replace"))
            data = json.loads(z.read("Data").decode("utf-8", errors="replace"))
            uid = meta.get("uniqueId") or mf.stem
            cat = meta.get("category")
            typ = meta.get("type")

            icon_png = None
            if "Icon" in z.namelist():
                ip = extract_dir / f"{uid}_Icon.png"
                if not ip.exists():
                    _extract_png(z, "Icon", ip)
                icon_png = str(ip)

            parts: list[MelmodPart] = []
            for part in data.get("parts", []):
                asset = part.get("mainTexture", {}).get("AssetId")
                ppu = float(part.get("pixelsPerUnit", 256.0))
                if not asset or asset not in z.namelist():
                    continue
                pngp = extract_dir / f"{uid}_{asset}.png"
                if not pngp.exists():
                    _extract_png(z, asset, pngp)
                from PIL import Image  # lazy
                with Image.open(pngp) as im:
                    pw, ph = im.size
                phys_w = pw / ppu if ppu > 0 else 0.0
                phys_h = ph / ppu if ppu > 0 else 0.0
                parts.append(MelmodPart(
                    unique_id=uid,
                    asset_id=asset,
                    png_path=str(pngp),
                    ppu=ppu,
                    pixel_w=pw,
                    pixel_h=ph,
                    phys_w=phys_w,
                    phys_h=phys_h,
                ))
            entries.append(MelmodEntry(
                file=mf.name,
                unique_id=uid,
                category=cat,
                type=typ,
                icon_png=icon_png,
                parts=parts,
            ))

    # Write/refresh manifest
    man = []
    for e in entries:
        man.append({
            "file": e.file,
            "uniqueId": e.unique_id,
            "category": e.category,
            "type": e.type,
            "icon": e.icon_png,
            "parts": [
                {
                    "assetId": p.asset_id,
                    "png": p.png_path,
                    "ppu": p.ppu,
                    "size": [p.pixel_w, p.pixel_h],
                    "physSize": [p.phys_w, p.phys_h],
                } for p in e.parts
            ],
        })
    manifest_path.write_text(json.dumps(man, indent=2, ensure_ascii=False), encoding="utf-8")

    # Auto-register for visuals / preview
    try:
        from . import visuals as _vis
        for e in entries:
            for p in e.parts:
                _vis.register_melmod_override(e.unique_id, p.png_path, p.ppu)
                _vis.register_melmod_override(p.asset_id, p.png_path, p.ppu)
    except Exception:
        pass

    return entries


def find_part(entries: list[MelmodEntry], asset_id: str) -> MelmodPart | None:
    for e in entries:
        for p in e.parts:
            if p.asset_id == asset_id:
                return p
    return None


def find_by_unique(entries: list[MelmodEntry], unique_id: str) -> MelmodEntry | None:
    for e in entries:
        if e.unique_id == unique_id:
            return e
    return None
