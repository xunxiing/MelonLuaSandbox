#!/usr/bin/env python3
"""Build xj11 rocket save by cloning the real 2297.melsave Lua chip template.

Strategy: load 2297.melsave (verified working on real device), deep-copy the
Lua chip saveObjects, then modify:
  - lua_chip_source: our rocket controller source
  - lua_chip_inputs/outputs: our gate definitions
  - mechanicSerializedInputs/Outputs: matching gates
  - constraints: point to rocket body + engines

This preserves ALL the real-device-required fields (saveMetaData entry shape,
LuaValue shape, constraint fields, etc.) that a hand-built JSON would miss.
"""
from __future__ import annotations

import copy
import json
import sys
import uuid
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def load_template_save() -> dict:
    """Load 2297.melsave as template (verified working on real device)."""
    p = ROOT / "temp" / "2297.melsave"
    with zipfile.ZipFile(p, "r") as zf:
        return json.loads(zf.read("Data").decode("utf-8"))


def load_xj11_save() -> dict:
    """Load original xj11 save for non-chip objects."""
    p = ROOT / "temp" / "xj11" / "xj 11(1).melsave"
    with zipfile.ZipFile(p, "r") as zf:
        return json.loads(zf.read("Data").decode("utf-8"))


def load_meta_icon(path: Path) -> tuple[dict | None, bytes | None]:
    with zipfile.ZipFile(path, "r") as zf:
        meta = None
        icon = None
        if "MetaData" in zf.namelist():
            md = zf.read("MetaData")
            if md:
                meta = json.loads(md.decode("utf-8"))
        if "Icon" in zf.namelist():
            icon = zf.read("Icon")
    return meta, icon


def make_lua_value(value_type: int) -> dict:
    """Build a complete LuaValue dict matching real-device structure."""
    return {
        "Type": value_type,
        "NumberValue": 0.0,
        "IntegerValue": 0,
        "StringValue": None,
        "VectorValue": {"x": 0.0, "y": 0.0, "z": 0.0, "w": 0.0,
                         "magnitude": 0.0, "sqrMagnitude": 0.0},
        "ArrayValue": None,
    }


def make_io_entry(name: str, type_id: int, lua_value_type: int,
                  can_be_changed: bool = True) -> dict:
    """Build a lua_chip_inputs/outputs entry."""
    return {
        "Name": name,
        "Type": type_id,
        "LuaValue": make_lua_value(lua_value_type),
        "CanBeChanged": can_be_changed,
    }


def make_save_meta_entry(key: str, string_value: str = "",
                         int_value: int = 0, bool_value: bool = False) -> dict:
    """Build a complete saveMetaDatas entry with ALL required fields."""
    return {
        "key": key,
        "boolValue": bool_value,
        "stringValue": string_value,
        "intValue": int_value,
        "floatValue": 0.0,
        "vector2Value": {"x": 0.0, "y": 0.0},
        "vector3Value": {"x": 0.0, "y": 0.0, "z": 0.0},
        "vector4Value": {"x": 0.0, "y": 0.0, "z": 0.0, "w": 0.0,
                         "magnitude": 0.0, "sqrMagnitude": 0.0},
        "texture2DValue": None,
    }


def make_gate(key: str, data_type: int, data_name: str | None = None,
              gate_data: str | None = None) -> dict:
    """Build a mechanicSerializedInputs/Outputs entry."""
    return {
        "Key": key,
        "DataType": data_type,
        "DataName": data_name or key,
        "CanBeEdit": True,
        "GateData": gate_data,
        "GroupId": None,
        "Group": 0,
        "GroupName": None,
    }


def make_constraint(start_idx: int, end_idx: int,
                    output_id: str, input_id: str,
                    start_pos: tuple = (0.0, 0.0), end_pos: tuple = (0.0, 0.0),
                    name: str = "") -> dict:
    """Build a mechanic gate connection constraint.

    SDK contract for mechanic connections (gate wiring):
    - constraintId is always 13 (mechanic connection type, NOT physics rope kind)
    - mechCon holds the gate wiring: outputID (source gate) -> inputID (target gate)
    - startPoint/endPoint are visual port offsets in object-local space (small values)
    - mainGuid must have IsEmpty:false
    - Constraint is stored on the START object (the one with the output gate)
    - startObjectId/endObjectId are CONTAINER INDICES (not objectId, not localId)
    - Materials default to Paper/Metal (visual rope appearance, irrelevant for mechanic)
    """
    return {
        "mainGuid": {"Value": str(uuid.uuid4()), "IsEmpty": False},
        "constraintId": 13,
        "startPoint": {"x": start_pos[0], "y": start_pos[1], "z": 0.0},
        "endPoint": {"x": end_pos[0], "y": end_pos[1], "z": 0.0},
        "mechCon": {
            "inputID": input_id,
            "outputID": output_id,
            "inputGroup": "",
            "outputGroup": "",
        },
        "distance": 0.0,
        "startObjectId": start_idx,
        "endObjectId": end_idx,
        "linkedRopeGuid": None,
        "constraintName": name,
        "isNameVisible": False,
        "startObjectConnectionMaterial": "Paper",
        "endObjectConnectionMaterial": "Metal",
        "customRope": None,
    }


def build_new_lua_chip(template_chip: dict, position: dict,
                       lua_source: str) -> dict:
    """Clone a real Lua chip template and modify for our use."""
    chip = copy.deepcopy(template_chip)

    # Update position
    chip["position"] = {"x": position["x"], "y": position["y"],
                        "z": 0.000499999849}
    chip["rotation"] = {"x": 0.0, "y": 0.0, "z": 0.0}
    chip["scale"] = {"x": 1.0, "y": 1.0, "z": 1.0}

    # Ensure activation
    chip["freezed"] = False
    chip["isActivationForced"] = False  # real device has False
    chip["isVisible"] = False  # real chip is invisible
    chip["gravity"] = True
    chip["modedObjectId"] = ""

    # Build inputs: target (vec), rocket (entity)
    inputs_list = [
        make_io_entry("target", 8, 4),   # Vector
        make_io_entry("rocket", 1, 6),   # Entity
    ]

    # Build outputs: input 2/3/5/6 (all Number)
    outputs_list = [
        make_io_entry("input 2", 2, 1),
        make_io_entry("input 3", 2, 1),
        make_io_entry("input 5", 2, 1),
        make_io_entry("input 6", 2, 1),
    ]

    # Build saveMetaDatas with complete field structure
    chip["saveMetaDatas"] = [
        make_save_meta_entry("lua_chip_id", str(uuid.uuid4())),
        make_save_meta_entry("lua_chip_source", lua_source),
        make_save_meta_entry("lua_chip_inputs", json.dumps(inputs_list)),
        make_save_meta_entry("lua_chip_outputs", json.dumps(outputs_list)),
        make_save_meta_entry("lua_chip_variables", "[]"),
        make_save_meta_entry("lua_chip_tps", int_value=60),
        make_save_meta_entry("lua_chip_priority", int_value=0),
        make_save_meta_entry("lua_chip_instruction_cost", int_value=5000),
        make_save_meta_entry("lua_chip_visual_name",
                             json.dumps({"Title": "Rocket Controller",
                                         "TitleVisibilityType": 4,
                                         "TitleColor": {"x": 1.0, "y": 1.0, "z": 1.0, "w": 1.0,
                                                         "normalized": {"x": 0.5, "y": 0.5, "z": 0.5, "w": 0.5,
                                                                         "magnitude": 1.0, "sqrMagnitude": 1.0},
                                                         "magnitude": 2.0, "sqrMagnitude": 4.0},
                                         "TitleFontType": 0})),
        make_save_meta_entry("lua_chip_metadata",
                             json.dumps({"ApiVersion": 1, "PreambleVersion": 1,
                                         "BackendType": "LuaCSharp",
                                         "BackendVersion": "1.0.0",
                                         "AppVersion": "36.0",
                                         "SavedAtUnixSeconds": 1782026752,
                                         "Extras": {}})),
    ]

    # Build mechanicData
    # System inputs: activation
    sys_in = [make_gate("activation", 2, "activation",
                        '{"Value":1.0,"Default":0.0,"Min":-3.40282347E+38,"Max":3.40282347E+38,"IsCheckbox":false}')]
    # User inputs
    user_in = [
        make_gate("target", 8, "target"),
        make_gate("rocket", 1, "rocket"),
    ]
    # System outputs
    sys_out_keys = ["entity", "activation", "tick", "status", "total_ticks",
                    "time", "entities", "info", "pointer", "clicked"]
    sys_out = [make_gate(k, 2, k) for k in sys_out_keys]
    # User outputs
    user_out = [make_gate("input 2", 2, "input 2"),
                make_gate("input 3", 2, "input 3"),
                make_gate("input 5", 2, "input 5"),
                make_gate("input 6", 2, "input 6")]

    chip["mechanicData"] = [{
        "activationInput": 1.0,
        "floatParameters": [1.0],
        "mechanicSerializedInputs": json.dumps(sys_in + user_in),
        "mechanicSerializedOutputs": json.dumps(sys_out + user_out),
    }]

    # Clear joints and constraints (will be added separately)
    chip["hingeJoints"] = []
    chip["distJoints"] = []
    chip["constraints"] = []

    return chip


def build_new_save(output_path: str):
    """Build new save with single Lua chip replacing 6 VP chips."""
    from melon_lua.melsave_writer import write_melsave, connect_gates

    template_data = load_template_save()
    xj11_data = load_xj11_save()

    # Get the real Lua chip template from 2297.melsave
    template_chip = None
    for cont in template_data["saveObjectContainers"]:
        so = cont.get("saveObjects", {})
        if so.get("objectId") == 507707712:
            template_chip = so
            break
    if not template_chip:
        raise ValueError("No Lua chip template in 2297.melsave")

    xj11_containers = xj11_data["saveObjectContainers"]
    vp_indices = {4, 7, 8, 9, 11, 12}

    # Calculate center position of VP chips
    positions = []
    for i in vp_indices:
        pos = xj11_containers[i]["saveObjects"].get("position", {})
        positions.append((pos.get("x", 0), pos.get("y", 0)))
    avg_x = sum(p[0] for p in positions) / len(positions)
    avg_y = sum(p[1] for p in positions) / len(positions)

    # Build new containers: keep non-VP, add new chip
    new_containers = []
    old_to_new = {}
    for i, cont in enumerate(xj11_containers):
        if i in vp_indices:
            continue
        old_to_new[i] = len(new_containers)
        new_containers.append(cont)

    # Load rocket controller source
    src_path = ROOT / "temp" / "rocket_controller.lua"
    with open(src_path, "r", encoding="utf-8") as f:
        lua_source = f.read()

    # Create new Lua chip
    new_chip = build_new_lua_chip(template_chip, {"x": avg_x, "y": avg_y},
                                  lua_source)
    new_chip_idx = len(new_containers)
    new_containers.append({"saveObjects": new_chip, "saveObjectChildren": []})

    # Remove old MECHANIC constraints from kept objects (pointed to VP chips),
    # but PRESERVE physical constraints (constraintId=10, mechCon=None) like
    # engine-to-rocket-body ropes/joints.
    for old_i in [0, 5, 6, 10]:
        ni = old_to_new[old_i]
        so = new_containers[ni]["saveObjects"]
        old_cs = so.get("constraints", []) or []
        so["constraints"] = [c for c in old_cs if c.get("mechCon") is None]

    # Fix physical constraint container indices (VP chips removed, shifted)
    for old_i in [0, 5, 6, 10]:
        ni = old_to_new[old_i]
        so = new_containers[ni]["saveObjects"]
        for c in so.get("constraints", []) or []:
            s = c.get("startObjectId")
            e = c.get("endObjectId")
            if s in old_to_new:
                c["startObjectId"] = old_to_new[s]
            if e in old_to_new:
                c["endObjectId"] = old_to_new[e]

    xj11_data["saveObjectContainers"] = new_containers

    # Wire mechanic gate connections using the SDK
    # UI controller -> new chip: target position
    connect_gates(xj11_data, old_to_new[0], "Dot worlds position",
                  new_chip_idx, "target",
                  name="target position",
                  start_point=(0.02, -0.11), end_point=(0.03, -0.07))
    # Rocket body -> new chip: rocket entity
    connect_gates(xj11_data, old_to_new[5], "entity",
                  new_chip_idx, "rocket",
                  name="rocket entity",
                  start_point=(1.04, -0.06), end_point=(-0.02, 0.01))
    # New chip -> right engine: force + activation
    connect_gates(xj11_data, new_chip_idx, "input 2",
                  old_to_new[10], "force",
                  name="right engine force",
                  start_point=(0.05, -0.03), end_point=(0.01, -0.08))
    connect_gates(xj11_data, new_chip_idx, "input 6",
                  old_to_new[10], "activation",
                  name="right engine activation",
                  start_point=(-0.09, 0.06), end_point=(-0.03, -0.25))
    # New chip -> left engine: force + activation
    connect_gates(xj11_data, new_chip_idx, "input 3",
                  old_to_new[6], "force",
                  name="left engine force",
                  start_point=(0.06, -0.02), end_point=(0.04, -0.15))
    connect_gates(xj11_data, new_chip_idx, "input 5",
                  old_to_new[6], "activation",
                  name="left engine activation",
                  start_point=(-0.06, -0.03), end_point=(-0.01, -0.17))

    # Update MetaData
    meta, icon = load_meta_icon(Path(ROOT / "temp" / "2297.melsave"))
    if meta:
        meta["appVersion"] = "36.0"
        meta["mapName"] = "EndlessCity"

    write_melsave(output_path, xj11_data, meta, icon)

    print(f"Created {output_path}")
    print(f"  Containers: {len(new_containers)} (was {len(xj11_containers)})")
    print(f"  New chip at container {new_chip_idx}, pos=({avg_x:.2f}, {avg_y:.2f})")


if __name__ == "__main__":
    output_path = str(ROOT / "temp" / "xj11_new.melsave")
    build_new_save(output_path)
