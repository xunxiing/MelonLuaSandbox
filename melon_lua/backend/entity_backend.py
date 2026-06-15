"""__entity_raw — the C# side of the Entity API.

The LuaPreamble.lua sets up Entity(id) as an OOP wrapper that delegates
every method to __entity_raw.<method>(id, ...). We register every method
the preamble knows about + every method mentioned in ApiReference.

Signatures follow ApiReference exactly: most return multi-values (tuples),
which lupa unpacks when unpack_returned_tuples=True is set on the runtime.
"""
import math
from typing import Any

from ..entity import Entity
from ..world import WorldContext

try:
    from Box2D import b2_dynamicBody, b2_staticBody
    _HAS_BOX2D = True
except ImportError:
    _HAS_BOX2D = False
    b2_dynamicBody = 2
    b2_staticBody = 0


def _e(world: WorldContext, eid: Any) -> Entity | None:
    if eid is None:
        return None
    try:
        return world.get_entity(int(eid))
    except (TypeError, ValueError):
        return None


def register_entity_backend(lua, g, world: WorldContext):
    raw = lua.table_from({})

    # ===== Transform (11) =====
    def get_position(id):
        b = world.get_body(id)
        if b:
            return float(b.position.x), float(b.position.y)
        e = _e(world, id)
        if not e:
            return 0.0, 0.0
        return e.position_x, e.position_y

    def set_position(id, x, y):
        e = _e(world, id)
        if not e: return
        e.position_x = float(x); e.position_y = float(y)
        b = world.get_body(id)
        if b: b.position = (float(x), float(y))

    def get_angle(id):
        e = _e(world, id)
        return e.angle if e else 0.0

    def set_angle(id, a):
        e = _e(world, id)
        if not e: return
        e.angle = float(a)
        b = world.get_body(id)
        if b: b.angle = math.radians(float(a))

    def get_scale(id):
        e = _e(world, id)
        if not e: return 1.0, 1.0
        return e.scale_x, e.scale_y

    def set_scale(id, sx, sy):
        e = _e(world, id)
        if e:
            e.scale_x = float(sx); e.scale_y = float(sy)

    def get_normal(id):
        e = _e(world, id)
        if not e: return 0.0, 1.0
        return e.normal_x, e.normal_y

    def local_to_world(id, lx, ly):
        e = _e(world, id)
        if not e: return 0.0, 0.0
        a = math.radians(e.angle)
        ca, sa = math.cos(a), math.sin(a)
        return e.position_x + lx * ca - ly * sa, e.position_y + lx * sa + ly * ca

    def world_to_local(id, wx, wy):
        e = _e(world, id)
        if not e: return 0.0, 0.0
        a = math.radians(-e.angle)
        ca, sa = math.cos(a), math.sin(a)
        dx, dy = wx - e.position_x, wy - e.position_y
        return dx * ca - dy * sa, dx * sa + dy * ca

    def local_angle_to_world(id, la):
        e = _e(world, id)
        return (e.angle + la) if e else la

    def world_angle_to_local(id, wa):
        e = _e(world, id)
        return (wa - e.angle) if e else wa

    # ===== Physics (15) =====
    def get_velocity(id):
        e = _e(world, id)
        if not e: return 0.0, 0.0
        b = world.get_body(id)
        if b: return float(b.linearVelocity.x), float(b.linearVelocity.y)
        return e.velocity_x, e.velocity_y

    def set_velocity(id, vx, vy):
        e = _e(world, id)
        if not e: return
        e.velocity_x = float(vx); e.velocity_y = float(vy)
        b = world.get_body(id)
        if b: b.linearVelocity = (float(vx), float(vy))

    def get_angular_velocity(id):
        e = _e(world, id)
        if not e: return 0.0
        b = world.get_body(id)
        import math as _m
        return _m.degrees(b.angularVelocity) if b else e.angular_velocity

    def set_angular_velocity(id, w):
        e = _e(world, id)
        if not e: return
        e.angular_velocity = float(w)
        b = world.get_body(id)
        if b:
            import math as _m
            b.angularVelocity = _m.radians(float(w))

    def add_force(id, fx, fy):
        b = world.get_body(id)
        if b: b.ApplyForceToCenter((float(fx), float(fy)), wake=True)

    def add_torque(id, t):
        b = world.get_body(id)
        if b: b.ApplyTorque(float(t), wake=True)

    def add_force_at_position(id, fx, fy, px, py):
        b = world.get_body(id)
        if b: b.ApplyForce((float(fx), float(fy)), (float(px), float(py)), wake=True)

    def get_velocity_at_point(id, px, py):
        b = world.get_body(id)
        if b:
            v = b.GetLinearVelocityFromWorldPoint((float(px), float(py)))
            return float(v.x), float(v.y)
        e = _e(world, id)
        if not e: return 0.0, 0.0
        return e.velocity_x, e.velocity_y

    def get_mass(id):
        b = world.get_body(id)
        if b: return float(b.mass)
        e = _e(world, id)
        return e.mass if e else 0.0

    def get_center_of_mass(id):
        b = world.get_body(id)
        if b:
            lc = b.localCenter
            return float(lc.x), float(lc.y)
        e = _e(world, id)
        if not e: return 0.0, 0.0
        return e.center_of_mass_x, e.center_of_mass_y

    def get_gravity_scale(id):
        b = world.get_body(id)
        if b: return float(b.gravityScale)
        e = _e(world, id)
        return e.gravity_scale if e else 1.0

    def set_gravity_scale(id, s):
        e = _e(world, id)
        if e: e.gravity_scale = float(s)
        b = world.get_body(id)
        if b: b.gravityScale = float(s)

    def freeze(id, flag):
        e = _e(world, id)
        if e: e.is_frozen = bool(flag)
        b = world.get_body(id)
        if b: b.type = b2_staticBody if flag else b2_dynamicBody

    def freeze_rotation(id, flag):
        e = _e(world, id)
        if e: e.is_rotation_frozen = bool(flag)
        b = world.get_body(id)
        if b: b.fixedRotation = bool(flag)

    def set_collision_enabled(id, flag):
        e = _e(world, id)
        if e: e.collision_enabled = bool(flag)
        b = world.get_body(id)
        if b:
            for f in b.fixtures:
                f.sensor = not bool(flag)

    # ===== Health / Temperature (8) =====
    def get_temperature(id):
        e = _e(world, id)
        return e.temperature if e else 0.0

    def set_temperature(id, t):
        e = _e(world, id)
        if e: e.temperature = float(t)

    def is_on_fire(id):
        e = _e(world, id)
        return 1 if (e and e.on_fire) else 0

    def is_frozen(id):
        e = _e(world, id)
        return 1 if (e and e.is_frozen) else 0

    def ignite(id):
        e = _e(world, id)
        if e: e.on_fire = True

    def extinguish(id):
        e = _e(world, id)
        if e: e.on_fire = False

    def get_health(id):
        e = _e(world, id)
        return e.health if e else 0.0

    def is_breakable(id):
        e = _e(world, id)
        return 1 if (e and e.breakable) else 0

    # ===== Visuals (6) =====
    def get_color(id):
        e = _e(world, id)
        if not e: return 1.0, 1.0, 1.0, 1.0
        return e.color_r, e.color_g, e.color_b, e.color_a

    def set_color(id, r, g, b, a=1.0):
        e = _e(world, id)
        if e:
            e.color_r = float(r); e.color_g = float(g)
            e.color_b = float(b); e.color_a = float(a)

    def get_name(id):
        e = _e(world, id)
        return e.name if e else ""

    def get_localized_name(id):
        e = _e(world, id)
        return (e.localized_name or e.name) if e else ""

    def is_visible(id):
        e = _e(world, id)
        return 1 if (e and e.visible) else 0

    def set_visible(id, flag):
        e = _e(world, id)
        if e: e.visible = bool(flag)

    # ===== Electricity (1) =====
    def get_voltage(id):
        e = _e(world, id)
        return e.voltage if e else 0.0

    # ===== Interaction (5) =====
    def is_draggable(id):
        e = _e(world, id)
        return 1 if (e and e.draggable) else 0

    def set_draggable(id, flag):
        e = _e(world, id)
        if e: e.draggable = bool(flag)

    def activate(id, flag):
        e = _e(world, id)
        if e: e.activation_input = 1.0 if flag else 0.0

    def get_activation_input(id):
        e = _e(world, id)
        return e.activation_input if e else 0.0

    def delete(id):
        world.remove_entity(id)

    # ===== Identity (4) =====
    def get_id(id):
        return int(id) if id else 0

    def is_valid(id):
        e = _e(world, id)
        return 1 if e else 0

    def all_(_id=None):
        # called as __entity_raw.all() — but preamble assigns entity.all = _e.all
        # so first arg may be nil. Count live entities.
        return sum(1 for e in world.entities.values() if e.alive)

    def find(_id_or_name, name=None):
        # entity.find("Human") → id of first match
        target = name if name is not None else _id_or_name
        if not isinstance(target, str):
            return None
        for eid, e in world.entities.items():
            if e.alive and e.name == target:
                return eid
        return None

    # ===== Hierarchy (3) =====
    def get_root(id):
        e = _e(world, id)
        if not e: return 0
        cur = e
        while cur.parent_id is not None:
            p = world.entities.get(cur.parent_id)
            if not p: break
            cur = p
        return cur.entity_id

    def get_parent(id):
        e = _e(world, id)
        return e.parent_id if e else None

    def get_children(id):
        e = _e(world, id)
        if not e: return []
        return lua.table_from(list(e.children_ids))

    # ===== Bounds (5) =====
    def get_size(id):
        e = _e(world, id)
        if not e: return 1.0, 1.0
        return e.real_size()

    def get_base_size(id):
        e = _e(world, id)
        if not e: return 1.0, 1.0
        return e.base_size_x, e.base_size_y

    def get_bounds(id):
        e = _e(world, id)
        if not e: return 0.0, 0.0, 0.0, 0.0
        w, h = e.real_size()
        return e.position_x - w/2, e.position_y - h/2, e.position_x + w/2, e.position_y + h/2

    def get_full_bounds(id):
        return get_bounds(id)  # mock: same as bounds

    def get_collider_bounds(id):
        return get_bounds(id)  # mock

    # ===== Extended (4) =====
    def look_at(id, target_id, deg_per_sec=360):
        e = _e(world, id)
        t = _e(world, target_id)
        if e and t:
            dx, dy = t.position_x - e.position_x, t.position_y - e.position_y
            e.angle = math.degrees(math.atan2(dy, dx)) + 90

    def get_elevation(id, tx, ty):
        e = _e(world, id)
        if not e: return 0.0
        dx, dy = tx - e.position_x, ty - e.position_y
        return math.degrees(math.atan2(dy, dx))

    def can_be_activated(id):
        e = _e(world, id)
        return 1 if (e and e.can_be_activated) else 0

    def get_physic_material(id):
        e = _e(world, id)
        return e.physic_material if e else "Default"

    # ===== Collision / Trigger / Wire subscriptions =====
    # These register a callback id with the engine. The engine later fires
    # __dispatch_collision / __dispatch_trigger / __dispatch_wire_* with
    # __cb_id etc. set. We accept the cbId and store it; in the sandbox
    # nothing fires unless the host injects events via runner.dispatch_*.

    def _subscribe_stub(id, cb_id):
        # Real game: register cbId against entity+event. We just remember it.
        return cb_id

    def _unsubscribe_stub(id, cb_id):
        return 0

    def unsubscribe_all(id):
        return 0

    # Build the table
    methods = {
        # Transform
        "getPosition": get_position, "setPosition": set_position,
        "getAngle": get_angle, "setAngle": set_angle,
        "getScale": get_scale, "setScale": set_scale,
        "getNormal": get_normal,
        "localToWorld": local_to_world, "worldToLocal": world_to_local,
        "localAngleToWorld": local_angle_to_world, "worldAngleToLocal": world_angle_to_local,
        # Physics
        "getVelocity": get_velocity, "setVelocity": set_velocity,
        "getAngularVelocity": get_angular_velocity, "setAngularVelocity": set_angular_velocity,
        "addForce": add_force, "addTorque": add_torque,
        "addForceAtPosition": add_force_at_position,
        "getVelocityAtPoint": get_velocity_at_point,
        "getMass": get_mass, "getCenterOfMass": get_center_of_mass,
        "getGravityScale": get_gravity_scale, "setGravityScale": set_gravity_scale,
        "freeze": freeze, "freezeRotation": freeze_rotation,
        "setCollisionEnabled": set_collision_enabled,
        # Health / Temperature
        "getTemperature": get_temperature, "setTemperature": set_temperature,
        "isOnFire": is_on_fire, "isFrozen": is_frozen,
        "ignite": ignite, "extinguish": extinguish,
        "getHealth": get_health, "isBreakable": is_breakable,
        # Visuals
        "getColor": get_color, "setColor": set_color,
        "getName": get_name, "getLocalizedName": get_localized_name,
        "isVisible": is_visible, "setVisible": set_visible,
        # Electricity
        "getVoltage": get_voltage,
        # Interaction
        "isDraggable": is_draggable, "setDraggable": set_draggable,
        "activate": activate, "getActivationInput": get_activation_input,
        "delete": delete,
        # Identity
        "getId": get_id, "isValid": is_valid,
        "all": all_, "find": find,
        # Hierarchy
        "getRoot": get_root, "getParent": get_parent, "getChildren": get_children,
        # Bounds
        "getSize": get_size, "getBaseSize": get_base_size,
        "getBounds": get_bounds, "getFullBounds": get_full_bounds,
        "getColliderBounds": get_collider_bounds,
        # Extended
        "lookAt": look_at, "getElevation": get_elevation,
        "canBeActivated": can_be_activated, "getPhysicMaterial": get_physic_material,
        # Subscriptions (stubs)
        "subscribeCollisionEnter": _subscribe_stub,
        "subscribeCollisionExit": _subscribe_stub,
        "subscribeCollisionStay": _subscribe_stub,
        "subscribeTriggerEnter": _subscribe_stub,
        "subscribeTriggerExit": _subscribe_stub,
        "subscribeTriggerStay": _subscribe_stub,
        "subscribeWireConnected": _subscribe_stub,
        "subscribeWireDisconnected": _subscribe_stub,
        "unsubscribeCollisionEnter": _unsubscribe_stub,
        "unsubscribeCollisionExit": _unsubscribe_stub,
        "unsubscribeCollisionStay": _unsubscribe_stub,
        "unsubscribeTriggerEnter": _unsubscribe_stub,
        "unsubscribeTriggerExit": _unsubscribe_stub,
        "unsubscribeTriggerStay": _unsubscribe_stub,
        "unsubscribeWireConnected": _unsubscribe_stub,
        "unsubscribeWireDisconnected": _unsubscribe_stub,
        "unsubscribeAll": unsubscribe_all,
    }
    for name, fn in methods.items():
        raw[name] = fn
    g["__entity_raw"] = raw
