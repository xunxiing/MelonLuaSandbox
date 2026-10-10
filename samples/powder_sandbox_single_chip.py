"""Powder Sandbox (Falling Sand & Water Physics) Simulator - Single Chip Implementation."""
from melon_lua import MelsaveSession

def main():
    with MelsaveSession() as s:
        cv0 = s.create_canvas(width=32, height=32, display_type="led_matrix", x=0.0, y=0.0)

        lua_code = """
        local buf = canvas_0.buffer

        -- Element Types
        local EMPTY = 0
        local SAND  = 1
        local WATER = 2
        local WALL  = 3

        -- Colors
        local COLOR_EMPTY = {x=0, y=0, z=0, w=1}
        local COLOR_SAND  = {x=0.95, y=0.75, z=0.2, w=1}
        local COLOR_WATER = {x=0.2, y=0.6, z=1.0, w=1}
        local COLOR_WALL  = {x=0.5, y=0.5, z=0.5, w=1}

        -- Grids (32x32 = 1024 cells)
        local W = 32
        local H = 32
        local grid = {}
        local updated = {}

        for i = 1, 1024 do
            grid[i] = EMPTY
            updated[i] = false
        end

        -- Create Obstacle Platforms in the middle
        -- Platform 1: Middle-Left Platform (x=4..18, y=14)
        for x = 4, 18 do
            grid[14 * 32 + x + 1] = WALL
        end

        -- Platform 2: Middle-Right Platform (x=14..28, y=22)
        for x = 14, 28 do
            grid[22 * 32 + x + 1] = WALL
        end

        local tick_cnt = 0

        function OnTick()
            tick_cnt = tick_cnt + 1

            -- Reset updated flag
            for i = 1, 1024 do
                updated[i] = false
            end

            -- 1. Emitter Spawner: Spawn Sand & Water from top emitters
            if tick_cnt % 2 == 0 then
                -- Spawn Sand at top left (x=8..9, y=1)
                grid[1 * 32 + 8 + 1] = SAND
                grid[1 * 32 + 9 + 1] = SAND

                -- Spawn Water at top right (x=22..23, y=1)
                grid[1 * 32 + 22 + 1] = WATER
                grid[1 * 32 + 23 + 1] = WATER
            end

            -- 2. Cellular Automata Physics Scan (Bottom to Top)
            for y = H - 2, 0, -1 do
                for x = 0, W - 1 do
                    local idx = y * 32 + x + 1
                    local cell = grid[idx]

                    if (cell == SAND or cell == WATER) and not updated[idx] then
                        local below_y = y + 1
                        local below_idx = below_y * 32 + x + 1

                        -- Physics Rule 1: Fall Straight Down
                        if grid[below_idx] == EMPTY then
                            grid[below_idx] = cell
                            grid[idx] = EMPTY
                            updated[below_idx] = true

                        -- Physics Rule 1.5: Heavy Sand density displacement (Sand sinks in Water!)
                        elseif cell == SAND and grid[below_idx] == WATER then
                            grid[below_idx] = SAND
                            grid[idx] = WATER
                            updated[below_idx] = true

                        else
                            -- Physics Rule 2: Diagonal Slide (Down-Left vs Down-Right)
                            local dir = (tick_cnt + x + y) % 2 == 0 and 1 or -1
                            local dl_x = x - dir
                            local dr_x = x + dir

                            local dl_valid = dl_x >= 0 and dl_x < W
                            local dr_valid = dr_x >= 0 and dr_x < W

                            local dl_idx = dl_valid and (below_y * 32 + dl_x + 1) or nil
                            local dr_idx = dr_valid and (below_y * 32 + dr_x + 1) or nil

                            if dl_idx and grid[dl_idx] == EMPTY then
                                grid[dl_idx] = cell
                                grid[idx] = EMPTY
                                updated[dl_idx] = true
                            elseif dr_idx and grid[dr_idx] == EMPTY then
                                grid[dr_idx] = cell
                                grid[idx] = EMPTY
                                updated[dr_idx] = true

                            elseif cell == WATER then
                                -- Physics Rule 3: Liquid Horizontal Flow (Left vs Right)
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

            -- 3. Intrusive Direct Buffer Render
            for i = 1, 1024 do
                local cell = grid[i]
                if cell == EMPTY then
                    buf[i] = COLOR_EMPTY
                elseif cell == SAND then
                    buf[i] = COLOR_SAND
                elseif cell == WATER then
                    buf[i] = COLOR_WATER
                elseif cell == WALL then
                    buf[i] = COLOR_WALL
                end
            end

            canvas_0:flush()
        end
        """

        s.add_lua_chip(
            lua_code,
            canvases=[cv0],
            inputs=[{"name": "target", "type": "entity"}],
            outputs=[{"name": "status", "type": "string", "value": "Powder Sandbox Active"}],
            instruction_cost=100000
        )

        res = s.debug_run(ticks=30)
        print("Debug run status:", "OK" if not res.get("error") else res.get("error"))

        s.save("powder_sandbox_single.melsave")
        print("Saved powder_sandbox_single.melsave successfully!")

if __name__ == "__main__":
    main()
