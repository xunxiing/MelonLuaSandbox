"""Runtime mechanic simulations (Radar, etc.) for sandbox ticks."""
from .radar import (
    RADAR_OBJECT_ID,
    parse_radar_config,
    query_radar_hits,
    simulate_radars,
)
from .gate_propagate import (
    build_chip_inputs_from_wires,
    merge_inputs,
)

__all__ = [
    "RADAR_OBJECT_ID",
    "parse_radar_config",
    "query_radar_hits",
    "simulate_radars",
    "build_chip_inputs_from_wires",
    "merge_inputs",
]
