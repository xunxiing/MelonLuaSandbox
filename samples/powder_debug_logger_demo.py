"""Powder Sandbox Debug Logger Demo.

Injects explicit print() logs and outputs.string.status debug messages into both
Master and Worker Lua scripts to verify execution step-by-step in-game and in debug_run.
"""
from melon_lua import MelsaveSession

def run_debug_single():
    print("\n==================================================")
    print("      RUNNING SINGLE SCREEN DEBUG DIAGNOSTIC")
    print("==================================================")
    with MelsaveSession() as s:
        cv = s.create_canvas(width=32, height=32, display_type="led_matrix")

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

        -- Obstacle Platforms
        for x = 4, 18 do grid[14 * 32 + x + 1] = WALL end
        for x = 14, 28 do grid[22 * 32 + x + 1] = WALL end

        local tick_cnt = 0
        local buf = canvas_0.buffer

        function OnTick()
            tick_cnt = tick_cnt + 1
            for i = 1, 1024 do updated[i] = false end

            -- Emitter
            if tick_cnt % 2 == 0 then
                grid[1 * 32 + 8 + 1] = SAND
                grid[1 * 32 + 9 + 1] = SAND
                grid[1 * 32 + 22 + 1] = WATER
                grid[1 * 32 + 23 + 1] = WATER
            end

            -- CA Physics Loop
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

            -- Counts & Render
            local sand_cnt = 0
            local water_cnt = 0
            for i = 1, 1024 do
                local p = buf[i]
                local cell = grid[i]
                if cell == EMPTY then
                    p.x = 0; p.y = 0; p.z = 0; p.w = 1
                elseif cell == SAND then
                    sand_cnt = sand_cnt + 1
                    p.x = 0.95; p.y = 0.75; p.z = 0.2; p.w = 1
                elseif cell == WATER then
                    water_cnt = water_cnt + 1
                    p.x = 0.2; p.y = 0.6; p.z = 1.0; p.w = 1
                elseif cell == WALL then
                    p.x = 0.5; p.y = 0.5; p.z = 0.5; p.w = 1
                end
            end

            -- DEBUG LOGS
            local status_msg = string.format("Tick: %d | Sand: %d | Water: %d", tick_cnt, sand_cnt, water_cnt)
            outputs.string.status = status_msg
            if tick_cnt % 5 == 0 then
                print("[SINGLE-DEBUG] " .. status_msg)
            end

            canvas_0:flush()
        end
        """

        chip_idx = s.add_lua_chip(
            lua_code,
            canvases=[cv],
            outputs=[{"name": "status", "type": "string"}],
            instruction_cost=100000
        )

        res = s.debug_run(ticks=15)
        print("Simulator Logs:")
        for log in res.get("logs", []):
            print(" ", log)

        s.save("powder_sandbox_debug_single.melsave")
        print("Saved powder_sandbox_debug_single.melsave successfully!")

def run_debug_master_worker():
    print("\n==================================================")
    print("   RUNNING 4-SCREEN MASTER-WORKER DIAGNOSTIC")
    print("==================================================")
    with MelsaveSession() as s:
        cv0 = s.create_canvas(width=32, height=32, display_type="led_matrix", x=0.0, y=0.0)
        cv1 = s.create_canvas(width=32, height=32, display_type="led_matrix", x=2.0, y=0.0)
        cv2 = s.create_canvas(width=32, height=32, display_type="led_matrix", x=0.0, y=2.0)
        cv3 = s.create_canvas(width=32, height=32, display_type="led_matrix", x=2.0, y=2.0)

        master_lua = """
        local tick_cnt = 0
        function OnTick()
            tick_cnt = tick_cnt + 1

            local out0 = inputs.array_vec.worker0_data or {}
            local out1 = inputs.array_vec.worker1_data or {}
            local out2 = inputs.array_vec.worker2_data or {}
            local out3 = inputs.array_vec.worker3_data or {}

            local in0 = {}
            local in1 = {}
            local in2 = {}
            local in3 = {}

            local routed_cnt = 0
            local function route_particle(p)
                if not p or not p.z or p.z == 0 then return end
                routed_cnt = routed_cnt + 1
                local gx = p.x; local gy = p.y

                if gx >= 0 and gx < 32 and gy >= 0 and gy < 32 then
                    table.insert(in0, p)
                elseif gx >= 32 and gx < 64 and gy >= 0 and gy < 32 then
                    table.insert(in1, p)
                elseif gx >= 0 and gx < 32 and gy >= 32 and gy < 64 then
                    table.insert(in2, p)
                elseif gx >= 32 and gx < 64 and gy >= 32 and gy < 64 then
                    table.insert(in3, p)
                end
            end

            for _, p in ipairs(out0) do route_particle(p) end
            for _, p in ipairs(out1) do route_particle(p) end
            for _, p in ipairs(out2) do route_particle(p) end
            for _, p in ipairs(out3) do route_particle(p) end

            outputs.array_vec.send0_data = in0
            outputs.array_vec.send1_data = in1
            outputs.array_vec.send2_data = in2
            outputs.array_vec.send3_data = in3

            local msg = string.format("Master T:%d | Recv:[%d,%d,%d,%d] | Send:[%d,%d,%d,%d]",
                tick_cnt, #out0, #out1, #out2, #out3, #in0, #in1, #in2, #in3)
            outputs.string.status = msg

            if tick_cnt % 5 == 0 then
                print("[MASTER-DEBUG] " .. msg)
            end
        end
        """

        def make_worker_lua(canvas_var, tile_col, tile_row, worker_id):
            gx_offset = tile_col * 32
            gy_offset = tile_row * 32

            return f"""
            local buf = {canvas_var}.buffer
            local EMPTY = 0; local SAND = 1; local WATER = 2; local WALL = 3
            local W = 32; local H = 32
            local gx_offset = {gx_offset}; local gy_offset = {gy_offset}

            local grid = {{}}
            local updated = {{}}
            for i = 1, 1024 do grid[i] = EMPTY; updated[i] = false end

            if gy_offset == 0 and gx_offset == 0 then
                for x = 6, 26 do grid[16 * 32 + x + 1] = WALL end
            end

            local tick_cnt = 0
            function OnTick()
                tick_cnt = tick_cnt + 1
                for i = 1, 1024 do updated[i] = false end

                -- Emitter in Top-Left (0,0) screen
                if gx_offset == 0 and gy_offset == 0 and tick_cnt % 2 == 0 then
                    grid[1 * 32 + 8 + 1] = SAND
                    grid[1 * 32 + 9 + 1] = SAND
                    grid[1 * 32 + 22 + 1] = WATER
                    grid[1 * 32 + 23 + 1] = WATER
                end

                -- Inject incoming boundary particles from Master Manager
                local incoming = inputs.array_vec.recv_data
                local injected_cnt = 0
                if incoming then
                    for _, p in ipairs(incoming) do
                        if p and p.z and p.z > 0 then
                            local lx = math.floor(p.x) - gx_offset
                            local ly = math.floor(p.y) - gy_offset
                            if lx >= 0 and lx < 32 and ly >= 0 and ly < 32 then
                                local idx = ly * 32 + lx + 1
                                grid[idx] = math.floor(p.z)
                                updated[idx] = true
                                injected_cnt = injected_cnt + 1
                            end
                        end
                    end
                end

                local boundary_outgoing = {{}}

                -- CA Physics Loop
                for y = H - 1, 0, -1 do
                    for x = 0, W - 1 do
                        local idx = y * 32 + x + 1
                        local cell = grid[idx]

                        if (cell == SAND or cell == WATER) and not updated[idx] then
                            local gx = gx_offset + x; local gy = gy_offset + y

                            if y == H - 1 then
                                if gy + 1 < 64 then
                                    table.insert(boundary_outgoing, {{x = gx, y = gy + 1, z = cell, w = 1}})
                                    grid[idx] = EMPTY
                                end
                            else
                                local below_idx = (y + 1) * 32 + x + 1

                                if grid[below_idx] == EMPTY then
                                    grid[below_idx] = cell; grid[idx] = EMPTY; updated[below_idx] = true
                                elseif cell == SAND and grid[below_idx] == WATER then
                                    grid[below_idx] = SAND; grid[idx] = WATER; updated[below_idx] = true
                                else
                                    local dir = (tick_cnt + x + y) % 2 == 0 and 1 or -1
                                    local dl_x = x - dir; local dr_x = x + dir
                                    local dl_valid = dl_x >= 0 and dl_x < W
                                    local dr_valid = dr_x >= 0 and dr_x < W
                                    local dl_idx = dl_valid and ((y + 1) * 32 + dl_x + 1) or nil
                                    local dr_idx = dr_valid and ((y + 1) * 32 + dr_x + 1) or nil

                                    if dl_idx and grid[dl_idx] == EMPTY then
                                        grid[dl_idx] = cell; grid[idx] = EMPTY; updated[dl_idx] = true
                                    elseif dr_idx and grid[dr_idx] == EMPTY then
                                        grid[dr_idx] = cell; grid[idx] = EMPTY; updated[dr_idx] = true
                                    elseif not dl_valid and dl_x < 0 and (gx - 1) >= 0 then
                                        table.insert(boundary_outgoing, {{x = gx - 1, y = gy + 1, z = cell, w = 1}})
                                        grid[idx] = EMPTY
                                    elseif not dr_valid and dr_x >= W and (gx + 1) < 64 then
                                        table.insert(boundary_outgoing, {{x = gx + 1, y = gy + 1, z = cell, w = 1}})
                                        grid[idx] = EMPTY
                                    end
                                end
                            end
                        end
                    end
                end

                outputs.array_vec.send_data = boundary_outgoing

                -- Render to LED Matrix
                local sand_cnt = 0; local water_cnt = 0
                for i = 1, 1024 do
                    local p = buf[i]
                    local cell = grid[i]
                    if cell == EMPTY then
                        p.x = 0; p.y = 0; p.z = 0; p.w = 1
                    elseif cell == SAND then
                        sand_cnt = sand_cnt + 1
                        p.x = 0.95; p.y = 0.75; p.z = 0.2; p.w = 1
                    elseif cell == WATER then
                        water_cnt = water_cnt + 1
                        p.x = 0.2; p.y = 0.6; p.z = 1.0; p.w = 1
                    elseif cell == WALL then
                        p.x = 0.5; p.y = 0.5; p.z = 0.5; p.w = 1
                    end
                end

                local status_msg = string.format("W%d T:%d | Sand:%d | Water:%d | Out:%d | Injected:%d",
                    {worker_id}, tick_cnt, sand_cnt, water_cnt, #boundary_outgoing, injected_cnt)
                outputs.string.status = status_msg

                if tick_cnt % 5 == 0 then
                    print("[WORKER-" .. {worker_id} .. "-DEBUG] " .. status_msg)
                end

                {canvas_var}:flush()
            end
            """

        master_idx = s.add_lua_chip(
            master_lua,
            inputs=[
                {"name": "worker0_data", "type": "array_vec"},
                {"name": "worker1_data", "type": "array_vec"},
                {"name": "worker2_data", "type": "array_vec"},
                {"name": "worker3_data", "type": "array_vec"}
            ],
            outputs=[
                {"name": "send0_data", "type": "array_vec"},
                {"name": "send1_data", "type": "array_vec"},
                {"name": "send2_data", "type": "array_vec"},
                {"name": "send3_data", "type": "array_vec"},
                {"name": "status", "type": "string"}
            ],
            x=1.0, y=-2.0,
            instruction_cost=100000
        )

        canvases = [cv0, cv1, cv2, cv3]
        for idx, (col, row) in enumerate([(0,0), (1,0), (0,1), (1,1)]):
            cv = canvases[idx]
            code = make_worker_lua(cv.lua_var, col, row, idx)

            w_idx = s.add_lua_chip(
                code,
                canvases=[cv],
                inputs=[{"name": "recv_data", "type": "array_vec"}],
                outputs=[
                    {"name": "send_data", "type": "array_vec"},
                    {"name": "status", "type": "string"}
                ],
                x=col * 2.0 + 0.5,
                y=row * 2.0 + 1.0,
                instruction_cost=100000
            )

            s.connect(w_idx, "send_data", master_idx, f"worker{idx}_data")
            s.connect(master_idx, f"send{idx}_data", w_idx, "recv_data")

        res = s.debug_run(ticks=20)
        print("Simulator Logs:")
        for log in res.get("logs", []):
            print(" ", log)

        s.save("powder_sandbox_debug_master_worker.melsave")
        print("Saved powder_sandbox_debug_master_worker.melsave successfully!")

if __name__ == "__main__":
    run_debug_single()
    run_debug_master_worker()
