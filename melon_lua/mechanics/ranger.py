"""Range Finder (激光雷达 / Ranger, objectId 13) raycast simulation.

Each tick, for every alive Ranger entity, cast a ray from its position along
its facing direction and report the closest hit distance / entity id into
``world.gate_output_values[container_idx]`` under gate names ``dist`` /
``hit`` (plus ``distance`` alias). Mirrors the area-radar sim in radar.py.
"""

from __future__ import annotations

import math
from typing import Any

try:
    from Box2D import b2RayCastCallback
except ImportError:  # pragma: no cover - Box2D optional
    b2RayCastCallback = object

RANGER_OBJECT_ID = 13
DEFAULT_RANGE = 50.0


class _ClosestRayHit(b2RayCastCallback):
    """pybox2d raycast callback keeping the closest fixture hit."""

    def __init__(self, skip_body: Any = None) -> None:
        super().__init__()
        self.fraction = 1.0
        self.fixture = None
        self.point = None
        self.normal = None
        self.skip_body = skip_body

    def ReportFixture(self, fixture, point, normal, fraction):  # noqa: N802
        body = fixture.body
        if body is self.skip_body:
            return -1.0  # ignore self, keep casting
        if fraction < self.fraction:
            self.fraction = fraction
            self.fixture = fixture
            self.point = point
            self.normal = normal
        return fraction  # clip ray at current best


def _entity_id_of_body(world: Any, body: Any) -> int:
    eid = getattr(body, "userData", None)
    try:
        return int(eid) if eid is not None else 0
    except (TypeError, ValueError):
        return 0


def simulate_rangers(world: Any, doc_raw: dict | None = None) -> dict[int, dict[str, Any]]:
    """Raycast every Ranger entity; store outputs on world.gate_output_values."""
    if not hasattr(world, "gate_output_values") or world.gate_output_values is None:
        world.gate_output_values = {}

    b2_world = getattr(world, "b2_world", None)
    if b2_world is None:
        return {}

    results: dict[int, dict[str, Any]] = {}
    for e in list(world.entities.values()):
        if not getattr(e, "alive", True):
            continue
        if int(e.object_id or 0) != RANGER_OBJECT_ID:
            continue
        cidx = e.custom_data.get("container_idx")
        if cidx is None:
            continue
        cidx = int(cidx)

        # activation comes from the save container (default on), not the
        # entity attribute (which is 0 unless driven by an input gate).
        act = 1.0
        if doc_raw:
            conts = doc_raw.get("saveObjectContainers") or []
            if isinstance(conts, list) and 0 <= cidx < len(conts):
                so = conts[cidx].get("saveObjects") or {}
                if isinstance(so, dict):
                    act = float(so.get("activation", 1) or 0.0)
        bucket = world.gate_output_values.setdefault(cidx, {})
        if act < 0.5:
            bucket.update({"dist": 0.0, "distance": 0.0, "hit": 0})
            results[cidx] = bucket
            continue

        body = world.get_body(e.entity_id)
        px, py = float(e.position_x), float(e.position_y)
        ang = math.radians(float(getattr(e, "angle", 0.0) or 0.0))
        dx, dy = math.cos(ang), math.sin(ang)
        p2 = (px + dx * DEFAULT_RANGE, py + dy * DEFAULT_RANGE)

        cb = _ClosestRayHit(skip_body=body)
        try:
            b2_world.RayCast(cb, (px, py), p2)
        except Exception:
            cb = _ClosestRayHit(skip_body=body)  # type: ignore[assignment]

        if cb.fixture is not None:
            dist = float(cb.fraction) * DEFAULT_RANGE
            eid = _entity_id_of_body(world, cb.fixture.body)
            bucket.update({"dist": dist, "distance": dist, "hit": eid})
        else:
            bucket.update({"dist": 0.0, "distance": 0.0, "hit": 0})
        results[cidx] = bucket
    return results
