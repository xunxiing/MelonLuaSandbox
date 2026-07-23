"""World state — single Lua VM session owns one of these.

Holds entities, chip variables, spawn catalog, time, signals, cross-chip shared.
Mirrors the union of fields touched by all 11 ApiModules (EntityApiModule,
SpawnCatalogApiModule, EnvironmentApiModule, WorldApiModule, LuaVariablesApiModule,
MechanicApiModule, UIControlApiModule, CameraApiModule, ChipApiModule,
InputFilterApiModule, PrintApiModule).
"""
from dataclasses import dataclass, field
from typing import Any, Optional
import json
import time as _time
from pathlib import Path

from .entity import Entity
from . import catalog as _catalog
from .constraints import ConstraintRegistry, GateWireRegistry

try:
    from Box2D import b2World, b2_dynamicBody, b2_kinematicBody, b2_staticBody
    _HAS_BOX2D = True
except ImportError:
    _HAS_BOX2D = False

import math as _math

# Full catalog: 495 spawnables with objectId + size (APK colliders + fallbacks)
_PHYSICS_BY_ID_PATH = Path(__file__).parent / "data" / "object_physics_by_id.json"
_PHYSICS_DB_PATH = Path(__file__).parent / "data" / "object_physics.json"
_PHYSICS_DB_CACHE: Optional[dict[str, dict]] = None
_PHYSICS_BY_OID_CACHE: Optional[dict[str, dict]] = None


def _load_physics_by_object_id() -> dict[str, dict]:
    global _PHYSICS_BY_OID_CACHE
    if _PHYSICS_BY_OID_CACHE is not None:
        return _PHYSICS_BY_OID_CACHE
    if not _PHYSICS_BY_ID_PATH.exists():
        _PHYSICS_BY_OID_CACHE = {}
        return _PHYSICS_BY_OID_CACHE
    try:
        data = json.loads(_PHYSICS_BY_ID_PATH.read_text(encoding="utf-8"))
        _PHYSICS_BY_OID_CACHE = data.get("byObjectId") or {}
    except Exception:
        _PHYSICS_BY_OID_CACHE = {}
    return _PHYSICS_BY_OID_CACHE


def _load_physics_db() -> dict[str, dict]:
    """Load physics profiles keyed by prefab name (from full objectId table)."""
    global _PHYSICS_DB_CACHE
    if _PHYSICS_DB_CACHE is not None:
        return _PHYSICS_DB_CACHE
    if _PHYSICS_BY_ID_PATH.exists():
        try:
            data = json.loads(_PHYSICS_BY_ID_PATH.read_text(encoding="utf-8"))
            by_name = data.get("byName") or {}
            if by_name:
                _PHYSICS_DB_CACHE = by_name
                return _PHYSICS_DB_CACHE
        except Exception:
            pass
    if not _PHYSICS_DB_PATH.exists():
        _PHYSICS_DB_CACHE = {}
        return _PHYSICS_DB_CACHE
    try:
        data = json.loads(_PHYSICS_DB_PATH.read_text(encoding="utf-8"))
        _PHYSICS_DB_CACHE = data if isinstance(data, dict) else {}
    except Exception:
        _PHYSICS_DB_CACHE = {}
    return _PHYSICS_DB_CACHE


def _radians(deg: float) -> float:
    return _math.radians(deg)

def _degrees(rad: float) -> float:
    return _math.degrees(rad)


@dataclass
class CameraState:
    pos_x: float = 0.0
    pos_y: float = 0.0
    zoom: float = 1.0
    follow_id: Optional[int] = None


@dataclass
class InputState:
    # Pointer
    pointer_down: bool = False
    pointer_up: bool = False
    pointer_pos: tuple[float, float] = (0.0, 0.0)
    pointer_screen_pos: tuple[float, float] = (0.0, 0.0)
    pointer_delta: tuple[float, float] = (0.0, 0.0)
    over_ui: bool = False
    pointer_down_filtered: bool = False
    pointer_up_filtered: bool = False
    raycast_hit_id: int = 0
    raycast_all_hits: list[int] = field(default_factory=list)

    # Touch
    touch_count: int = 0
    touches: dict[int, dict[str, Any]] = field(default_factory=dict)

    # Gestures
    pinch_distance: float = 0.0
    pinch_angle: float = 0.0
    pinch_center: tuple[float, float] = (0.0, 0.0)

    # Keyboard
    keys_held: set[str] = field(default_factory=set)
    keys_pressed_this_frame: set[str] = field(default_factory=set)


@dataclass
class WorldContext:
    entities: dict[int, Entity] = field(default_factory=dict)
    entity_counter: int = 0
    current_tick: int = 0
    elapsed_time: float = 0.0
    time_scale: float = 1.0
    frame_count: int = 0
    session_start: float = field(default_factory=_time.time)
    session_active: bool = False
    is_world_editor: bool = False

    # Physics: Box2D world (gravity points -y, matching Unity 2D convention)
    # When None (Box2D unavailable), physics ops degrade to kinematic mock.
    b2_world: Optional[Any] = field(default=None, repr=False)
    gravity: tuple[float, float] = (0.0, -9.8)
    _b2_bodies: dict[int, Any] = field(default_factory=dict, repr=False)  # entity_id → b2Body
    _b2_joints: dict[int, Any] = field(default_factory=dict, repr=False)  # constraint_id → b2Joint

    # Rope / constraint data layer (serializes back to melsave)
    constraints: ConstraintRegistry = field(default_factory=ConstraintRegistry)

    # Mechanic gate wire data layer (signal wires between chip/entity gates)
    gate_wires: GateWireRegistry = field(default_factory=GateWireRegistry)

    # Chip variables (variables.Set/Get) — type-locked per key
    chip_variables: dict[str, Any] = field(default_factory=dict)
    chip_variable_types: dict[str, str] = field(default_factory=dict)

    # Cross-chip shared table (shared.*)
    shared_table: dict[str, Any] = field(default_factory=dict)

    # Signal event bus state is kept in Lua preamble (_sig_listeners etc.)
    # but C# side needs nothing — signal.* is pure Lua in the preamble.

    # Spawn catalog (pre-seeded with a few built-in aliases)
    spawn_catalog: dict[str, str] = field(default_factory=lambda: {
        "crate_wood": "Wooden Crate",
        "crate_metal": "Metal Crate",
        "human": "Human",
        "barrel": "Barrel",
        "ball": "Ball",
        "plank_wood": "Wooden Plank",
    })
    spawn_saves: dict[str, str] = field(default_factory=dict)
    spawn_resource_saves: dict[str, str] = field(default_factory=dict)
    spawn_mods: dict[str, str] = field(default_factory=dict)
    spawn_request_counter: int = 0
    spawn_requests: dict[int, list[int]] = field(default_factory=dict)

    camera: CameraState = field(default_factory=CameraState)
    input: InputState = field(default_factory=InputState)

    # Chip / mechanic introspection (ChipApiModule, MechanicApiModule, UIControlApiModule)
    # Keyed by either int (entity id) or str ("mechanic:<id>", "uicontrol:<id>")
    chip_metadata: dict[Any, dict[str, Any]] = field(default_factory=dict)

    # Console buffer
    console_buffer: list[tuple[str, str]] = field(default_factory=list)

    # ——— API ———

    def __post_init__(self):
        if _HAS_BOX2D:
            self.b2_world = b2World(gravity=self.gravity)
        # Load real physics profile from APK reverse engineering.
        # Source: object_physics_merged.json (329 items from APK triage)
        self.physics_db: dict[str, dict] = _load_physics_db()
        from .spawn_queue import SpawnQueue

        self.spawn_queue = SpawnQueue(self)

    def apply_physics_profile(self, e: Entity) -> None:
        """If objectId or `name` matches catalog, set base size + mass from APK data."""
        prof = None
        if e.object_id is not None:
            prof = _catalog.get_profile_by_object_id(e.object_id)
        if not prof and e.name:
            prof = self.physics_db.get(e.name) or _catalog.get_profile_by_name(e.name)
        if not prof:
            return
        if e.object_id is None and prof.get("objectId") is not None:
            e.object_id = int(prof["objectId"])
        if not e.name and prof.get("name"):
            e.name = str(prof["name"])
        aabb = prof.get("aabb") or {}
        rb = prof.get("rigidbody") or {}
        w = abs(aabb.get("width", 0.0) or prof.get("aabbWidth", 0.0) or 0.0)
        h = abs(aabb.get("height", 0.0) or prof.get("aabbHeight", 0.0) or 0.0)
        if w < 0.001 or h < 0.001:
            # try summed colliders if AABB is missing (e.g. capsule only)
            cs = prof.get("colliders") or []
            if cs:
                xs = []
                ys = []
                for c in cs:
                    if c.get("kind") == "box":
                        xs.append(abs(c.get("size_x", 0.1)))
                        ys.append(abs(c.get("size_y", 0.1)))
                w = max(xs) if xs else 0.2
                h = max(ys) if ys else 0.2
        if w < 0.001: w = 0.2
        if h < 0.001: h = 0.2
        e.base_size_x = w
        e.base_size_y = h
        e.mass = rb.get("mass", 1.0) if rb else 1.0
        e.gravity_scale = rb.get("gravity_scale", 1.0) if rb else 1.0

    def spawn_entity(
        self,
        name: str,
        x: float = 0.0,
        y: float = 0.0,
        dynamic: bool = True,
        object_id: Optional[int] = None,
        **kw,
    ) -> Entity:
        resolved = _catalog.resolve_spawn_name(name)
        if object_id is None and str(name).strip().isdigit():
            object_id = int(str(name).strip())
        self.entity_counter += 1
        e = Entity(
            entity_id=self.entity_counter,
            local_id=self.entity_counter,
            name=resolved,
            object_id=object_id,
            position_x=x,
            position_y=y,
            **kw,
        )
        self.entities[e.entity_id] = e
        e.bind_world(self)
        # Apply real prefab physics if we have it.
        self.apply_physics_profile(e)
        from .visuals import resolve_sprite

        e.sprite_path = resolve_sprite(e.object_id, e.name)
        # Create a Box2D body if physics is available
        if self.b2_world is not None:
            self._create_body(e, dynamic=dynamic)
        return e

    def _create_body(self, e: Entity, dynamic: bool = True):
        sx, sy = e.real_size()
        # Guard against zero/near-zero area which Box2D rejects (area > b2_epsilon)
        if sx < 0.02:
            sx = 0.2
        if sy < 0.02:
            sy = 0.2
        body_def = {
            "type": b2_dynamicBody if dynamic else b2_staticBody,
            "position": (e.position_x, e.position_y),
            "angle": _radians(e.angle),
            "linearVelocity": (e.velocity_x, e.velocity_y),
            "angularVelocity": _radians(e.angular_velocity),
            "linearDamping": 0.05,
            "angularDamping": 0.05,
            # bullet=True enables continuous collision detection (CCD),
            # which prevents fast-falling objects from tunneling through
            # thin static floors. Only meaningful for dynamic bodies.
            "bullet": bool(dynamic and getattr(e, 'is_bullet', False)),
            "allowSleep": True,
            "awake": True,
        }
        body = self.b2_world.CreateDynamicBody(**body_def) if dynamic \
               else self.b2_world.CreateStaticBody(position=body_def["position"],
                                                    angle=body_def["angle"])
        # Box fixture sized to entity's real size. Static bodies get an
        # extra-thick fixture to prevent tunneling of fast dynamic objects.
        if dynamic:
            body.CreatePolygonFixture(box=(sx * 0.5, sy * 0.5), density=e.mass,
                                      friction=0.3, restitution=0.1)
        else:
            # Make static floor/wall at least 1.0 thick, but keep it centered.
            tx = max(sx, 1.0)
            ty = max(sy, 1.0)
            body.CreatePolygonFixture(box=(tx * 0.5, ty * 0.5), density=0,
                                      friction=0.5, restitution=0.0)
        # Apply entity gravity scale
        body.gravityScale = e.gravity_scale
        if e.is_frozen:
            body.type = b2_staticBody
        if e.is_rotation_frozen:
            body.fixedRotation = True
        self._b2_bodies[e.entity_id] = body

    def get_body(self, entity_id: int):
        return self._b2_bodies.get(entity_id)

    def destroy_body(self, entity_id: int):
        body = self._b2_bodies.pop(entity_id, None)
        if body and self.b2_world is not None:
            self.b2_world.DestroyBody(body)

    def sync_body_from_entity(self, entity_id: int) -> None:
        """Push Entity transform/velocity into Box2D body after clone or setters."""
        e = self.entities.get(entity_id)
        body = self._b2_bodies.get(entity_id)
        if not e or not body or not e.alive:
            return
        body.position = (float(e.position_x), float(e.position_y))
        body.angle = _radians(float(e.angle))
        body.linearVelocity = (float(e.velocity_x), float(e.velocity_y))
        body.angularVelocity = _radians(float(e.angular_velocity))
        body.gravityScale = float(e.gravity_scale)

    def get_entity(self, entity_id: int) -> Optional[Entity]:
        if entity_id is None or entity_id <= 0:
            return None
        e = self.entities.get(entity_id)
        return e if (e and e.alive) else None

    def remove_entity(self, entity_id: int) -> bool:
        e = self.entities.get(entity_id)
        if e:
            e.alive = False
            self.destroy_body(entity_id)
            return True
        return False

    def new_spawn_request(self, entity_ids: list[int]) -> int:
        self.spawn_request_counter += 1
        self.spawn_requests[self.spawn_request_counter] = entity_ids
        return self.spawn_request_counter

    def tick(self, dt: float):
        self.current_tick += 1
        self.elapsed_time += dt * self.time_scale
        self.frame_count += 1
        # Clear per-frame input edges
        self.input.keys_pressed_this_frame.clear()
        # Step the Box2D world and sync transforms back to entities
        if self.b2_world is not None:
            scaled_dt = dt * self.time_scale
            self.b2_world.Step(scaled_dt, velocityIterations=8,
                               positionIterations=3)
            for eid, body in self._b2_bodies.items():
                e = self.entities.get(eid)
                if not e or not e.alive:
                    continue
                # Avoid Entity.__setattr__ re-pushing into body mid-readback
                object.__setattr__(e, "_syncing_from_body", True)
                try:
                    e.position_x = float(body.position.x)
                    e.position_y = float(body.position.y)
                    e.angle = _degrees(float(body.angle))
                    e.velocity_x = float(body.linearVelocity.x)
                    e.velocity_y = float(body.linearVelocity.y)
                    e.angular_velocity = _degrees(float(body.angularVelocity))
                finally:
                    object.__setattr__(e, "_syncing_from_body", False)

    def step_physics(self, dt: float):
        """Alias of ``tick(dt)`` — common agent name for advancing Box2D."""
        return self.tick(dt)

    def step(self, dt: float):
        """Alias of ``tick(dt)``."""
        return self.tick(dt)

    def set_entity_velocity(self, entity_id: int, vx: float, vy: float) -> bool:
        """Set linear velocity on entity + Box2D body. Returns False if missing."""
        e = self.get_entity(entity_id)
        if e is None:
            return False
        e.set_velocity(vx, vy)
        return True

    # ——— Ropes / constraints ———

    def create_rope(
        self,
        from_entity_id: int,
        to_entity_id: int,
        kind: str | int = "Simple",
        *,
        distance: float = 0.0,
        break_force: float = 5000.0,
        frequency: float = 4.0,
        damping: float = 0.7,
        **kw,
    ) -> int:
        """Register a constraint and create a matching Box2D joint.

        Returns the constraint id. When Box2D is unavailable or the kind has
        no physics representation, only the registry entry is created.
        """
        from_e = self.entities.get(from_entity_id)
        to_e = self.entities.get(to_entity_id)
        if from_e is None or to_e is None:
            raise ValueError(
                f"create_rope: missing entity ({from_entity_id=}, {to_entity_id=})"
            )
        cid = self.constraints.create_constraint(
            from_e.local_id,
            to_e.local_id,
            kind,
            distance=distance,
            start_material=kw.get("start_material", "Wood"),
            end_material=kw.get("end_material", "Wood"),
            name=kw.get("name", ""),
            custom_rope=kw.get("custom_rope"),
        )
        if self.b2_world is None:
            return cid
        body_a = self._b2_bodies.get(from_entity_id)
        body_b = self._b2_bodies.get(to_entity_id)
        if body_a is None or body_b is None:
            return cid
        c = self.constraints.get(cid)
        kind_id = c.constraint_id if c is not None else 0
        # Resolve effective length: caller value or current body separation.
        if distance <= 0:
            dx = float(body_b.position.x) - float(body_a.position.x)
            dy = float(body_b.position.y) - float(body_a.position.y)
            length = _math.sqrt(dx * dx + dy * dy)
            if length < 1e-4:
                length = 0.1
        else:
            length = float(distance)
        anchor = (
            (float(body_a.position.x) + float(body_b.position.x)) * 0.5,
            (float(body_a.position.y) + float(body_b.position.y)) * 0.5,
        )
        joint = None
        try:
            if kind_id in (2, 3, 4, 5):
                # Simple / SimpleBreakable / FixedDistance / BreakableFixedDistance
                joint = self.b2_world.CreateDistanceJoint(
                    bodyA=body_a,
                    bodyB=body_b,
                    anchorA=(float(body_a.position.x), float(body_a.position.y)),
                    anchorB=(float(body_b.position.x), float(body_b.position.y)),
                    length=length,
                    frequencyHz=frequency,
                    dampingRatio=damping,
                    collideConnected=False,
                )
            elif kind_id in (6, 7):
                # FixedLine / BreakableFixedLine — weld the two bodies together.
                joint = self.b2_world.CreateWeldJoint(
                    bodyA=body_a,
                    bodyB=body_b,
                    anchor=anchor,
                    frequencyHz=frequency,
                    dampingRatio=damping,
                )
            elif kind_id == 9:
                # Spring — soft distance joint.
                joint = self.b2_world.CreateDistanceJoint(
                    bodyA=body_a,
                    bodyB=body_b,
                    anchorA=(float(body_a.position.x), float(body_a.position.y)),
                    anchorB=(float(body_b.position.x), float(body_b.position.y)),
                    length=length,
                    frequencyHz=frequency,
                    dampingRatio=damping,
                    collideConnected=False,
                )
            elif kind_id == 16:
                # Slider — prismatic along the body-to-body axis.
                axis_x = float(body_b.position.x) - float(body_a.position.x)
                axis_y = float(body_b.position.y) - float(body_a.position.y)
                amag = _math.sqrt(axis_x * axis_x + axis_y * axis_y) or 1.0
                joint = self.b2_world.CreatePrismaticJoint(
                    bodyA=body_a,
                    bodyB=body_b,
                    anchor=anchor,
                    axis=(axis_x / amag, axis_y / amag),
                    collideConnected=False,
                )
            elif kind_id == 18:
                # Wheel — suspension along the body-to-body axis.
                axis_x = float(body_b.position.x) - float(body_a.position.x)
                axis_y = float(body_b.position.y) - float(body_a.position.y)
                amag = _math.sqrt(axis_x * axis_x + axis_y * axis_y) or 1.0
                joint = self.b2_world.CreateWheelJoint(
                    bodyA=body_a,
                    bodyB=body_b,
                    anchor=anchor,
                    axis=(axis_x / amag, axis_y / amag),
                    frequencyHz=frequency,
                    dampingRatio=damping,
                    collideConnected=False,
                )
            elif kind_id == 17:
                # Friction
                joint = self.b2_world.CreateFrictionJoint(
                    bodyA=body_a,
                    bodyB=body_b,
                    anchor=anchor,
                    maxForce=break_force,
                    maxTorque=break_force,
                    collideConnected=False,
                )
            elif kind_id == 19:
                # Relative — motor joint
                joint = self.b2_world.CreateMotorJoint(
                    bodyA=body_a,
                    bodyB=body_b,
                    collideConnected=False,
                )
            # kinds 14, 15, 20, 21, 23, 24 have no Box2D representation.
        except Exception:
            joint = None
        if joint is not None:
            self._b2_joints[cid] = joint
        return cid

    def destroy_rope(self, constraint_id: int) -> bool:
        """Remove a constraint and destroy its Box2D joint if any."""
        joint = self._b2_joints.pop(constraint_id, None)
        if joint is not None and self.b2_world is not None:
            try:
                self.b2_world.DestroyJoint(joint)
            except Exception:
                pass
        return self.constraints.remove(constraint_id)

    def set_rope_param(self, constraint_id: int, key: str, value) -> bool:
        """Forward to registry; also nudge the live Box2D joint when possible."""
        ok = self.constraints.set_param(constraint_id, key, value)
        if not self.constraints.get(constraint_id):
            return ok
        joint = self._b2_joints.get(constraint_id)
        if joint is None:
            return ok
        try:
            if key == "breakForce":
                joint.breakForce = float(value)
            elif key == "distance":
                try:
                    joint.length = float(value)
                except Exception:
                    pass
            elif key == "frequency":
                joint.frequencyHz = float(value)
            elif key == "damping":
                joint.dampingRatio = float(value)
        except Exception:
            pass
        return ok
