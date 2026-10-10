"""Standalone Powder Sandbox (No Package Framework Dependency).

Uses pure property mutation (p.x, p.y, p.z, p.w) on pre-allocated vector tables
to ensure 100% C# engine Lua-CSharp marshalling compatibility.
"""
from melon_lua import MelsaveSession

def main():
    with MelsaveSession() as s:
        # Create 1 Display (32x32)
        cv = s.create_canvas(width=32, height=32, display_type="led_matrix")

        # Standalone Lua script (Pure property mutation - NO table reference re-assignment!)
        lua_code = """
        local EMPTY = 0
        local SAND  = 1
        local WATER = 2
        local WALL  = 3

        local W = 32
        local H = 32

        local grid = {}
        local updated = {}

        for i = 1, 1024 do
            grid[i] = EMPTY
            updated[i] = false
        end

        -- Obstacle Platforms in middle
        for x = 4, 18 do grid[14 * 32 + x + 1] = WALL end
        for x = 14, 28 do grid[22 * 32 + x + 1] = WALL end

        local tick_cnt = 0
        local buf = canvas_0.buffer

        function OnTick()
            tick_cnt = tick_cnt + 1

            for i = 1, 1024 do updated[i] = false end

            -- Emitter at top
            if tick_cnt % 2 == 0 then
                grid[1 * 32 + 8 + 1] = SAND
                grid[1 * 32 + 9 + 1] = SAND
                grid[1 * 32 + 22 + 1] = WATER
                grid[1 * 32 + 23 + 1] = WATER
            end

            -- Cellular Automata Physics Loop
            for y = H - 2, 0, -1 do
                for x = 0, W - 1 do
                    local idx = y * 32 + x + 1
                    local cell = grid[idx]

                    if (cell == SAND or cell == WATER) and not updated[idx] then
                        local below_y = y + 1
                        local below_idx = below_y * 32 + x + 1

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

            -- Pure Property Mutation on Buffer (Crucial for C# Lua-CSharp marshalling!)
            for i = 1, 1024 do
                local p = buf[i]
                local cell = grid[i]
                if cell == EMPTY then
                    p.x = 0; p.y = 0; p.z = 0; p.w = 1
                elseif cell == SAND then
                    p.x = 0.95; p.y = 0.75; p.z = 0.2; p.w = 1
                elseif cell == WATER then
                    p.x = 0.2; p.y = 0.6; p.z = 1.0; p.w = 1
                elseif cell == WALL then
                    p.x = 0.5; p.y = 0.5; p.z = 0.5; p.w = 1
                end
            end

            canvas_0:flush()
        end
        """

        s.add_lua_chip(
            lua_code,
            canvases=[cv],
            instruction_cost=100000
        )

        res = s.debug_run(ticks=10)
        print("Standalone debug run status:", "OK" if not res.get("error") else res.get("error"))

        s.save("powder_sandbox_standalone.melsave")
        print("Saved powder_sandbox_standalone.melsave successfully!")

if __name__ == "__main__":
    main()
