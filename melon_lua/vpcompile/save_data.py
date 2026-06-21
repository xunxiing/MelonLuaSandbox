"""Parse VP node SaveData JSON."""
from __future__ import annotations

import json

from .ir import VPNode


def constant_value(node: VPNode) -> float:
    sd = node.save_data
    if not sd:
        return 0.0
    try:
        obj = json.loads(sd)
        dv = obj.get("DataValue")
        if dv is None:
            return 0.0
        return float(dv)
    except (json.JSONDecodeError, TypeError, ValueError):
        return 0.0