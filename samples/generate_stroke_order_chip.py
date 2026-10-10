import sys
import os
import re
import json
import urllib.request
import urllib.parse
from PIL import Image, ImageDraw
import numpy as np

from pathlib import Path
_ROOT = Path(__file__).resolve().parent.parent
(_ROOT / "temp").mkdir(exist_ok=True)
sys.path.insert(0, str(_ROOT))
from melon_lua import MelsaveSession

def get_clean_stroke_pixel_sequence(char, x_offset=0, grid_w=32, grid_h=32):
    url = 'https://cdn.jsdelivr.net/npm/hanzi-writer-data@2.0/' + urllib.parse.quote(char) + '.json'
    req = urllib.request.urlopen(url)
    data = json.loads(req.read().decode('utf-8'))
    
    stroke_list = []
    for stroke_idx, stroke_svg in enumerate(data['strokes']):
        tokens = re.findall(r'[A-Za-z]|-?\d+(?:\.\d+)?', stroke_svg)
        commands = []
        i = 0
        while i < len(tokens):
            if tokens[i].isalpha():
                cmd = tokens[i]
                i += 1
                args = []
                while i < len(tokens) and not tokens[i].isalpha():
                    args.append(float(tokens[i]))
                    i += 1
                commands.append((cmd, args))
        
        centerline_pts = []
        curr = (0.0, 0.0)
        for cmd, args in commands:
            if cmd in ('M', 'L'):
                curr = (args[0], args[1])
                centerline_pts.append(curr)
            elif cmd == 'Q':
                p0 = curr
                p1, p2 = (args[0], args[1]), (args[2], args[3])
                for step in range(1, 10):
                    t = step / 9.0
                    x = (1-t)**2 * p0[0] + 2*(1-t)*t * p1[0] + t**2 * p2[0]
                    y = (1-t)**2 * p0[1] + 2*(1-t)*t * p1[1] + t**2 * p2[1]
                    centerline_pts.append((x, y))
                curr = p2
            elif cmd == 'C':
                p0 = curr
                p1, p2, p3 = (args[0], args[1]), (args[2], args[3]), (args[4], args[5])
                for step in range(1, 10):
                    t = step / 9.0
                    x = (1-t)**3 * p0[0] + 3*(1-t)**2*t * p1[0] + 3*(1-t)*t**2 * p2[0] + t**3 * p3[0]
                    y = (1-t)**3 * p0[1] + 3*(1-t)**2*t * p1[1] + 3*(1-t)*t**2 * p2[1] + t**3 * p3[1]
                    centerline_pts.append((x, y))
                curr = p3
        
        img = Image.new('L', (grid_w, grid_h), 0)
        draw = ImageDraw.Draw(img)
        poly_pts = [(2.0 + pt[0] / 1024.0 * (grid_w - 4), 2.0 + (1024.0 - pt[1]) / 1024.0 * (grid_h - 4)) for pt in centerline_pts]
        draw.polygon(poly_pts, fill=255)
        arr = np.array(img)
        
        pixel_set = set()
        for y in range(grid_h):
            for x in range(grid_w):
                if arr[y, x] > 100:
                    pixel_set.add((x + x_offset, y))
        
        def get_pixel_progress(px_offset, py):
            px = px_offset - x_offset
            min_dist = 999999.0
            best_idx = 0
            for idx, cpt in enumerate(centerline_pts):
                cx = 2.0 + cpt[0] / 1024.0 * (grid_w - 4)
                cy = 2.0 + (1024.0 - cpt[1]) / 1024.0 * (grid_h - 4)
                dist = (px - cx)**2 + (py - cy)**2
                if dist < min_dist:
                    min_dist = dist
                    best_idx = idx
            return best_idx
            
        ordered_pixels = sorted(list(pixel_set), key=lambda p: get_pixel_progress(p[0], p[1]))
        stroke_list.append({
            "char": char,
            "stroke_num": stroke_idx + 1,
            "total_strokes": len(data['strokes']),
            "pixels": ordered_pixels
        })
    return stroke_list

def main():
    print("Generating iPad-Crash-Proof Flat Encoded Stroke Order Chip...")
    yuan_strokes = get_clean_stroke_pixel_sequence('原', x_offset=0)
    shen_strokes = get_clean_stroke_pixel_sequence('神', x_offset=32)
    
    all_strokes = yuan_strokes + shen_strokes
    
    # Flat hex encoding for crash-proof Lua parsing
    strokes_lua_items = []
    for st in all_strokes:
        hex_data = "".join([f"{x:02x}{y:02x}" for x, y in st["pixels"]])
        strokes_lua_items.append(
            f"{{char='{st['char']}', stroke_num={st['stroke_num']}, total_strokes={st['total_strokes']}, data='{hex_data}'}}"
        )
    
    lua_db_str = "{\n" + ",\n".join(strokes_lua_items) + "\n}"
    
    lua_code = f"""
local stroke_raw_db = {lua_db_str}
local total_strokes = #stroke_raw_db

local stroke_db = {{}}
local curr_stroke_idx = 1
local curr_pixel_step = 1
local speed_pixels_per_tick = 3
local pause_ticks = 30
local pause_counter = 0

local function decode_hex_pts(hex_str)
    local pts = {{}}
    local len = #hex_str
    for i = 1, len, 4 do
        local x = tonumber(string.sub(hex_str, i, i + 1), 16)
        local y = tonumber(string.sub(hex_str, i + 2, i + 3), 16)
        pts[#pts + 1] = {{x, y}}
    end
    return pts
end

function OnInit()
    -- Decode flat hex string to points table safely inside OnInit
    for i = 1, total_strokes do
        local item = stroke_raw_db[i]
        stroke_db[i] = {{
            char = item.char,
            stroke_num = item.stroke_num,
            total_strokes = item.total_strokes,
            pts = decode_hex_pts(item.data)
        }}
    end

    curr_stroke_idx = 1
    curr_pixel_step = 1
    pause_counter = 0
end

function OnTick()
    -- Hide Screen Border
    local targetId = inputs.entity.target
    if targetId and targetId ~= 0 then
        local e = Entity(targetId)
        if e and e:isValid() == 1 then
            e:setColor(0, 0, 0, 0)
        end
    end

    local buf = canvas_0.buffer
    if not buf or #stroke_db == 0 then return end

    canvas_0:clear(0, 0, 0)

    local curr_stroke = stroke_db[curr_stroke_idx]
    local pts = curr_stroke.pts
    local n_pts = #pts

    -- 1. Draw Ghost Outline for all character strokes (Dim Translucent Gray)
    for i = 1, total_strokes do
        local st = stroke_db[i]
        if st.char == curr_stroke.char then
            for _, pt in ipairs(st.pts) do
                canvas_0:setPixel(pt[1], pt[2], 0.12, 0.12, 0.16, 1.0)
            end
        end
    end

    -- 2. Draw Completed Strokes for current character (Solid Neon Cyan)
    for i = 1, curr_stroke_idx - 1 do
        local st = stroke_db[i]
        if st.char == curr_stroke.char then
            for _, pt in ipairs(st.pts) do
                canvas_0:setPixel(pt[1], pt[2], 0.0, 0.85, 1.0, 1.0)
            end
        end
    end

    -- 3. Draw Active Stroke Unrolling Animation
    if pause_counter == 0 then
        curr_pixel_step = curr_pixel_step + speed_pixels_per_tick
        if curr_pixel_step >= n_pts then
            curr_pixel_step = n_pts
            if curr_stroke_idx == total_strokes or stroke_db[curr_stroke_idx + 1].char ~= curr_stroke.char then
                pause_counter = pause_ticks -- Pause when full character is written
            else
                curr_stroke_idx = curr_stroke_idx + 1
                curr_pixel_step = 1
            end
        end
    else
        pause_counter = pause_counter - 1
        if pause_counter == 0 then
            curr_stroke_idx = curr_stroke_idx + 1
            curr_pixel_step = 1
            if curr_stroke_idx > total_strokes then
                curr_stroke_idx = 1 -- Repeat loop
            end
        end
    end

    -- Draw written portion of active stroke up to curr_pixel_step (Solid Neon Cyan)
    for p = 1, math.min(curr_pixel_step, n_pts) do
        local pt = pts[p]
        canvas_0:setPixel(pt[1], pt[2], 0.0, 0.85, 1.0, 1.0)
    end

    -- Draw Active Golden Writing Tip EXACTLY on the current stroke pixel (Brilliant Golden Red)
    if curr_pixel_step <= n_pts and curr_pixel_step >= 1 then
        local tip_pt = pts[curr_pixel_step]
        canvas_0:setPixel(tip_pt[1], tip_pt[2], 1.0, 0.9, 0.1, 1.0)
    end

    canvas_0:flush()

    outputs.string.status = string.format("【%s】书写中... 第 %d / %d 笔", curr_stroke.char, curr_stroke.stroke_num, curr_stroke.total_strokes)
end
"""

    output_path = _ROOT / "temp" / "stroke_order_demo.melsave"
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
        print(f"Saved iPad-Crash-Proof Stroke Order Melsave to: {output_path}")

if __name__ == "__main__":
    main()
