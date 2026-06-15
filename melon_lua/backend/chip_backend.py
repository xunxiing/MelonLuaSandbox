"""chip — VPChip / LuaChip introspection (11 methods).

Source: ChipApiModule.cs (IL2CPP dump) + Example_ApiReference_en.lua:DemoChip.
The chip is the entity that owns the running Lua script. world.chip_metadata
stores per-entity chip info (inputs/outputs/TPS/etc.) seeded by the host.
"""
from typing import Any
from ..world import WorldContext


def _meta(world: WorldContext, eid: Any) -> dict:
    if eid is None: return {}
    try:
        return world.chip_metadata.setdefault(int(eid), {
            "type": "LuaChip",
            "inputs": {},   # gateName → GateDataType
            "outputs": {},
            "values": {},   # current gate values
            "wired": set(), # gate names with wires
            "activation": 0.0,
            "name": "",
            "tps": 20,
        })
    except (TypeError, ValueError):
        return {}


def _gates_to_array(lua, gates_dict):
    return lua.table_from([f"{k}|{v}" for k, v in gates_dict.items()])


def register_chip_backend(lua, g, world: WorldContext):
    chip = lua.table_from({})

    def has(eid):
        m = _meta(world, eid)
        return 1 if m else 0

    def get_type(eid):
        m = _meta(world, eid)
        return m.get("type") if m else None

    def get_inputs(eid):
        m = _meta(world, eid)
        return _gates_to_array(lua, m.get("inputs", {}))

    def get_outputs(eid):
        m = _meta(world, eid)
        return _gates_to_array(lua, m.get("outputs", {}))

    def get_value(eid, gate_name):
        m = _meta(world, eid)
        # outputs first, then inputs
        if gate_name in m.get("values", {}):
            return m["values"][gate_name]
        return None

    def set_value(eid, gate_name, value):
        m = _meta(world, eid)
        if gate_name in m.get("wired", set()):
            return 0  # wired → can't set
        m.setdefault("values", {})[gate_name] = value
        return 1

    def has_wire(eid, gate_name):
        m = _meta(world, eid)
        return 1 if gate_name in m.get("wired", set()) else 0

    def get_activation(eid):
        m = _meta(world, eid)
        return m.get("activation", 0.0)

    def set_activation(eid, val):
        m = _meta(world, eid)
        m["activation"] = float(val)
        return 1

    def get_name(eid):
        m = _meta(world, eid)
        return m.get("name", "")

    def get_tps(eid):
        m = _meta(world, eid)
        return m.get("tps", 20)

    for name, fn in {
        "has": has, "getType": get_type,
        "getInputs": get_inputs, "getOutputs": get_outputs,
        "getValue": get_value, "setValue": set_value,
        "hasWire": has_wire,
        "getActivation": get_activation, "setActivation": set_activation,
        "getName": get_name, "getTPS": get_tps,
    }.items():
        chip[name] = fn
    g["chip"] = chip
