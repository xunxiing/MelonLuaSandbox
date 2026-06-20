"""Mock Entity — matches every field the real Entity API touches.

Fields are populated based on the 60+ methods in EntityApiModule.cs (IL2CPP dump)
and the signatures in Example_ApiReference_en.lua. This is NOT a physics body:
state is set directly by setters. A future IPhysicsWorld hook can drive motion.
"""
from dataclasses import dataclass, field
from typing import Any, Optional


@dataclass
class Entity:
    entity_id: int
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
