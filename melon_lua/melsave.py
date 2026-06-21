"""Read Melon Playground .melsave archives (ZIP: Data, MetaData, Icon).

APK flow (IL2CPP): SavesManager.TryDeserialize / SaveConverter.Convert(json) →
SaveObjectDataContainer with saveObjectContainers[] of { saveObjects, saveObjectChildren }.

This module extracts a sandbox-friendly view: metadata + flat object list with
objectId, position, rotation, scale, flags, and catalog-resolved names.
"""
from __future__ import annotations

import json
import zipfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

from . import catalog as _catalog


@dataclass
class MelsaveObject:
    index: int
    object_id: int
    instance_id: int
    name: str
    localized_hint: str = ""
    x: float = 0.0
    y: float = 0.0
    z: float = 0.0
    rotation_z: float = 0.0
    scale_x: float = 1.0
    scale_y: float = 1.0
    parent_id: int = -1
    gravity: bool = True
    freezed: bool = False
    children_count: int = 0
    visible: bool = True
    raw: dict[str, Any] = field(default_factory=dict, repr=False)


@dataclass
class MelsaveDocument:
    path: str
    save_name: str
    category: str
    app_version: str
    version_id: int
    map_name: str
    object_count: int
    objects: list[MelsaveObject]
    metadata: dict[str, Any]
    data_extras: dict[str, Any]


def _vec3(d: Any, key: str, default: float = 0.0) -> tuple[float, float, float]:
    if not isinstance(d, dict):
        return default, default, default
    v = d.get(key) or {}
    if not isinstance(v, dict):
        return default, default, default
    return (
        float(v.get("x", default)),
        float(v.get("y", default)),
        float(v.get("z", default)),
    )


def _resolve_name(object_id: int) -> tuple[str, str]:
    prof = _catalog.get_profile_by_object_id(object_id)
    if not prof:
        return f"objectId_{object_id}", ""
    name = str(prof.get("name") or f"objectId_{object_id}")
    hint = str(prof.get("category") or prof.get("buttonName") or "")
    return name, hint


def read_melsave(path: str | Path) -> MelsaveDocument:
    path = Path(path)
    with zipfile.ZipFile(path, "r") as zf:
        if "Data" not in zf.namelist():
            raise ValueError(f"Not a .melsave (missing Data): {path}")
        data = json.loads(zf.read("Data").decode("utf-8"))
        meta: dict[str, Any] = {}
        if "MetaData" in zf.namelist():
            meta = json.loads(zf.read("MetaData").decode("utf-8"))

    containers = data.get("saveObjectContainers") or []
    objects: list[MelsaveObject] = []
    child_index = 100000  # offset so children don't collide with root indices in simple lists

    for idx, container in enumerate(containers):
        so = container.get("saveObjects") or {}
        if so:
            oid = int(so.get("objectId", 0))
            name, hint = _resolve_name(oid)
            px, py, pz = _vec3(so, "position")
            _, _, rz = _vec3(so, "rotation")
            sx, sy, _ = _vec3(so, "scale", 1.0)
            children = container.get("saveObjectChildren") or []
            objects.append(
                MelsaveObject(
                    index=idx,
                    object_id=oid,
                    instance_id=int(so.get("instanceId", 0)),
                    name=name,
                    localized_hint=hint,
                    x=px,
                    y=py,
                    z=pz,
                    rotation_z=rz,
                    scale_x=sx,
                    scale_y=sy,
                    parent_id=int(so.get("parentId", -1)),
                    gravity=bool(so.get("gravity", True)),
                    freezed=bool(so.get("freezed", False)),
                    children_count=len(children) if isinstance(children, list) else 0,
                    raw=so,
                )
            )

        # Also parse direct children as separate spawnable objects.
        # objectId==0 children are named sub-components (Motor, PistonPart, Wheel, Handle...).
        # They carry their own world position/rotation in the save, so we can spawn them.
        # We treat objectId=0 as "part" with the childName as the visual name.
        kids = container.get("saveObjectChildren") or []
        for k in kids:
            if not isinstance(k, dict):
                continue
            koid = int(k.get("objectId", 0))
            kname = k.get("childName") or "part"
            khint = kname
            kpx, kpy, _ = _vec3(k, "position")
            _, _, krz = _vec3(k, "rotation")
            ksx, ksy, _ = _vec3(k, "scale", 1.0)
            objects.append(
                MelsaveObject(
                    index=child_index,
                    object_id=koid,
                    instance_id=int(k.get("instanceId", 0)),
                    name=kname,
                    localized_hint=khint,
                    x=kpx,
                    y=kpy,
                    z=0.0,
                    rotation_z=krz,
                    scale_x=ksx,
                    scale_y=ksy,
                    parent_id=int(k.get("parentId", -1)),
                    gravity=bool(k.get("gravity", True)),
                    freezed=bool(k.get("freezed", False)),
                    children_count=0,
                    raw=k,
                )
            )
            child_index += 1

    md = meta.get("metadata") or {}
    save_name = str(md.get("Name") or path.stem)
    return MelsaveDocument(
        path=str(path.resolve()),
        save_name=save_name,
        category=str(meta.get("category") or ""),
        app_version=str(meta.get("appVersion") or ""),
        version_id=int(meta.get("versionId", 0)),
        map_name=str(meta.get("mapName") or ""),
        object_count=len(objects),
        objects=objects,
        metadata=meta,
        data_extras={
            "averagePosition": data.get("averagePosition"),
            "autoLightData": data.get("autoLightData"),
        },
    )


def document_to_dict(doc: MelsaveDocument, *, include_raw: bool = False) -> dict[str, Any]:
    """JSON-serializable summary for inspection / API discussion."""
    objs = []
    for o in doc.objects:
        row: dict[str, Any] = {
            "index": o.index,
            "objectId": o.object_id,
            "name": o.name,
            "instanceId": o.instance_id,
            "position": {"x": o.x, "y": o.y, "z": o.z},
            "rotationZ": o.rotation_z,
            "scale": {"x": o.scale_x, "y": o.scale_y},
            "parentId": o.parent_id,
            "gravity": o.gravity,
            "freezed": o.freezed,
            "childrenCount": o.children_count,
        }
        if o.localized_hint:
            row["catalogHint"] = o.localized_hint
        if include_raw:
            row["raw"] = o.raw
        objs.append(row)

    by_oid: dict[str, int] = {}
    for o in doc.objects:
        k = str(o.object_id)
        by_oid[k] = by_oid.get(k, 0) + 1

    return {
        "format": "MelonLuaSandbox.melsave.v1",
        "source": doc.path,
        "save": {
            "name": doc.save_name,
            "category": doc.category,
            "appVersion": doc.app_version,
            "versionId": doc.version_id,
            "mapName": doc.map_name,
        },
        "stats": {
            "objectCount": doc.object_count,
            "uniqueObjectIds": len(by_oid),
            "countsByObjectId": by_oid,
        },
        "objects": objs,
        "extras": doc.data_extras,
    }


def list_objects(path: str | Path) -> list[MelsaveObject]:
    return read_melsave(path).objects


def spawn_document_into_world(doc: MelsaveDocument, world: Any, *, melmod_overrides: dict[int, str] | None = None) -> list[int]:
    """Spawn all objects (roots + children saved in the melsave) into WorldContext.

    melmod_overrides: optional map instanceId -> melmod uniqueId or Part_assetId
    """
    ids: list[int] = []
    for o in doc.objects:
        e = world.spawn_entity(
            str(o.object_id),
            o.x,
            o.y,
            object_id=o.object_id,
            angle=o.rotation_z,
            scale_x=o.scale_x,
            scale_y=o.scale_y,
            is_frozen=o.freezed,
            gravity_scale=0.0 if not o.gravity else 1.0,
        )
        raw_col = (o.raw or {}).get("color") if isinstance(o.raw, dict) else None
        if isinstance(raw_col, dict) and any(
            abs(float(raw_col.get(k, 0.0))) > 1e-6 for k in ("r", "g", "b", "a")
        ):
            e.color_r = float(raw_col.get("r", 1.0))
            e.color_g = float(raw_col.get("g", 1.0))
            e.color_b = float(raw_col.get("b", 1.0))
            e.color_a = float(raw_col.get("a", 1.0))
        # if the child entry had isVisible=False we can hide it
        if not o.visible:
            try:
                e.visible = False
            except Exception:
                pass
        # Apply melmod custom texture if provided for this instance
        if melmod_overrides:
            key = o.instance_id
            uid = melmod_overrides.get(key) or melmod_overrides.get(int(key)) if isinstance(key, (int, float)) else None
            if uid:
                try:
                    from . import visuals as _vis
                    _vis.apply_melmod_texture(e, str(uid))
                except Exception:
                    pass
        raw_lid = int(o.raw.get("localId", 0)) if isinstance(o.raw, dict) else 0
        if not raw_lid:
            raw_lid = o.index + 1 if o.index < 100000 else o.index
        e.local_id = raw_lid
        ids.append(e.entity_id)
    return ids