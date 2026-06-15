"""mechanic — standard mechanics introspection (9 methods).

Source: MechanicApiModule.cs + Example_ApiReference_en.lua:DemoMechanic.
Excludes VPChip / LuaChip / UIControlMechanic (those have their own modules).
For the sandbox, mechanic metadata lives in world.chip_metadata under the
key "mechanic:<id>".
"""
from typing import Any
from ..world import WorldContext


def _mech(world: WorldContext, eid: Any) -> dict:
    try:
        eid = int(eid)
    except (TypeError, ValueError):
        return {}
    return world.chip_metadata.get(f"mechanic:{eid}", {})


def _gates_to_array(lua, gates_dict):
    return lua.table_from([f"{k}|{v}" for k, v in gates_dict.items()])


def register_mechanic_backend(lua, g, world: WorldContext):
    mech = lua.table_from({})

    def has(eid):
        return 1 if _mech(world, eid) else 0
    def get_type(eid):
        m = _mech(world, eid)
        return m.get("type") if m else None
    def get_inputs(eid):
        m = _mech(world, eid)
        return _gates_to_array(lua, m.get("inputs", {}))
    def get_outputs(eid):
        m = _mech(world, eid)
        return _gates_to_array(lua, m.get("outputs", {}))
    def get_value(eid, gate_name):
        m = _mech(world, eid)
        return m.get("values", {}).get(gate_name)
    def set_value(eid, gate_name, value):
        m = _mech(world, eid)
        if not m: return 0
        if gate_name in m.get("wired", set()): return 0
        m.setdefault("values", {})[gate_name] = value
        return 1
    def has_wire(eid, gate_name):
        m = _mech(world, eid)
        return 1 if gate_name in m.get("wired", set()) else 0
    def get_activation(eid):
        m = _mech(world, eid)
        return m.get("activation", 0.0)
    def set_activation(eid, val):
        m = _mech(world, eid)
        if not m: return 0
        m["activation"] = float(val)
        return 1

    for name, fn in {
        "has": has, "getType": get_type,
        "getInputs": get_inputs, "getOutputs": get_outputs,
        "getValue": get_value, "setValue": set_value,
        "hasWire": has_wire,
        "getActivation": get_activation, "setActivation": set_activation,
    }.items():
        mech[name] = fn
    g["mechanic"] = mech
