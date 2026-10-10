"""Sample Demo: Cyber Hanzi HUD Weather & Time Station using 紫晶石灰 Chinese_character_printing API.

Exported Save: chinese_printing_hud.melsave
"""
import sys
from pathlib import Path
_ROOT = Path(__file__).resolve().parent.parent
(_ROOT / "temp").mkdir(exist_ok=True)
sys.path.insert(0, str(_ROOT))

from melon_lua import MelsaveSession
from melon_lua.packages import add_chinese_printing_provider

def main():
    output_path = _ROOT / "temp" / "chinese_printing_hud.melsave"
    print("Generating Cyber Hanzi HUD Station Demo Save with Lazy Module Require...")

    with MelsaveSession() as s:
        # 1. Create 32x32 LED Matrix Display
        cv = s.create_canvas(width=32, height=32, display_type="led_matrix", x=0.0, y=0.0)

        # 2. Add 紫晶石灰 Chinese_character_printing Module Provider Chip (x=-3.0)
        provider_idx = add_chinese_printing_provider(s, x=-3.0, y=0.0)

        # 3. Add User Control Chip (x=3.0)
        user_script = """
local print_char = nil
local frame = 0
local text_page = 1

local pages = {
    {c1="甜", c2="瓜", c3="游", c4="乐"},
    {c1="原", c2="神", c3="启", c4="动"},
    {c1="赛", c2="博", c3="芯", c4="片"}
}

function OnTick()
    -- Lazy require module inside OnTick to prevent top-level chunk load order error
    if not print_char then
        if shared and shared.modules and shared.modules["Chinese_character_printing"] then
            print_char = require("Chinese_character_printing")
        elseif _G.Chinese_character_printing then
            print_char = _G.Chinese_character_printing
        else
            outputs.string.status = "等待汉字模块加载..."
            return
        end
    end

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
    frame = frame + 1

    -- Switch text page every 90 ticks (~3 seconds)
    if frame % 90 == 0 then
        text_page = text_page + 1
        if text_page > #pages then text_page = 1 end
    end

    local curr = pages[text_page]

    -- Dynamic Pulsing Colors
    local pulse = 0.7 + math.sin(frame * 0.1) * 0.3
    local GOLD    = {x = 1.0 * pulse, y = 0.85 * pulse, z = 0.2, w = 1.0}
    local CYAN    = {x = 0.0, y = 0.85 * pulse, z = 1.0 * pulse, w = 1.0}
    local EMERALD = {x = 0.2, y = 1.0 * pulse, z = 0.4, w = 1.0}
    local CRIMSON = {x = 1.0, y = 0.2, z = 0.4 * pulse, w = 1.0}

    -- Print character using resolved print_char / Chinese_character_printing API
    print_char(buf, 32, 32, 2, 2, curr.c1, GOLD)
    print_char(buf, 32, 32, 16, 2, curr.c2, CYAN)
    print_char(buf, 32, 32, 2, 16, curr.c3, EMERALD)
    print_char(buf, 32, 32, 16, 16, curr.c4, CRIMSON)

    canvas_0:flush()

    outputs.string.status = string.format("赛博汉字 HUD 页[%d/3] | Tick: %d", text_page, frame)
end
"""

        chip_idx = s.add_lua_chip(
            user_script,
            canvases=[cv],
            inputs=[{"name": "target", "type": "entity"}],
            outputs=[{"name": "status", "type": "string"}],
            x=3.0, y=0.0,
            instruction_cost=300000
        )
        s.connect(cv.item_idx, "entity", chip_idx, "target")

        s.save(output_path)
        print(f"Successfully generated Cyber Hanzi HUD Save with Lazy Require: {output_path}")

if __name__ == "__main__":
    main()
