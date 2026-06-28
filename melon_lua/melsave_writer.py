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
    """Write a .melsave ZIP with Data (JSON), MetaData (JSON or empty), Icon (PNG or skip).

    Uses compact JSON (separators=(",",":")) to match real-device format;
    indented JSON is rejected by the melon save loader.
    """
    out = Path(out_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    data_bytes = json.dumps(data_json, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    with zipfile.ZipFile(out, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("Data", data_bytes)
        if meta_json is not None:
            zf.writestr(
                "MetaData",
                json.dumps(meta_json, ensure_ascii=False, separators=(",", ":")).encode("utf-8"),
            )
        else:
            zf.writestr("MetaData", b"")
        if icon_bytes is not None:
            zf.writestr("Icon", icon_bytes)
    return out


# ---------------------------------------------------------------------------
# Mechanic gate connection SDK
# ---------------------------------------------------------------------------

MECHANIC_CONSTRAINT_ID = 13


def connect_gates(
    data_json: dict,
    source_idx: int,
    output_gate: str,
    target_idx: int,
    input_gate: str,
    *,
    name: str = "",
    start_point: tuple[float, float] = (0.0, 0.0),
    end_point: tuple[float, float] = (0.0, 0.0),
    output_group: str = "",
    input_group: str = "",
) -> dict:
    """Wire a mechanic gate connection between two containers in a save's Data JSON.

    Adds a constraint entry to the **source** container's ``constraints`` list
    (the real device stores mechanic connections on the output/source side only).
    Gate names are used verbatim (spaces preserved, e.g. ``"input 2"``,
    ``"Dot worlds position"``).

    SDK contract (reverse-engineered from real-device saves 2297.melsave + xj11):

    - ``constraintId`` is always 13 for mechanic gate connections
      (10 = physics rope, mechCon is None for those)
    - ``mechCon.outputID`` = source object's output gate name
    - ``mechCon.inputID``  = target object's input gate name
    - ``startObjectId``/``endObjectId`` are **container indices** (0-based array
      positions in saveObjectContainers), NOT objectId or localId
    - ``startPoint``/``endPoint`` are visual port offsets in object-local space
      (small values <1.25); they affect rope rendering, not signal routing
    - ``mainGuid`` must have ``IsEmpty: false``

    Args:
        data_json: The parsed Data dict (mutated in place).
        source_idx: Container index of the source (output) object.
        output_gate: Output gate name on the source object.
        target_idx: Container index of the target (input) object.
        input_gate: Input gate name on the target object.
        name: Optional constraint display name.
        start_point: Visual offset of the source port (local space).
        end_point: Visual offset of the target port (local space).

    Returns:
        The constraint dict that was added.
    """
    constraint = {
        "mainGuid": {"Value": str(__import__("uuid").uuid4()), "IsEmpty": False},
        "constraintId": MECHANIC_CONSTRAINT_ID,
        "startPoint": {"x": float(start_point[0]), "y": float(start_point[1]), "z": 0.0},
        "endPoint": {"x": float(end_point[0]), "y": float(end_point[1]), "z": 0.0},
        "mechCon": {
            "inputID": input_gate,
            "outputID": output_gate,
            "inputGroup": input_group,
            "outputGroup": output_group,
        },
        "distance": 0.0,
        "startObjectId": source_idx,
        "endObjectId": target_idx,
        "linkedRopeGuid": None,
        "constraintName": name,
        "isNameVisible": bool(name),
        "startObjectConnectionMaterial": "Paper",
        "endObjectConnectionMaterial": "Metal",
        "customRope": None,
    }
    containers = data_json.get("saveObjectContainers") or []
    if source_idx < 0 or source_idx >= len(containers):
        raise IndexError(f"source_idx {source_idx} out of range ({len(containers)} containers)")
    if target_idx < 0 or target_idx >= len(containers):
        raise IndexError(f"target_idx {target_idx} out of range ({len(containers)} containers)")
    so = containers[source_idx].get("saveObjects") or {}
    cs = so.get("constraints")
    if not isinstance(cs, list):
        cs = []
        so["constraints"] = cs
    cs.append(constraint)
    return constraint


def disconnect_gates(
    data_json: dict,
    source_idx: int,
    output_gate: str | None = None,
    target_idx: int | None = None,
    input_gate: str | None = None,
) -> int:
    """Remove mechanic gate connections from a source container.

    Filters by any combination of output_gate / target_idx / input_gate.
    Only removes mechanic connections (constraintId=13); physics ropes are kept.

    Returns the number of constraints removed.
    """
    containers = data_json.get("saveObjectContainers") or []
    if source_idx < 0 or source_idx >= len(containers):
        return 0
    so = containers[source_idx].get("saveObjects") or {}
    cs = so.get("constraints")
    if not isinstance(cs, list) or not cs:
        return 0
    keep: list[dict] = []
    removed = 0
    for c in cs:
        if c.get("constraintId") != MECHANIC_CONSTRAINT_ID or c.get("mechCon") is None:
            keep.append(c)
            continue
        mc = c.get("mechCon") or {}
        match = True
        if output_gate is not None and mc.get("outputID") != output_gate:
            match = False
        if target_idx is not None and c.get("endObjectId") != target_idx:
            match = False
        if input_gate is not None and mc.get("inputID") != input_gate:
            match = False
        if match:
            removed += 1
        else:
            keep.append(c)
    so["constraints"] = keep
    return removed


def list_gate_connections(data_json: dict, container_idx: int | None = None) -> list[dict]:
    """List mechanic gate connections, optionally filtered to one container.

    Each result dict: {source_idx, target_idx, output_gate, input_gate, name, constraint}.
    """
    containers = data_json.get("saveObjectContainers") or []
    results: list[dict] = []
    for si, cont in enumerate(containers):
        if container_idx is not None and si != container_idx:
            continue
        so = cont.get("saveObjects") or {}
        for c in so.get("constraints", []) or []:
            if c.get("constraintId") != MECHANIC_CONSTRAINT_ID:
                continue
            mc = c.get("mechCon")
            if not mc:
                continue
            results.append({
                "source_idx": si,
                "target_idx": c.get("endObjectId"),
                "output_gate": mc.get("outputID"),
                "input_gate": mc.get("inputID"),
                "name": c.get("constraintName", ""),
                "constraint": c,
            })
    return results


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
    extra_containers: list[dict] | None = None,
) -> Path:
    """Build a diff from world, patch original Data, and write a new .melsave.

    Gate wires from ``world.gate_wires`` are merged into the patched
    ``constraints`` lists (mechanic connections coexist with physical ropes).

    Args:
        extra_containers: Raw saveObjects dicts to append as new containers
            (e.g. Lua chips added via MelsaveSession.add_lua_chip()).
    """
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
    # Append session-added chip containers (Lua chips added via add_lua_chip).
    if extra_containers:
        containers = patched.setdefault("saveObjectContainers", [])
        for so in extra_containers:
            containers.append({"saveObjects": so, "saveObjectChildren": []})
    # Merge gate wires into the patched constraints lists.
    gate_wires = getattr(world, "gate_wires", None)
    if gate_wires is not None and len(gate_wires) > 0:
        _merge_gate_wires_into_save(patched, gate_wires)
    meta = (
        copy.deepcopy(original_doc.metadata)
        if isinstance(original_doc.metadata, dict)
        else {}
    )
    icon: bytes | None = None
    if write_icon:
        icon = _read_icon_from_melsave(original_path)
    return write_melsave(out_path, patched, meta, icon)


def _merge_gate_wires_into_save(save_data: dict, gate_wires: Any) -> None:
    """Merge gate-wire constraints into save's ``constraints`` lists.

    When the registry is non-empty, it is the **source of truth** for all
    mechanic gate wires: for each source container that appears in the
    registry, pre-existing mechanic constraints are stripped and replaced
    with the registry's current wires. Physical ropes (constraintId=10,
    mechCon null) are preserved untouched. Containers not referenced by any
    wire in the registry keep their original constraints as-is.

    When the registry is empty, no changes are made (original constraints
    preserved verbatim).
    """
    wire_dicts = gate_wires.to_constraint_dicts()
    if not wire_dicts:
        return
    containers = save_data.get("saveObjectContainers") or []
    # Group wires by source container index
    by_source: dict[int, list[dict]] = {}
    for wd in wire_dicts:
        si = int(wd.get("startObjectId", 0))
        by_source.setdefault(si, []).append(wd)
    # For containers that have wires in the registry, replace mechanic constraints
    for si, wires in by_source.items():
        if si < 0 or si >= len(containers):
            continue
        so = containers[si].get("saveObjects") or {}
        existing = so.get("constraints")
        if not isinstance(existing, list):
            existing = []
        # Keep only physical ropes (non-mechanic); drop ALL old mechanic wires
        # since the registry is the source of truth for current wires.
        kept_physical = [
            c for c in existing
            if isinstance(c, dict)
            and (c.get("constraintId") != MECHANIC_CONSTRAINT_ID
                 or c.get("mechCon") is None)
        ]
        so["constraints"] = kept_physical + wires
