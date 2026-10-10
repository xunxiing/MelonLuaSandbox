"""Spawn catalog + physics profiles (495 objects, keyed by objectId and name).

Data: melon_lua/data/object_physics_by_id.json (from lua-triage build).
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Optional

_DATA_PATH = Path(__file__).resolve().parent / "data" / "object_physics_by_id.json"
_MENU_ALIASES_PATH = Path(__file__).resolve().parent / "data" / "spawn_menu_aliases.json"

_by_oid: Optional[dict[str, dict]] = None
_by_name: Optional[dict[str, dict]] = None
_stats: Optional[dict] = None
# catalog gameObjectName → [device menu aliases]
_name_to_aliases: Optional[dict[str, list[str]]] = None
_alias_to_name: Optional[dict[str, str]] = None

# Known device menu alias → sandbox physics objectId (display-name ↔ catalog
# name diverge: "crate" shows as "Crate" but the catalog name is "Box" oid 23).
MENU_ALIAS_OID: dict[str, int] = {
    "plastic_plate": 202,
    "resizable_brick": 202,
    "crate": 23,
    "barrel": 24,
    "wheel": 121,
    "wooden_lath": 202,
    "wooden_plate": 202,
    "metal_plate": 202,
}


def _load_menu_alias_map() -> dict[str, list[str]]:
    """Invert data/spawn_menu_aliases.json (alias → DisplayName) → name → aliases."""
    global _name_to_aliases, _alias_to_name
    if _name_to_aliases is not None:
        return _name_to_aliases
    _name_to_aliases, _alias_to_name = {}, {}
    try:
        raw = json.loads(_MENU_ALIASES_PATH.read_text(encoding="utf-8"))
        for alias, name in (raw.get("alias_to_name") or {}).items():
            _alias_to_name[str(alias)] = str(name)
            _name_to_aliases.setdefault(str(name), []).append(str(alias))
    except Exception:
        pass
    return _name_to_aliases


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


def catalog_search(query: str, limit: int = 20) -> str:
    """Search spawnables by name / alias / objectId substring → report string.

    The documented SDK contract is ``catalog_search -> str``; missing it made
    ``from melon_lua import catalog_search`` raise ImportError. Reimplemented here:
    matches name (case-insensitive substring), exact objectId, and alias-style
    keys (snake_case / lowercase / no-space variants).

    Returns a human-readable multi-line report (str), one entry per line:
    ``"202  ResizablePlastic  0.4x0.4  mass=0.150"``
    plus a header with match count / total. No matches → "no spawnable found".
    """
    _load()
    q = str(query or "").strip()
    if not q:
        return "catalog_search: empty query"
    ql = q.lower()
    q_compact = ql.replace(" ", "").replace("_", "").replace("-", "")
    alias_map = _load_menu_alias_map()
    rows: list[tuple[int, str]] = []
    for prof in (_by_name or {}).values():
        n = prof.get("name") or ""
        if not n:
            continue
        oid = prof.get("objectId")
        nl = n.lower()
        nl_compact = nl.replace(" ", "").replace("_", "").replace("-", "")
        # device menu aliases pointing at this catalog name (e.g. crate → Box)
        aliases = [a for a in alias_map.get(str(n), [])]
        alias_hit = any(
            ql in a.lower() or q_compact in a.lower().replace("_", "")
            for a in aliases
        )
        hit = (
            ql in nl
            or q_compact in nl_compact
            or (oid is not None and q == str(oid))
            or alias_hit
        )
        if hit:
            aabb = prof.get("aabb") or {}
            w = prof.get("aabbWidth") or aabb.get("width")
            h = prof.get("aabbHeight") or aabb.get("height")
            mass = (prof.get("rigidbody") or {}).get("mass")
            size = f"{w}x{h}" if (w is not None and h is not None) else "?"
            mass_s = f"mass={mass}" if mass is not None else ""
            alias_s = f"  [alias: {', '.join(sorted(aliases))}]" if aliases else ""
            rows.append((int(oid or 0), f"{oid}  {n}  {size}  {mass_s}{alias_s}".rstrip()))
    rows.sort(key=lambda r: r[0])
    # Device spawn-menu aliases whose display name is not a catalog name
    # (e.g. query "crate" → display "Crate", catalog name "Box"). Report the
    # alias directly — it's what spawn.create() needs on the real device.
    alias_rows: list[str] = []
    a2n = dict(_alias_to_name or {})
    for alias, display in sorted(a2n.items()):
        al, dl = alias.lower(), display.lower()
        if (ql in al or q_compact in al.replace("_", "")
                or ql in dl or q_compact in dl.replace(" ", "").replace("-", "")):
            oid = MENU_ALIAS_OID.get(alias)
            oid_s = f"  oid={oid}" if oid is not None else ""
            alias_rows.append(f"alias: {alias} → {display}{oid_s}  (device spawn menu)")
    total = len(rows) + len(alias_rows)
    budget = max(1, limit)
    out_rows = rows[:budget]
    out_alias = alias_rows[:max(0, budget - len(out_rows))]
    out = [f"catalog_search('{q}'): {len(out_rows) + len(out_alias)} of {total} matches"]
    out.extend(r[1] for r in out_rows)
    out.extend(out_alias)
    if total == 0:
        out = [f"catalog_search('{q}'): no spawnable found",
               "tip: use list_spawnables() to see all names, or pass a numeric objectId"]
    return "\n".join(out)


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