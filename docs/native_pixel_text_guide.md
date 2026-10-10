# MelonLuaSandbox Native Pixel Text Printing Package Guide

## Overview

`melon_lua.packages.text_printer` is the official built-in Python SDK pixel text printing package for Melon Playground LED matrix displays and canvas chips.

Unlike third-party modules that execute slow `table.remove`/`table.insert` array operations, `text_printer` provides a **100% crash-proof, 0-allocation native text printing engine** with **dynamic font sizing and auto-fit screen scaling**:
- **Compact Font Sizes**: Supports 8px ultra-mini micro pixel fonts (8x8 grid), 10px compact fonts, and 12px standard fonts.
- **Auto-Fit Screen Scaling**: Automatically calculates font size based on `max_width` / `max_height` bounds so text never spills over screen boundaries.
- **Zero GC Overhead**: Operates directly on pre-allocated Vector4 display buffers (`buf[slot].x = r`).
- **Mobile/iPad Crash-Proof**: Text pixel data is compressed into compact Flat Hex strings (`data = "001802..."`), causing zero C# AST stack recursion on IL2CPP platforms.

## Usage in Python SDK

```python
from melon_lua.session import MelsaveSession
from melon_lua.packages.text_printer import (
    generate_lua_text_printer_preamble,
    rasterize_text_to_hex,
)

s = MelsaveSession()
cv = s.create_canvas(width=64, height=32)

# 1. Rasterize text with 8px compact font size & auto-fit
hex_title, w, h, size = rasterize_text_to_hex(
    "甜瓜游乐场 · 8px微型点阵字",
    font_size=8,
    max_width=60,
    auto_fit=True
)

preamble = generate_lua_text_printer_preamble()

lua_code = f"""{preamble}
local hex_title = "{hex_title}"
local GOLD = {{ x = 1.0, y = 0.85, z = 0.2, w = 1.0 }}

function OnTick()
    canvas_0:clear(0, 0, 0)
    TextPrinter.print(canvas_0.buffer, 64, 32, 2, 2, hex_title, GOLD)
    canvas_0:flush()
end
"""

s.add_lua_chip(lua_code, canvases=[cv])
s.save("my_text_demo.melsave")
```

## Features

- **Font Size Control (`font_size`)**: Choose between 6px, 8px, 10px, 12px, 16px font sizes.
- **Auto-Fit Scaling (`auto_fit=True`, `max_width`)**: Prevents characters from being too large for screen boundaries.
- **Crash-Proof Flat Hex Encoding**: Stores point matrices as compact hex strings.
- **Direct Vector4 In-Place Mutation**: Preserves host C# VM memory reflection on `led-matrix-data`.
