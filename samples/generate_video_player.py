import sys
import os
import cv2

video_path = _ROOT / "temp" / "1427965331-1-192.mp4"
output_save = _ROOT / "temp" / "video_player_9screens.melsave"

from pathlib import Path
_ROOT = Path(__file__).resolve().parent.parent
(_ROOT / "temp").mkdir(exist_ok=True)
sys.path.insert(0, str(_ROOT))
from melon_lua import MelsaveSession

def main():
    print("Extracting 200x160 video frames from 2:00 (120s)...")
    cap = cv2.VideoCapture(video_path)
    fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
    start_frame = int(120 * fps)
    target_fps = 10
    step = int(fps / target_fps)
    
    total_duration_sec = 30
    total_frames_target = total_duration_sec * target_fps # 300 frames
    
    cap.set(cv2.CAP_PROP_POS_FRAMES, start_frame)
    
    raw_frames = []
    curr = 0
    while len(raw_frames) < total_frames_target:
        ret, frame = cap.read()
        if not ret:
            break
        if curr % step == 0:
            resized = cv2.resize(frame, (200, 160), interpolation=cv2.INTER_AREA)
            rgb = cv2.cvtColor(resized, cv2.COLOR_BGR2RGB)
            raw_frames.append(rgb)
        curr += 1
    cap.release()
    print(f"Extracted {len(raw_frames)} frames @ 200x160 resolution.")

    # Palette generation
    palette_entries = []
    for code in range(512):
        qr = (code >> 6) & 7
        qg = (code >> 3) & 7
        qb = code & 7
        r = round(qr / 7.0, 3)
        g = round(qg / 7.0, 3)
        b = round(qb / 7.0, 3)
        palette_entries.append(f"[{code}]={{{r},{g},{b}}}")
    pal_str = "{" + ",".join(palette_entries) + "}"

    # Split 300 frames across 3 VP Storage Chips per Screen Tile (100 frames per VP storage chip)
    # 9 screens x 3 VP storage chips = 27 VP storage chips
    tile_streams = { (tr, tc): [] for tr in range(3) for tc in range(3) }
    for f in raw_frames:
        for tr in range(3):
            for tc in range(3):
                y0, y1 = tr * 53, min(160, (tr + 1) * 53)
                x0, x1 = tc * 66, min(200, (tc + 1) * 66)
                crop = f[y0:y1, x0:x1]
                tile_img = cv2.resize(crop, (32, 32), interpolation=cv2.INTER_AREA)
                
                pixels = []
                for py in range(32):
                    for px in range(32):
                        r, g, b = tile_img[py, px]
                        qr, qg, qb = r >> 5, g >> 5, b >> 5
                        code = (qr << 6) | (qg << 3) | qb
                        pixels.append(code)
                tile_streams[(tr, tc)].append(pixels)

    print("Building Progressive JIT-Precompute Architecture Melsave...")
    with MelsaveSession() as s:
        xs = [-1.0040, -0.3449, 0.3142]
        ys = [1.3315, 0.6724, 0.0134]
        
        canvases = {}
        for tr in range(3):
            for tc in range(3):
                cv = s.create_canvas(width=32, height=32, display_type="led_matrix", x=xs[tc], y=ys[tr])
                canvases[(tr, tc)] = cv

        # Master Controller & Sync Clock Chip
        master_src = """
local TOTAL_FRAMES = 300

function OnInit()
    shared.precomputed = false
    shared.comp_frame = 0
    shared.play_frame = 1
    shared.play_tick = 0
    shared.state = "PRECOMPUTING"
end

function OnTick()
    if shared.state == "PRECOMPUTING" then
        -- Progressive JIT precompute: process 5 frames per tick across chips
        shared.comp_frame = (shared.comp_frame or 0) + 5
        outputs.string.status = string.format("Compiling Video: %d / %d frames (%.0f%%)", 
            math.min(shared.comp_frame, TOTAL_FRAMES), TOTAL_FRAMES, math.min(100, (shared.comp_frame/TOTAL_FRAMES)*100))
        
        if shared.comp_frame >= TOTAL_FRAMES then
            shared.state = "PLAYING"
        end
    else
        shared.play_tick = (shared.play_tick or 0) + 1
        if shared.play_tick % 3 == 0 then
            shared.play_frame = (shared.play_frame or 1) + 1
            if shared.play_frame > TOTAL_FRAMES then
                shared.play_frame = 1
            end
        end
        outputs.string.status = string.format("Playing Video: Frame %d / %d", shared.play_frame, TOTAL_FRAMES)
    end
end
"""
        s.add_lua_chip(master_src, outputs=[{"name": "status", "type": "string"}], x=0.0, y=2.2, instruction_cost=1000000)

        # 9 Display Worker Groups (Each screen has 3 VP Storage Chips + 1 Fast Decoder Render Chip)
        for tr in range(3):
            for tc in range(3):
                cv = canvases[(tr, tc)]
                all_frames = tile_streams[(tr, tc)] # 300 frames
                
                # Split 300 frames into 3 VP Storage Chips (100 frames each)
                vp1_frames = all_frames[:100]
                vp2_frames = all_frames[100:200]
                vp3_frames = all_frames[200:300]
                
                for vp_idx, vp_f in enumerate([vp1_frames, vp2_frames, vp3_frames]):
                    tbl_str = "{" + ",\n".join(["{" + ",".join(map(str, f)) + "}" for f in vp_f]) + "}"
                    vp_src = f"""
local raw_store = {tbl_str}
local start_f = {vp_idx * 100 + 1}
local end_f = {(vp_idx + 1) * 100}

function OnInit()
    shared.ram_video_{tr}_{tc} = shared.ram_video_{tr}_{tc} or {{}}
end

function OnTick()
    if shared.state == "PRECOMPUTING" then
        local target_comp = shared.comp_frame or 0
        local ram = shared.ram_video_{tr}_{tc}
        
        -- Progressive JIT compile: decode raw stream to pre-built RGB float table in RAM
        for f = start_f, math.min(end_f, target_comp) do
            local local_idx = f - start_f + 1
            if not ram[f] and raw_store[local_idx] then
                local raw = raw_store[local_idx]
                local pre_rgb = {{}}
                for i = 1, 1024 do
                    local code = raw[i] or 0
                    local qr = math.floor(code / 64) % 8
                    local qg = math.floor(code / 8) % 8
                    local qb = code % 8
                    pre_rgb[i] = {{ qr / 7.0, qg / 7.0, qb / 7.0 }}
                end
                ram[f] = pre_rgb
            end
        end
    end
end
"""
                    chip_x = -3.5 if tc == 0 else (3.5 if tc == 2 else 0.0)
                    chip_y = ys[tr] + (vp_idx * 0.3)
                    s.add_lua_chip(vp_src, x=chip_x, y=chip_y, instruction_cost=1000000)

                # 1 Fast Decoder Render Chip per Screen (0 decoding overhead during playback!)
                decoder_src = f"""
local last_rendered = -1

function OnTick()
    -- Hide Border
    local targetId = inputs.entity.target
    if targetId and targetId ~= 0 then
        local e = Entity(targetId)
        if e and e:isValid() == 1 then
            e:setColor(0, 0, 0, 0)
        end
    end
    
    if shared.state ~= "PLAYING" then return end
    
    local play_f = shared.play_frame or 1
    if play_f == last_rendered then return end
    last_rendered = play_f
    
    local ram = shared.ram_video_{tr}_{tc}
    if not ram then return end
    local f_rgb = ram[play_f]
    if not f_rgb then return end
    
    local buf = {cv.lua_var}.buffer
    if not buf then return end
    
    -- 0-Decoding Render Loop: Direct RAM memcpy with Differential Write
    for i = 1, 1024 do
        local c = f_rgb[i]
        if c then
            local p = buf[i]
            if p and (p.x ~= c[1] or p.y ~= c[2] or p.z ~= c[3]) then
                p.x = c[1]; p.y = c[2]; p.z = c[3]; p.w = 1.0
            end
        end
    end
    
    {cv.lua_var}:flush()
end
"""
                dec_x = -2.5 if tc == 0 else (4.5 if tc == 2 else 1.2)
                dec_y = ys[tr]
                dec_idx = s.add_lua_chip(decoder_src, canvases=[cv], inputs=[{"name": "target", "type": "entity"}], x=dec_x, y=dec_y, instruction_cost=1000000)
                s.connect(cv.item_idx, "entity", dec_idx, "target")

        s.save(output_save)
        print(f"Successfully exported Progressive JIT Precompute Video Player save: {output_save}")

if __name__ == "__main__":
    main()
