"""Sample script showing 4 Parallel Worker Chips driving a 2x2 Screen Cluster (64x64) in Pure Intrusive Mode."""
from melon_lua import MelsaveSession

def main():
    def worker_builder(col: int, row: int, canvas) -> str:
        gx_offset = col * 32
        gy_offset = row * 32

        return f"""-- Worker Chip Tile ({col},{row}) - 4-Screen Pure Intrusive Canvas Controller
        local buf = {canvas.lua_var}.buffer
        local gx_offset = {gx_offset}
        local gy_offset = {gy_offset}

        local BLACK = {{x=0, y=0, z=0, w=1}}
        local GOLD  = {{x=1, y=0.8, z=0.1, w=1}}
        local RED   = {{x=1, y=0, z=0, w=1}}
        local GREEN = {{x=0, y=1, z=0, w=1}}
        local BLUE  = {{x=0, y=0, z=1, w=1}}

        local tick_count = 0
        local bx = 10.0
        local by = 15.0
        local vx = 1.6
        local vy = 1.2
        local radius = 3.0

        function OnTick()
            tick_count = tick_count + 1

            -- 1. Fast intrusive buffer clear (1024 pixels)
            for i = 1, 1024 do
                buf[i] = BLACK
            end

            -- 2. Corner diagnostic indicators (Top-Left: RED, Top-Right: GREEN, Bottom-Left: BLUE)
            buf[1] = RED
            buf[32] = GREEN
            buf[993] = BLUE

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

            -- 4. Direct intrusive pixel write for sub-viewport
            local center_x = math.floor(bx)
            local center_y = math.floor(by)

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

            -- 5. Direct intrusive flush
            {canvas.lua_var}:flush()
        end
        """

    with MelsaveSession() as s:
        # Create 2x2 LED display cluster (64x64 total resolution)
        cluster = s.create_canvas_cluster(cols=2, rows=2, tile_width=32, tile_height=32)
        print("Display Cluster created: 2x2 grid, Total Res: 64x64")

        # Spawn 4 Parallel Worker Chips directly wired to the 4 displays
        s.add_parallel_canvas_chips(
            cluster=cluster,
            worker_script_fn=worker_builder,
            inputs=[{"name": "target", "type": "entity"}],
            outputs=[{"name": "status", "type": "string", "value": "4-Screen Active"}],
        )

        res = s.debug_run(ticks=10)
        print("Debug run status:", "OK" if not res.get("error") else res.get("error"))

        s.save("canvas_4screens_demo.melsave")
        print("Saved canvas_4screens_demo.melsave successfully!")

if __name__ == "__main__":
    main()
