"""Runtime mechanic simulations (Radar, Ranger, etc.) for sandbox ticks."""
from .radar import (
    RADAR_OBJECT_ID,
    parse_radar_config,
    query_radar_hits,
    simulate_radars,
)
from .ranger import (
    RANGER_OBJECT_ID,
    simulate_rangers,
)
from .gate_propagate import (
    build_chip_inputs_from_wires,
    merge_inputs,
    normalize_inputs,
)

__all__ = [
    "RADAR_OBJECT_ID",
    "parse_radar_config",
    "query_radar_hits",
    "simulate_radars",
    "RANGER_OBJECT_ID",
    "simulate_rangers",
    "build_chip_inputs_from_wires",
    "merge_inputs",
    "normalize_inputs",
]
