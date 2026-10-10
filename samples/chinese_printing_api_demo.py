"""Sample Demo: Integrating 紫晶石灰 Chinese_character_printing API into MelonLuaSandbox SDK.

Creates a 2-chip topology with Lazy Module Require inside OnTick().
"""
import sys
from pathlib import Path
_ROOT = Path(__file__).resolve().parent.parent
(_ROOT / "temp").mkdir(exist_ok=True)
sys.path.insert(0, str(_ROOT))

from melon_lua import MelsaveSession
from melon_lua.packages import add_chinese_printing_provider

def main():
    output_path = _ROOT / "temp" / "chinese_printing_api_demo.melsave"
    print("Generating Chinese Character Printing API Demo Save with Lazy Module Require...")

    with MelsaveSession() as s:
        # 1. Create a 32x32 LED Matrix Display
        cv = s.create_canvas(width=32, height=32, display_type="led_matrix", x=0.0, y=0.0)

        # 2. Add 紫晶石灰 Chinese_character_printing Module Provider Chip (Obj x=-3.0)
        provider_idx = add_chinese_printing_provider(s, x=-3.0, y=0.0)

        # 3. Add User Control Chip calling Chinese_character_printing API (Obj x=3.0)
        user_chip_code = """
local print_char = nil
local frame = 0

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

    -- Color definitions {x=r, y=g, z=b, w=a}
    local GOLD = {x = 1.0, y = 0.85, z = 0.2, w = 1.0}
    local CYAN = {x = 0.0, y = 0.85, z = 1.0, w = 1.0}

    -- Print '原' at top-left (2, 2) in Gold
    print_char(buf, 32, 32, 2, 2, "原", GOLD)

    -- Print '神' at top-right (16, 2) in Cyan
    print_char(buf, 32, 32, 16, 2, "神", CYAN)

    -- Print '启' at bottom-left (2, 16) in Cyan
    print_char(buf, 32, 32, 2, 16, "启", CYAN)

    -- Print '动' at bottom-right (16, 16) in Gold
    print_char(buf, 32, 32, 16, 16, "动", GOLD)

    canvas_0:flush()
    outputs.string.status = string.format("API 汉字打印运行中 | Tick: %d", frame)
end
"""
        chip_idx = s.add_lua_chip(
            user_chip_code,
            canvases=[cv],
            inputs=[{"name": "target", "type": "entity"}],
            outputs=[{"name": "status", "type": "string"}],
            x=3.0, y=0.0,
            instruction_cost=300000
        )
        s.connect(cv.item_idx, "entity", chip_idx, "target")

        s.save(output_path)
        print(f"Successfully exported save: {output_path}")

if __name__ == "__main__":
    main()
