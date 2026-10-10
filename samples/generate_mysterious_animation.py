import sys
import os
from PIL import Image, ImageDraw, ImageFont
import numpy as np

from pathlib import Path
_ROOT = Path(__file__).resolve().parent.parent
(_ROOT / "temp").mkdir(exist_ok=True)
sys.path.insert(0, str(_ROOT))
from melon_lua import MelsaveSession

def render_text_to_hex_data(text, font_size=12):
    font_path = "C:\\Windows\\Fonts\\arial.ttf"
    if os.path.exists(font_path):
        font = ImageFont.truetype(font_path, font_size)
    else:
        font = ImageFont.load_default()
        
    bbox = font.getbbox(text)
    w = int(max(bbox[2] + 4, 64))
    h = 16
    
    img = Image.new('L', (w, h), 0)
    draw = ImageDraw.Draw(img)
    draw.text((2, 0), text, font=font, fill=255)
    
    arr = np.array(img)
    mask = (arr > 100)
    
    pixels = []
    height, width = mask.shape
    for x in range(width):
        for y in range(height):
            if mask[y, x]:
                pixels.append((x, y))
    hex_data = "".join([f"{x:02x}{y:02x}" for x, y in pixels])
    return hex_data, width

def main():
    print("Generating Mysterious Sci-Fi Matrix Animation Chip...")
    text1_hex, text1_w = render_text_to_hex_data("MELON LUA MATRIX", font_size=12)
    text2_hex, text2_w = render_text_to_hex_data("SYSTEM AWAKENED", font_size=12)
    
    lua_code = f"""
local hex_t1 = "{text1_hex}"
local hex_t2 = "{text2_hex}"

local pixels_t1 = {{}}
local pixels_t2 = {{}}

local phase = 1
local ticks = 0

-- Digital Rain Columns
local rain_drops = {{}}
for c = 0, 63 do
    rain_drops[c] = math.random(0, 31)
end

local function decode_hex(hex_str)
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
    pixels_t1 = decode_hex(hex_t1)
    pixels_t2 = decode_hex(hex_t2)
    phase = 1
    ticks = 0
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
    if not buf then return end

    canvas_0:clear(0, 0, 0)
    ticks = ticks + 1

    -- Stage Management (Loop through 3 Mysterious Phases)
    local cycle_tick = ticks % 450

    if cycle_tick < 150 then
        -- STAGE 1: Matrix Digital Rain & Signal Glitch (神秘数字雨与电波涟漪)
        for x = 0, 63, 2 do
            local head_y = (rain_drops[x] + math.floor(ticks * 0.8)) % 32
            -- Drop Head (Cyan Glow)
            canvas_0:setPixel(x, head_y, 0.2, 1.0, 0.4, 1.0)
            -- Trail (Dark Green)
            for tail = 1, 6 do
                local ty = (head_y - tail + 32) % 32
                local alpha = 1.0 - (tail / 6.0)
                canvas_0:setPixel(x, ty, 0.0, 0.4 * alpha, 0.1 * alpha, 1.0)
            end
        end

    elseif cycle_tick < 300 then
        -- STAGE 2: Cyber Eye Awakening & Geometric Pulse (神秘法阵 / 赛博全息之眼开合)
        local t_eye = cycle_tick - 150
        local radius = 3.0 + math.sin(t_eye * 0.15) * 4.0
        local cx, cy = 32, 16

        -- Pulsing Magic Circle
        for angle = 0, 360, 15 do
            local rad = angle * 3.14159 / 180.0
            local px = math.floor(cx + math.cos(rad) * radius)
            local py = math.floor(cy + math.sin(rad) * radius)
            if px >= 0 and px < 64 and py >= 0 and py < 32 then
                canvas_0:setPixel(px, py, 1.0, 0.8, 0.1, 1.0)
            end
        end

        -- Center Pupils / Energy Core
        local pupil_glow = 0.5 + math.sin(t_eye * 0.3) * 0.5
        for dx = -1, 1 do
            for dy = -1, 1 do
                canvas_0:setPixel(cx + dx, cy + dy, 1.0, 0.2 * pupil_glow, 0.9 * pupil_glow, 1.0)
            end
        end

        -- Radiating Waves
        for w = 1, 3 do
            local wave_r = (t_eye + w * 10) % 25
            for a = 0, 360, 30 do
                local rad = a * 3.14159 / 180.0
                local wx = math.floor(cx + math.cos(rad) * wave_r)
                local wy = math.floor(cy + math.sin(rad) * wave_r * 0.5)
                if wx >= 0 and wx < 64 and wy >= 0 and wy < 32 then
                    canvas_0:setPixel(wx, wy, 0.0, 0.7, 1.0, 1.0)
                end
            end
        end

    else
        -- STAGE 3: Holographic Text Awakening (全息字模降临)
        local t_text = cycle_tick - 300
        local active_pts = (t_text < 75) and pixels_t1 or pixels_t2
        local reveal_count = math.floor((t_text % 75) * (#active_pts / 50.0))

        for i = 1, math.min(reveal_count, #active_pts) do
            local pt = active_pts[i]
            if pt and pt[1] ~= nil and pt[2] ~= nil then
                local py = pt[2] + 8
                if py >= 0 and py < 32 then
                    -- Pulsing Cyan Blue Gradient
                    local wave = 0.7 + math.sin(ticks * 0.2 + pt[1] * 0.1) * 0.3
                    canvas_0:setPixel(pt[1], py, 0.0, 0.85 * wave, 1.0 * wave, 1.0)
                end
            end
        end
    end

    canvas_0:flush()

    outputs.string.status = string.format("神秘矩阵 Phase %d | Tick: %d", (math.floor(cycle_tick / 150) + 1), ticks)
end
"""

    output_path = _ROOT / "temp" / "mysterious_animation.melsave"
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
        print(f"Saved Mysterious Sci-Fi Animation Melsave to: {output_path}")

if __name__ == "__main__":
    main()
