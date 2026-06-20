"""Melon Lua Sandbox — 甜瓜游乐场 Lua 芯片执行器模拟.

芯片运行时对齐 APK：LuaPreamble + 11 ApiModules + melon 允许的标准库。
SDK 提供 WorldContext / MelonScriptRunner 与 495 物体 objectId+尺寸目录。
"""
from .runner import MelonScriptRunner
from .preview import render_world
from .world import WorldContext, CameraState, InputState
from .entity import Entity
from .constraints import ConstraintRegistry, Constraint
from .catalog import (
    catalog_stats,
    get_profile_by_object_id,
    get_profile_by_name,
    list_spawnables,
    object_id_for_name,
    resolve_spawn_name,
)
from .melmod import load_melmod_pack, MelmodEntry, MelmodPart
from .melsave import read_melsave, list_objects, MelsaveDocument, MelsaveObject
from .melsave_writer import write_melsave, write_world_to_melsave, build_diff_from_world, WorldDiff
from .session import MelsaveSession

__version__ = "3.2.0"

__all__ = [
    "MelonScriptRunner",
    "render_world",
    "WorldContext",
    "CameraState",
    "InputState",
    "Entity",
    "ConstraintRegistry",
    "Constraint",
    "catalog_stats",
    "get_profile_by_object_id",
    "get_profile_by_name",
    "list_spawnables",
    "object_id_for_name",
    "resolve_spawn_name",
    "load_melmod_pack",
    "MelmodEntry",
    "MelmodPart",
    "read_melsave",
    "list_objects",
    "MelsaveDocument",
    "MelsaveObject",
    "write_melsave",
    "write_world_to_melsave",
    "build_diff_from_world",
    "WorldDiff",
    "MelsaveSession",
]