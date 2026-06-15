"""Backend C# functions exposed to Lua.

Each backend module registers functions into a Lua table. The real game
binds C# methods to the same names via LuaFunctionEntry in each ApiModule.
We replicate the contract but mock behavior.

Public API: register_all(lua_globals, world) — installs every module.
"""
from .entity_backend import register_entity_backend
from .env_backend import register_env_backend
from .camera_backend import register_camera_backend
from .input_backend import register_input_backend
from .spawn_backend import register_spawn_backend
from .chip_backend import register_chip_backend
from .mechanic_backend import register_mechanic_backend
from .uicontrol_backend import register_uicontrol_backend
from .world_backend import register_world_backend
from .variables_backend import register_variables_backend
from .print_backend import register_print_backend

__all__ = [
    "register_all",
    "register_entity_backend",
    "register_env_backend",
    "register_camera_backend",
    "register_input_backend",
    "register_spawn_backend",
    "register_chip_backend",
    "register_mechanic_backend",
    "register_uicontrol_backend",
    "register_world_backend",
    "register_variables_backend",
    "register_print_backend",
]


def register_all(lua, g, world, on_log=None, error_log_fn=None, queue_spawn_result=None):
    """Install every backend module into the Lua globals `g`."""
    register_print_backend(lua, g, world, on_log=on_log, error_log_fn=error_log_fn)
    register_entity_backend(lua, g, world)
    register_env_backend(lua, g, world)
    register_camera_backend(lua, g, world)
    register_input_backend(lua, g, world)
    register_spawn_backend(lua, g, world, queue_spawn_result=queue_spawn_result)
    register_chip_backend(lua, g, world)
    register_mechanic_backend(lua, g, world)
    register_uicontrol_backend(lua, g, world)
    register_world_backend(lua, g, world)
    register_variables_backend(lua, g, world)
