import sys
import os
from PIL import Image, ImageDraw, ImageFont
import numpy as np

from pathlib import Path
_ROOT = Path(__file__).resolve().parent.parent
(_ROOT / "temp").mkdir(exist_ok=True)
sys.path.insert(0, str(_ROOT))
from melon_lua import MelsaveSession

def render_text_to_pixel_list(text, font_size=14):
    """Render any text string to sharp 1-bit pixel matrix coordinates."""
    font_path = "C:\\Windows\\Fonts\\simsun.ttc"
    if os.path.exists(font_path):
        font = ImageFont.truetype(font_path, font_size)
    else:
        font = ImageFont.load_default()
        
    bbox = font.getbbox(text)
    w = int(max(bbox[2] + 4, 64))
    h = 32
    
    img = Image.new('L', (w, h), 0)
    draw = ImageDraw.Draw(img)
    draw.text((2, 4), text, font=font, fill=255)
    
    arr = np.array(img)
    mask = (arr > 110)
    
    pixels = []
    height, width = mask.shape
    for x in range(width):
        for y in range(height):
            if mask[y, x]:
                pixels.append((x, y))
    return pixels, width, height

def main():
    text_content = "MELON LUA · 原神 启动!"
    print(f"Rasterizing universal text: '{text_content}'...")
    
    pixels, total_width, total_height = render_text_to_pixel_list(text_content, font_size=14)
    print(f"Text width: {total_width}px, height: {total_height}px, total pixels: {len(pixels)}")
    
    hex_data = "".join([f"{x:02x}{y:02x}" for x, y in pixels])
    
    lua_code = f"""
local raw_hex_data = "{hex_data}"
local total_text_width = {total_width}
local screen_width = 64
local screen_height = 32

local all_pixels = {{}}
local scroll_offset = 0

local function decode_hex_data(hex_str)
    local pts = {{}}
    if not hex_str then return pts end
    local len = #hex_str
    for i = 1, len, 4 do
        local sx = string.sub(hex_str, i, i + 1)
        local sy = string.sub(hex_str, i + 2, i + 3)
        if #sx == 2 and #sy == 2 then
            local x = tonumber(sx, 16)
            local y = tonumber(sy, 16)
            if x ~= nil and y ~= nil then
                pts[#pts + 1] = {{x, y}}
            end
        end
    end
    return pts
end

function OnInit()
    all_pixels = decode_hex_data(raw_hex_data)
    scroll_offset = 0
end

function OnTick()
    -- Hide Screen Border Frame
    local targetId = inputs.entity.target
    if targetId and targetId ~= 0 then
        local e = Entity(targetId)
        if e and e:isValid() == 1 then
            e:setColor(0, 0, 0, 0)
        end
    end

    local buf = canvas_0.buffer
    if not buf or #all_pixels == 0 then return end

    canvas_0:clear(0, 0, 0)

    -- Advance smooth marquee scroll offset
    scroll_offset = scroll_offset + 1
    if scroll_offset >= total_text_width + screen_width then
        scroll_offset = 0
    end

    -- Render pixels with strict nil guards
    for i = 1, #all_pixels do
        local pt = all_pixels[i]
        if pt and pt[1] ~= nil and pt[2] ~= nil then
            local world_x = pt[1] - scroll_offset + screen_width
            local world_y = pt[2]
            
            if world_x >= 0 and world_x < screen_width and world_y >= 0 and world_y < screen_height then
                local r = 0.0 + (world_x / 64.0) * 0.9
                local g = 0.85
                local b = 1.0 - (world_x / 64.0) * 0.8
                canvas_0:setPixel(world_x, world_y, r, g, b, 1.0)
            end
        end
    end

    canvas_0:flush()

    outputs.string.status = string.format("印刷引擎运行中 | 文本: '%s'", "{text_content}")
end
"""

    output_path = _ROOT / "temp" / "universal_text_printer.melsave"
    with MelsaveSession() as s:
        cv = s.create_canvas(width=64, height=32, display_type="led_matrix", x=0, y=0, scale_x=2.0, scale_y=1.0)
        chip_idx = s.add_lua_chip(
            lua_code,
            canvases=[cv],
            inputs=[{"name": "target", "type": "entity"}],
            outputs=[{"name": "status", "type": "string"}],
            x=3.0, y=0.0,
            instruction_cost=200000
        )
        s.connect(cv.item_idx, "entity", chip_idx, "target")
        s.save(output_path)
        print(f"Saved Fixed Universal Text Printer Melsave to: {output_path}")

if __name__ == "__main__":
    main()
