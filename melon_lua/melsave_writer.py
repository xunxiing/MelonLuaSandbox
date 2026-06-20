"""Write Melon Playground .melsave archives (ZIP: Data, MetaData, Icon).

APK flow (IL2CPP): SavesManager.TrySerialize / SaveConverter.Convert(json) <->
SaveObjectDataContainer with saveObjectContainers[] of { saveObjects, saveObjectChildren }.

This module provides the write-back side: patch an existing Data JSON with a
WorldDiff (modified / added / removed objects + constraints), then serialize a
new .melsave ZIP. A naive round-trip of MelsaveObject.raw preserves all ~48
SaveObject fields, so write-back is lossless when no diff is applied.
"""
from __future__ import annotations

import copy
import json
import zipfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from .melsave import MelsaveDocument, MelsaveObject

_TEMPLATE_DIR = Path(__file__).parent.parent / "temp" / "objectid_templates"

_CHILD_INDEX_OFFSET = 100000


@dataclass
class WorldDiff:
    """Diff between a live WorldContext and an original MelsaveDocument."""
    modified_objects: dict[int, dict[str, Any]] = field(default_factory=dict)
    added_objects: list[dict[str, Any]] = field(default_factory=list)
    removed_local_ids: set[int] = field(default_factory=set)
    modified_constraints: dict[int, dict[str, list[dict]]] = field(default_factory=dict)

    def is_empty(self) -> bool:
        return (
            not self.modified_objects
            and not self.added_objects
            and not self.removed_local_ids
            and not self.modified_constraints
        )


def write_melsave(
    out_path: str | Path,
    data_json: dict,
    meta_json: dict | None = None,
    icon_bytes: bytes | None = None,
) -> Path:
    """Write a .melsave ZIP with Data (JSON), MetaData (JSON or empty), Icon (PNG or skip)."""
    out = Path(out_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    data_bytes = json.dumps(data_json, indent=2, ensure_ascii=False).encode("utf-8")
    with zipfile.ZipFile(out, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("Data", data_bytes)
        if meta_json is not None:
            zf.writestr(
                "MetaData",
                json.dumps(meta_json, indent=2, ensure_ascii=False).encode("utf-8"),
            )
        else:
            zf.writestr("MetaData", b"")
        if icon_bytes is not None:
            zf.writestr("Icon", icon_bytes)
    return out


def clone_object_template(
    object_id: int,
    *,
    position: tuple[float, float] | None = None,
    rotation_z: float = 0.0,
    scale: tuple[float, float] | None = None,
    local_id: int = 0,
    parent_id: int = -1,
) -> dict | None:
    """Clone a template SaveObject from temp/objectid_templates/<objectId>.json with overrides."""
    tpl_path = _TEMPLATE_DIR / f"{object_id}.json"
    if not tpl_path.exists():
        return None
    try:
        obj = json.loads(tpl_path.read_text(encoding="utf-8"))
    except Exception:
        return None
    obj = json.loads(json.dumps(obj))
    obj = copy.deepcopy(obj)
    if position is not None:
        obj["position"] = {"x": float(position[0]), "y": float(position[1]), "z": 0.0}
    obj["rotation"] = {"x": 0.0, "y": 0.0, "z": float(rotation_z)}
    if scale is not None:
        obj["scale"] = {"x": float(scale[0]), "y": float(scale[1]), "z": 1.0}
    obj["localId"] = int(local_id)
    obj["parentId"] = int(parent_id)
    obj["instanceId"] = 0
    return obj


def _deep_merge(base: dict[str, Any], patch: dict[str, Any]) -> dict[str, Any]:
    """Recursive merge: dict values merge, scalars/lists replace."""
    for k, v in patch.items():
        if k in base and isinstance(base[k], dict) and isinstance(v, dict):
            _deep_merge(base[k], v)
        else:
            base[k] = copy.deepcopy(v)
    return base


def _apply_patches_to_save_object(
    so: Any,
    diff: "WorldDiff",
) -> None:
    """Apply modified_objects / modified_constraints to a single saveObjects dict."""
    if not isinstance(so, dict):
        return
    lid = int(so.get("localId", 0))
    if lid in diff.modified_objects:
        _deep_merge(so, diff.modified_objects[lid])
    if lid in diff.modified_constraints:
        mc = diff.modified_constraints[lid]
        if "constraints" in mc:
            so["constraints"] = copy.deepcopy(mc["constraints"])
        if "distJoints" in mc:
            so["distJoints"] = copy.deepcopy(mc["distJoints"])
        if "hingeJoints" in mc:
            so["hingeJoints"] = copy.deepcopy(mc["hingeJoints"])


def _apply_patches_to_save_object_with_lid(
    so: Any,
    diff: "WorldDiff",
    eff_lid: int,
) -> None:
    """Apply patches using an explicit effective local id (falls back to raw localId)."""
    if not isinstance(so, dict):
        return
    raw_lid = int(so.get("localId", 0))
    for candidate in (eff_lid, raw_lid):
        if not candidate:
            continue
        if candidate in diff.modified_objects:
            _deep_merge(so, diff.modified_objects[candidate])
        if candidate in diff.modified_constraints:
            mc = diff.modified_constraints[candidate]
            if "constraints" in mc:
                existing = so.get("constraints")
                if isinstance(existing, list) and existing:
                    seen_guids = {
                        (c.get("mainGuid") or {}).get("Value")
                        for c in mc["constraints"]
                        if isinstance(c, dict)
                    }
                    preserved = [
                        c for c in existing
                        if isinstance(c, dict)
                        and ((c.get("mainGuid") or {}).get("Value") or None) not in seen_guids
                    ]
                    so["constraints"] = preserved + copy.deepcopy(mc["constraints"])
                else:
                    so["constraints"] = copy.deepcopy(mc["constraints"])
            if "distJoints" in mc:
                so["distJoints"] = copy.deepcopy(mc["distJoints"])
            if "hingeJoints" in mc:
                so["hingeJoints"] = copy.deepcopy(mc["hingeJoints"])
            break


def _effective_lid(raw_lid: int, index: int, is_child: bool = False) -> int:
    """Resolve the effective local id used by the diff.

    Melsave objects often have localId=0 in their raw JSON (the real game
    reassigns localId on load). The sandbox assigns entity.local_id = index+1
    for root objects during spawn_document_into_world, so we mirror that here
    when the raw localId is zero.
    """
    if raw_lid:
        return raw_lid
    return index + 1 if not is_child else index + _CHILD_INDEX_OFFSET


def patch_save_data(original_data: dict, diff: "WorldDiff") -> dict:
    """Apply a WorldDiff to a deep copy of original Data JSON and return the patched dict."""
    data = copy.deepcopy(original_data)
    containers = data.get("saveObjectContainers")
    if not isinstance(containers, list):
        containers = []
        data["saveObjectContainers"] = containers

    keep: list[dict[str, Any]] = []
    for ci, container in enumerate(containers):
        if not isinstance(container, dict):
            keep.append(container)
            continue
        so = container.get("saveObjects")
        raw_lid = int(so.get("localId", 0)) if isinstance(so, dict) else 0
        eff_lid = _effective_lid(raw_lid, ci)
        if eff_lid in diff.removed_local_ids or raw_lid in diff.removed_local_ids:
            continue
        if isinstance(so, dict):
            _apply_patches_to_save_object_with_lid(so, diff, eff_lid)
        children = container.get("saveObjectChildren")
        if isinstance(children, list):
            new_children: list[dict[str, Any]] = []
            for chi, child in enumerate(children):
                if not isinstance(child, dict):
                    new_children.append(child)
                    continue
                crlid = int(child.get("localId", 0))
                ceff_lid = _effective_lid(crlid, chi, is_child=True)
                if ceff_lid in diff.removed_local_ids or crlid in diff.removed_local_ids:
                    continue
                _apply_patches_to_save_object_with_lid(child, diff, ceff_lid)
                new_children.append(child)
            container["saveObjectChildren"] = new_children
        keep.append(container)

    for added in diff.added_objects:
        keep.append({"saveObjects": copy.deepcopy(added), "saveObjectChildren": []})

    data["saveObjectContainers"] = keep
    return data


def _read_icon_from_melsave(path: str | Path) -> bytes | None:
    try:
        with zipfile.ZipFile(path, "r") as zf:
            if "Icon" in zf.namelist():
                return zf.read("Icon")
    except Exception:
        pass
    return None


def _entity_local_id(e: Any) -> int:
    lid = getattr(e, "local_id", 0)
    try:
        return int(lid) if lid is not None else 0
    except Exception:
        return 0


def _obj_local_id(obj: "MelsaveObject") -> int:
    raw = getattr(obj, "raw", None)
    if isinstance(raw, dict):
        try:
            lid = int(raw.get("localId", 0))
            if lid:
                return lid
        except Exception:
            pass
    idx = getattr(obj, "index", 0)
    try:
        idx = int(idx)
    except Exception:
        return 0
    return idx + 1 if idx < _CHILD_INDEX_OFFSET else idx


def _entity_color_dict(e: Any) -> dict[str, float]:
    return {
        "r": float(getattr(e, "color_r", 1.0)),
        "g": float(getattr(e, "color_g", 1.0)),
        "b": float(getattr(e, "color_b", 1.0)),
        "a": float(getattr(e, "color_a", 1.0)),
    }


def _build_transform_patch(e: Any) -> dict[str, Any]:
    return {
        "position": {
            "x": float(getattr(e, "position_x", 0.0)),
            "y": float(getattr(e, "position_y", 0.0)),
            "z": 0.0,
        },
        "rotation": {
            "x": 0.0,
            "y": 0.0,
            "z": float(getattr(e, "angle", 0.0)),
        },
        "scale": {
            "x": float(getattr(e, "scale_x", 1.0)),
            "y": float(getattr(e, "scale_y", 1.0)),
            "z": 1.0,
        },
        "gravity": bool(getattr(e, "gravity_scale", 1.0) > 0.0),
        "freezed": bool(getattr(e, "is_frozen", False)),
        "color": _entity_color_dict(e),
    }


def _build_transform_patch_if_changed(e: Any, obj: "MelsaveObject") -> dict[str, Any] | None:
    """Build a patch dict only if transform differs from the original melsave object."""
    raw = getattr(obj, "raw", None) or {}
    pos = raw.get("position") or {}
    rot = raw.get("rotation") or {}
    scl = raw.get("scale") or {}
    col = raw.get("color") or {}
    changed: dict[str, Any] = {}

    ex = float(getattr(e, "position_x", 0.0))
    ey = float(getattr(e, "position_y", 0.0))
    if abs(ex - float(pos.get("x", 0.0))) > 1e-6 or abs(ey - float(pos.get("y", 0.0))) > 1e-6:
        changed["position"] = {"x": ex, "y": ey, "z": 0.0}

    ez = float(getattr(e, "angle", 0.0))
    if abs(ez - float(rot.get("z", 0.0))) > 1e-6:
        changed["rotation"] = {"x": 0.0, "y": 0.0, "z": ez}

    sx = float(getattr(e, "scale_x", 1.0))
    sy = float(getattr(e, "scale_y", 1.0))
    if abs(sx - float(scl.get("x", 1.0))) > 1e-6 or abs(sy - float(scl.get("y", 1.0))) > 1e-6:
        changed["scale"] = {"x": sx, "y": sy, "z": 1.0}

    e_grav = bool(getattr(e, "gravity_scale", 1.0) > 0.0)
    raw_grav = bool(raw.get("gravity", True))
    if e_grav != raw_grav and raw_grav:
        changed["gravity"] = e_grav

    e_frz = bool(getattr(e, "is_frozen", False))
    raw_frz = bool(raw.get("freezed", False))
    if e_frz != raw_frz:
        changed["freezed"] = e_frz

    cr = float(getattr(e, "color_r", 1.0))
    cg = float(getattr(e, "color_g", 1.0))
    cb = float(getattr(e, "color_b", 1.0))
    ca = float(getattr(e, "color_a", 1.0))
    raw_cr = float(col.get("r", 1.0))
    raw_cg = float(col.get("g", 1.0))
    raw_cb = float(col.get("b", 1.0))
    raw_ca = float(col.get("a", 1.0))
    if raw_cr == 0.0 and raw_cg == 0.0 and raw_cb == 0.0 and raw_ca == 0.0:
        pass
    elif (abs(cr - raw_cr) > 1e-6 or abs(cg - raw_cg) > 1e-6
            or abs(cb - raw_cb) > 1e-6 or abs(ca - raw_ca) > 1e-6):
        changed["color"] = {"r": cr, "g": cg, "b": cb, "a": ca}

    return changed if changed else None


def build_diff_from_world(world: Any, original_doc: "MelsaveDocument") -> "WorldDiff":
    """Compare current world state against the original melsave document."""
    diff = WorldDiff()
    entities = getattr(world, "entities", {}) or {}

    by_local_id: dict[int, Any] = {}
    by_entity_id: dict[int, Any] = {}
    alive_sorted: list[Any] = []
    for e in entities.values():
        if not getattr(e, "alive", True):
            continue
        alive_sorted.append(e)
        lid = _entity_local_id(e)
        if lid:
            by_local_id[lid] = e
        eid = getattr(e, "entity_id", 0)
        if eid:
            by_entity_id[int(eid)] = e
    alive_sorted.sort(key=lambda e: int(getattr(e, "entity_id", 0)))

    matched_entity_ids: set[int] = set()
    max_local_id = 0
    for obj in original_doc.objects:
        olid = _obj_local_id(obj)
        if olid > max_local_id:
            max_local_id = olid

    for obj in original_doc.objects:
        olid = _obj_local_id(obj)
        e: Optional[Any] = None
        if olid and olid in by_local_id:
            e = by_local_id[olid]
        elif obj.instance_id and obj.instance_id in by_entity_id:
            e = by_entity_id[obj.instance_id]

        if e is None:
            if olid:
                diff.removed_local_ids.add(olid)
            continue
        matched_entity_ids.add(int(getattr(e, "entity_id", 0)))

        patch = _build_transform_patch_if_changed(e, obj)
        if patch and olid:
            diff.modified_objects[olid] = patch

    for e in alive_sorted:
        eid = int(getattr(e, "entity_id", 0))
        if eid in matched_entity_ids:
            continue
        oid = getattr(e, "object_id", None)
        if oid is None:
            continue
        max_local_id += 1
        new_lid = max_local_id
        cloned = clone_object_template(
            int(oid),
            position=(
                float(getattr(e, "position_x", 0.0)),
                float(getattr(e, "position_y", 0.0)),
            ),
            rotation_z=float(getattr(e, "angle", 0.0)),
            scale=(
                float(getattr(e, "scale_x", 1.0)),
                float(getattr(e, "scale_y", 1.0)),
            ),
            local_id=new_lid,
            parent_id=-1,
        )
        if cloned is None:
            continue
        cloned["freezed"] = bool(getattr(e, "is_frozen", False))
        cloned["gravity"] = bool(getattr(e, "gravity_scale", 1.0) > 0.0)
        cloned["color"] = _entity_color_dict(e)
        diff.added_objects.append(cloned)

    registry = getattr(world, "constraints", None)
    if registry is not None:
        try:
            _collect_constraint_diff(registry, diff, original_doc)
        except Exception:
            pass

    return diff


def _collect_constraint_diff(
    registry: Any,
    diff: "WorldDiff",
    original_doc: "MelsaveDocument",
) -> None:
    candidate_lids: set[int] = set()
    for obj in original_doc.objects:
        olid = _obj_local_id(obj)
        if olid:
            candidate_lids.add(olid)
    for added in diff.added_objects:
        al = int(added.get("localId", 0))
        if al:
            candidate_lids.add(al)

    all_constraints, all_dist, all_hinge = _safe_to_save_dicts(registry)
    if not all_constraints:
        return

    for lid in candidate_lids:
        lst = None
        try:
            lst = registry.list_for_object(lid)
        except Exception:
            lst = None
        if not lst:
            continue
        my_constraints = [c for c in all_constraints if _constraint_local_ids_match(c, lid)]
        if not my_constraints:
            continue
        my_cids = {i + 1 for i, c in enumerate(all_constraints) if _constraint_local_ids_match(c, lid)}
        my_dist = [d for d in all_dist if int(d.get("index", 0)) in my_cids]
        my_hinge = [h for h in all_hinge if int(h.get("index", 0)) in my_cids]
        diff.modified_constraints[lid] = {
            "constraints": my_constraints,
            "distJoints": my_dist,
            "hingeJoints": my_hinge,
        }


def _safe_to_save_dicts(registry: Any) -> tuple[list[dict], list[dict], list[dict]]:
    try:
        result = registry.to_save_dicts()
    except Exception:
        return [], [], []
    if isinstance(result, tuple) and len(result) == 3:
        constraints, dist, hinge = result
        return list(constraints or []), list(dist or []), list(hinge or [])
    return [], [], []


def _constraint_local_ids_match(constraint_json: dict, local_id: int) -> bool:
    s = int(constraint_json.get("startObjectId", 0))
    e = int(constraint_json.get("endObjectId", 0))
    return s == local_id or e == local_id


def _build_constraint_entry(registry: Any) -> dict[str, list[dict]] | None:
    try:
        result = registry.to_save_dicts()
    except Exception:
        return None
    if isinstance(result, tuple) and len(result) == 3:
        constraints_json, dist_joints_json, hinge_joints_json = result
    elif isinstance(result, dict):
        constraints_json = result.get("constraints", [])
        dist_joints_json = result.get("distJoints", [])
        hinge_joints_json = result.get("hingeJoints", [])
    else:
        return None
    return {
        "constraints": list(constraints_json or []),
        "distJoints": list(dist_joints_json or []),
        "hingeJoints": list(hinge_joints_json or []),
    }


def write_world_to_melsave(
    world: Any,
    original_doc: "MelsaveDocument",
    out_path: str | Path,
    *,
    write_icon: bool = True,
) -> Path:
    """Build a diff from world, patch original Data, and write a new .melsave."""
    diff = build_diff_from_world(world, original_doc)
    original_path = original_doc.path
    original_data: dict[str, Any] = {}
    try:
        with zipfile.ZipFile(original_path, "r") as zf:
            if "Data" in zf.namelist():
                original_data = json.loads(zf.read("Data").decode("utf-8"))
    except Exception:
        original_data = {"saveObjectContainers": []}
    patched = patch_save_data(original_data, diff)
    meta = (
        copy.deepcopy(original_doc.metadata)
        if isinstance(original_doc.metadata, dict)
        else {}
    )
    icon: bytes | None = None
    if write_icon:
        icon = _read_icon_from_melsave(original_path)
    return write_melsave(out_path, patched, meta, icon)
