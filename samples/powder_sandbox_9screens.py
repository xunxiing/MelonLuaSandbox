"""Powder Sandbox - 9 Screens (3x3 Grid) High-Performance Demo.

Includes User-Proposed Core Game-Engine Optimizations:
1. Tick Timestamp Mark (updated_tick[idx] == tick_cnt) for O(1) update validation (zero array clears per tick)
2. Differential Incremental Rendering (only mutates C# Vector4 properties when grid[idx] != prev_grid[idx])
3. Active Particle Array Capping (MAX_PARTICLES = 120 per tile)
4. Fast O(1) Particle List Swap-Remove
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from melon_lua import MelsaveSession


def main():
    with MelsaveSession() as s:
        # Create 3x3 Canvas Cluster (9 Screens total)
        cluster = s.create_canvas_cluster(cols=3, rows=3, display_type="led_matrix")

        def make_9screen_worker_lua(canvas_var: str, row: int, col: int) -> str:
            return f"""-- 3x3 Tile Worker Chip (Row {row}, Col {col})
local TILE_COL = {col}
local TILE_ROW = {row}
local MAX_PARTICLES = 120

local W = 32
local H = 32

local grid = {{}}
local prev_grid = {{}}
local updated_tick = {{}}

for i = 1, 1024 do
    grid[i] = 0
    prev_grid[i] = -1
    updated_tick[i] = 0
end

-- Obstacle Platforms
if TILE_ROW == 0 and TILE_COL == 1 then
    for x = 6, 26 do grid[16 * 32 + x + 1] = 3 end
elseif TILE_ROW == 1 and TILE_COL == 0 then
    for x = 4, 20 do grid[20 * 32 + x + 1] = 3 end
elseif TILE_ROW == 1 and TILE_COL == 2 then
    for x = 12, 28 do grid[20 * 32 + x + 1] = 3 end
end

local active = {{}}
local active_cnt = 0

function OnInit()
    if not shared.grid_transfers then
        shared.grid_transfers = {{}}
    end
    shared.grid_transfers[TILE_ROW .. "_" .. TILE_COL] = {{}}
end

local tick_cnt = 0

function OnTick()
    if not outputs or not outputs.array_vec then return end
    tick_cnt = tick_cnt + 1

    -- 1. Receive incoming boundary particles
    local transfer_key = TILE_ROW .. "_" .. TILE_COL
    if shared.grid_transfers and shared.grid_transfers[transfer_key] then
        local in_q = shared.grid_transfers[transfer_key]
        for k = #in_q, 1, -1 do
            local p = in_q[k]
            in_q[k] = nil
            if active_cnt < MAX_PARTICLES then
                local idx = p.y * 32 + p.x + 1
                if grid[idx] == 0 then
                    grid[idx] = p.type
                    updated_tick[idx] = tick_cnt
                    active_cnt = active_cnt + 1
                    active[active_cnt] = {{ x = p.x, y = p.y, type = p.type }}
                end
            end
        end
    end

    -- 2. Emitter (Tile 0,1 spawns sand and water)
    if TILE_ROW == 0 and TILE_COL == 1 and tick_cnt % 3 == 0 then
        if active_cnt < MAX_PARTICLES - 2 then
            local sx1, sy1 = 15, 1
            local idx1 = sy1 * 32 + sx1 + 1
            if grid[idx1] == 0 then
                grid[idx1] = 1
                updated_tick[idx1] = tick_cnt
                active_cnt = active_cnt + 1
                active[active_cnt] = {{ x = sx1, y = sy1, type = 1 }}
            end

            local sx2, sy2 = 16, 1
            local idx2 = sy2 * 32 + sx2 + 1
            if grid[idx2] == 0 then
                grid[idx2] = 2
                updated_tick[idx2] = tick_cnt
                active_cnt = active_cnt + 1
                active[active_cnt] = {{ x = sx2, y = sy2, type = 2 }}
            end
        end
    end

    -- 3. Particle Physics (O(1) Tick Timestamp Mark: updated_tick[idx] == tick_cnt)
    local i = active_cnt
    while i >= 1 do
        local pt = active[i]
        local x, y, type_id = pt.x, pt.y, pt.type
        local cur_idx = y * 32 + x + 1

        if updated_tick[cur_idx] ~= tick_cnt then
            if y >= H - 1 then
                if TILE_ROW < 2 then
                    local target_key = (TILE_ROW + 1) .. "_" .. TILE_COL
                    if shared.grid_transfers and shared.grid_transfers[target_key] then
                        table.insert(shared.grid_transfers[target_key], {{ x = x, y = 0, type = type_id }})
                    end
                end
                grid[cur_idx] = 0
                active[i] = active[active_cnt]
                active[active_cnt] = nil
                active_cnt = active_cnt - 1
            else
                local below_idx = (y + 1) * 32 + x + 1
                if grid[below_idx] == 0 then
                    grid[cur_idx] = 0
                    grid[below_idx] = type_id
                    updated_tick[below_idx] = tick_cnt
                    pt.y = y + 1
                elseif type_id == 1 and grid[below_idx] == 2 then
                    grid[cur_idx] = 2
                    grid[below_idx] = 1
                    updated_tick[cur_idx] = tick_cnt
                    updated_tick[below_idx] = tick_cnt
                    pt.y = y + 1
                else
                    local dir = (tick_cnt + i) % 2 == 0 and 1 or -1
                    local nx = x + dir
                    if nx >= 0 and nx < W then
                        local diag_idx = (y + 1) * 32 + nx + 1
                        if grid[diag_idx] == 0 then
                            grid[cur_idx] = 0
                            grid[diag_idx] = type_id
                            updated_tick[diag_idx] = tick_cnt
                            pt.x = nx
                            pt.y = y + 1
                        elseif type_id == 2 then
                            local lat_idx = y * 32 + nx + 1
                            if grid[lat_idx] == 0 then
                                grid[cur_idx] = 0
                                grid[lat_idx] = 2
                                updated_tick[lat_idx] = tick_cnt
                                pt.x = nx
                            end
                        end
                    end
                end
            end
        end
        i = i - 1
    end

    -- 4. Differential Incremental Render (Only write when grid[idx] != prev_grid[idx])
    local buf = {canvas_var}.buffer
    if buf then
        for idx = 1, 1024 do
            local c = grid[idx]
            if c ~= prev_grid[idx] then
                prev_grid[idx] = c
                local p = buf[idx]
                if c == 0 then
                    p.x = 0.0; p.y = 0.0; p.z = 0.0; p.w = 1.0
                elseif c == 1 then
                    p.x = 0.95; p.y = 0.75; p.z = 0.2; p.w = 1.0
                elseif c == 2 then
                    p.x = 0.2; p.y = 0.6; p.z = 1.0; p.w = 1.0
                elseif c == 3 then
                    p.x = 0.5; p.y = 0.5; p.z = 0.5; p.w = 1.0
                end
            end
        end
        {canvas_var}:flush()
    end
end
"""

        # Spawn 9 Chips for 3x3 Canvas Cluster
        for r in range(3):
            for c in range(3):
                cv = cluster.get_tile(c, r)
                code = make_9screen_worker_lua(cv.lua_var, row=r, col=c)
                pos_x = (c - 1) * 3.5
                pos_y = (1 - r) * 3.5 - 5.0
                s.add_lua_chip(
                    code,
                    canvases=[cv],
                    outputs=[{"name": "status", "type": "string"}],
                    x=pos_x,
                    y=pos_y,
                    instruction_cost=1000000
                )

        res = s.debug_run(ticks=30)
        print("Debug run status:", "OK" if not res.get("error") else res.get("error"))

        s.save("powder_sandbox_9screens.melsave")
        print("Saved powder_sandbox_9screens.melsave successfully!")


if __name__ == "__main__":
    main()
