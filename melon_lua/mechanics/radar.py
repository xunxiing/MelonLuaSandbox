"""Area Radar (objectId 892993856) runtime simulation.

Mirrors device behaviour enough for chip wiring:
- activation gate / activationInput
- sizeX/sizeY (width/height) + shift
- Radar_selected_entities objectId filter (empty = detect nothing)
- outputs: entity array, entity, trigger, activation

Geometry: axis-aligned detection box at radar position + shift
(rotated by radar angle). Entity centers are tested against the box.
"""
from __future__ import annotations

import json
import math
from typing import Any, Optional

RADAR_OBJECT_ID = 892993856
_SELECTED_KEY = "Radar_selected_entities"


def _gate_value_float(gate: dict, default: float = 0.0) -> float:
    gd = gate.get("GateData")
    if isinstance(gd, str) and gd:
        try:
            data = json.loads(gd)
            if isinstance(data, dict) and "Value" in data:
                return float(data["Value"])
        except (TypeError, ValueError, json.JSONDecodeError):
            pass
    return float(default)


def _parse_input_gates(so: dict) -> dict[str, float]:
    """Map Key/DataName → float Value from mechanicSerializedInputs."""
    out: dict[str, float] = {}
    md = so.get("mechanicData")
    if not isinstance(md, list) or not md:
        return out
    raw = md[0].get("mechanicSerializedInputs") if isinstance(md[0], dict) else None
    if not raw:
        return out
    try:
        gates = json.loads(raw) if isinstance(raw, str) else list(raw)
    except (TypeError, json.JSONDecodeError):
        return out
    for g in gates:
        if not isinstance(g, dict):
            continue
        val = _gate_value_float(g, 0.0)
        key = g.get("Key")
        name = g.get("DataName")
        if key:
            out[str(key)] = val
        if name:
            out[str(name)] = val
    return out


def parse_selected_object_ids(so: dict) -> set[str]:
    """Parse Radar_selected_entities stringValue → set of id strings.

    Empty / missing / \"[]\" → empty set (device: detect nothing).
    """
    metas = so.get("saveMetaDatas")
    if not isinstance(metas, list):
        return set()
    for md in metas:
        if not isinstance(md, dict) or md.get("key") != _SELECTED_KEY:
            continue
        sv = md.get("stringValue") or "[]"
        try:
            arr = json.loads(sv)
        except (TypeError, json.JSONDecodeError):
            return set()
        if not isinstance(arr, list):
            return set()
        return {str(x) for x in arr}
    return set()


def parse_radar_config(so: dict) -> dict[str, Any]:
    """Read radar parameters from a saveObjects dict."""
    gates = _parse_input_gates(so)
    md0: dict = {}
    md = so.get("mechanicData")
    if isinstance(md, list) and md and isinstance(md[0], dict):
        md0 = md[0]
    raw_fps = md0.get("floatParameters")
    fps: list[Any] = list(raw_fps) if isinstance(raw_fps, list) else []
    # floatParameters: [?, shiftX?, shiftY?, ?, sizeX, sizeY] per template/docs
    size_x = gates.get("sizeX", gates.get("width"))
    size_y = gates.get("sizeY", gates.get("height"))
    if size_x is None and len(fps) > 4:
        size_x = float(fps[4])
    if size_y is None and len(fps) > 5:
        size_y = float(fps[5])
    if size_x is None:
        size_x = 1.0
    if size_y is None:
        size_y = 1.0
    shift_x = gates.get("shiftX", gates.get("shift x"))
    shift_y = gates.get("shiftY", gates.get("shift y"))
    if shift_x is None and len(fps) > 1:
        shift_x = float(fps[1])
    if shift_y is None and len(fps) > 2:
        shift_y = float(fps[2])
    if shift_x is None:
        shift_x = 0.0
    if shift_y is None:
        shift_y = 0.0
    act = gates.get("activation")
    if act is None:
        act = float(md0.get("activationInput", so.get("activationInput", 1.0)) or 0.0)
    return {
        "activation": float(act),
        "width": float(size_x),
        "height": float(size_y),
        "shift_x": float(shift_x),
        "shift_y": float(shift_y),
        "selected_ids": parse_selected_object_ids(so),
    }


def query_radar_hits(
    world: Any,
    radar: Any,
    *,
    width: float,
    height: float,
    shift_x: float = 0.0,
    shift_y: float = 0.0,
    selected_object_ids: Optional[set[str]] = None,
    exclude_self: bool = True,
) -> list[int]:
    """Return runtime entity_ids whose centers lie inside the radar area."""
    if width <= 0.0 or height <= 0.0:
        return []
    if selected_object_ids is not None and len(selected_object_ids) == 0:
        return []

    ang = math.radians(float(getattr(radar, "angle", 0.0) or 0.0))
    c, s = math.cos(ang), math.sin(ang)
    # shift in radar local space → world
    cx = float(radar.position_x) + shift_x * c - shift_y * s
    cy = float(radar.position_y) + shift_x * s + shift_y * c
    half_w = width * 0.5
    half_h = height * 0.5
    # inverse rotate world → radar local for AABB test
    inv_c, inv_s = c, -s

    hits: list[int] = []
    for eid, e in world.entities.items():
        if not getattr(e, "alive", True):
            continue
        if exclude_self and eid == radar.entity_id:
            continue
        if selected_object_ids is not None:
            oid = e.object_id
            if oid is None:
                continue
            if str(int(oid)) not in selected_object_ids and str(oid) not in selected_object_ids:
                continue
        dx = float(e.position_x) - cx
        dy = float(e.position_y) - cy
        lx = dx * inv_c - dy * inv_s
        ly = dx * inv_s + dy * inv_c
        if abs(lx) <= half_w and abs(ly) <= half_h:
            hits.append(int(eid))
    hits.sort()
    return hits


def simulate_radars(world: Any, doc_raw: dict | None = None) -> dict[int, dict[str, Any]]:
    """Update all Radar entities; store outputs on world.gate_output_values.

    Returns mapping container_idx → output gate dict.
    Requires entities tagged with custom_data['container_idx'] (set at spawn).
    """
    if not hasattr(world, "gate_output_values") or world.gate_output_values is None:
        world.gate_output_values = {}

    # container_idx → saveObjects (for live parameter re-read)
    so_by_idx: dict[int, dict] = {}
    if isinstance(doc_raw, dict):
        containers = doc_raw.get("saveObjectContainers") or []
        for i, c in enumerate(containers):
            if not isinstance(c, dict):
                continue
            so = c.get("saveObjects")
            if isinstance(so, dict) and int(so.get("objectId", 0) or 0) == RADAR_OBJECT_ID:
                so_by_idx[i] = so

    results: dict[int, dict[str, Any]] = {}
    for e in list(world.entities.values()):
        if not getattr(e, "alive", True):
            continue
        if int(e.object_id or 0) != RADAR_OBJECT_ID:
            continue
        cidx = e.custom_data.get("container_idx")
        if cidx is None:
            continue
        cidx = int(cidx)
        so = so_by_idx.get(cidx)
        if so is not None:
            cfg = parse_radar_config(so)
        else:
            # runtime-only radar: default select-all from package data if present
            cfg = {
                "activation": float(getattr(e, "activation_input", 1.0) or 1.0),
                "width": float(e.custom_data.get("radar_width", 1.0)),
                "height": float(e.custom_data.get("radar_height", 1.0)),
                "shift_x": float(e.custom_data.get("radar_shift_x", 0.0)),
                "shift_y": float(e.custom_data.get("radar_shift_y", 0.0)),
                "selected_ids": e.custom_data.get("radar_selected_ids"),
            }
            if cfg["selected_ids"] is None:
                try:
                    from ..melsave_builder import _radar_select_all_ids
                    cfg["selected_ids"] = set(_radar_select_all_ids())
                except Exception:
                    cfg["selected_ids"] = set()

        act = float(cfg["activation"])
        if act < 0.5:
            hits: list[int] = []
        else:
            selected = cfg.get("selected_ids")
            if selected is not None and not isinstance(selected, set):
                selected = set(str(x) for x in selected)
            hits = query_radar_hits(
                world,
                e,
                width=float(cfg["width"]),
                height=float(cfg["height"]),
                shift_x=float(cfg["shift_x"]),
                shift_y=float(cfg["shift_y"]),
                selected_object_ids=selected,
            )

        first = int(hits[0]) if hits else 0
        outs = {
            "entity array": hits,
            "entity": first,
            "trigger": 1.0 if hits else 0.0,
            "activation": act,
        }
        world.gate_output_values[cidx] = outs
        # also by common DataName aliases
        results[cidx] = outs
    return results
