"""Chinese Character Printing Package Extension (紫晶石灰 API).

Provides Chinese character rendering using the Cubic_11 11x11 pixel font library (8105 Hanzi + ASCII 32~126).

The bundled provider source ships as package data
(``melon_lua/data/chinese_printing_provider.lua``). To load the provider
from a device save instead, point the ``MELON_CHINESE_PRINTING_SAVE``
environment variable at a ``.melsave`` file containing the
``Chinese_character_printing`` chip.
"""
import os
from pathlib import Path
from typing import Optional

_PROVIDER_DATA = Path(__file__).resolve().parent.parent / "data" / "chinese_printing_provider.lua"

# Optional override: path to a .melsave that contains the provider chip.
PROVIDER_SAVE_PATH = os.environ.get("MELON_CHINESE_PRINTING_SAVE", "")

_CHINESE_PRINTING_SOURCE_CACHE: Optional[str] = None


def _extract_source_from_save(path: str) -> Optional[str]:
    """Pull the largest Chinese_character_printing lua_chip_source from a save."""
    from melon_lua.melsave import read_melsave

    doc = read_melsave(path)
    best: Optional[str] = None
    for obj in doc.objects:
        for meta in obj.raw.get("saveMetaDatas", []):
            if meta.get("key") == "lua_chip_source":
                val = meta.get("stringValue")
                if isinstance(val, str) and "Chinese_character_printing" in val:
                    if best is None or len(val) > len(best):
                        best = val
    return best


def _apply_device_patches(val: str) -> str:
    # All patches are guarded so they are idempotent: the bundled provider
    # source already carries them, and a raw device save gets patched once.
    # Patch 1: Fix 3-byte UTF-8 Chinese character substring traversal (string.sub(ezm,ci,ci) -> string.sub(ezm,ci,ci+2))
    if "string.sub(ezm,ci,ci+2)" not in val:
        val = val.replace("local za=string.sub(ezm,ci,ci)", "local za=string.sub(ezm,ci,ci+2)")
        val = val.replace("ci=ci+1", "ci=ci+3")

    # Patch 2: Fix 0-based index returned by hip(xr,yr,gx,gy) to 1-based indexing ((xr*gy)+gx -> (xr*gy)+gx+1)
    if "(xr*gy)+gx+1" not in val:
        val = val.replace("return (xr*gy)+gx", "return (xr*gy)+gx+1")

    # Patch 3: Replace C#-Reflection-breaking table.remove / table.insert with direct Vector4 property mutation
    old_mutation = "table.remove(arrayu,we)\n table.insert(arrayu,we,rgb)"
    new_mutation = "local p=arrayu[we]\n if p then p.x=rgb.x or rgb[1] or 0; p.y=rgb.y or rgb[2] or 0; p.z=rgb.z or rgb[3] or 0; p.w=rgb.w or rgb[4] or 1 end"
    if "table.remove(arrayu,we)" in val:
        val = val.replace(old_mutation, new_mutation)
    return val


def get_chinese_printing_source() -> str:
    """Retrieve the full 379KB Lua module source code for Chinese_character_printing with real-device compatibility patches."""
    global _CHINESE_PRINTING_SOURCE_CACHE
    if _CHINESE_PRINTING_SOURCE_CACHE is not None:
        return _CHINESE_PRINTING_SOURCE_CACHE

    raw: Optional[str] = None
    tried = []
    if PROVIDER_SAVE_PATH:
        tried.append(PROVIDER_SAVE_PATH)
        if os.path.exists(PROVIDER_SAVE_PATH):
            raw = _extract_source_from_save(PROVIDER_SAVE_PATH)
    if raw is None:
        tried.append(str(_PROVIDER_DATA))
        if _PROVIDER_DATA.exists():
            raw = _PROVIDER_DATA.read_text(encoding="utf-8")

    if raw is None:
        raise FileNotFoundError(
            "Chinese character printing provider source not found. "
            f"Tried: {tried}. "
            "Set MELON_CHINESE_PRINTING_SAVE to a .melsave containing the "
            "Chinese_character_printing chip to override."
        )

    val = _apply_device_patches(raw)
    _CHINESE_PRINTING_SOURCE_CACHE = val
    return val


def add_chinese_printing_provider(session, x: float = -3.0, y: float = 0.0) -> int:
    """Add a dedicated Chinese_character_printing provider chip to the MelsaveSession.

    This chip registers the 'Chinese_character_printing' module in shared.modules on OnInit().
    Any other Lua chip in the save can then use require("Chinese_character_printing") or call it directly.
    """
    src = get_chinese_printing_source()
    chip_idx = session.add_lua_chip(
        src,
        inputs=[],
        outputs=[],
        x=x, y=y,
        instruction_cost=1000000
    )
    return chip_idx
