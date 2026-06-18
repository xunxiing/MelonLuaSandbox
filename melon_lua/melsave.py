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

    for idx, container in enumerate(containers):
        so = container.get("saveObjects") or {}
        if not so:
            continue
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


def spawn_document_into_world(doc: MelsaveDocument, world: Any) -> list[int]:
    """Spawn all root objects (parentId == -1) into WorldContext. Returns entity ids."""
    ids: list[int] = []
    for o in doc.objects:
        if o.parent_id != -1:
            continue
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
        ids.append(e.entity_id)
    return ids