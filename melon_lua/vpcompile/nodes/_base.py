"""Shared types for VP node Lua emitters."""
from __future__ import annotations

from typing import Callable

from ..ir import VPNode

NodeEmitter = Callable[[str, list[str], VPNode], list[str]]