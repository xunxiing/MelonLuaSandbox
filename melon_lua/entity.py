"""Mock Entity — matches every field the real Entity API touches.

Fields are populated based on the 60+ methods in EntityApiModule.cs (IL2CPP dump)
and the signatures in Example_ApiReference_en.lua.

Python-side field writes for transform/velocity sync into the owning
WorldContext Box2D body (via ``_world`` set by ``spawn_entity``), so that
Lua ``Entity(id):getVelocity()`` sees the same values.
"""
from dataclasses import dataclass, field
from typing import Any, Optional

# Fields that must push into Box2D when assigned from Python.
_BODY_SYNC_FIELDS = frozenset({
    "position_x", "position_y", "angle",
    "velocity_x", "velocity_y", "angular_velocity",
    "gravity_scale", "is_frozen", "is_rotation_frozen",
})


@dataclass
class Entity:
    entity_id: int
    local_id: int = 0
    name: str = "object"
    object_id: Optional[int] = None
    localized_name: str = ""
    sprite_path: Optional[str] = None

    # Transform
    position_x: float = 0.0
    position_y: float = 0.0
    angle: float = 0.0  # degrees
    scale_x: float = 1.0
    scale_y: float = 1.0
    base_size_x: float = 1.0
    base_size_y: float = 1.0

    # Physics
    velocity_x: float = 0.0
    velocity_y: float = 0.0
    angular_velocity: float = 0.0
    mass: float = 1.0
    center_of_mass_x: float = 0.0
    center_of_mass_y: float = 0.0
    gravity_scale: float = 1.0
    is_frozen: bool = False
    is_rotation_frozen: bool = False
    collision_enabled: bool = True
    physic_material: str = "Default"

    # Health / Temperature
    temperature: float = 20.0
    on_fire: bool = False
    health: float = 100.0
    breakable: bool = False

    # Visuals
    color_r: float = 1.0
    color_g: float = 1.0
    color_b: float = 1.0
    color_a: float = 1.0
    visible: bool = True

    # Electricity
    voltage: float = 0.0

    # Interaction
    draggable: bool = True
    activation_input: float = 0.0
    can_be_activated: bool = False

    # Hierarchy
    parent_id: Optional[int] = None
    children_ids: list[int] = field(default_factory=list)

    # Custom texture override (from .melmod)
    custom_texture_png: str | None = None
    custom_texture_ppu: float | None = None

    # Bookkeeping
    alive: bool = True
    custom_data: dict[str, Any] = field(default_factory=dict)

    # Owning world (not a dataclass field — set by WorldContext.spawn_entity)
    # so field assignment can sync Box2D.
    def __post_init__(self) -> None:
        object.__setattr__(self, "_world", None)
        object.__setattr__(self, "_syncing_from_body", False)

    def __setattr__(self, name: str, value) -> None:
        object.__setattr__(self, name, value)
        if name in _BODY_SYNC_FIELDS and not self.__dict__.get("_syncing_from_body"):
            w = self.__dict__.get("_world")
            if w is not None:
                w.sync_body_from_entity(self.entity_id)

    def bind_world(self, world) -> None:
        """Attach owning WorldContext (called by spawn_entity)."""
        object.__setattr__(self, "_world", world)

    def set_velocity(self, vx: float, vy: float) -> None:
        """Python alias matching Lua Entity:setVelocity — writes + syncs body."""
        self.velocity_x = float(vx)
        self.velocity_y = float(vy)

    def set_linear_velocity(self, vx: float, vy: float) -> None:
        """Alias of set_velocity."""
        self.set_velocity(vx, vy)

    def get_velocity(self) -> tuple[float, float]:
        """Python-side velocity; prefers Box2D body when present."""
        w = self.__dict__.get("_world")
        if w is not None:
            b = w.get_body(self.entity_id)
            if b is not None:
                return float(b.linearVelocity.x), float(b.linearVelocity.y)
        return float(self.velocity_x), float(self.velocity_y)

    @property
    def normal_x(self) -> float:
        import math
        a = math.radians(self.angle)
        return math.cos(a)

    @property
    def normal_y(self) -> float:
        import math
        a = math.radians(self.angle + 90)
        return math.sin(a)

    def real_size(self) -> tuple[float, float]:
        return (self.base_size_x * self.scale_x, self.base_size_y * self.scale_y)
