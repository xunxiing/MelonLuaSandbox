"""Spawn requests — spawn.create returns requestId; entities created immediately (no artificial delay).

Failure contract (fixes silent-failure debugging): a spawn that cannot resolve
its alias/objectId produces NO entity and OnSpawned fires with a ``reason``
string: ``OnSpawned(requestId, nil, reason)``. Device-safety warnings (e.g.
objectId spawns that work in sandbox but not on the real device) are recorded
in ``SpawnQueue.warnings`` and logged by the runner at flush time.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal, Optional

from .catalog import (
    MENU_ALIAS_OID,
    get_profile_by_name,
    get_profile_by_object_id,
    resolve_spawn_name,
)
from .entity import Entity
from .world import WorldContext

SpawnKind = Literal["create", "clone", "clone_temp", "save", "mod"]


def _unknown_alias_reason(key: str, w: "WorldContext") -> str:
    aliases = ", ".join(sorted((w.spawn_catalog or {}).keys())[:12])
    return (
        f"spawn.create: unknown spawn alias '{key}' — no entity created. "
        f"Valid: device menu aliases from spawn.getItems() (e.g. {aliases}...), "
        f"catalog gameObjectName (list_spawnables()/catalog_search()), "
        f"or numeric objectId."
    )


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
    _ready_callbacks: list[tuple[int, list[int], Optional[str]]] = field(default_factory=list)
    # request_id → device-safety warning (spawn succeeded in sandbox, but the
    # real device would reject this alias/kind). Logged at flush time.
    warnings: dict[int, str] = field(default_factory=dict)

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
        ent_ids, reason = self._execute_one(op)
        self.world.spawn_requests[rid] = ent_ids
        self._ready_callbacks.append((rid, ent_ids, reason))
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
        ent_ids, reason = self._execute_one(op)
        self.world.spawn_requests[rid] = ent_ids
        self._ready_callbacks.append((rid, ent_ids, reason))
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
        ent_ids, reason = self._execute_one(op)
        self.world.spawn_requests[rid] = ent_ids
        self._ready_callbacks.append((rid, ent_ids, reason))
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
        ent_ids, reason = self._execute_one(op)
        self.world.spawn_requests[rid] = ent_ids
        self._ready_callbacks.append((rid, ent_ids, reason))
        return rid

    def flush(self) -> list[tuple[int, list[int], Optional[str]]]:
        """Fire OnSpawned callbacks: (request_id, entity_ids, fail_reason).

        Empty ids + reason → the spawn failed (reason carries the cause).
        Non-empty ids + reason=None → success. Device-safety warnings are in
        ``self.warnings`` (runner logs them).
        """
        results = list(self._ready_callbacks)
        self._ready_callbacks = []
        for op in self.pending_ops:
            ent_ids, reason = self._execute_one(op)
            self.world.spawn_requests[op.request_id] = ent_ids
            results.append((op.request_id, ent_ids, reason))
        self.pending_ops = []
        return results

    def _execute_one(self, op: SpawnOp) -> tuple[list[int], Optional[str]]:
        w = self.world
        if op.kind in ("clone", "clone_temp"):
            src = w.get_entity(op.clone_entity_id or 0)
            if not src:
                return [], (
                    f"spawn.{op.kind}: source entity {op.clone_entity_id} not found "
                    f"or destroyed — nothing cloned."
                )
            e = w.spawn_entity(
                name=src.name,
                x=op.x,
                y=op.y,
                object_id=src.object_id,
                dynamic=op.kind != "clone_temp" or True,
            )
            self._copy_entity_state(src, e, temp=op.kind == "clone_temp")
            w.sync_body_from_entity(e.entity_id)
            return [e.entity_id], None

        if op.kind == "save":
            display = f"[save]{op.save_or_mod_name}"
            e = w.spawn_entity(display, op.x, op.y, dynamic=True)
            if op.angle is not None:
                e.angle = float(op.angle)
            return [e.entity_id], None

        if op.kind == "mod":
            display = f"[mod]{op.save_or_mod_name}"
            e = w.spawn_entity(display, op.x, op.y, dynamic=True)
            if op.angle is not None:
                e.angle = float(op.angle)
            return [e.entity_id], None

        # ---- create ----
        # Resolution order (fixes both silent failure and dual naming):
        # 1. device menu alias (spawn_catalog)          → device-safe
        # 2. known alias→oid map (_MENU_OID)            → device-safe
        # 3. numeric objectId in catalog                → sandbox-only, warn
        # 4. catalog gameObjectName (auto-fallback oid) → sandbox-only, warn
        # 5. anything else                              → FAIL with reason
        key = op.alias_or_name
        menu_name = (w.spawn_catalog or {}).get(str(key))
        oid = op.object_id
        resolved: Optional[str] = None
        device_safe = False

        if menu_name:
            resolved = str(menu_name)
            device_safe = True  # menu aliases are accepted by the real device
            if str(key) in MENU_ALIAS_OID and oid is None:
                oid = MENU_ALIAS_OID[str(key)]
        elif str(key) in MENU_ALIAS_OID:
            resolved = str(key)
            device_safe = True
            if oid is None:
                oid = MENU_ALIAS_OID[str(key)]
        elif key.isdigit():
            prof = get_profile_by_object_id(int(key))
            if prof is None:
                return [], (
                    f"spawn.create: objectId {key} is not in the object catalog "
                    f"— no entity created. Check the id with "
                    f"get_profile_by_object_id({key}) or catalog_search()."
                )
            resolved = str(prof.get("name") or key)
            oid = int(key)
        else:
            prof = get_profile_by_name(str(key)) or get_profile_by_name(
                str(resolve_spawn_name(key))
            )
            if prof is not None and prof.get("name"):
                resolved = str(prof["name"])
                if oid is None and prof.get("objectId") is not None:
                    oid = int(prof["objectId"])
            # else: fall through to failure below

        if resolved is None:
            return [], _unknown_alias_reason(key, w)

        if not device_safe:
            self.warnings[op.request_id] = (
                f"spawn.create('{key}'): works in the sandbox, but the REAL DEVICE "
                f"only accepts spawn-menu aliases (spawn.getItems()) — it would "
                f"silently return an empty OnSpawned. Prefer a menu alias."
            )

        e = w.spawn_entity(
            name=resolved,
            x=op.x,
            y=op.y,
            object_id=oid,
            dynamic=op.dynamic,
        )
        if op.angle is not None:
            e.angle = float(op.angle)
            if w.get_body(e.entity_id) is not None:
                import math

                body = w.get_body(e.entity_id)
                if body is not None:
                    body.angle = math.radians(float(op.angle))
        return [e.entity_id], None

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