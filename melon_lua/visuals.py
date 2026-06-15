"""Resolve sprite path per objectId for sandbox rendering."""
from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

_PKG = Path(__file__).resolve().parent
_DATA = _PKG / "data" / "sprites_by_object_id.json"
_PACK = _PKG / "data" / "sprites_pack"
_TRIAGE = _PKG.parent.parent / "lua-triage" / "object_sprites_by_id"


@lru_cache(maxsize=1)
def _load_rows() -> dict[int, dict]:
    for p in (_DATA, _TRIAGE / "sprites_by_object_id.json"):
        if p.is_file():
            data = json.loads(p.read_text(encoding="utf-8"))
            return {int(r["objectId"]): r for r in data.get("sprites", []) if r.get("objectId") is not None}
    return {}


def _resolve_file(rel: str) -> str | None:
    if not rel:
        return None
    rel_path = Path(rel.replace("/", "\\") if "\\" in str(_PKG) else rel)
    for base in (_PKG / "data", _PACK, _TRIAGE):
        if rel.startswith("sprites_pack/"):
            cand = _PKG / "data" / rel_path
        else:
            cand = base / rel_path.name if base == _PACK and rel_path.name else base / rel_path
        if cand.is_file():
            return str(cand.resolve())
        cand2 = _PKG / "data" / rel_path
        if cand2.is_file():
            return str(cand2.resolve())
    full = _TRIAGE / rel
    if full.is_file():
        return str(full.resolve())
    full = _TRIAGE / "images" / rel_path.name
    return str(full.resolve()) if full.is_file() else None


def sprite_path_for_object_id(object_id: int | None) -> str | None:
    if object_id is None:
        return None
    row = _load_rows().get(int(object_id))
    if not row:
        return None
    return _resolve_file(row.get("spritePath") or "")


def fallback_sprite_path() -> str | None:
    for name in (
        "sprites_pack/images/0202_plastic_fallback.png",
        "images/0202_plastic_fallback.png",
        "0202_plastic_fallback.png",
    ):
        p = _resolve_file(name)
        if p:
            return p
    return None


def resolve_sprite(object_id: int | None, game_object_name: str = "") -> str | None:
    del game_object_name
    return sprite_path_for_object_id(object_id) or fallback_sprite_path()