"""Cthulhu Cosmic Serpent Multi-Chip Entity Generator (No Display Screen).

Creates cthulhu_serpent.melsave containing a 10-chip Lovecraftian Segmented Cosmic Serpent:
- Obj 0: Cthulhu Serpent Head Master Chip (Mind of Abyssal Chaos)
- Obj 1~8: Cthulhu Serpent Body Segment Chips 1..8 (Undulating Slithering Body)
- Obj 9: Cthulhu Serpent Tail Tip Chip (Writhing Void Tail)

Uses zero-wire shared memory (shared.cthulhu_serpent) to drive multi-segment sine-wave
body kinematics, Lovecraftian eldritch pulsing status telemetry, and unearthly aura.
"""
import os
from melon_lua.session import MelsaveSession

def generate_cthulhu_serpent():
    s = MelsaveSession()
    
    num_segments = 10
    
    # -------------------------------------------------------------
    # HEAD CHIP: Cthulhu Master Mind (x = -4.5, y = 0.0)
    # -------------------------------------------------------------
    head_code = """-- Cthulhu Cosmic Serpent Head Master Controller
function OnInit()
    shared.cthulhu_serpent = {
        tick = 0,
        wave_freq = 0.15,
        wave_amp = 0.8,
        speed = 0.05,
        head_x = -4.5,
        head_y = 0.0,
        target_y = 0.0,
        segments = {},
        phase_name = "【深渊觉醒·旧日巨蛇】"
    }
    for i = 1, 10 do
        shared.cthulhu_serpent.segments[i] = { x = -4.5 + (i - 1) * 0.9, y = 0.0, angle = 0.0 }
    end
end

function OnTick()
    local c = shared.cthulhu_serpent
    if not c then return end

    c.tick = c.tick + 1
    local t = c.tick

    -- Cosmic serpent undulating head movement
    c.target_y = math.sin(t * c.wave_freq) * c.wave_amp + math.cos(t * 0.07) * 0.4
    c.head_y = c.head_y + (c.target_y - c.head_y) * 0.1
    c.segments[1].x = c.head_x
    c.segments[1].y = c.head_y

    -- Lovecraftian state machine
    local cycle = math.floor((t % 300) / 100)
    if cycle == 0 then
        c.phase_name = "【深渊之视 · 虚空凝眸】"
    elseif cycle == 1 then
        c.phase_name = "【混沌蠕动 · 疯狂游走】"
    else
        c.phase_name = "【星海掠食 · 旧日吞噬】"
    end

    if outputs and outputs.string and outputs.string.status then
        outputs.string.status = string.format("蛇头主控: %s | 频率:%.2f 振幅:%.2f", c.phase_name, c.wave_freq, c.head_y)
    end
end
"""
    
    s.add_lua_chip(
        head_code,
        inputs=[],
        outputs=[{"name": "status", "type": "string"}],
        x=-4.5, y=0.0,
        title="[蛇头] 克苏鲁主脑"
    )

    # -------------------------------------------------------------
    # BODY SEGMENT CHIPS 2..10 (8 Body Segments + 1 Tail Tip)
    # -------------------------------------------------------------
    for seg_idx in range(2, num_segments + 1):
        is_tail = (seg_idx == num_segments)
        chip_title = f"[尾尖] 虚空游尾" if is_tail else f"[躯干-{seg_idx-1}] 克苏鲁触节"
        pos_x = -4.5 + (seg_idx - 1) * 0.9
        
        segment_code = f"""-- Cthulhu Serpent Body Segment Chip {seg_idx}
local SEG_ID = {seg_idx}

function OnTick()
    local c = shared.cthulhu_serpent
    if not c or not c.segments then return end

    local prev_seg = c.segments[SEG_ID - 1]
    local cur_seg = c.segments[SEG_ID]
    if not prev_seg or not cur_seg then return end

    local t = c.tick or 0
    -- Inverse Kinematics & Eldritch Sine Wave Propagation
    local phase_offset = (SEG_ID - 1) * 0.45
    local local_wave = math.sin(t * c.wave_freq - phase_offset) * (c.wave_amp * (1.0 + SEG_ID * 0.05))
    
    cur_seg.y = prev_seg.y * 0.65 + local_wave * 0.35
    cur_seg.angle = math.atan2(cur_seg.y - prev_seg.y, 0.9) * (180.0 / 3.14159)

    local runes = {{"👁️", "🐙", "🌌", "⚡", "🔮", "☠️", "🌀", "🩸"}}
    local rune = runes[((SEG_ID + math.floor(t / 10)) % #runes) + 1]

    if outputs and outputs.string and outputs.string.status then
        outputs.string.status = string.format("触节[%d] %%s 姿态角:%%.1f° Y:%%.2f", SEG_ID, rune, cur_seg.angle, cur_seg.y)
    end
end
"""
        s.add_lua_chip(
            segment_code,
            inputs=[],
            outputs=[{"name": "status", "type": "string"}],
            x=pos_x, y=0.0,
            title=chip_title
        )

    save_path = "cthulhu_serpent.melsave"
    s.save(save_path)
    print(f"Successfully generated Cthulhu Cosmic Serpent 10-Chip Entity: {os.path.abspath(save_path)}")

if __name__ == "__main__":
    generate_cthulhu_serpent()
