"""High-level builder for Melon Playground .melsave files (from scratch).

Unlike `MelsaveSession` (which patches an existing save via world diff), this
builder constructs a save **programmatically**: spawn items, add Lua chips,
wire gates, and export — all verified against the real-device save format.

Based on reverse-engineering of `1132luaexample.melsave` (verified working on
real device: item + Lua chip + gate connection).

Typical usage:

    from melon_lua import MelsaveBuilder

    b = MelsaveBuilder()
    item = b.add_item(202, x=0.5, y=0.03, color=(0, 1, 0.3, 1))
    chip = b.add_lua_chip(lua_source, x=-0.5, y=-0.03,
                          inputs=[{"name": "target", "type": "entity"}],
                          outputs=[{"name": "tick", "type": "number"},
                                   {"name": "status", "type": "string"}])
    b.connect(item, "entity", chip, "target", name="entity target")
    b.save("output.melsave")
"""
from __future__ import annotations

import copy
import json
import uuid
import zipfile
from pathlib import Path
from typing import Any, Literal

from .melsave_writer import write_melsave, connect_gates, MECHANIC_CONSTRAINT_ID

# ---------------------------------------------------------------------------
# Gate type system
# ---------------------------------------------------------------------------

# Gate DataType (used in mechanicSerializedInputs/Outputs)
GATE_ENTITY = 1
GATE_NUMBER = 2
GATE_STRING = 4
GATE_VECTOR = 8
GATE_INTEGER = 32
GATE_ARRAY_NUMBER = 128
GATE_ARRAY_STRING = 256
GATE_ARRAY_VECTOR = 512
GATE_ENTITY_ARRAY = 1024

# lua_chip_inputs/outputs Type (same as gate DataType for most)
# lua_chip_inputs/outputs LuaValue.Type (different enum)
LUAVAL_NUMBER = 1
LUAVAL_INTEGER = 2
LUAVAL_STRING = 3
LUAVAL_VECTOR = 4
LUAVAL_COLOR = 5
LUAVAL_ENTITY = 6
LUAVAL_ARRAY = 7

# String alias → (GateDataType, LuaValue.Type)
_TYPE_MAP: dict[str, tuple[int, int]] = {
    "entity": (GATE_ENTITY, LUAVAL_ENTITY),
    "number": (GATE_NUMBER, LUAVAL_NUMBER),
    "num": (GATE_NUMBER, LUAVAL_NUMBER),
    "string": (GATE_STRING, LUAVAL_STRING),
    "str": (GATE_STRING, LUAVAL_STRING),
    "vector": (GATE_VECTOR, LUAVAL_VECTOR),
    "vec": (GATE_VECTOR, LUAVAL_VECTOR),
    "int": (GATE_INTEGER, LUAVAL_INTEGER),
    "integer": (GATE_INTEGER, LUAVAL_INTEGER),
    "array_num": (GATE_ARRAY_NUMBER, LUAVAL_ARRAY),
    "array_number": (GATE_ARRAY_NUMBER, LUAVAL_ARRAY),
    "array_string": (GATE_ARRAY_STRING, LUAVAL_ARRAY),
    "array_str": (GATE_ARRAY_STRING, LUAVAL_ARRAY),
    "array_vec": (GATE_ARRAY_VECTOR, LUAVAL_ARRAY),
    "array_vector": (GATE_ARRAY_VECTOR, LUAVAL_ARRAY),
    "array_entity": (GATE_ENTITY_ARRAY, LUAVAL_ARRAY),
}

# System gates that every chip has (auto-added)
_SYS_INPUT_GATES = [
    {"name": "activation", "type": "number", "value": 1.0},
]
_SYS_OUTPUT_GATES = [
    {"name": "entity", "type": "entity"},
    {"name": "activation", "type": "number", "value": 1.0},
    {"name": "tick", "type": "number", "value": 0.0},
    {"name": "status", "type": "string", "value": ""},
]

# ---------------------------------------------------------------------------
# Default MetaData
# ---------------------------------------------------------------------------

_DEFAULT_META: dict[str, Any] = {
    "UniqueId": "",  # filled at save time
    "icon": {"AssetId": "Icon", "CanBeNull": False},
    "metadata": {"ManifestId": "", "Name": ""},
    "versionId": 7,
    "appVersion": "36.0",
    "mapName": "Default",
    "CustomMapChangesVersion": 0,
    "seed": -1,
    "timeScale": 1.0,
    "category": "video",
    "CategoryValidated": "video",
}

# ---------------------------------------------------------------------------
# Helpers for building saveObjects sub-structures
# ---------------------------------------------------------------------------

_FLOAT_MAX = 3.40282347e38


def _make_lua_value(lv_type: int, **kw) -> dict:
    """Build a complete LuaValue dict."""
    v: dict[str, Any] = {
        "Type": lv_type,
        "NumberValue": kw.get("number_value", 0.0),
        "IntegerValue": kw.get("integer_value", 0),
        "StringValue": kw.get("string_value", None),
        "VectorValue": {
            "x": 0.0, "y": 0.0, "z": 0.0, "w": 0.0,
            "magnitude": 0.0, "sqrMagnitude": 0.0,
        },
        "ArrayValue": None,
    }
    return v


def _make_meta_entry(key: str, *, string_value: str | None = None,
                     int_value: int = 0, bool_value: bool = False) -> dict:
    """Build a complete saveMetaDatas entry (9 fields)."""
    return {
        "key": key,
        "boolValue": bool_value,
        "stringValue": string_value,
        "intValue": int_value,
        "floatValue": 0.0,
        "vector2Value": {"x": 0.0, "y": 0.0},
        "vector3Value": {"x": 0.0, "y": 0.0, "z": 0.0},
        "vector4Value": {
            "x": 0.0, "y": 0.0, "z": 0.0, "w": 0.0,
            "magnitude": 0.0, "sqrMagnitude": 0.0,
        },
        "texture2DValue": None,
    }


def _number_gate_data(value: float = 0.0) -> str:
    return json.dumps({
        "Value": value, "Default": 0.0,
        "Min": -_FLOAT_MAX, "Max": _FLOAT_MAX,
        "IsCheckbox": False,
    }, separators=(",", ":"))


def _integer_gate_data(value: int = 32, min_v: float = 1.0,
                       max_v: float = 256.0) -> str:
    """IntegerNumber gate (matches real LED width/height GateData)."""
    v = float(value)
    return json.dumps({
        "Value": v, "Default": v,
        "Min": min_v, "Max": max_v,
        "DropdownOptions": None,
        "DropdownOptionsLocalizationKey": None,
    }, separators=(",", ":"))


def _array_gate_data() -> str:
    return json.dumps({"Value": None, "Default": None}, separators=(",", ":"))


def _string_gate_data(value: str = "") -> str:
    return json.dumps({
        "IsMultiline": False, "Value": value,
        "Default": None, "MaxLength": 2147483647,
    }, separators=(",", ":"))


def _make_mech_gate(key: str, data_type: int,
                    gate_data: str | None = None) -> dict:
    """Build a mechanicSerializedInputs/Outputs entry."""
    return {
        "Key": key,
        "DataType": data_type,
        "DataName": key,
        "CanBeEdit": True,
        "GateData": gate_data,
        "GroupId": None,
        "Group": 0,
        "GroupName": None,
    }


def _resolve_type(type_alias: str) -> tuple[int, int]:
    """Resolve a type alias string to (GateDataType, LuaValueType)."""
    key = type_alias.lower().strip()
    if key not in _TYPE_MAP:
        raise ValueError(
            f"Unknown type '{type_alias}'. Valid: {sorted(_TYPE_MAP.keys())}"
        )
    return _TYPE_MAP[key]


def _gate_data_for(type_alias: str, value: Any = None) -> str | None:
    """Build GateData JSON string for a gate type."""
    key = type_alias.lower().strip()
    if key in ("int", "integer"):
        return _integer_gate_data(int(value) if value is not None else 32)
    if key in ("number", "num"):
        return _number_gate_data(float(value) if value is not None else 0.0)
    if key in ("string", "str"):
        return _string_gate_data(str(value) if value is not None else "")
    if key in (
        "array_num", "array_number", "array_string", "array_str",
        "array_vec", "array_vector", "array_entity",
    ):
        return _array_gate_data()
    # Entity, Vector, Color → no GateData (connected via wire)
    return None


def _lua_value_for(type_alias: str, value: Any = None) -> dict:
    """Build LuaValue for chip meta, with sensible defaults."""
    gate_type, lv_type = _resolve_type(type_alias)
    key = type_alias.lower().strip()
    if key in ("int", "integer"):
        return _make_lua_value(
            lv_type, integer_value=int(value) if value is not None else 32
        )
    if key in ("number", "num"):
        return _make_lua_value(
            lv_type, number_value=float(value) if value is not None else 0.0
        )
    if key in ("string", "str"):
        return _make_lua_value(
            lv_type, string_value=str(value) if value is not None else ""
        )
    return _make_lua_value(lv_type)


# ---------------------------------------------------------------------------
# Item (spawnable object) template loading
# ---------------------------------------------------------------------------

_ITEM_TEMPLATE_DIR = Path(__file__).parent / "data" / "item_templates"


def _load_item_template(object_id: int) -> dict | None:
    """Load a deep-copied item template by objectId.

    Looks in the vendored data directory first, then falls back to the
    source repo's temp/objectid_templates (for dev convenience).
    """
    for d in (_ITEM_TEMPLATE_DIR,
              Path(__file__).parent.parent / "temp" / "objectid_templates"):
        p = d / f"{object_id}.json"
        if p.exists():
            if d != _ITEM_TEMPLATE_DIR:
                import warnings
                warnings.warn(
                    f"item template loaded from dev fallback {p}; "
                    f"this path does not exist in pip-installed distributions",
                    stacklevel=3,
                )
            with open(p, "r", encoding="utf-8") as f:
                return json.load(f)
    return None


def _summarize_mech_gate(g: dict) -> dict:
    """Compact gate entry for list_item_gates."""
    key = g.get("Key")
    dn = g.get("DataName")
    return {
        "key": key,
        "data_name": dn,
        "name": dn if dn not in (None, "") else key,
        "data_type": g.get("DataType"),
        "can_edit": g.get("CanBeEdit", g.get("CanBeEdited")),
        "group_id": g.get("GroupId"),
        "group": g.get("Group"),
        "group_name": g.get("GroupName"),
    }


def list_item_gates(object_id_or_name) -> dict:
    """Return mechanic input/output gates for a spawnable item template.

    Prefer this over dumping a full saveObjects JSON when an agent only needs
    gate names for ``connect()``.

    Args:
        object_id_or_name: int objectId, or catalog name / Chinese alias
            (resolved via ``object_id_for_name``).

    Returns:
        {
          "object_id": int,
          "name": str | None,
          "inputs": [{"key","data_name","name","data_type",...}, ...],
          "outputs": [...],
          "error": str | None,
        }
    """
    from .catalog import object_id_for_name, get_profile_by_object_id

    oid: int | None
    if isinstance(object_id_or_name, int):
        oid = object_id_or_name
    else:
        s = str(object_id_or_name).strip()
        if s.isdigit() or (s.startswith("-") and s[1:].isdigit()):
            oid = int(s)
        else:
            oid = object_id_for_name(s)

    if oid is None:
        return {
            "object_id": None,
            "name": str(object_id_or_name),
            "inputs": [],
            "outputs": [],
            "error": f"unknown object: {object_id_or_name!r}",
        }

    so = _load_item_template(oid)
    if not so:
        return {
            "object_id": oid,
            "name": None,
            "inputs": [],
            "outputs": [],
            "error": f"no item template for objectId={oid}",
        }

    profile = get_profile_by_object_id(oid) or {}
    name = profile.get("name") if isinstance(profile, dict) else None

    md = so.get("mechanicData")
    inputs: list[dict] = []
    outputs: list[dict] = []
    if isinstance(md, list) and md:
        m0 = md[0] if isinstance(md[0], dict) else {}
        for side, bucket in (
            ("mechanicSerializedInputs", inputs),
            ("mechanicSerializedOutputs", outputs),
        ):
            raw = m0.get(side, "")
            try:
                gates = json.loads(raw) if isinstance(raw, str) and raw else (raw or [])
            except (TypeError, json.JSONDecodeError):
                gates = []
            if isinstance(gates, list):
                for g in gates:
                    if isinstance(g, dict):
                        bucket.append(_summarize_mech_gate(g))

    return {
        "object_id": oid,
        "name": name or so.get("objectId"),
        "inputs": inputs,
        "outputs": outputs,
        "error": None,
    }


# Sensors / displays that should power on when placed via SDK (game stock
# templates often ship activation=0 so they do nothing until wired).
_DEFAULT_ACTIVATION_ON_IDS = frozenset({
    13,          # Ranger / 激光雷达
    261,         # ScreenTextDevice / 文字屏
    596836672,   # LEDMatrixDisplay
    892993856,   # Radar / 区域雷达
})

_RADAR_OBJECT_ID = 892993856
_RADAR_SELECTED_META_KEY = "Radar_selected_entities"
_RADAR_SELECT_ALL_IDS: list[str] | None = None


def _radar_select_all_ids() -> list[str]:
    """ObjectId strings for Radar filter Select-All (game save format)."""
    global _RADAR_SELECT_ALL_IDS
    if _RADAR_SELECT_ALL_IDS is not None:
        return _RADAR_SELECT_ALL_IDS
    path = Path(__file__).parent / "data" / "radar_select_all_ids.json"
    if path.exists():
        with open(path, "r", encoding="utf-8") as f:
            raw = json.load(f)
        if isinstance(raw, list) and raw:
            _RADAR_SELECT_ALL_IDS = [str(x) for x in raw]
            return _RADAR_SELECT_ALL_IDS
    # Fallback: physics catalog keys only (still better than empty []).
    phys = Path(__file__).parent / "data" / "object_physics_by_id.json"
    ids: list[str] = []
    if phys.exists():
        with open(phys, "r", encoding="utf-8") as f:
            data = json.load(f)
        by = data.get("byObjectId") or {}
        ids = [str(k) for k in by.keys()]
    _RADAR_SELECT_ALL_IDS = ids
    return _RADAR_SELECT_ALL_IDS


def _set_mechanic_activation(so: dict, value: float = 1.0) -> None:
    """Set mechanic activationInput + input-gate Value (in-place)."""
    if "activationInput" in so:
        so["activationInput"] = float(value)
    md = so.get("mechanicData")
    if not isinstance(md, list):
        return
    for m in md:
        if not isinstance(m, dict):
            continue
        m["activationInput"] = float(value)
        raw = m.get("mechanicSerializedInputs")
        if not raw:
            continue
        try:
            gates = json.loads(raw) if isinstance(raw, str) else list(raw)
        except (TypeError, json.JSONDecodeError):
            continue
        changed = False
        for g in gates:
            if not isinstance(g, dict):
                continue
            if g.get("Key") != "activation" and (g.get("DataName") or "") != "activation":
                continue
            gd = g.get("GateData")
            if not isinstance(gd, str) or not gd:
                continue
            try:
                data = json.loads(gd)
            except json.JSONDecodeError:
                continue
            data["Value"] = float(value)
            g["GateData"] = json.dumps(data)
            changed = True
        if changed:
            m["mechanicSerializedInputs"] = (
                json.dumps(gates, separators=(",", ":"))
                if isinstance(raw, str)
                else gates
            )


def _set_radar_select_all(so: dict) -> None:
    """Write Radar_selected_entities as full Select-All objectId list.

    Real device: empty stringValue \"[]\" filters out every object. UI Select All
    fills stringValue with a JSON array of objectId strings (boolValue stays
    false). Without this, entity array is always empty on device.
    """
    ids = _radar_select_all_ids()
    payload = json.dumps(ids, ensure_ascii=False, separators=(",", ":"))
    entry = {
        "key": _RADAR_SELECTED_META_KEY,
        "boolValue": False,
        "stringValue": payload,
        "intValue": 0,
        "floatValue": 0.0,
        "vector2Value": {"x": 0.0, "y": 0.0},
        "vector3Value": {"x": 0.0, "y": 0.0, "z": 0.0},
        "vector4Value": {
            "x": 0.0,
            "y": 0.0,
            "z": 0.0,
            "w": 0.0,
            "magnitude": 0.0,
            "sqrMagnitude": 0.0,
        },
        "texture2DValue": None,
    }
    metas = so.get("saveMetaDatas")
    if not isinstance(metas, list):
        so["saveMetaDatas"] = [entry]
        return
    for i, md in enumerate(metas):
        if isinstance(md, dict) and md.get("key") == _RADAR_SELECTED_META_KEY:
            metas[i] = entry
            return
    metas.append(entry)


def _build_item_save_objects(
    object_id: int,
    x: float,
    y: float,
    *,
    z: float = -0.0005,
    rotation: float = 0.0,
    scale_x: float = 1.0,
    scale_y: float = 1.0,
    color: tuple[float, float, float, float] | None = None,
    dynamic: bool = True,
    freezed: bool = False,
    template: dict | None = None,
) -> dict:
    """Build a complete saveObjects dict for a spawnable item."""
    template_dict: dict
    if template is not None:
        template_dict = template
    else:
        template_dict = _load_item_template(object_id)  # type: ignore
    if not template_dict:
        raise ValueError(
            f"No item template found for objectId={object_id}. "
            f"Place a template at melon_lua/data/item_templates/{object_id}.json"
        )
    so = copy.deepcopy(template_dict)
    so["objectId"] = object_id
    so["instanceId"] = -abs(hash((object_id, x, y))) % (2**31) * -1
    so["localId"] = 0
    so["originLocalId"] = 0
    so["parentId"] = -1
    so["position"] = {"x": float(x), "y": float(y), "z": float(z)}
    so["rotation"] = {"x": 0.0, "y": 0.0, "z": float(rotation)}
    so["scale"] = {"x": float(scale_x), "y": float(scale_y), "z": 1.0}
    if color is not None:
        so["color"] = {"r": color[0], "g": color[1], "b": color[2], "a": color[3]}
    so["gravity"] = dynamic
    so["freezed"] = freezed
    so["constraints"] = []
    so["hingeJoints"] = []
    so["distJoints"] = []
    if object_id in _DEFAULT_ACTIVATION_ON_IDS:
        _set_mechanic_activation(so, 1.0)
    if object_id == _RADAR_OBJECT_ID:
        _set_radar_select_all(so)
    return so


# ---------------------------------------------------------------------------
# Chip (Lua chip) builder
# ---------------------------------------------------------------------------

_CHIP_TEMPLATE_PATH = Path(__file__).parent / "data" / "chip_template_1132.json"


def _build_chip_save_objects(
    lua_source: str,
    x: float,
    y: float,
    *,
    z: float = 0.0005,
    inputs: list[dict] | None = None,
    outputs: list[dict] | None = None,
    variables: list[dict] | None = None,
    tps: int = 30,
    priority: int = 0,
    instruction_cost: int = 1000,
    title: str = "",
    template: dict | None = None,
) -> dict:
    """Build a complete saveObjects dict for a Lua chip.

    Args:
        lua_source: The Lua source code.
        x, y: Chip position.
        inputs: List of {"name": str, "type": str, "value": optional} dicts.
            Type aliases: entity/number/string/vector/int.
        outputs: Same format as inputs.
        variables: List of {"name": str, "value": float} for chip_variables.
        tps: Ticks per second (1-60).
        priority: Chip execution priority.
        instruction_cost: Max instructions per tick.
        title: Visual title shown on chip.
        template: Optional pre-loaded chip template dict.
    """
    template_dict: dict
    if template is not None:
        template_dict = template
    elif _CHIP_TEMPLATE_PATH.exists():
        with open(_CHIP_TEMPLATE_PATH, "r", encoding="utf-8") as f:
            template_dict = json.load(f)
    else:
        template_dict = _minimal_chip_template()
    so = copy.deepcopy(template_dict)

    inputs = inputs or []
    outputs = outputs or []
    variables = variables or []

    so["position"] = {"x": float(x), "y": float(y), "z": float(z)}
    so["rotation"] = {"x": 0.0, "y": 0.0, "z": 0.0}
    so["scale"] = {"x": 1.0, "y": 1.0, "z": 1.0}
    so["freezed"] = False
    so["isActivationForced"] = False
    so["isVisible"] = False
    so["constraints"] = []
    so["hingeJoints"] = []
    so["distJoints"] = []

    # --- lua_chip_inputs/outputs (saveMetaDatas) ---
    chip_inputs: list[dict] = []
    for inp in inputs:
        gate_type, _ = _resolve_type(inp["type"])
        is_entity = gate_type == GATE_ENTITY
        chip_inputs.append({
            "Name": inp["name"],
            "Type": gate_type,
            "LuaValue": _lua_value_for(inp["type"], inp.get("value")),
            "CanBeChanged": not is_entity,  # entity inputs are wire-connected
        })

    chip_outputs: list[dict] = []
    for out in outputs:
        gate_type, _ = _resolve_type(out["type"])
        chip_outputs.append({
            "Name": out["name"],
            "Type": gate_type,
            "LuaValue": _lua_value_for(out["type"], out.get("value")),
            "CanBeChanged": True,
        })

    # --- mechanicSerializedInputs/Outputs (mechanicData) ---
    mech_inputs = [_make_mech_gate("activation", GATE_NUMBER,
                                    _number_gate_data(1.0))]
    for inp in inputs:
        gate_type, _ = _resolve_type(inp["type"])
        gd = _gate_data_for(inp["type"], inp.get("value"))
        mech_inputs.append(_make_mech_gate(inp["name"], gate_type, gd))

    # System outputs: entity, activation, tick, status
    mech_outputs = [
        _make_mech_gate("entity", GATE_ENTITY, None),
        _make_mech_gate("activation", GATE_NUMBER, _number_gate_data(1.0)),
        _make_mech_gate("tick", GATE_NUMBER, _number_gate_data(0.0)),
        _make_mech_gate("status", GATE_STRING, _string_gate_data("")),
    ]
    for out in outputs:
        gate_type, _ = _resolve_type(out["type"])
        gd = _gate_data_for(out["type"], out.get("value"))
        # Skip if name collides with system gate
        if out["name"] not in ("entity", "activation", "tick", "status"):
            mech_outputs.append(_make_mech_gate(out["name"], gate_type, gd))

    so["mechanicData"] = [{
        "activationInput": 1.0,
        "floatParameters": [1.0],
        "mechanicSerializedInputs": json.dumps(mech_inputs, ensure_ascii=False,
                                                separators=(",", ":")),
        "mechanicSerializedOutputs": json.dumps(mech_outputs, ensure_ascii=False,
                                                 separators=(",", ":")),
    }]

    # --- chip_variables ---
    var_list = []
    for var in variables:
        var_list.append({
            "Key": var["name"],
            "DataType": 2,
            "GateData": _number_gate_data(float(var.get("value", 0.0))),
        })

    # --- saveMetaDatas ---
    chip_id = str(uuid.uuid4())
    metadata = json.dumps({
        "ApiVersion": 1, "PreambleVersion": 1,
        "BackendType": "LuaCSharp", "BackendVersion": "1.0.0",
        "AppVersion": "36.0",
        "SavedAtUnixSeconds": 0,
        "Extras": {},
    }, separators=(",", ":"))

    visual_name = json.dumps({
        "Title": title,
        "TitleVisibilityType": 4,
        "TitleColor": {
            "x": 1.0, "y": 1.0, "z": 1.0, "w": 1.0,
            "normalized": {"x": 0.5, "y": 0.5, "z": 0.5, "w": 0.5,
                            "magnitude": 1.0, "sqrMagnitude": 1.0},
            "magnitude": 2.0, "sqrMagnitude": 4.0,
        },
        "TitleFontType": 0,
    }, separators=(",", ":"))

    so["saveMetaDatas"] = [
        _make_meta_entry("lua_chip_id", string_value=chip_id),
        _make_meta_entry("lua_chip_source", string_value=lua_source),
        _make_meta_entry("lua_chip_inputs",
                         string_value=json.dumps(chip_inputs, ensure_ascii=False,
                                                  separators=(",", ":"))),
        _make_meta_entry("lua_chip_outputs",
                         string_value=json.dumps(chip_outputs, ensure_ascii=False,
                                                  separators=(",", ":"))),
        _make_meta_entry("lua_chip_variables",
                         string_value=json.dumps(var_list, ensure_ascii=False,
                                                  separators=(",", ":"))),
        _make_meta_entry("lua_chip_tps", int_value=tps),
        _make_meta_entry("lua_chip_priority", int_value=priority),
        _make_meta_entry("lua_chip_instruction_cost", int_value=instruction_cost),
        _make_meta_entry("lua_chip_visual_name", string_value=visual_name),
        _make_meta_entry("lua_chip_metadata", string_value=metadata),
    ]

    return so


def _minimal_chip_template() -> dict:
    """A minimal chip template with all required saveObjects fields.

    Used when chip_template_1132.json is not available.
    """
    return {
        "objectId": 507707712,
        "instanceId": 0,
        "modedObjectId": "",
        "localId": 0,
        "originLocalId": 0,
        "parentId": -1,
        "position": {"x": 0, "y": 0, "z": 0.0005},
        "rotation": {"x": 0, "y": 0, "z": 0},
        "scale": {"x": 1, "y": 1, "z": 1},
        "color": {"r": 0, "g": 0, "b": 0, "a": 0},
        "intensity": 0.0,
        "bottomColor": {"r": 0, "g": 0, "b": 0, "a": 0},
        "isGradientActive": False,
        "layer": 0,
        "sortingLayer": "Default",
        "orderLayer": 0,
        "gravity": True,
        "freezed": False,
        "ballooned": False,
        "glued": False,
        "rotationFrozen": False,
        "notBreakable": False,
        "isVisible": False,
        "isMeltable": False,
        "isHuman": False,
        "isMutationPart": False,
        "isActivationForced": False,
        "prohibitDrag": False,
        "prohibitBrokeByWater": False,
        "interactionType": "Physic",
        "hasInvisible": False,
        "fluorescentIntensity": 0.0,
        "fluorescentColor": {"r": 0, "g": 0, "b": 0, "a": 0},
        "TreeBranch": None,
        "LightSaveData": {
            "IsActive": False, "ColorIsChanged": True,
            "Color": {"r": 0, "g": 0, "b": 0, "a": 0},
            "IsBrokenByWater": False, "ChildrenSaveData": None,
            "<IsActive>k__BackingField": False,
            "<ColorIsChanged>k__BackingField": True,
            "<Color>k__BackingField": {"r": 0, "g": 0, "b": 0, "a": 0},
            "<IsBrokenByWater>k__BackingField": False,
            "<ChildrenSaveData>k__BackingField": None,
        },
        "BreakableSaveData": None,
        "SpikeComponentData": None,
        "TakenObjectData": None,
        "humanData": [],
        "mechanicData": [],
        "brokenJoints": [],
        "hingeJoints": [],
        "distJoints": [],
        "constraints": [],
        "collisionIgnores": [],
        "addData": [],
        "saveMetaDatas": [],
        "ContextMenuActionsRestrictionSaveData": None,
        "pixelTargetColor": {"r": 0, "g": 0, "b": 0, "a": 0},
        "isPixelTextureWasChanged": False,
    }


# ---------------------------------------------------------------------------
# MelsaveBuilder
# ---------------------------------------------------------------------------

class MelsaveBuilder:
    """Thin wrapper around ``MelsaveSession`` for building saves from scratch.

    This is now a convenience class that delegates to ``MelsaveSession`` in
    document mode. All methods behave identically to the corresponding
    ``MelsaveSession`` methods. New code should prefer ``MelsaveSession``
    directly; this class is kept for backward compatibility.

    Example::

        b = MelsaveBuilder()
        item = b.add_item(202, x=0.5, y=0.03, color=(0, 1, 0.3, 1))
        chip = b.add_lua_chip(source, x=-0.5, y=-0.03,
                              inputs=[{"name": "target", "type": "entity"}],
                              outputs=[{"name": "tick", "type": "number"}])
        b.connect(item, "entity", chip, "target")
        b.save("output.melsave")
    """

    def __init__(self, *, app_version: str = "36.0", map_name: str = "Default"):
        from .session import MelsaveSession
        self._session: MelsaveSession = MelsaveSession(
            app_version=app_version, map_name=map_name
        )

    # ------------------------------------------------------------------
    # Add objects — delegate to session
    # ------------------------------------------------------------------

    def add_item(self, *args, **kwargs) -> int:
        return self._session.add_item(*args, **kwargs)

    def add_lua_chip(self, *args, **kwargs) -> int:
        return self._session.add_lua_chip(*args, **kwargs)

    def add_container(self, save_objects: dict) -> int:
        return self._session.add_container(save_objects)

    def add_ui_controller(self, controller, x: float = 0.0, y: float = 0.0) -> int:
        return self._session.add_ui_controller(controller, x=x, y=y)

    # ------------------------------------------------------------------
    # Wire gates — delegate
    # ------------------------------------------------------------------

    def connect(self, *args, **kwargs) -> dict:
        return self._session.connect(*args, **kwargs)

    # ------------------------------------------------------------------
    # Introspection — delegate
    # ------------------------------------------------------------------

    @property
    def container_count(self) -> int:
        return self._session.container_count

    def containers(self) -> list[dict]:
        return self._session.containers()

    def get_container(self, idx: int) -> dict:
        return self._session.get_container(idx)

    # ------------------------------------------------------------------
    # MetaData / Icon — delegate
    # ------------------------------------------------------------------

    def set_meta(self, **kwargs) -> None:
        self._session.set_meta(**kwargs)

    def set_icon(self, icon_bytes: bytes) -> None:
        self._session.set_icon(icon_bytes)

    def load_icon_from(self, path: str | Path) -> None:
        self._session.load_icon_from(path)

    # ------------------------------------------------------------------
    # Export — delegate
    # ------------------------------------------------------------------

    def build_data(self) -> dict:
        """Return a deep copy of the Data JSON dict."""
        return copy.deepcopy(self._session.document.raw_data)

    def save(self, out_path: str | Path, *, write_icon: bool = True) -> Path:
        return self._session.save(out_path, write_icon=write_icon)


# Re-export for convenience
__all__ = [
    "MelsaveBuilder",
    "connect_gates",
    "MECHANIC_CONSTRAINT_ID",
    "GATE_ENTITY",
    "GATE_NUMBER",
    "GATE_STRING",
    "GATE_VECTOR",
    "GATE_INTEGER",
    "GATE_ARRAY_NUMBER",
    "GATE_ARRAY_STRING",
    "GATE_ARRAY_VECTOR",
    "GATE_ENTITY_ARRAY",
]
