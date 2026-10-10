"""Native SDK 12x12 Pixel Text Printer Package Demo.

Demonstrates using melon_lua.packages.text_printer to rasterize standard 12x12
CJK pixel fonts and print them onto a 64x32 LED display matrix with 0-allocation Lua execution.
"""
import os
from melon_lua.session import MelsaveSession
from melon_lua.packages.text_printer import (
    generate_lua_text_printer_preamble,
    rasterize_text_to_hex,
)

def generate_native_text_save():
    s = MelsaveSession()
    
    # 1. Add 64x32 LED Matrix Canvas Display Screen (Obj 0)
    cv = s.create_canvas(
        width=64,
        height=32,
        x=0.0, y=3.0,
        scale_x=2.0, scale_y=1.0
    )

    # 2. Pre-rasterize test text strings with standard 12x12 pixel font
    hex_yuanshen, w1, h1 = rasterize_text_to_hex("原神", font_size=12)
    hex_tiangua, w2, h2 = rasterize_text_to_hex("甜瓜", font_size=12)
    hex_title, w3, h3 = rasterize_text_to_hex("12×12 像素点阵文字", font_size=12)

    preamble = generate_lua_text_printer_preamble()

    user_code = f"""{preamble}

local border_hidden = false
local hex_yuanshen = "{hex_yuanshen}"
local hex_tiangua = "{hex_tiangua}"
local hex_title = "{hex_title}"

local GOLD = {{ x = 1.0, y = 0.85, z = 0.2, w = 1.0 }}
local CYAN = {{ x = 0.0, y = 0.85, z = 1.0, w = 1.0 }}
local CRIMSON = {{ x = 1.0, y = 0.2, z = 0.3, w = 1.0 }}

function OnTick()
    if not border_hidden then
        if inputs and inputs.entity and inputs.entity.target then
            Entity(inputs.entity.target):setColor(0, 0, 0, 0)
            border_hidden = true
        end
    end

    local cv_inst = canvas_0
    if not cv_inst or not cv_inst.buffer then return end

    cv_inst:clear(0, 0, 0)

    -- Print crisp 12x12 pixel text test characters
    TextPrinter.print(cv_inst.buffer, 64, 32, 2, 2, hex_yuanshen, GOLD)
    TextPrinter.print(cv_inst.buffer, 64, 32, 32, 2, hex_tiangua, CYAN)
    TextPrinter.print(cv_inst.buffer, 64, 32, 2, 18, hex_title, CRIMSON)

    cv_inst:flush()

    if outputs and outputs.string and outputs.string.status then
        outputs.string.status = "标准 12x12 像素文字引擎运行中 | 0 垃圾回收"
    end
end
"""

    chip_idx = s.add_lua_chip(
        user_code,
        inputs=[{"name": "target", "type": "entity"}],
        outputs=[{"name": "status", "type": "string"}],
        canvases=[cv],
        x=0.0, y=-2.0
    )

    s.connect(cv.item_idx, "entity", chip_idx, "target")

    save_path = "native_pixel_text_demo.melsave"
    s.save(save_path)
    print(f"Successfully generated 12x12 Native Pixel Text Demo: {os.path.abspath(save_path)}")

if __name__ == "__main__":
    generate_native_text_save()
