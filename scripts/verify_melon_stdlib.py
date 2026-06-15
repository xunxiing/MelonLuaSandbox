#!/usr/bin/env python3
"""Verify lupa exposes every symbol melon chip Lua allows (Lua-CSharp 5.2 subset)."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from lupa import LuaRuntime  # noqa: E402
from melon_lua.stdlib_melon import apply_melon_stdlib, DANGEROUS_GLOBALS  # noqa: E402

# From Lua-CSharp Standard/* + BasicLibrary (minus sandbox-stripped)
MELON_GLOBALS = [
    "assert",
    "error",
    "getmetatable",
    "ipairs",
    "next",
    "pairs",
    "pcall",
    "rawequal",
    "select",
    "setmetatable",
    "tonumber",
    "tostring",
    "type",
    "xpcall",
]

MELON_MATH = [
    "abs", "acos", "asin", "atan", "atan2", "ceil", "cos", "cosh", "deg", "exp",
    "floor", "fmod", "frexp", "ldexp", "log", "max", "min", "modf", "pow", "rad",
    "random", "randomseed", "sin", "sinh", "sqrt", "tan", "tanh",
]

MELON_STRING = [
    "byte", "char", "dump", "find", "format", "gmatch", "gsub", "len", "lower",
    "match", "rep", "reverse", "sub", "upper",
]

MELON_TABLE = ["concat", "insert", "pack", "remove", "sort", "unpack"]

MELON_BIT32 = [
    "arshift", "band", "bnot", "bor", "btest", "bxor", "extract", "lrotate",
    "lshift", "replace", "rrotate", "rshift",
]

MELON_COROUTINE = ["create", "resume", "running", "status", "wrap", "yield"]

MELON_OS = ["time", "clock"]

BANNED_MUST_BE_NIL = list(DANGEROUS_GLOBALS)


def probe(lua, code: str) -> bool:
    try:
        return bool(lua.eval(code))
    except Exception:
        return False


def main() -> int:
    lua = LuaRuntime(unpack_returned_tuples=True)
    g = lua.globals()
    apply_melon_stdlib(lua, g)

    missing: list[str] = []
    banned_ok: list[str] = []
    banned_bad: list[str] = []

    for name in MELON_GLOBALS:
        if not probe(lua, f"type({name}) == 'function' or type({name}) == 'table'"):
            missing.append(f"_G.{name}")

    for fn in MELON_MATH:
        if not probe(lua, f"type(math.{fn}) == 'function' or type(math.{fn}) == 'number'"):
            if fn == "huge" and probe(lua, "type(math.huge) == 'number'"):
                continue
            missing.append(f"math.{fn}")

    if not probe(lua, "type(math.huge) == 'number'"):
        missing.append("math.huge")

    if not probe(lua, "type(math.pi) == 'number'"):
        missing.append("math.pi")

    for fn in MELON_STRING:
        if not probe(lua, f"type(string.{fn}) == 'function'"):
            missing.append(f"string.{fn}")

    for fn in MELON_TABLE:
        if not probe(lua, f"type(table.{fn}) == 'function'"):
            missing.append(f"table.{fn}")

    for fn in MELON_BIT32:
        if not probe(lua, f"type(bit32.{fn}) == 'function'"):
            missing.append(f"bit32.{fn}")

    for fn in MELON_COROUTINE:
        if not probe(lua, f"type(coroutine.{fn}) == 'function'"):
            missing.append(f"coroutine.{fn}")

    for fn in MELON_OS:
        if not probe(
            lua,
            f"type(os.{fn}) == 'function' or type(os.{fn}) == 'userdata'",
        ):
            missing.append(f"os.{fn}")

    for name in BANNED_MUST_BE_NIL:
        if probe(lua, f"{name} ~= nil"):
            banned_bad.append(name)
        else:
            banned_ok.append(name)

    print("=== Melon stdlib verification (lupa after apply_melon_stdlib) ===")
    print(f"Missing ({len(missing)}):")
    for m in missing:
        print(f"  - {m}")
    print(f"Banned still present ({len(banned_bad)}): {banned_bad}")
    if not missing and not banned_bad:
        print("OK: full melon-allowed stdlib surface present.")
        return 0
    return 1


if __name__ == "__main__":
    raise SystemExit(main())