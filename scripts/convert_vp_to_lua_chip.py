"""Convert VP chips to NEW Lua chip objects (objectId 507707712).

Strategy:
1. Load melsave JSON
2. For each oid=248 VP chip:
   a. Parse chip_graph -> compile to Lua source
   b. Create a NEW Lua chip object based on the real-device template (oid=507707712)
   c. Copy position/rotation/scale/gravity/freezed from the VP chip
   d. Build lua_chip_inputs/outputs from VP chip_inputs/outputs
   e. Build mechanicData with correct mechanicSerializedInputs/Outputs
   f. Preserve constraints/distJoints/hingeJoints (connections to other objects)
   g. Replace the VP chip container with the new Lua chip container
3. Write modified melsave
"""
from __future__ import annotations

import json
import zipfile
import copy
import os
import time
from typing import Any


# GateDataType -> LuaValue.ValueType
GATE_TO_LUA_TYPE: dict[str, int] = {
    "Entity": 6,
    "Number": 1,
    "String": 3,
    "Vector": 4,
    "Color": 5,
    "IntegerNumber": 2,
    "ArrayNumber": 7,
    "ArrayString": 7,
    "ArrayVector": 7,
    "ArrayEntity": 7,
}

# GateDataType -> Type int (for mechanicSerializedInputs/Outputs DataType field)
GATE_TO_TYPE_INT: dict[str, int] = {
    "Entity": 1,
    "Number": 2,
    "String": 4,
    "Vector": 8,
    "Color": 24,
    "IntegerNumber": 32,
    "ArrayNumber": 128,
    "ArrayString": 256,
    "ArrayVector": 512,
    "ArrayEntity": 1024,
}


def _make_lua_value(gate_type: str, serialized_value: str | None) -> dict[str, Any]:
    """Create a LuaValue dict from VP GateDataType + SerializedValue."""
    lv_type = GATE_TO_LUA_TYPE.get(gate_type, 1)
    lv: dict[str, Any] = {
        "Type": lv_type,
        "NumberValue": 0.0,
        "IntegerValue": 0,
        "StringValue": None,
        "VectorValue": {"x": 0.0, "y": 0.0, "z": 0.0, "w": 0.0},
        "ArrayValue": None,
    }
    if serialized_value:
        try:
            sv = json.loads(serialized_value)
        except (json.JSONDecodeError, TypeError):
            return lv
        if lv_type == 1:  # Number
            lv["NumberValue"] = float(sv.get("Value", 0.0))
        elif lv_type == 2:  # Integer
            lv["IntegerValue"] = int(sv.get("Value", 0))
        elif lv_type == 3:  # String
            lv["StringValue"] = str(sv.get("Value", ""))
        elif lv_type == 4:  # Vector
            v = sv.get("Value", {})
            lv["VectorValue"] = {
                "x": float(v.get("x", 0)),
                "y": float(v.get("y", 0)),
                "z": float(v.get("z", 0)),
                "w": float(v.get("w", 0)),
            }
        elif lv_type == 5:  # Color
            v = sv.get("Value", {})
            lv["VectorValue"] = {
                "x": float(v.get("x", 0)),
                "y": float(v.get("y", 0)),
                "z": float(v.get("z", 0)),
                "w": float(v.get("w", 1)),
            }
    return lv


def _convert_vp_inputs_to_lua(vp_inputs: list[dict]) -> list[dict]:
    """Convert VP chip_inputs to lua_chip_inputs format (excluding system keys).
    Gate names are preserved as-is (may contain spaces like "input 1"); the
    codegen uses bracket notation (inputs.num["input 1"]) to access them."""
    lua_inputs = []
    for inp in vp_inputs:
        key = inp.get("Key", "")
        if key in SYSTEM_INPUT_KEYS:
            continue
        gate_type = inp.get("GateDataType", "Number")
        sv = inp.get("SerializedValue")
        type_int = GATE_TO_TYPE_INT.get(gate_type, 2)
        lua_value = _make_lua_value(gate_type, sv)
        lua_inputs.append({
            "Name": key,
            "Type": type_int,
            "LuaValue": lua_value,
        })
    return lua_inputs


def _convert_vp_outputs_to_lua(vp_outputs: list[dict]) -> list[dict]:
    """Convert VP chip_outputs to lua_chip_outputs format (excluding system keys).
    Gate names are preserved as-is (may contain spaces like "input 2"); the
    codegen uses bracket notation (outputs.num["input 2"]) to access them."""
    lua_outputs = []
    for out in vp_outputs:
        key = out.get("Key", "")
        if key in SYSTEM_OUTPUT_KEYS:
            continue
        gate_type = out.get("GateDataType", "Number")
        sv = out.get("SerializedValue")
        type_int = GATE_TO_TYPE_INT.get(gate_type, 2)
        lua_value = _make_lua_value(gate_type, sv)
        lua_outputs.append({
            "Name": key,
            "Type": type_int,
            "LuaValue": lua_value,
        })
    return lua_outputs


# System gate keys that exist on every Lua chip but are NOT in lua_chip_inputs/outputs
# (they are filtered by LuaChip.InputSystemKeys / OutputSystemKeys)
SYSTEM_INPUT_KEYS = {"activation"}
SYSTEM_OUTPUT_KEYS = {
    "entity", "activation", "tick", "status", "total_ticks",
    "time", "entities", "info", "pointer", "clicked",
}

# Fixed system outputs that every Lua chip has (from real-device template)
SYSTEM_OUTPUTS_TEMPLATE = [
    ("entity", 1, None),
    ("activation", 2, json.dumps({"Value": 1.0, "Default": 0.0, "Min": -3.40282347e38, "Max": 3.40282347e38, "IsCheckbox": False})),
    ("tick", 2, json.dumps({"Value": 0.0, "Default": 0.0, "Min": -3.40282347e38, "Max": 3.40282347e38, "IsCheckbox": False})),
    ("status", 4, json.dumps({"IsMultiline": False, "Value": "running", "Default": None, "MaxLength": 2147483647})),
    ("total_ticks", 2, json.dumps({"Value": 0.0, "Default": 0.0, "Min": -3.40282347e38, "Max": 3.40282347e38, "IsCheckbox": False})),
    ("time", 2, json.dumps({"Value": 0.0, "Default": 0.0, "Min": -3.40282347e38, "Max": 3.40282347e38, "IsCheckbox": False})),
    ("entities", 2, json.dumps({"Value": 0.0, "Default": 0.0, "Min": -3.40282347e38, "Max": 3.40282347e38, "IsCheckbox": False})),
    ("info", 4, json.dumps({"IsMultiline": False, "Value": "", "Default": None, "MaxLength": 2147483647})),
    ("pointer", 8, None),
    ("clicked", 1, None),
]


def _build_mechanic_data(
    lua_inputs: list[dict],
    lua_outputs: list[dict],
    vp_mechanic_data: list[dict] | None = None,
) -> list[dict]:
    """Build mechanicData from lua_chip_inputs/outputs.

    mechanicSerializedInputs = [activation gate] + user inputs
    mechanicSerializedOutputs = [entity, activation, tick, status, total_ticks,
                                  time, entities, info, pointer, clicked] + user outputs
    System gates are always present; user gates are appended after.

    If vp_mechanic_data is provided, user input/output GateData (which holds the
    user-set Value, Default, Min, Max) is copied from the original VP chip's
    mechanicSerializedInputs/Outputs by matching Key. Without this, user-tuned
    values (PID gains, activation thresholds, target positions) are lost and
    default to 0.0, breaking chip behavior.
    """
    _ACTIVATION_GATE = json.dumps(
        {"Value": 1.0, "Default": 0.0, "Min": -3.40282347e38, "Max": 3.40282347e38, "IsCheckbox": False}
    )

    # Index original VP chip's mechanicSerializedInputs/Outputs by Key for GateData lookup
    vp_msi_by_key: dict[str, dict] = {}
    vp_mso_by_key: dict[str, dict] = {}
    if vp_mechanic_data:
        vp_md0 = vp_mechanic_data[0] if vp_mechanic_data else {}
        vp_msi_raw = vp_md0.get("mechanicSerializedInputs", "[]")
        vp_mso_raw = vp_md0.get("mechanicSerializedOutputs", "[]")
        vp_msi = json.loads(vp_msi_raw) if isinstance(vp_msi_raw, str) else (vp_msi_raw or [])
        vp_mso = json.loads(vp_mso_raw) if isinstance(vp_mso_raw, str) else (vp_mso_raw or [])
        for entry in vp_msi:
            k = entry.get("Key")
            if k:
                vp_msi_by_key[k] = entry
        for entry in vp_mso:
            k = entry.get("Key")
            if k:
                vp_mso_by_key[k] = entry

    # Build mechanicSerializedInputs: activation + user inputs
    msi = [{
        "Key": "activation",
        "DataType": 2,
        "DataName": "activation",
        "CanBeEdit": True,
        "GateData": _ACTIVATION_GATE,
        "GroupId": None,
        "Group": 0,
        "GroupName": None,
    }]
    for inp in lua_inputs:
        if inp["Name"] in SYSTEM_INPUT_KEYS:
            continue
        # Preserve original VP chip's GateData (holds user-set Value) if available
        vp_entry = vp_msi_by_key.get(inp["Name"])
        gate_data = vp_entry.get("GateData") if vp_entry else None
        msi.append({
            "Key": inp["Name"],
            "DataType": inp["Type"],
            "DataName": inp["Name"],
            "CanBeEdit": True,
            "GateData": gate_data,
            "GroupId": None,
            "Group": 0,
            "GroupName": None,
        })

    # Build mechanicSerializedOutputs: system outputs + user outputs
    mso = []
    for name, dtype, gate_data in SYSTEM_OUTPUTS_TEMPLATE:
        mso.append({
            "Key": name,
            "DataType": dtype,
            "DataName": name,
            "CanBeEdit": True,
            "GateData": gate_data,
            "GroupId": None,
            "Group": 0,
            "GroupName": None,
        })
    for out in lua_outputs:
        if out["Name"] in SYSTEM_OUTPUT_KEYS:
            continue
        # Preserve original VP chip's GateData if available
        vp_entry = vp_mso_by_key.get(out["Name"])
        gate_data = vp_entry.get("GateData") if vp_entry else None
        mso.append({
            "Key": out["Name"],
            "DataType": out["Type"],
            "DataName": out["Name"],
            "CanBeEdit": True,
            "GateData": gate_data,
            "GroupId": None,
            "Group": 0,
            "GroupName": None,
        })

    return [{
        "activationInput": 1.0,
        "floatParameters": [1.0, 0.0],
        "mechanicSerializedInputs": json.dumps(msi, separators=(",", ":")),
        "mechanicSerializedOutputs": json.dumps(mso, separators=(",", ":")),
    }]


def _make_metadata() -> dict[str, Any]:
    return {
        "ApiVersion": 1,
        "PreambleVersion": 1,
        "BackendType": "LuaCSharp",
        "BackendVersion": "1.0.0",
        "AppVersion": "36.0",
        "SavedAtUnixSeconds": int(time.time()),
        "Extras": {},
    }


def _make_visual_name() -> str:
    return json.dumps({
        "Title": "",
        "TitleVisibilityType": 4,
        "TitleColor": {"x": 1.0, "y": 1.0, "z": 1.0, "w": 1.0},
        "TitleFontType": 0,
    })


def _make_meta_entry(key: str, string_value: str | None = None, int_value: int | None = None) -> dict:
    entry = {
        "key": key,
        "boolValue": False,
        "stringValue": string_value,
        "intValue": int_value if int_value is not None else 0,
        "floatValue": 0.0,
        "vector2Value": {"x": 0.0, "y": 0.0},
        "vector3Value": {"x": 0.0, "y": 0.0, "z": 0.0},
        "vector4Value": {"x": 0.0, "y": 0.0, "z": 0.0, "w": 0.0},
    }
    return entry


def _find_meta(sm_list: list[dict], key: str) -> dict | None:
    for m in sm_list:
        if m.get("key") == key:
            return m
    return None


# Real-device Lua chip objectId
LUA_CHIP_OBJECT_ID = 507707712


def _create_new_lua_chip_object(vp_so: dict, graph: Any, lua_source: str, chip_index: int) -> dict:
    """Create a brand new Lua chip SaveObject based on the real-device template,
    copying physical properties and connections from the VP chip.
    """
    sm = vp_so.get("saveMetaDatas", [])

    # Extract VP chip metadata
    tps = 30
    tps_meta = _find_meta(sm, "chip_tps")
    if tps_meta and tps_meta.get("intValue"):
        tps = tps_meta["intValue"]

    priority = 0
    pri_meta = _find_meta(sm, "chip_priority")
    if pri_meta and pri_meta.get("intValue") is not None:
        priority = pri_meta["intValue"]

    chip_id = ""
    id_meta = _find_meta(sm, "chip_id")
    if id_meta and id_meta.get("stringValue"):
        chip_id = id_meta["stringValue"]

    visual_name = ""
    vn_meta = _find_meta(sm, "chip_visual_name")
    if vn_meta and vn_meta.get("stringValue"):
        visual_name = vn_meta["stringValue"]

    # Parse VP inputs/outputs
    vp_inputs = []
    inp_meta = _find_meta(sm, "chip_inputs")
    if inp_meta and inp_meta.get("stringValue"):
        try:
            vp_inputs = json.loads(inp_meta["stringValue"])
        except json.JSONDecodeError:
            pass

    vp_outputs = []
    out_meta = _find_meta(sm, "chip_outputs")
    if out_meta and out_meta.get("stringValue"):
        try:
            vp_outputs = json.loads(out_meta["stringValue"])
        except json.JSONDecodeError:
            pass

    vp_variables = "[]"
    var_meta = _find_meta(sm, "chip_variables")
    if var_meta and var_meta.get("stringValue"):
        vp_variables = var_meta["stringValue"]

    # Convert inputs/outputs
    lua_inputs = _convert_vp_inputs_to_lua(vp_inputs)
    lua_outputs = _convert_vp_outputs_to_lua(vp_outputs)

    # Build new saveMetaDatas
    new_sm = [
        _make_meta_entry("lua_chip_id", string_value=chip_id),
        _make_meta_entry("lua_chip_source", string_value=lua_source),
        _make_meta_entry("lua_chip_inputs", string_value=json.dumps(lua_inputs)),
        _make_meta_entry("lua_chip_outputs", string_value=json.dumps(lua_outputs)),
        _make_meta_entry("lua_chip_variables", string_value=vp_variables),
        _make_meta_entry("lua_chip_tps", int_value=tps),
        _make_meta_entry("lua_chip_priority", int_value=priority),
        _make_meta_entry("lua_chip_instruction_cost", int_value=0),
        _make_meta_entry("lua_chip_visual_name", string_value=_make_visual_name()),
        _make_meta_entry("lua_chip_metadata", string_value=json.dumps(_make_metadata())),
    ]

    # Build new Lua chip SaveObject: copy ALL fields from VP chip, then override
    new_so = copy.deepcopy(vp_so)
    new_so["objectId"] = LUA_CHIP_OBJECT_ID
    # modedObjectId MUST stay empty string (real Lua chip has empty modedObjectId)
    new_so["modedObjectId"] = ""
    # originLocalId should be 0 (not None) to match real Lua chip format
    if new_so.get("originLocalId") is None:
        new_so["originLocalId"] = 0
    new_so["saveMetaDatas"] = new_sm
    new_so["mechanicData"] = _build_mechanic_data(lua_inputs, lua_outputs, vp_so.get("mechanicData"))

    # position/rotation/scale/gravity/freezed are already copied via deepcopy
    # constraints/distJoints/hingeJoints are already copied via deepcopy
    # NOTE: constraint mechCon gate names are fixed in convert_melsave_vp_to_lua()
    # after ALL chips are converted, because constraints connect chips to other
    # objects and both sides' gate names must be renamed consistently.

    print("  Converted chip {}: {} nodes, {} inputs, {} outputs, {} lines Lua".format(
        chip_index, len(graph.nodes), len(lua_inputs), len(lua_outputs), lua_source.count("\n") + 1))
    return new_so


def convert_melsave_vp_to_lua(input_path: str, output_path: str) -> int:
    """Convert all VP chips to NEW Lua chip objects. Returns count."""
    from melon_lua.vpcompile.graph import parse_chip_graph
    from melon_lua.vpcompile.codegen import generate_lua

    with zipfile.ZipFile(input_path, "r") as zf:
        data = json.loads(zf.read("Data"))

    converted = 0
    containers = data.get("saveObjectContainers", [])
    for i, cont in enumerate(containers):
        so = cont.get("saveObjects", {})
        sm = so.get("saveMetaDatas", [])
        has_chip_graph = any(m.get("key") == "chip_graph" for m in sm)
        if not has_chip_graph:
            continue

        print("Converting container {} oid={} instanceId={}...".format(
            i, so.get("objectId"), so.get("instanceId")))

        # Parse and compile chip graph
        graph_meta = _find_meta(sm, "chip_graph")
        if not graph_meta:
            continue
        graph_str = graph_meta.get("stringValue", "") or ""
        try:
            graph_json = json.loads(graph_str) if isinstance(graph_str, str) else graph_str
            graph = parse_chip_graph(graph_json)
        except Exception as e:
            print("  ERROR parsing chip_graph: {}".format(e))
            continue

        # Get TPS for codegen
        tps = 30
        tps_meta = _find_meta(sm, "chip_tps")
        if tps_meta and tps_meta.get("intValue"):
            tps = tps_meta["intValue"]

        # Get chip_variables (user-set variable values) for codegen
        chip_variables_str = ""
        var_meta = _find_meta(sm, "chip_variables")
        if var_meta and var_meta.get("stringValue"):
            chip_variables_str = var_meta["stringValue"]

        try:
            lua_source = generate_lua(graph, chip_meta={
                "instanceId": so.get("instanceId", 0),
                "tps": tps,
                "chip_variables": chip_variables_str,
            })
        except Exception as e:
            print("  ERROR compiling chip_graph: {}".format(e))
            continue

        # Create new Lua chip object, replacing the VP chip
        new_so = _create_new_lua_chip_object(so, graph, lua_source, converted)
        cont["saveObjects"] = new_so
        converted += 1

    # NOTE: constraint mechCon gate names are preserved as-is (raw, with spaces).
    # The real device's LuaChip uses the raw gate Name as the inputs/outputs table
    # key, and the codegen emits bracket notation (inputs.num["input 1"]) to
    # access gates with spaces. So constraints, mechanicSerializedInputs/Outputs
    # Keys, and lua_chip_inputs/outputs Names all use the same raw gate name —
    # no transformation needed.

    # Write output melsave
    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
    # Upgrade appVersion to 36.0 to match the Lua chip's expected version
    meta = data.get("MetaData", {}) or data.get("metadata", {})
    # MetaData might be in the Data JSON or a separate zip entry; check both
    if "MetaData" not in data:
        # MetaData is a separate zip entry; we'll handle it below
        pass
    else:
        if data.get("MetaData", {}).get("appVersion"):
            data["MetaData"]["appVersion"] = "36.0"

    with zipfile.ZipFile(output_path, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("Data", json.dumps(data))
        with zipfile.ZipFile(input_path, "r") as zf_in:
            for item in zf_in.infolist():
                if item.filename == "Data":
                    continue
                content = zf_in.read(item.filename)
                if item.filename == "MetaData":
                    try:
                        m = json.loads(content)
                        m["appVersion"] = "36.0"
                        content = json.dumps(m).encode()
                    except (json.JSONDecodeError, UnicodeDecodeError):
                        pass
                zf.writestr(item, content)

    print("\nConverted {} VP chips to Lua chips (objectId={})".format(converted, LUA_CHIP_OBJECT_ID))
    print("Output: {}".format(output_path))
    return converted


if __name__ == "__main__":
    import sys
    inp = sys.argv[1] if len(sys.argv) > 1 else "temp/xj11/xj 11(1).melsave"
    outp = sys.argv[2] if len(sys.argv) > 2 else "temp/xj11_lua.melsave"
    convert_melsave_vp_to_lua(inp, outp)
