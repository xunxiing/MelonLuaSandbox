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
            name=resolved,
            object_id=object_id,
            position_x=x,
            position_y=y,
            **kw,
        )
        self.entities[e.entity_id] = e
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
                e.position_x = float(body.position.x)
                e.position_y = float(body.position.y)
                e.angle = _degrees(float(body.angle))
                e.velocity_x = float(body.linearVelocity.x)
                e.velocity_y = float(body.linearVelocity.y)
                e.angular_velocity = _degrees(float(body.angularVelocity))
