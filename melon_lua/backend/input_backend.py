"""input — pointer / multi-touch / gestures / keyboard (31 methods).

Signatures from Example_ApiReference_en.lua:DemoInput and InputFilterApiModule.cs.
The host drives state by mutating world.input fields before each tick.
"""
from ..world import WorldContext


def register_input_backend(lua, g, world: WorldContext):
    inp = lua.table_from({})
    s = world.input

    # === Pointer ===
    def pointer_down():        return 1 if s.pointer_down else 0
    def pointer_up():          return 1 if s.pointer_up else 0
    def pointer_pos():         return s.pointer_pos
    def pointer_screen_pos():  return s.pointer_screen_pos
    def pointer_delta():       return s.pointer_delta
    def pointer_raycast():     return s.raycast_hit_id
    def pointer_raycast_all(): return lua.table_from(list(s.raycast_all_hits))
    def is_over_ui():          return 1 if s.over_ui else 0
    def pointer_down_filtered(): return 1 if s.pointer_down_filtered else 0
    def pointer_up_filtered():   return 1 if s.pointer_up_filtered else 0

    # === Multi-touch (1-based index) ===
    def touch_count(): return s.touch_count

    def _get_touch(i):
        if i is None or i < 1: return None
        return s.touches.get(int(i))

    def touch_set(i):
        t = _get_touch(i); return 1 if t else 0
    def touch_down(i):
        t = _get_touch(i); return 1 if (t and t.get("down")) else 0
    def touch_up(i):
        t = _get_touch(i); return 1 if (t and t.get("up")) else 0
    def touch_age(i):
        t = _get_touch(i); return float(t["age"]) if t else 0.0
    def touch_id(i):
        t = _get_touch(i); return int(t["hw_id"]) if t else 0
    def touch_pos(i):
        t = _get_touch(i); return (t["pos"] if t else (0.0, 0.0))
    def touch_screen_pos(i):
        t = _get_touch(i); return (t["screen_pos"] if t else (0.0, 0.0))
    def touch_start_screen_pos(i):
        t = _get_touch(i); return (t["start_screen_pos"] if t else (0.0, 0.0))
    def touch_delta(i):
        t = _get_touch(i); return (t["delta"] if t else (0.0, 0.0))
    def touch_swipe_delta(i):
        t = _get_touch(i); return (t["swipe_delta"] if t else (0.0, 0.0))
    def touch_tap(i):
        t = _get_touch(i); return 1 if (t and t.get("tap")) else 0
    def touch_tap_count(i):
        t = _get_touch(i); return int(t["tap_count"]) if t else 0
    def touch_swipe(i):
        t = _get_touch(i); return 1 if (t and t.get("swipe")) else 0
    def touch_is_over_ui(i):
        t = _get_touch(i); return 1 if (t and t.get("over_ui")) else 0
    def touch_started_over_ui(i):
        t = _get_touch(i); return 1 if (t and t.get("started_over_ui")) else 0

    # === Gestures (two fingers) ===
    def pinch_distance(a=1, b=2):
        return s.pinch_distance
    def pinch_angle(a=1, b=2):
        return s.pinch_angle
    def pinch_center(a=1, b=2):
        return s.pinch_center

    # === Keyboard ===
    def key(name):
        return 1 if str(name).lower() in s.keys_held else 0
    def key_down(name):
        return 1 if str(name).lower() in s.keys_pressed_this_frame else 0

    for name, fn in {
        "pointerDown": pointer_down, "pointerUp": pointer_up,
        "pointerPos": pointer_pos, "pointerScreenPos": pointer_screen_pos,
        "pointerDelta": pointer_delta,
        "pointerRaycast": pointer_raycast, "pointerRaycastAll": pointer_raycast_all,
        "isOverUI": is_over_ui,
        "pointerDownFiltered": pointer_down_filtered,
        "pointerUpFiltered": pointer_up_filtered,
        "touchCount": touch_count,
        "touchSet": touch_set, "touchDown": touch_down, "touchUp": touch_up,
        "touchAge": touch_age, "touchId": touch_id,
        "touchPos": touch_pos, "touchScreenPos": touch_screen_pos,
        "touchStartScreenPos": touch_start_screen_pos,
        "touchDelta": touch_delta, "touchSwipeDelta": touch_swipe_delta,
        "touchTap": touch_tap, "touchTapCount": touch_tap_count,
        "touchSwipe": touch_swipe,
        "touchIsOverUI": touch_is_over_ui,
        "touchStartedOverUI": touch_started_over_ui,
        "pinchDistance": pinch_distance, "pinchAngle": pinch_angle,
        "pinchCenter": pinch_center,
        "key": key, "keyDown": key_down,
    }.items():
        inp[name] = fn
    g["input"] = inp
