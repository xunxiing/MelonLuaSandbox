"""Constraint registry — pure-Python rope/joint data layer for MelonLuaSandbox.

Mirrors the C# `Constraint` struct (from Assembly-CSharp) and its companions
`distJoints` / `hingeJoints`. Holds no physics state; it tracks ropes as data
so a save writer can round-trip them back into a `.melsave` SaveObject.

Each `Constraint` corresponds to one entry in `SaveObject.constraints`. The
`startObjectId` / `endObjectId` fields are **localId** references (not
instanceId), matching how the real game serializes them.
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass, field, replace


KIND_NAMES: dict[str, int] = {
    "Simple": 2,
    "SimpleBreakable": 3,
    "FixedDistance": 4,
    "BreakableFixedDistance": 5,
    "FixedLine": 6,
    "BreakableFixedLine": 7,
    "Spring": 9,
    "Festoon": 14,
    "AntiCollision": 15,
    "Slider": 16,
    "Friction": 17,
    "Wheel": 18,
    "Relative": 19,
    "NoPhysics": 20,
    "Electricity": 21,
    "RopeToRope": 23,
    "Liquid": 24,
}

KIND_IDS: dict[int, str] = {v: k for k, v in KIND_NAMES.items()}


def _new_guid() -> str:
    """Return a fresh SerializableGuid.Value string."""
    return str(uuid.uuid4())


@dataclass
class Constraint:
    main_guid: str
    constraint_id: int
    start_point: tuple[float, float, float]
    end_point: tuple[float, float, float]
    distance: float
    start_object_id: int
    end_object_id: int
    linked_rope_guid: str
    constraint_name: str
    is_name_visible: bool
    start_material: str
    end_material: str
    custom_rope: dict | None


@dataclass
class DistJointMod:
    index: int
    dist: float


@dataclass
class HingeJointMod:
    index: int
    limits: tuple[float, float]
    use_limits: bool


class ConstraintRegistry:
    """Tracks ropes/constraints as data, mirroring C# `Constraint` lists."""

    def __init__(self):
        self._constraints: dict[int, Constraint] = {}
        self._dist_mods: dict[int, list[DistJointMod]] = {}
        self._hinge_mods: dict[int, list[HingeJointMod]] = {}
        self._next_id: int = 1

    def create_constraint(
        self,
        start_local_id: int,
        end_local_id: int,
        kind: int | str,
        *,
        distance: float = 0.0,
        start_point: tuple[float, float, float] = (0.0, 0.0, 0.0),
        end_point: tuple[float, float, float] = (0.0, 0.0, 0.0),
        start_material: str = "Wood",
        end_material: str = "Wood",
        name: str = "",
        custom_rope: dict | None = None,
    ) -> int:
        """Register a constraint; return its auto-incremented id."""
        if isinstance(kind, str):
            if kind not in KIND_NAMES:
                raise ValueError(f"Unknown constraint kind name: {kind!r}")
            kind_id = KIND_NAMES[kind]
        else:
            kind_id = int(kind)
            if kind_id not in KIND_IDS:
                raise ValueError(f"Unknown constraint kind id: {kind_id!r}")
        cid = self._next_id
        self._next_id += 1
        c = Constraint(
            main_guid=_new_guid(),
            constraint_id=kind_id,
            start_point=(float(start_point[0]), float(start_point[1]), float(start_point[2])),
            end_point=(float(end_point[0]), float(end_point[1]), float(end_point[2])),
            distance=float(distance),
            start_object_id=int(start_local_id),
            end_object_id=int(end_local_id),
            linked_rope_guid="",
            constraint_name=name,
            is_name_visible=bool(name),
            start_material=start_material,
            end_material=end_material,
            custom_rope=custom_rope,
        )
        self._constraints[cid] = c
        return cid

    def get(self, constraint_id: int) -> Constraint | None:
        return self._constraints.get(constraint_id)

    def remove(self, constraint_id: int) -> bool:
        existed = self._constraints.pop(constraint_id, None) is not None
        self._dist_mods.pop(constraint_id, None)
        self._hinge_mods.pop(constraint_id, None)
        return existed

    def list_for_object(self, local_id: int) -> list[Constraint]:
        return [
            c for c in self._constraints.values()
            if c.start_object_id == local_id or c.end_object_id == local_id
        ]

    def set_distance_mod(self, constraint_id: int, dist: float) -> None:
        """Add/replace a DistJointMod on a constraint."""
        mods = self._dist_mods.setdefault(constraint_id, [])
        for m in mods:
            m.dist = float(dist)
            return
        mods.append(DistJointMod(index=constraint_id, dist=float(dist)))

    def set_hinge_mod(
        self,
        constraint_id: int,
        limits: tuple[float, float],
        use_limits: bool = True,
    ) -> None:
        """Add/replace a HingeJointMod on a constraint."""
        mods = self._hinge_mods.setdefault(constraint_id, [])
        for m in mods:
            m.limits = (float(limits[0]), float(limits[1]))
            m.use_limits = bool(use_limits)
            return
        mods.append(
            HingeJointMod(
                index=constraint_id,
                limits=(float(limits[0]), float(limits[1])),
                use_limits=bool(use_limits),
            )
        )

    def set_param(self, constraint_id: int, key: str, value) -> bool:
        """Generic setter for any Constraint field by snake_case key."""
        c = self._constraints.get(constraint_id)
        if c is None:
            return False
        aliases = {
            "main_guid": "main_guid",
            "constraint_id": "constraint_id",
            "start_point": "start_point",
            "end_point": "end_point",
            "distance": "distance",
            "start_object_id": "start_object_id",
            "end_object_id": "end_object_id",
            "linked_rope_guid": "linked_rope_guid",
            "constraint_name": "constraint_name",
            "is_name_visible": "is_name_visible",
            "start_material": "start_material",
            "end_material": "end_material",
            "custom_rope": "custom_rope",
        }
        if key not in aliases:
            return False
        field_name = aliases[key]
        new_val = value
        if field_name in ("start_point", "end_point") and isinstance(value, (tuple, list)):
            new_val = tuple(float(v) for v in value)
        elif field_name == "distance":
            new_val = float(value)
        elif field_name in ("start_object_id", "end_object_id", "constraint_id"):
            new_val = int(value)
        elif field_name == "is_name_visible":
            new_val = bool(value)
        self._constraints[constraint_id] = replace(c, **{field_name: new_val})
        return True

    def to_save_dicts(self) -> tuple[list[dict], list[dict], list[dict]]:
        """Serialize to (constraints, distJoints, hingeJoints) for melsave."""
        constraints_json: list[dict] = []
        for cid in sorted(self._constraints.keys()):
            c = self._constraints[cid]
            constraints_json.append({
                "mainGuid": {"Value": c.main_guid},
                "constraintId": c.constraint_id,
                "startPoint": {"x": c.start_point[0], "y": c.start_point[1], "z": c.start_point[2]},
                "endPoint": {"x": c.end_point[0], "y": c.end_point[1], "z": c.end_point[2]},
                "distance": c.distance,
                "startObjectId": c.start_object_id,
                "endObjectId": c.end_object_id,
                "linkedRopeGuid": c.linked_rope_guid,
                "constraintName": c.constraint_name,
                "isNameVisible": c.is_name_visible,
                "startObjectConnectionMaterial": c.start_material,
                "endObjectConnectionMaterial": c.end_material,
                "customRope": c.custom_rope,
            })
        dist_json: list[dict] = []
        for cid in sorted(self._dist_mods.keys()):
            for m in self._dist_mods[cid]:
                dist_json.append({"index": cid, "dist": m.dist})
        hinge_json: list[dict] = []
        for cid in sorted(self._hinge_mods.keys()):
            for m in self._hinge_mods[cid]:
                hinge_json.append({
                    "index": cid,
                    "limits": {"x": m.limits[0], "y": m.limits[1]},
                    "useLimits": m.use_limits,
                })
        return constraints_json, dist_json, hinge_json

    def from_save_dicts(
        self,
        constraints_json: list,
        dist_joints_json: list,
        hinge_joints_json: list,
    ) -> None:
        """Load from parsed melsave JSON; IDs assigned from list order."""
        self._constraints.clear()
        self._dist_mods.clear()
        self._hinge_mods.clear()
        next_id = 1
        for entry in constraints_json or []:
            if not isinstance(entry, dict):
                continue
            mg = entry.get("mainGuid") or {}
            guid = mg.get("Value") if isinstance(mg, dict) else str(mg)
            sp = entry.get("startPoint") or {}
            ep = entry.get("endPoint") or {}
            cid = next_id
            next_id += 1
            self._constraints[cid] = Constraint(
                main_guid=str(guid or _new_guid()),
                constraint_id=int(entry.get("constraintId", 0)),
                start_point=(float(sp.get("x", 0.0)), float(sp.get("y", 0.0)), float(sp.get("z", 0.0))),
                end_point=(float(ep.get("x", 0.0)), float(ep.get("y", 0.0)), float(ep.get("z", 0.0))),
                distance=float(entry.get("distance", 0.0)),
                start_object_id=int(entry.get("startObjectId", 0)),
                end_object_id=int(entry.get("endObjectId", 0)),
                linked_rope_guid=str(entry.get("linkedRopeGuid", "") or ""),
                constraint_name=str(entry.get("constraintName", "") or ""),
                is_name_visible=bool(entry.get("isNameVisible", False)),
                start_material=str(entry.get("startObjectConnectionMaterial", "Wood") or "Wood"),
                end_material=str(entry.get("endObjectConnectionMaterial", "Wood") or "Wood"),
                custom_rope=entry.get("customRope"),
            )
        self._next_id = next_id
        for entry in dist_joints_json or []:
            if not isinstance(entry, dict):
                continue
            idx = int(entry.get("index", 0))
            self._dist_mods.setdefault(idx, []).append(
                DistJointMod(index=idx, dist=float(entry.get("dist", 0.0)))
            )
        for entry in hinge_joints_json or []:
            if not isinstance(entry, dict):
                continue
            idx = int(entry.get("index", 0))
            lim = entry.get("limits") or {}
            self._hinge_mods.setdefault(idx, []).append(
                HingeJointMod(
                    index=idx,
                    limits=(float(lim.get("x", 0.0)), float(lim.get("y", 0.0))),
                    use_limits=bool(entry.get("useLimits", False)),
                )
            )
