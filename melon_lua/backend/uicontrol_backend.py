"""uicontrol — runtime UIControl panels (12 methods).

Source: UIControlApiModule.cs + Example_ApiReference_en.lua:DemoUIControl.
Per-entity UI elements stored in world.chip_metadata["uicontrol:<id>"].
"""
from typing import Any
from ..world import WorldContext


def _ui(world: WorldContext, eid: Any) -> dict:
    try:
        eid = int(eid)
    except (TypeError, ValueError):
        return {}
    return world.chip_metadata.get(f"uicontrol:{eid}", {})


def _elements_to_array(lua, elements):
    return lua.table_from([f"{e['name']}|{e['type']}|{e['id']}" for e in elements])


def register_uicontrol_backend(lua, g, world: WorldContext):
    ui = lua.table_from({})

    def has_ui_control(eid):
        return 1 if _ui(world, eid) else 0

    def get_elements(eid):
        m = _ui(world, eid)
        return _elements_to_array(lua, m.get("elements", []))

    def find_element(eid, name):
        m = _ui(world, eid)
        for el in m.get("elements", []):
            if el["name"] == str(name):
                return el["id"]
        return None

    def get_elements_by_type(eid, type_name):
        m = _ui(world, eid)
        matches = [el for el in m.get("elements", []) if el["type"] == str(type_name)]
        return lua.table_from([el["id"] for el in matches])

    def _gates_array(lua, m, element_id, key):
        el = next((e for e in m.get("elements", []) if e["id"] == element_id), None)
        if not el: return lua.table_from([])
        return lua.table_from([f"{g}|{t}" for g, t in el.get(key, {}).items()])

    def get_input_gates(eid, element_id):
        m = _ui(world, eid)
        return _gates_array(lua, m, element_id, "inputs")

    def get_output_gates(eid, element_id):
        m = _ui(world, eid)
        return _gates_array(lua, m, element_id, "outputs")

    def get_value(eid, element_id, gate_name):
        m = _ui(world, eid)
        el = next((e for e in m.get("elements", []) if e["id"] == element_id), None)
        if not el: return None
        return el.get("values", {}).get(gate_name)

    def set_value(eid, element_id, gate_name, value):
        m = _ui(world, eid)
        el = next((e for e in m.get("elements", []) if e["id"] == element_id), None)
        if not el: return 0
        if gate_name in el.get("wired", set()): return 0
        el.setdefault("values", {})[gate_name] = value
        return 1

    def has_wire(eid, element_id, gate_name):
        m = _ui(world, eid)
        el = next((e for e in m.get("elements", []) if e["id"] == element_id), None)
        if not el: return 0
        return 1 if gate_name in el.get("wired", set()) else 0

    def get_anchors(eid, element_id):
        m = _ui(world, eid)
        el = next((e for e in m.get("elements", []) if e["id"] == element_id), None)
        if not el: return 0.0, 0.0, 0.0, 0.0
        a = el.get("anchors", (0, 0, 1, 1))
        return a[0], a[1], a[2], a[3]

    def get_anchored_position(eid, element_id):
        m = _ui(world, eid)
        el = next((e for e in m.get("elements", []) if e["id"] == element_id), None)
        if not el: return 0.0, 0.0
        p = el.get("anchored_pos", (0.0, 0.0))
        return p[0], p[1]

    def set_anchored_position(eid, element_id, x, y):
        m = _ui(world, eid)
        el = next((e for e in m.get("elements", []) if e["id"] == element_id), None)
        if not el: return 0
        el["anchored_pos"] = (float(x), float(y))
        return 1

    for name, fn in {
        "hasUIControl": has_ui_control,
        "getElements": get_elements, "findElement": find_element,
        "getElementsByType": get_elements_by_type,
        "getInputGates": get_input_gates, "getOutputGates": get_output_gates,
        "getValue": get_value, "setValue": set_value,
        "hasWire": has_wire,
        "getAnchors": get_anchors,
        "getAnchoredPosition": get_anchored_position,
        "setAnchoredPosition": set_anchored_position,
    }.items():
        ui[name] = fn
    g["uicontrol"] = ui
