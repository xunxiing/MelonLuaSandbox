"""Spawn requests — spawn.create returns requestId; entities created immediately (no artificial delay)."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal, Optional

from .catalog import resolve_spawn_name
from .entity import Entity
from .world import WorldContext

SpawnKind = Literal["create", "clone", "clone_temp", "save", "mod"]


@dataclass
class SpawnOp:
    request_id: int
    kind: SpawnKind
    alias_or_name: str = ""
    x: float = 0.0
    y: float = 0.0
    angle: Optional[float] = None
    object_id: Optional[int] = None
    clone_entity_id: Optional[int] = None
    save_or_mod_name: str = ""
    dynamic: bool = True


@dataclass
class SpawnQueue:
    world: WorldContext
    pending_ops: list[SpawnOp] = field(default_factory=list)
    _ready_callbacks: list[tuple[int, list[int]]] = field(default_factory=list)

    def allocate_request_id(self) -> int:
        self.world.spawn_request_counter += 1
        rid = self.world.spawn_request_counter
        self.world.spawn_requests[rid] = []
        return rid

    def enqueue_create(
        self,
        alias_or_name: str,
        x: float,
        y: float,
        angle: Optional[float] = None,
    ) -> int:
        key = str(alias_or_name).strip()
        oid = int(key) if key.isdigit() else None
        rid = self.allocate_request_id()
        op = SpawnOp(
            request_id=rid,
            kind="create",
            alias_or_name=key,
            x=float(x),
            y=float(y),
            angle=angle,
            object_id=oid,
        )
        ent_ids = self._execute_one(op)
        self.world.spawn_requests[rid] = ent_ids
        self._ready_callbacks.append((rid, ent_ids))
        return rid

    def enqueue_clone(
        self,
        entity_id: int,
        x: float,
        y: float,
        *,
        temp: bool = False,
    ) -> int:
        rid = self.allocate_request_id()
        op = SpawnOp(
            request_id=rid,
            kind="clone_temp" if temp else "clone",
            x=float(x),
            y=float(y),
            clone_entity_id=int(entity_id),
        )
        ent_ids = self._execute_one(op)
        self.world.spawn_requests[rid] = ent_ids
        self._ready_callbacks.append((rid, ent_ids))
        return rid

    def enqueue_save(self, name: str, x: float, y: float) -> int:
        rid = self.allocate_request_id()
        op = SpawnOp(
            request_id=rid,
            kind="save",
            x=float(x),
            y=float(y),
            save_or_mod_name=str(name),
        )
        ent_ids = self._execute_one(op)
        self.world.spawn_requests[rid] = ent_ids
        self._ready_callbacks.append((rid, ent_ids))
        return rid

    def enqueue_mod(self, name: str, x: float, y: float) -> int:
        rid = self.allocate_request_id()
        op = SpawnOp(
            request_id=rid,
            kind="mod",
            x=float(x),
            y=float(y),
            save_or_mod_name=str(name),
        )
        ent_ids = self._execute_one(op)
        self.world.spawn_requests[rid] = ent_ids
        self._ready_callbacks.append((rid, ent_ids))
        return rid

    def flush(self) -> list[tuple[int, list[int]]]:
        """Fire OnSpawned for entities already created this frame."""
        results = list(self._ready_callbacks)
        self._ready_callbacks = []
        for op in self.pending_ops:
            ent_ids = self._execute_one(op)
            self.world.spawn_requests[op.request_id] = ent_ids
            results.append((op.request_id, ent_ids))
        self.pending_ops = []
        return results

    def _execute_one(self, op: SpawnOp) -> list[int]:
        w = self.world
        if op.kind in ("clone", "clone_temp"):
            src = w.get_entity(op.clone_entity_id or 0)
            if not src:
                return []
            e = w.spawn_entity(
                name=src.name,
                x=op.x,
                y=op.y,
                object_id=src.object_id,
                dynamic=op.kind != "clone_temp" or True,
            )
            self._copy_entity_state(src, e, temp=op.kind == "clone_temp")
            w.sync_body_from_entity(e.entity_id)
            return [e.entity_id]

        if op.kind == "save":
            display = f"[save]{op.save_or_mod_name}"
            e = w.spawn_entity(display, op.x, op.y, dynamic=True)
            if op.angle is not None:
                e.angle = float(op.angle)
            return [e.entity_id]

        if op.kind == "mod":
            display = f"[mod]{op.save_or_mod_name}"
            e = w.spawn_entity(display, op.x, op.y, dynamic=True)
            if op.angle is not None:
                e.angle = float(op.angle)
            return [e.entity_id]

        resolved = resolve_spawn_name(op.alias_or_name) or op.alias_or_name
        e = w.spawn_entity(
            name=resolved,
            x=op.x,
            y=op.y,
            object_id=op.object_id,
            dynamic=op.dynamic,
        )
        if op.angle is not None:
            e.angle = float(op.angle)
            if w.get_body(e.entity_id) is not None:
                import math

                body = w.get_body(e.entity_id)
                if body is not None:
                    body.angle = math.radians(float(op.angle))
        return [e.entity_id]

    @staticmethod
    def _copy_entity_state(src: Entity, dst: Entity, *, temp: bool) -> None:
        dst.scale_x = src.scale_x
        dst.scale_y = src.scale_y
        dst.angle = src.angle
        dst.mass = src.mass
        dst.gravity_scale = src.gravity_scale
        dst.velocity_x = src.velocity_x if not temp else 0.0
        dst.velocity_y = src.velocity_y if not temp else 0.0
        dst.angular_velocity = src.angular_velocity if not temp else 0.0
        dst.color_r, dst.color_g, dst.color_b, dst.color_a = (
            src.color_r,
            src.color_g,
            src.color_b,
            src.color_a,
        )
        dst.temperature = src.temperature
        dst.health = src.health