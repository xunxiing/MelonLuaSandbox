"""Melon chip Lua standard library — mirrors LuaSandboxConfigBase + ApiReference.

Engine: Lua-CSharp 5.2 with selective Open*Library calls from LuaBackendConfig.
Sandbox: strip dangerous globals (LuaSandboxGlobals.Dangerous).

This module applies the same policy on lupa (LuaJIT 5.1): keep math/string/table/coroutine,
optional bit32 (shim from LuaJIT `bit`), minimal os.time/os.clock, ban io/package/load*.
"""
from __future__ import annotations

import time as _time
from pathlib import Path
from typing import Any

_SHIM_PATH = Path(__file__).resolve().parent / "stdlib_bit32_shim.lua"
_PACK_SHIM = """
if table.pack == nil then
    function table.pack(...)
        return { n = select('#', ...), ... }
    end
end
if unpack == nil and table.unpack ~= nil then
    unpack = table.unpack
end
"""

# Globals removed in melon (typical sandbox)
DANGEROUS_GLOBALS = (
    "io",
    "loadfile",
    "dofile",
    "package",
    "module",
    "debug",
    "collectgarbage",
    "load",
    "loadstring",
)

# ApiReference documents these; runner must not delete them
ALLOWED_GLOBALS_DOC = (
    "pairs",
    "ipairs",
    "type",
    "tostring",
    "tonumber",
    "select",
    "unpack",
    "pcall",
    "xpcall",
    "error",
    "assert",
    "next",
    "setmetatable",
    "getmetatable",
    "rawequal",
)


def apply_melon_stdlib(lua: Any, g: Any) -> None:
    """After LuaRuntime() creation, before preamble + backends."""
    for name in DANGEROUS_GLOBALS:
        g[name] = None

    if _SHIM_PATH.is_file():
        lua.execute(_SHIM_PATH.read_text(encoding="utf-8"))
    lua.execute(_PACK_SHIM)
    lua.execute(
        """
        if math.atan2 == nil and math.atan ~= nil then
            math.atan2 = function(y, x) return math.atan(y, x) end
        end
        if math.pow == nil then math.pow = function(x, y) return x ^ y end end
        if math.cosh == nil then
            math.cosh = function(x) local e = math.exp(x); return (e + 1/e) / 2 end
        end
        if math.sinh == nil then
            math.sinh = function(x) local e = math.exp(x); return (e - 1/e) / 2 end
        end
        if math.tanh == nil then
            math.tanh = function(x) local e = math.exp(2*x); return (e-1)/(e+1) end
        end
        """
    )

    lua.execute(
        """
        os = os or {}
        if os.time == nil then
            function os.time(t)
                if t then return 0 end
                return 0
            end
        end
        if os.clock == nil then
            function os.clock() return 0 end
        end
        """
    )
    os_tbl = lua.table_from(
        {
            "time": lambda *args: _melon_os_time(lua, *args),
            "clock": lambda: _time.perf_counter(),
        }
    )
    g["os"] = os_tbl


def _melon_os_time(lua: Any, *args: Any) -> float:
    if len(args) >= 1:
        # table unpack not needed for chip scripts; return wall clock
        return float(_time.time())
    return float(_time.time())