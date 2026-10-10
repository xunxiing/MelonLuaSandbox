"""Single direct control chip driving 1 LED Matrix screen directly using Intrusive Buffer mode."""
from melon_lua import MelsaveSession

def main():
    with MelsaveSession() as s:
        # 1. Create single 32x32 LED Matrix screen
        cv = s.create_canvas(width=32, height=32, display_type="led_matrix", x=0.0, y=0.0)

        # 2. Pure Intrusive Lua chip code directly manipulating buffer (matches videolua2 style)
        lua_code = f"""
        local tick_count = 0
        local bx = 5.0
        local by = 8.0
        local vx = 1.2
        local vy = 0.9
        local radius = 3.0

        -- Direct intrusive buffer reference (zero function call overhead)
        local buf = {cv.lua_var}.buffer

        -- Pre-allocated colors (zero GC allocations per frame)
        local BLACK = {{x=0, y=0, z=0, w=1}}
        local RED   = {{x=1, y=0, z=0, w=1}}
        local GREEN = {{x=0, y=1, z=0, w=1}}
        local BLUE  = {{x=0, y=0, z=1, w=1}}
        local GOLD  = {{x=1, y=0.8, z=0, w=1}}

        function OnTick()
            tick_count = tick_count + 1

            -- 1. Fast Clear all 1024 pixels in buffer directly
            for i = 1, 1024 do
                buf[i] = BLACK
            end

            -- 2. Corner markers
            buf[1] = RED         -- (0, 0)
            buf[32] = GREEN      -- (31, 0)
            buf[993] = BLUE      -- (0, 31)

            -- 3. Update bouncing ball physics
            bx = bx + vx
            by = by + vy

            if bx - radius <= 0 then
                bx = radius; vx = -vx
            elseif bx + radius >= 31 then
                bx = 31 - radius; vx = -vx
            end

            if by - radius <= 0 then
                by = radius; vy = -vy
            elseif by + radius >= 31 then
                by = 31 - radius; vy = -vy
            end

            -- 4. Direct pixel assignment to buffer
            local center_x = math.floor(bx)
            local center_y = math.floor(by)

            for dx = -3, 3 do
                for dy = -3, 3 do
                    if (dx * dx + dy * dy) <= (radius * radius + 0.5) then
                        local gx = center_x + dx
                        local gy = center_y + dy
                        if gx >= 0 and gx < 32 and gy >= 0 and gy < 32 then
                            local idx = gy * 32 + gx + 1
                            buf[idx] = GOLD
                        end
                    end
                end
            end

            -- 5. Flush to output gate directly
            {cv.lua_var}:flush()
        end
        """

        # 3. Add single direct control Lua chip
        s.add_lua_chip(
            lua_code,
            x=1.5,
            y=0.0,
            canvases=[cv],
            tps=30,
            instruction_cost=100000,
            inputs=[{"name": "target", "type": "entity"}],
            outputs=[
                {"name": "status", "type": "string", "value": "Single Intrusive Direct Active"},
            ],
            title="Direct Intrusive Controller",
        )

        # 4. Debug run & save
        res = s.debug_run(ticks=10)
        print("Debug run status:", "OK" if not res.get("error") else res.get("error"))

        s.save("canvas_single_direct.melsave")
        print("Saved canvas_single_direct.melsave with intrusive mode successfully!")

if __name__ == "__main__":
    main()
