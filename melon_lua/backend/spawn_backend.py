"""spawn — object creation (21 methods).

spawn.create* returns requestId immediately; entities materialize on spawn_queue.flush()
(end of tick / after OnInit), then OnSpawned via preamble __dispatch_spawn.
"""
from typing import Optional, Callable

from ..world import WorldContext


def _format_items(lua, items_dict, sep=None):
    arr = [f"{k}|{v}" for k, v in items_dict.items()]
    if sep is None:
        return lua.table_from(arr)
    return sep.join(arr)


def register_spawn_backend(
    lua,
    g,
    world: WorldContext,
    queue_spawn_result: Optional[Callable[[int, list], None]] = None,
):
    del queue_spawn_result
    q = world.spawn_queue
    spawn = lua.table_from({})

    def get_items():
        return _format_items(lua, world.spawn_catalog)

    def get_items_string(sep=", "):
        return _format_items(lua, world.spawn_catalog, sep)

    def get_item_count():
        return len(world.spawn_catalog)

    def get_saves():
        return _format_items(lua, world.spawn_saves)

    def get_saves_string(sep=", "):
        return _format_items(lua, world.spawn_saves, sep)

    def get_save_count():
        return len(world.spawn_saves)

    def get_resource_saves():
        return _format_items(lua, world.spawn_resource_saves)

    def get_resource_saves_string(sep=", "):
        return _format_items(lua, world.spawn_resource_saves, sep)

    def get_resource_save_count():
        return len(world.spawn_resource_saves)

    def get_mods():
        return _format_items(lua, world.spawn_mods)

    def get_mods_string(sep=", "):
        return _format_items(lua, world.spawn_mods, sep)

    def get_mod_count():
        return len(world.spawn_mods)

    def create(alias, x, y):
        return q.enqueue_create(alias, x, y)

    def create_with_angle(alias, x, y, angle):
        return q.enqueue_create(alias, x, y, angle=angle)

    def clone(entity_id, x, y):
        return q.enqueue_clone(entity_id, x, y, temp=False)

    def clone_temp(entity_id, x, y):
        return q.enqueue_clone(entity_id, x, y, temp=True)

    def create_save(name, x, y):
        return q.enqueue_save(name, x, y)

    def create_mod(name, x, y):
        return q.enqueue_mod(name, x, y)

    def destroy(entity_id):
        world.remove_entity(entity_id)
        return 0

    def get_name_by_alias(alias):
        return world.spawn_catalog.get(str(alias), "")

    def exists_by_alias(alias):
        return 1 if str(alias) in world.spawn_catalog else 0

    for name, fn in {
        "getItems": get_items,
        "getItemsString": get_items_string,
        "getItemCount": get_item_count,
        "getSaves": get_saves,
        "getSavesString": get_saves_string,
        "getSaveCount": get_save_count,
        "getResourceSaves": get_resource_saves,
        "getResourceSavesString": get_resource_saves_string,
        "getResourceSaveCount": get_resource_save_count,
        "getMods": get_mods,
        "getModsString": get_mods_string,
        "getModCount": get_mod_count,
        "create": create,
        "createWithAngle": create_with_angle,
        "clone": clone,
        "cloneTemp": clone_temp,
        "createSave": create_save,
        "createMod": create_mod,
        "destroy": destroy,
        "getNameByAlias": get_name_by_alias,
        "existsByAlias": exists_by_alias,
    }.items():
        spawn[name] = fn
    g["spawn"] = spawn