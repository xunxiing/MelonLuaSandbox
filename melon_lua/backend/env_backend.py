"""env — environment queries (15 methods).

Signatures from Example_ApiReference_en.lua:DemoEnv and EnvironmentApiModule.cs.
"""
import time as _time
import math as _math
from datetime import datetime, timezone


def register_env_backend(lua, g, world):
    env = lua.table_from({})

    def time_():
        return world.elapsed_time
    def delta_time():
        return 1.0 / 20.0  # fixed dt default; runner overrides via env var if needed
    def fixed_delta_time():
        return 1.0 / 50.0
    def time_scale():
        return world.time_scale
    def set_time_scale(s):
        s = max(0.0, min(2.0, float(s)))
        world.time_scale = s
    def frame_count():
        return world.frame_count
    def session_time():
        return _time.time() - world.session_start
    def entity_count():
        return sum(1 for e in world.entities.values() if e.alive)
    def is_world():
        return 1 if True else 0  # sandbox always pretends to be in-world
    def is_world_editor():
        return 1 if world.is_world_editor else 0
    def system_time():
        return _time.time()  # UTC seconds since epoch
    def system_date():
        # UTC days since epoch
        return int(_time.time() // 86400)
    def to_date(days):
        try:
            d = datetime.fromtimestamp(int(days) * 86400, tz=timezone.utc)
            return d.strftime("%d.%m.%Y")
        except Exception:
            return ""
    def to_time_format(utc_sec):
        try:
            d = datetime.fromtimestamp(int(utc_sec), tz=timezone.utc)
            return d.strftime("%H:%M:%S")
        except Exception:
            return ""
    def parse_date(s):
        try:
            d = datetime.strptime(str(s), "%d.%m.%Y").replace(tzinfo=timezone.utc)
            return int(d.timestamp() // 86400)
        except Exception:
            return 0

    for name, fn in {
        "time": time_, "deltaTime": delta_time, "fixedDeltaTime": fixed_delta_time,
        "timeScale": time_scale, "setTimeScale": set_time_scale,
        "frameCount": frame_count, "sessionTime": session_time,
        "entityCount": entity_count, "isWorld": is_world,
        "isWorldEditor": is_world_editor, "systemTime": system_time,
        "systemDate": system_date, "toDate": to_date,
        "toTimeFormat": to_time_format, "parseDate": parse_date,
    }.items():
        env[name] = fn
    g["env"] = env
