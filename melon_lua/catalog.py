"""Spawn catalog + physics profiles (495 objects, keyed by objectId and name).

Data: melon_lua/data/object_physics_by_id.json (from lua-triage build).
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Optional

_DATA_PATH = Path(__file__).resolve().parent / "data" / "object_physics_by_id.json"

_by_oid: Optional[dict[str, dict]] = None
_by_name: Optional[dict[str, dict]] = None
_stats: Optional[dict] = None


def _load() -> None:
    global _by_oid, _by_name, _stats
    if _by_oid is not None:
        return
    _by_oid, _by_name, _stats = {}, {}, {}
    if not _DATA_PATH.is_file():
        return
    try:
        raw = json.loads(_DATA_PATH.read_text(encoding="utf-8"))
        _by_oid = raw.get("byObjectId") or {}
        _by_name = raw.get("byName") or {}
        _stats = raw.get("stats") or {}
    except Exception:
        pass


def catalog_stats() -> dict[str, Any]:
    _load()
    return dict(_stats or {})


def get_profile_by_object_id(object_id: int) -> Optional[dict[str, Any]]:
    _load()
    return (_by_oid or {}).get(str(int(object_id)))


def get_profile_by_name(name: str) -> Optional[dict[str, Any]]:
    _load()
    if not name:
        return None
    return (_by_name or {}).get(name)


def resolve_spawn_name(alias_or_name: str) -> str:
    """Map catalog alias / display name / numeric objectId string → gameObjectName."""
    _load()
    key = str(alias_or_name).strip()
    if key.isdigit():
        prof = get_profile_by_object_id(int(key))
        if prof and prof.get("name"):
            return str(prof["name"])
    prof = get_profile_by_name(key)
    if prof:
        return str(prof.get("name") or key)
    return key


def object_id_for_name(name: str) -> Optional[int]:
    prof = get_profile_by_name(name)
    if not prof:
        return None
    oid = prof.get("objectId")
    return int(oid) if oid is not None else None


def list_spawnables() -> list[dict[str, Any]]:
    """All entries with a non-empty gameObjectName (for SDK / tools)."""
    _load()
    out: list[dict[str, Any]] = []
    for prof in (_by_name or {}).values():
        n = prof.get("name") or ""
        if not n:
            continue
        oid = prof.get("objectId")
        w = prof.get("aabbWidth")
        h = prof.get("aabbHeight")
        if w is None and prof.get("aabb"):
            w = prof["aabb"].get("width")
        if h is None and prof.get("aabb"):
            h = prof["aabb"].get("height")
        out.append(
            {
                "objectId": oid,
                "name": n,
                "width": w,
                "height": h,
                "mass": (prof.get("rigidbody") or {}).get("mass"),
                "source": prof.get("source", ""),
            }
        )
    out.sort(key=lambda x: (x.get("objectId") is None, x.get("objectId") or 0))
    return out