"""Sample script showing 1 Master Chip controlling 4 Worker Chips driving a 2x2 Screen Cluster (64x64) with Pure Intrusive Mode."""
from melon_lua import MelsaveSession

def main():
    # 1. Master Chip logic: calculates bouncing ball physics & broadcasts (bx, by, radius) to 4 Worker Chips
    master_script = """
    local tick_count = 0
    local bx = 10.0
    local by = 15.0
    local vx = 1.6
    local vy = 1.2
    local radius = 3.0

    function OnTick()
        tick_count = tick_count + 1

        -- Update physics on Master
        bx = bx + vx
        by = by + vy

        -- Bounce off 64x64 global boundaries
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

        -- Package position data into Vector4 array: {x=bx, y=by, z=radius, w=1}
        local ball_packet = { {x = bx, y = by, z = radius, w = 1.0} }

        -- Broadcast to 4 worker chips via gate wires
        outputs.array_vec.tile_out_0_0 = ball_packet
        outputs.array_vec.tile_out_0_1 = ball_packet
        outputs.array_vec.tile_out_1_0 = ball_packet
        outputs.array_vec.tile_out_1_1 = ball_packet
    end
    """

    # 2. Worker Chip logic: Pure Intrusive Mode (direct buffer assignment & flush)
    def worker_builder(col: int, row: int, canvas) -> str:
        gx_offset = col * 32
        gy_offset = row * 32

        return f"""-- Worker Chip Tile ({col},{row}) - Pure Intrusive Canvas Controller
        local buf = {canvas.lua_var}.buffer
        local gx_offset = {gx_offset}
        local gy_offset = {gy_offset}

        local BLACK = {{x=0, y=0, z=0, w=1}}
        local GOLD  = {{x=1, y=0.8, z=0.1, w=1}}

        function OnTick()
            -- 1. Fast intrusive buffer clear
            for i = 1, 1024 do
                buf[i] = BLACK
            end

            -- 2. Read position packet sent from Master Chip via physical Wire (tile_in)
            local input_data = inputs.array_vec.tile_in
            if input_data and input_data[1] then
                local pos = input_data[1]
                local bx = pos.x
                local by = pos.y
                local radius = pos.z or 3.0

                local center_x = math.floor(bx)
                local center_y = math.floor(by)

                -- 3. Direct intrusive pixel write for sub-viewport
                for dx = -3, 3 do
                    for dy = -3, 3 do
                        if (dx * dx + dy * dy) <= (radius * radius + 0.5) then
                            local gx = center_x + dx
                            local gy = center_y + dy
                            if gx >= gx_offset and gx < (gx_offset + 32) and gy >= gy_offset and gy < (gy_offset + 32) then
                                local lx = gx - gx_offset
                                local ly = gy - gy_offset
                                local idx = ly * 32 + lx + 1
                                buf[idx] = GOLD
                            end
                        end
                    end
                end
            end

            -- 4. Direct intrusive flush
            {canvas.lua_var}:flush()
        end
        """

    with MelsaveSession() as s:
        # Create 2x2 LED display cluster (64x64 total resolution)
        cluster = s.create_canvas_cluster(cols=2, rows=2, tile_width=32, tile_height=32)
        print("Display Cluster created: 2x2 grid, Total Res: 64x64")

        # Spawn 1 Master Chip and 4 Worker Chips with 8 auto-wired connections
        s.add_parallel_canvas_chips(
            cluster=cluster,
            worker_script_fn=worker_builder,
            master_script=master_script,
            inputs=[{"name": "target", "type": "entity"}],
            outputs=[{"name": "status", "type": "string", "value": "Master-Worker Active"}],
        )

        res = s.debug_run(ticks=10)
        print("Debug run status:", "OK" if not res.get("error") else res.get("error"))

        s.save("canvas_master_worker_ball.melsave")
        print("Saved canvas_master_worker_ball.melsave successfully!")

if __name__ == "__main__":
    main()
