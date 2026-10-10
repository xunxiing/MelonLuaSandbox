"""Powder Sandbox - 4 Independent Screens Demo (No cross-chip wires).

Each screen (32x32) is controlled independently by its own chip running
falling sand & water cellular automata physics locally.
"""
from melon_lua import MelsaveSession

def main():
    with MelsaveSession() as s:
        # Create 4 screens in 2x2 grid layout
        cv0 = s.create_canvas(width=32, height=32, display_type="led_matrix", x=-1.5, y=1.5)
        cv1 = s.create_canvas(width=32, height=32, display_type="led_matrix", x=1.5, y=1.5)
        cv2 = s.create_canvas(width=32, height=32, display_type="led_matrix", x=-1.5, y=-1.5)
        cv3 = s.create_canvas(width=32, height=32, display_type="led_matrix", x=1.5, y=-1.5)

        def make_chip_lua(canvas_var, screen_id):
            return f"""
            local buf = {canvas_var}.buffer

            local EMPTY = 0
            local SAND  = 1
            local WATER = 2
            local WALL  = 3

            local W = 32
            local H = 32

            local grid = {{}}
            local updated = {{}}

            for i = 1, 1024 do
                grid[i] = EMPTY
                updated[i] = false
            end

            -- Middle platform
            for x = 8, 24 do
                grid[16 * 32 + x + 1] = WALL
            end

            local tick_cnt = 0

            function OnTick()
                tick_cnt = tick_cnt + 1

                for i = 1, 1024 do updated[i] = false end

                -- Emitter at top
                if tick_cnt % 2 == 0 then
                    grid[1 * 32 + 10 + 1] = SAND
                    grid[1 * 32 + 11 + 1] = SAND
                    grid[1 * 32 + 20 + 1] = WATER
                    grid[1 * 32 + 21 + 1] = WATER
                end

                -- Reverse scan for physics updates
                for y = H - 1, 0, -1 do
                    for x = 0, W - 1 do
                        local idx = y * 32 + x + 1
                        local cell = grid[idx]

                        if (cell == SAND or cell == WATER) and not updated[idx] then
                            if y < H - 1 then
                                local below_idx = (y + 1) * 32 + x + 1

                                if grid[below_idx] == EMPTY then
                                    grid[below_idx] = cell
                                    grid[idx] = EMPTY
                                    updated[below_idx] = true
                                elseif cell == SAND and grid[below_idx] == WATER then
                                    grid[below_idx] = SAND
                                    grid[idx] = WATER
                                    updated[below_idx] = true
                                else
                                    local dir = (tick_cnt + x + y) % 2 == 0 and 1 or -1
                                    local dl_x = x - dir
                                    local dr_x = x + dir

                                    local dl_valid = dl_x >= 0 and dl_x < W
                                    local dr_valid = dr_x >= 0 and dr_x < W

                                    local dl_idx = dl_valid and ((y + 1) * 32 + dl_x + 1) or nil
                                    local dr_idx = dr_valid and ((y + 1) * 32 + dr_x + 1) or nil

                                    if dl_idx and grid[dl_idx] == EMPTY then
                                        grid[dl_idx] = cell
                                        grid[idx] = EMPTY
                                        updated[dl_idx] = true
                                    elseif dr_idx and grid[dr_idx] == EMPTY then
                                        grid[dr_idx] = cell
                                        grid[idx] = EMPTY
                                        updated[dr_idx] = true
                                    elseif cell == WATER then
                                        local hl_x = x - dir
                                        local hr_x = x + dir

                                        local hl_valid = hl_x >= 0 and hl_x < W
                                        local hr_valid = hr_x >= 0 and hr_x < W

                                        local hl_idx = hl_valid and (y * 32 + hl_x + 1) or nil
                                        local hr_idx = hr_valid and (y * 32 + hr_x + 1) or nil

                                        if hl_idx and grid[hl_idx] == EMPTY then
                                            grid[hl_idx] = WATER
                                            grid[idx] = EMPTY
                                            updated[hl_idx] = true
                                        elseif hr_idx and grid[hr_idx] == EMPTY then
                                            grid[hr_idx] = WATER
                                            grid[idx] = EMPTY
                                            updated[hr_idx] = true
                                        end
                                    end
                                end
                            end
                        end
                    end
                end

                -- Render pixels to canvas buffer
                for i = 1, 1024 do
                    local p = buf[i]
                    local cell = grid[i]
                    if cell == EMPTY then
                        p.x = 0; p.y = 0; p.z = 0; p.w = 1.0
                    elseif cell == SAND then
                        p.x = 0.95; p.y = 0.75; p.z = 0.2; p.w = 1.0
                    elseif cell == WATER then
                        p.x = 0.2; p.y = 0.6; p.z = 1.0; p.w = 1.0
                    elseif cell == WALL then
                        p.x = 0.5; p.y = 0.5; p.z = 0.5; p.w = 1.0
                    end
                end

                {canvas_var}:flush()

                outputs.string.status = string.format("Screen %d | Sand&Water Active", {screen_id})
            end
            """

        canvases = [cv0, cv1, cv2, cv3]
        positions = [(-1.5, 2.5), (1.5, 2.5), (-1.5, -2.5), (1.5, -2.5)]

        for idx, cv in enumerate(canvases):
            code = make_chip_lua(cv.lua_var, idx)
            pos_x, pos_y = positions[idx]
            s.add_lua_chip(
                code,
                canvases=[cv],
                outputs=[{"name": "status", "type": "string"}],
                x=pos_x,
                y=pos_y,
                instruction_cost=100000
            )

        res = s.debug_run(ticks=30)
        print("Debug run status:", "OK" if not res.get("error") else res.get("error"))

        s.save("powder_sandbox_4screens_independent.melsave")
        print("Saved powder_sandbox_4screens_independent.melsave successfully!")

if __name__ == "__main__":
    main()
