"""Canvas Level 2 Ultra-Performance Demo (Dirty List + Palette LUT).

Optimizations:
1. Dirty List Tracking: Only clear pixels that were drawn in the previous frame (e.g., 5 loops vs 1024 loops).
2. Color Palette LUT: Assign pre-allocated Vector4 objects instead of setting 4 fields (.x, .y, .z, .w) per pixel.
"""
from melon_lua import MelsaveSession


def main():
    with MelsaveSession() as s:
        cv = s.create_canvas(width=32, height=32, display_type="led_matrix")

        lua_code = f"""
        -- Static Color Palette LUT (Pre-allocated Vector4 instances)
        local BLACK = {{x=0, y=0, z=0, w=1}}
        local WHITE = {{x=1, y=1, z=1, w=1}}
        local RED   = {{x=1, y=0, z=0, w=1}}
        local GREEN = {{x=0, y=1, z=0, w=1}}

        local buf = {cv.lua_var}.buffer
        local dirty = {{}}
        local dirty_count = 0
        local tick_count = 0

        function OnTick()
            tick_count = tick_count + 1

            -- 1. Ultra-fast clear: ONLY reset pixels modified last tick (0 to ~10 loops vs 1024 loops!)
            for i = 1, dirty_count do
                buf[dirty[i]] = BLACK
            end
            dirty_count = 0

            -- 2. Draw moving pixel (1 assignment via LUT palette reference)
            local pos = tick_count % 32
            local idx = pos * 32 + pos + 1
            
            buf[idx] = WHITE
            
            -- Record dirty pixel
            dirty_count = dirty_count + 1
            dirty[dirty_count] = idx

            -- 3. Flush to gate
            {cv.lua_var}:flush()
        end
        """

        s.add_lua_chip(
            lua_code,
            canvases=[cv],
            inputs=[{"name": "target", "type": "entity"}],
            outputs=[{"name": "status", "type": "string", "value": "Ultra Canvas Active"}],
        )

        res = s.debug_run(ticks=10)
        print("Ultra debug run status:", "OK" if not res.get("error") else res.get("error"))

        s.save("canvas_ultra_demo.melsave")
        print("Saved canvas_ultra_demo.melsave successfully!")


if __name__ == "__main__":
    main()
