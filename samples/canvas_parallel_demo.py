"""Sample: Multi-chip parallel Canvas drawing on a 2x2 grid (64x64 total resolution).

Creates 4 LED Matrix Displays (32x32 each) and 4 parallel worker Lua Chips.
Each worker chip handles a 32x32 sub-viewport of the overall 64x64 canvas.
A moving wave / diagonal circle pattern is rendered across the 4 displays in parallel!
"""

from melon_lua import MelsaveSession


def worker_script_builder(col: int, row: int, canvas) -> str:
    """Returns Lua code for the worker chip rendering sub-tile (col, row)."""
    return f"""
    local tick_count = 0
    local tile = canvas_tile_{canvas.canvas_id}

    OnTick = {canvas.lua_var}:bind(function()
        tick_count = tick_count + 1
        {canvas.lua_var}:clear(0, 0, 0)

        -- Global animation: A 64x64 diagonal wave moving across all 4 screens
        local center_gx = (tick_count * 2) % 64
        local center_gy = (tick_count * 2) % 64

        -- Draw a 5x5 square wave around global (center_gx, center_gy)
        for dx = -2, 2 do
            for dy = -2, 2 do
                local gx = center_gx + dx
                local gy = center_gy + dy
                -- set_global_pixel automatically checks if (gx, gy) belongs to this tile!
                tile:set_global_pixel(gx, gy, 0, 1, 0)
            end
        end
    end)
    """


def main():
    with MelsaveSession() as s:
        # 1. Create a 2x2 cluster of 32x32 screens = 64x64 total virtual resolution
        cluster = s.create_canvas_cluster(cols=2, rows=2, tile_width=32, tile_height=32)
        print(f"Canvas Cluster created: {cluster.cols}x{cluster.rows} grid, Total Res: {cluster.total_width}x{cluster.total_height}")

        # 2. Add 4 parallel worker Lua chips auto-wired to the 4 displays
        group = s.add_parallel_canvas_chips(
            cluster=cluster,
            worker_script_fn=worker_script_builder,
            inputs=[{"name": "target", "type": "entity"}],
            outputs=[{"name": "status", "type": "string", "value": "Parallel Active"}],
        )
        print(f"Spawned {len(group.worker_chip_indices)}x{len(group.worker_chip_indices[0])} parallel worker chips!")

        # 3. Test local debug run
        res = s.debug_run(ticks=10)
        print(f"Debug run status: {res.get('status', 'OK')}")

        # 4. Save to .melsave
        s.save("canvas_parallel_demo.melsave")
        print("Saved canvas_parallel_demo.melsave successfully!")


if __name__ == "__main__":
    main()
