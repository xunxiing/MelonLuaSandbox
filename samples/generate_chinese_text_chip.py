import sys
import os
import numpy as np
from PIL import Image, ImageDraw, ImageFont

from pathlib import Path
_ROOT = Path(__file__).resolve().parent.parent
(_ROOT / "temp").mkdir(exist_ok=True)
sys.path.insert(0, str(_ROOT))
from melon_lua import MelsaveSession

def get_character_pixels(text, width=32, height=16):
    # Render text using SimHei font or msyh font matched to 32x16 pixel bounding box
    pil_img = Image.new('L', (width, height), 0)
    draw = ImageDraw.Draw(pil_img)
    
    font_path = "C:\\Windows\\Fonts\\simhei.ttf"
    if not os.path.exists(font_path):
        font_path = "C:\\Windows\\Fonts\\msyh.ttc"
    
    try:
        font = ImageFont.truetype(font_path, 14)
    except:
        font = ImageFont.load_default()
        
    draw.text((0, 0), text[0], fill=255, font=font)
    if len(text) > 1:
        draw.text((16, 0), text[1], fill=255, font=font)
        
    arr = np.array(pil_img)
    pixels = []
    # Collect non-zero pixel coordinates in stroke writing order
    for y in range(height):
        for x in range(width):
            if arr[y, x] > 100:
                pixels.append((x, y))
    return pixels

def main():
    text = "原神"
    width, height = 32, 16
    print(f"Generating pixel font for: {text} at resolution {width}x{height}")
    stroke_pixels = get_character_pixels(text, width=width, height=height)
    print(f"Total stroke pixels: {len(stroke_pixels)}")

    lua_pixels_str = "{" + ",".join([f"{{{x},{y}}}" for x, y in stroke_pixels]) + "}"

    lua_code = f"""
local stroke_pixels = {lua_pixels_str}
local total_pixels = #stroke_pixels
local drawn_count = 0
local ticks_per_pixel = 1
local tick_counter = 0

function OnInit()
    drawn_count = 0
    tick_counter = 0
end

function OnTick()
    -- Hide LED Screen Border (0,0,0,0)
    local targetId = inputs.entity.target
    if targetId and targetId ~= 0 then
        local e = Entity(targetId)
        if e and e:isValid() == 1 then
            e:setColor(0, 0, 0, 0)
        end
    end

    local buf = canvas_0.buffer
    if not buf then return end

    -- Advance stroke writing animation
    if drawn_count < total_pixels then
        tick_counter = tick_counter + 1
        if tick_counter >= ticks_per_pixel then
            tick_counter = 0
            drawn_count = math.min(total_pixels, drawn_count + 2)
        end
    end

    canvas_0:clear(0, 0, 0)

    -- Draw written strokes
    for i = 1, drawn_count do
        local pt = stroke_pixels[i]
        local px, py = pt[1], pt[2]
        
        if i >= drawn_count - 1 and drawn_count < total_pixels then
            -- Active writing tip (Golden Yellow Glow)
            canvas_0:setPixel(px, py, 1.0, 0.85, 0.2, 1.0)
        else
            -- Completed strokes (Cyan/Bright White Glow)
            canvas_0:setPixel(px, py, 0.1, 0.85, 1.0, 1.0)
        end
    end

    -- Pulse effect after text is fully written
    if drawn_count >= total_pixels then
        local pulse = 0.85 + 0.15 * math.sin(env.time() * 3.0)
        for i = 1, total_pixels do
            local pt = stroke_pixels[i]
            canvas_0:setPixel(pt[1], pt[2], 0.1 * pulse, 0.85 * pulse, 1.0 * pulse, 1.0)
        end
    end

    canvas_0:flush()
    outputs.string.status = string.format("Writing: %d / %d", drawn_count, total_pixels)
end
"""

    output_path = _ROOT / "temp" / "chinese_text_demo.melsave"
    with MelsaveSession() as s:
        # Scale 1:1 matching 32x16 pixel dimensions (width=32, height=16, scale_x=1.0, scale_y=0.5)
        cv = s.create_canvas(width=width, height=height, display_type="led_matrix", x=0, y=0, scale_x=1.0, scale_y=0.5)
        chip_idx = s.add_lua_chip(
            lua_code,
            canvases=[cv],
            inputs=[{"name": "target", "type": "entity"}],
            outputs=[{"name": "status", "type": "string"}],
            x=2.5, y=0.0,
            instruction_cost=1000000
        )
        s.connect(cv.item_idx, "entity", chip_idx, "target")
        s.save(output_path)
        print(f"Saved 1:1 scaled Chinese text demo melsave to: {output_path}")

if __name__ == "__main__":
    main()
