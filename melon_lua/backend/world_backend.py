"""world — world control (11 methods).

Source: WorldApiModule.cs + Example_ApiReference_en.lua:DemoWorld.
load/reset reload the scene in the real game (destroys the Lua VM);
here we no-op them since we own the world.
"""
from ..world import WorldContext


def register_world_backend(lua, g, world: WorldContext):
    w = lua.table_from({})

    def is_session_active():
        return 1 if world.session_active else 0
    def start_session():
        world.session_active = True
    def end_session():
        world.session_active = False
    def save():
        # Real game: persist world state. Sandbox: noop.
        return 0
    def load():
        return 0
    def reset():
        # Clear entities (but keep chip entity, if any)
        keep = {k: v for k, v in world.entities.items()
                if not v.alive or k < 1}
        world.entities.clear()
        world.entities.update(keep)
        return 0
    def clear_corpses():
        # In real game corpses are dead entities. We have no death state.
        return 0
    def clear_decals():
        return 0
    def clear_gibs():
        return 0
    def clear_living():
        # Remove all alive entities
        ids = [eid for eid, e in world.entities.items() if e.alive]
        for eid in ids:
            world.remove_entity(eid)
        return 0
    def radio_signal(channel):
        return 0.0

    for name, fn in {
        "isSessionActive": is_session_active,
        "startSession": start_session, "endSession": end_session,
        "save": save, "load": load, "reset": reset,
        "clearCorpses": clear_corpses, "clearDecals": clear_decals,
        "clearGibs": clear_gibs, "clearLiving": clear_living,
        "radioSignal": radio_signal,
    }.items():
        w[name] = fn
    g["world"] = w
