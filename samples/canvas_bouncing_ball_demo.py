"""Sample: Bouncing Ball Demo on 4 Parallel Screens (2x2 Grid, 64x64 Total Resolution).

Creates a 2x2 grid of LED Matrix Displays (32x32 each) driven by 4 parallel Lua chips.
A glowing yellow ball with radius 3 bounces off the 64x64 outer boundaries and seamlessly
crosses between the 4 screen tiles in real time!
"""

from melon_lua import MelsaveSession


def worker_script_builder(col: int, row: int, canvas) -> str:
    """Returns Lua code for the worker chip driving sub-tile (col, row)."""
    return f"""
    local tick_count = 0
    local bx = 10.0
    local by = 15.0
    local vx = 1.6
    local vy = 1.2
    local radius = 3.0

    local tile = canvas_tile_{canvas.canvas_id}

    OnTick = {canvas.lua_var}:bind(function()
        tick_count = tick_count + 1
        {canvas.lua_var}:clear(0, 0, 0)

        -- Physics: Update ball position
        bx = bx + vx
        by = by + vy

        -- Bounce off 64x64 global boundaries
        if bx - radius <= 0 then
            bx = radius
            vx = -vx
        elseif bx + radius >= 63 then
            bx = 63 - radius
            vx = -vx
        end

        if by - radius <= 0 then
            by = radius
            vy = -vy
        elseif by + radius >= 63 then
            by = 63 - radius
            vy = -vy
        end

        -- Render bouncing ball (radius 3) on global 64x64 screen
        local center_x = math.floor(bx)
        local center_y = math.floor(by)

        for dx = -3, 3 do
            for dy = -3, 3 do
                if (dx * dx + dy * dy) <= (radius * radius + 0.5) then
                    local gx = center_x + dx
                    local gy = center_y + dy
                    -- Yellow glowing ball: R=1.0, G=0.8, B=0.1
                    tile:set_global_pixel(gx, gy, 1.0, 0.8, 0.1)
                end
            end
        end
    end)
    """


def main():
    with MelsaveSession() as s:
        # 1. Create a 2x2 cluster of 32x32 displays = 64x64 total screen area
        cluster = s.create_canvas_cluster(cols=2, rows=2, tile_width=32, tile_height=32)
        print(f"Canvas Cluster initialized: {cluster.cols}x{cluster.rows} screens (64x64 total resolution)")

        # 2. Add 4 parallel worker chips
        group = s.add_parallel_canvas_chips(
            cluster=cluster,
            worker_script_fn=worker_script_builder,
            inputs=[{"name": "target", "type": "entity"}],
            outputs=[{"name": "status", "type": "string", "value": "Bouncing Ball Active"}],
        )
        print("Spawned 4 parallel worker chips auto-wired to the 4 display screens!")

        # 3. Local debug run
        res = s.debug_run(ticks=30)
        print(f"Debug run completed: {res.get('status', 'OK')}")

        # 4. Save melsave document
        save_path = "canvas_bouncing_ball_demo.melsave"
        s.save(save_path)
        print(f"Saved {save_path} successfully!")


if __name__ == "__main__":
    main()
