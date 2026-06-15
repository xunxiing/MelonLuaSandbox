"""camera — camera control (7 methods).

Signatures from Example_ApiReference_en.lua:DemoCamera and CameraApiModule.cs.
"""
from ..world import WorldContext


def register_camera_backend(lua, g, world: WorldContext):
    cam = lua.table_from({})
    c = world.camera

    def get_position():
        return c.pos_x, c.pos_y
    def set_position(x, y):
        if c.follow_id is None:
            c.pos_x = float(x); c.pos_y = float(y)
    def get_zoom():
        return c.zoom
    def set_zoom(z):
        c.zoom = float(z)
    def follow(entity_id):
        c.follow_id = int(entity_id) if entity_id else None
    def unfollow():
        c.follow_id = None
    def is_following():
        return 1 if c.follow_id is not None else 0

    for name, fn in {
        "getPosition": get_position, "setPosition": set_position,
        "getZoom": get_zoom, "setZoom": set_zoom,
        "follow": follow, "unfollow": unfollow,
        "isFollowing": is_following,
    }.items():
        cam[name] = fn
    g["camera"] = cam
