"""variables — chip-level state storage.

Source: LuaVariablesApiModule.cs + Example_ApiReference_en.lua:DemoVariables.
Type is locked once the variable exists (Number stays Number, etc).
Variables.Set returns 1.0 on success, 0.0 on type mismatch / error.
"""
from typing import Any
from ..world import WorldContext


def _infer_type(v: Any) -> str:
    if isinstance(v, bool): return "Boolean"
    if isinstance(v, int): return "Integer"
    if isinstance(v, float): return "Number"
    if isinstance(v, str): return "String"
    return "Any"


def register_variables_backend(lua, g, world: WorldContext):
    var = lua.table_from({})

    def Set(key, value):
        key = str(key)
        existing_type = world.chip_variable_types.get(key)
        new_type = _infer_type(value)
        if existing_type and existing_type != new_type:
            return 0.0  # type mismatch
        world.chip_variables[key] = value
        world.chip_variable_types[key] = new_type
        return 1.0

    def Get(key):
        key = str(key)
        return world.chip_variables.get(key)

    var["Set"] = Set
    var["Get"] = Get
    g["variables"] = var
