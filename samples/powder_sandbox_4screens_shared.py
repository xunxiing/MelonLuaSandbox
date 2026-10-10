"""Powder Sandbox - 4 Screens Complete Seamless Grid & Transparent Border.

Features:
- Seamless 2D Grid Alignment (Width 0.74m x Height 0.74m per LED screen, flush zero-gap tiling)
- Transparent Border via Entity(target):setColor(0, 0, 0, 0)
- Dual Emitters on Tile 0 (Top-Left) and Tile 1 (Top-Right)
- Full 4-Way Cross-Screen Routing (Vertical & Horizontal transfers between all 4 screens)
- 4-Tile Custom Obstacle Slopes
- Tick Timestamp Mark & Differential Incremental Rendering
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from melon_lua import MelsaveSession


def main():
    with MelsaveSession() as s:
        # User micro-tuned seamless 2x2 display grid coordinates (exact 0.6591m spacing)
        # Top-Left: (-0.3449, 0.6724), Top-Right: (0.3142, 0.6724)
        # Bottom-Left: (-0.3449, 0.0134), Bottom-Right: (0.3142, 0.0134)
        cv0 = s.create_canvas(width=32, height=32, display_type="led_matrix", x=-0.3449, y=0.6724)
        cv1 = s.create_canvas(width=32, height=32, display_type="led_matrix", x=0.3142, y=0.6724)
        cv2 = s.create_canvas(width=32, height=32, display_type="led_matrix", x=-0.3449, y=0.0134)
        cv3 = s.create_canvas(width=32, height=32, display_type="led_matrix", x=0.3142, y=0.0134)

        def make_worker_lua(canvas_var: str, tile_id: int) -> str:
            return f"""-- 4-Screen Shared Memory Tile {tile_id}
local TILE_ID = {tile_id}
local MAX_PARTICLES = 140
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

-- Obstacle slopes for all 4 tiles
if TILE_ID == 0 then
    -- Tile 0 (Top-Left): Right-tilting slope
    for k = 0, 15 do
        local x = 4 + k
        local y = 10 + k
        grid[y * 32 + x + 1] = 3
    end
elseif TILE_ID == 1 then
    -- Tile 1 (Top-Right): Left-tilting slope
    for k = 0, 15 do
        local x = 27 - k
        local y = 10 + k
        grid[y * 32 + x + 1] = 3
    end
elseif TILE_ID == 2 then
    -- Tile 2 (Bottom-Left): Funnel platform
    for k = 0, 12 do
        grid[(14 + k) * 32 + k + 1] = 3
        grid[(26 - k) * 32 + (20 + k) + 1] = 3
    end
elseif TILE_ID == 3 then
    -- Tile 3 (Bottom-Right): Step platform
    for x = 6, 26 do
        grid[18 * 32 + x + 1] = 3
    end
end

local active = {{}}
local active_cnt = 0
local color_set = false

function OnInit()
    if not shared.injected then
        shared.injected = {{ [0]={{}}, [1]={{}}, [2]={{}}, [3]={{}} }}
    end
    shared.injected[TILE_ID] = shared.injected[TILE_ID] or {{}}
end

local tick_cnt = 0

function OnTick()
    if not outputs or not outputs.array_vec then return end
    tick_cnt = tick_cnt + 1

    -- Set screen entity color to transparent (0, 0, 0, 0)
    if not color_set then
        local targetId = inputs and inputs.entity and inputs.entity.target
        if targetId and targetId ~= 0 then
            local e = Entity(targetId)
            if e:isValid() == 1 then
                e:setColor(0, 0, 0, 0)
                color_set = true
            end
        end
    end

    -- 1. Receive incoming boundary particles
    if shared.injected and shared.injected[TILE_ID] then
        local q = shared.injected[TILE_ID]
        for k = #q, 1, -1 do
            local p = q[k]
            q[k] = nil
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

    -- 2. Dual Emitters
    if TILE_ID == 0 and tick_cnt % 3 == 0 then
        if active_cnt < MAX_PARTICLES - 2 then
            local idx1 = 1 * 32 + 6 + 1
            if grid[idx1] == 0 then
                grid[idx1] = 1
                updated_tick[idx1] = tick_cnt
                active_cnt = active_cnt + 1
                active[active_cnt] = {{ x = 6, y = 1, type = 1 }}
            end

            local idx2 = 1 * 32 + 7 + 1
            if grid[idx2] == 0 then
                grid[idx2] = 2
                updated_tick[idx2] = tick_cnt
                active_cnt = active_cnt + 1
                active[active_cnt] = {{ x = 7, y = 1, type = 2 }}
            end
        end
    elseif TILE_ID == 1 and tick_cnt % 3 == 0 then
        if active_cnt < MAX_PARTICLES - 2 then
            local idx1 = 1 * 32 + 25 + 1
            if grid[idx1] == 0 then
                grid[idx1] = 1
                updated_tick[idx1] = tick_cnt
                active_cnt = active_cnt + 1
                active[active_cnt] = {{ x = 25, y = 1, type = 1 }}
            end

            local idx2 = 1 * 32 + 24 + 1
            if grid[idx2] == 0 then
                grid[idx2] = 2
                updated_tick[idx2] = tick_cnt
                active_cnt = active_cnt + 1
                active[active_cnt] = {{ x = 24, y = 1, type = 2 }}
            end
        end
    end

    -- 3. Particle Physics (with 4-way boundary cross transfers)
    local i = active_cnt
    while i >= 1 do
        local pt = active[i]
        local x, y, cell = pt.x, pt.y, pt.type
        local cur_idx = y * 32 + x + 1

        if updated_tick[cur_idx] ~= tick_cnt then
            if y >= H - 1 then
                -- Vertical transfer: Bottom boundary
                if TILE_ID == 0 and shared.injected then
                    table.insert(shared.injected[2], {{ x = x, y = 0, type = cell }})
                elseif TILE_ID == 1 and shared.injected then
                    table.insert(shared.injected[3], {{ x = x, y = 0, type = cell }})
                end
                grid[cur_idx] = 0
                active[i] = active[active_cnt]
                active[active_cnt] = nil
                active_cnt = active_cnt - 1
            else
                local below_idx = (y + 1) * 32 + x + 1
                if grid[below_idx] == 0 then
                    grid[cur_idx] = 0
                    grid[below_idx] = cell
                    updated_tick[below_idx] = tick_cnt
                    pt.y = y + 1
                elseif cell == 1 and grid[below_idx] == 2 then
                    grid[cur_idx] = 2
                    grid[below_idx] = 1
                    updated_tick[cur_idx] = tick_cnt
                    updated_tick[below_idx] = tick_cnt
                    pt.y = y + 1
                else
                    local dir = (tick_cnt + i) % 2 == 0 and 1 or -1
                    local nx = x + dir

                    if nx < 0 then
                        -- Horizontal transfer: Left boundary
                        if TILE_ID == 1 and shared.injected then
                            table.insert(shared.injected[0], {{ x = W - 1, y = y, type = cell }})
                            grid[cur_idx] = 0
                            active[i] = active[active_cnt]
                            active[active_cnt] = nil
                            active_cnt = active_cnt - 1
                        elseif TILE_ID == 3 and shared.injected then
                            table.insert(shared.injected[2], {{ x = W - 1, y = y, type = cell }})
                            grid[cur_idx] = 0
                            active[i] = active[active_cnt]
                            active[active_cnt] = nil
                            active_cnt = active_cnt - 1
                        end
                    elseif nx >= W then
                        -- Horizontal transfer: Right boundary
                        if TILE_ID == 0 and shared.injected then
                            table.insert(shared.injected[1], {{ x = 0, y = y, type = cell }})
                            grid[cur_idx] = 0
                            active[i] = active[active_cnt]
                            active[active_cnt] = nil
                            active_cnt = active_cnt - 1
                        elseif TILE_ID == 2 and shared.injected then
                            table.insert(shared.injected[3], {{ x = 0, y = y, type = cell }})
                            grid[cur_idx] = 0
                            active[i] = active[active_cnt]
                            active[active_cnt] = nil
                            active_cnt = active_cnt - 1
                        end
                    else
                        local diag_idx = (y + 1) * 32 + nx + 1
                        if grid[diag_idx] == 0 then
                            grid[cur_idx] = 0
                            grid[diag_idx] = cell
                            updated_tick[diag_idx] = tick_cnt
                            pt.x = nx
                            pt.y = y + 1
                        elseif cell == 2 then
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

    -- 4. Differential Incremental Render
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

        canvases = [cv0, cv1, cv2, cv3]
        chip_positions = [(-2.5, 1.0), (2.5, 1.0), (-2.5, -1.0), (2.5, -1.0)]

        for idx, cv in enumerate(canvases):
            code = make_worker_lua(cv.lua_var, idx)
            pos_x, pos_y = chip_positions[idx]
            chip_idx = s.add_lua_chip(
                code,
                canvases=[cv],
                inputs=[{"name": "target", "type": "entity"}],
                outputs=[{"name": "status", "type": "string"}],
                x=pos_x,
                y=pos_y,
                instruction_cost=1000000
            )

            # Auto-wire inputs.entity.target to the screen display container
            display_container_idx = cv.item_idx
            s.connect(display_container_idx, "entity", chip_idx, "target")

        res = s.debug_run(ticks=30)
        print("Debug run status:", "OK" if not res.get("error") else res.get("error"))

        s.save("powder_sandbox_4screens_shared.melsave")
        print("Saved powder_sandbox_4screens_shared.melsave successfully!")


if __name__ == "__main__":
    main()
