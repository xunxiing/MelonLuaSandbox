"""VP node name → Lua emitter registry (sharded by domain)."""
from __future__ import annotations

from ._base import NodeEmitter
from .entity_read import ENTITY_READ_EMITTERS
from .entity_write import ENTITY_WRITE_EMITTERS
from .flow import FLOW_EMITTERS
from .logic import LOGIC_EMITTERS
from .math_basic import MATH_BASIC_EMITTERS
from .math_trig import MATH_TRIG_EMITTERS
from .vector import VECTOR_EMITTERS

REGISTRY: dict[str, NodeEmitter] = {}
REGISTRY.update(MATH_BASIC_EMITTERS)
REGISTRY.update(MATH_TRIG_EMITTERS)
REGISTRY.update(VECTOR_EMITTERS)
REGISTRY.update(FLOW_EMITTERS)
REGISTRY.update(LOGIC_EMITTERS)
REGISTRY.update(ENTITY_READ_EMITTERS)
REGISTRY.update(ENTITY_WRITE_EMITTERS)

__all__ = ["REGISTRY", "NodeEmitter"]