"""Single-chip driving 4 LED displays (64x64 total resolution) in pure intrusive mode."""
from melon_lua import MelsaveSession

def main():
    with MelsaveSession() as s:
        # Create 4 LED Matrix displays in a 2x2 grid layout
        cv0 = s.create_canvas(width=32, height=32, display_type="led_matrix", x=0.0, y=0.0) # Top-Left (0,0)
        cv1 = s.create_canvas(width=32, height=32, display_type="led_matrix", x=2.0, y=0.0) # Top-Right (1,0)
        cv2 = s.create_canvas(width=32, height=32, display_type="led_matrix", x=0.0, y=2.0) # Bottom-Left (0,1)
        cv3 = s.create_canvas(width=32, height=32, display_type="led_matrix", x=2.0, y=2.0) # Bottom-Right (1,1)

        lua_code = """
        local buf0 = canvas_0.buffer
        local buf1 = canvas_1.buffer
        local buf2 = canvas_2.buffer
        local buf3 = canvas_3.buffer

        local BLACK = {x=0, y=0, z=0, w=1}
        local GOLD  = {x=1, y=0.8, z=0.1, w=1}
        local RED   = {x=1, y=0, z=0, w=1}
        local GREEN = {x=0, y=1, z=0, w=1}
        local BLUE  = {x=0, y=0, z=1, w=1}

        local tick_count = 0
        local bx = 10.0
        local by = 15.0
        local vx = 1.6
        local vy = 1.2
        local radius = 3.0

        function OnTick()
            tick_count = tick_count + 1

            -- 1. Fast intrusive clear on all 4 screen buffers
            for i = 1, 1024 do
                buf0[i] = BLACK
                buf1[i] = BLACK
                buf2[i] = BLACK
                buf3[i] = BLACK
            end

            -- 2. Corner diagnostic indicators on ALL 4 screens!
            buf0[1] = RED; buf0[32] = GREEN; buf0[993] = BLUE
            buf1[1] = RED; buf1[32] = GREEN; buf1[993] = BLUE
            buf2[1] = RED; buf2[32] = GREEN; buf2[993] = BLUE
            buf3[1] = RED; buf3[32] = GREEN; buf3[993] = BLUE

            -- 3. Deterministic 64x64 Bouncing Ball Physics
            bx = bx + vx
            by = by + vy

            if bx - radius <= 0 then
                bx = radius; vx = -vx
            elseif bx + radius >= 63 then
                bx = 63 - radius; vx = -vx
            end

            if by - radius <= 0 then
                by = radius; vy = -vy
            elseif by + radius >= 63 then
                by = 63 - radius; vy = -vy
            end

            -- 4. Multi-buffer intrusive rendering (64x64 global canvas)
            local center_x = math.floor(bx)
            local center_y = math.floor(by)

            for dx = -3, 3 do
                for dy = -3, 3 do
                    if (dx * dx + dy * dy) <= (radius * radius + 0.5) then
                        local gx = center_x + dx
                        local gy = center_y + dy
                        if gx >= 0 and gx < 64 and gy >= 0 and gy < 64 then
                            local target_buf = nil
                            local lx = 0
                            local ly = 0

                            if gx < 32 and gy < 32 then
                                target_buf = buf0; lx = gx; ly = gy
                            elseif gx >= 32 and gy < 32 then
                                target_buf = buf1; lx = gx - 32; ly = gy
                            elseif gx < 32 and gy >= 32 then
                                target_buf = buf2; lx = gx; ly = gy - 32
                            else
                                target_buf = buf3; lx = gx - 32; ly = gy - 32
                            end

                            local idx = ly * 32 + lx + 1
                            target_buf[idx] = GOLD
                        end
                    end
                end
            end

            -- 5. Flush all 4 screen buffers simultaneously
            canvas_0:flush()
            canvas_1:flush()
            canvas_2:flush()
            canvas_3:flush()
        end
        """

        s.add_lua_chip(
            lua_code,
            canvases=[cv0, cv1, cv2, cv3],
            inputs=[{"name": "target", "type": "entity"}],
            outputs=[{"name": "status", "type": "string", "value": "Single-Chip 4-Screen Active"}],
            x=1.0, y=4.0
        )

        res = s.debug_run(ticks=10)
        print("Debug run status:", "OK" if not res.get("error") else res.get("error"))

        s.save("canvas_4screens_demo.melsave")
        print("Saved canvas_4screens_demo.melsave (Single-Chip 4-Screen) successfully!")

if __name__ == "__main__":
    main()
