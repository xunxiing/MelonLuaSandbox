"""Two Chips Master-Worker Screen Controller Demo.

Architecture:
- Object 0: 32x32 LED Matrix Display
- Object 1: Master Control Chip (computes ball trajectory, sends vector package)
- Object 2: Worker Display Chip (receives vector package, renders to LED Matrix using pure property mutation)

Wire Constraints:
- Wire 1: Master (master_to_worker_vec) -> Worker (master_vec_data)
- Wire 2: Worker (canvas_out_0) -> Display (led-matrix-data)
"""
from melon_lua import MelsaveSession

def main():
    with MelsaveSession() as s:
        # 1. Create 32x32 LED Matrix Display
        cv = s.create_canvas(width=32, height=32, display_type="led_matrix", x=1.0, y=0.0)

        # 2. Master Control Chip Script
        master_lua = """
        local bx = 16.0
        local by = 16.0
        local vx = 1.2
        local vy = 0.9
        local radius = 3.0
        local tick_cnt = 0

        function OnTick()
            tick_cnt = tick_cnt + 1

            -- Physics ball bounce calculation (32x32 boundary)
            bx = bx + vx
            by = by + vy

            if bx <= radius or bx >= (32.0 - radius) then
                vx = -vx
                bx = bx + vx
            end
            if by <= radius or by >= (32.0 - radius) then
                vy = -vy
                by = by + vy
            end

            -- Package vector data for Worker Chip
            -- x: ball_x, y: ball_y, z: radius, w: active_flag
            local payload = {
                {x = bx, y = by, z = radius, w = 1.0}
            }

            outputs.array_vec.master_to_worker_vec = payload

            -- Status output for in-game UI & debugger
            local msg = string.format("Master T:%d | Pos:(%.1f, %.1f)", tick_cnt, bx, by)
            outputs.string.status = msg

            if tick_cnt % 10 == 0 then
                print("[MASTER-CHIP] " .. msg)
            end
        end
        """

        # 3. Worker Display Chip Script
        worker_lua = """
        local buf = canvas_0.buffer
        local tick_cnt = 0

        function OnTick()
            tick_cnt = tick_cnt + 1

            -- 1. Fast Clear All 1024 Pixels (Pure Property Mutation)
            for i = 1, 1024 do
                local p = buf[i]
                p.x = 0; p.y = 0; p.z = 0; p.w = 1
            end

            -- 2. Corner Alignment Markers (Red at Top-Left, Green at Top-Right, Blue at Bottom-Left)
            local p_tl = buf[1];    p_tl.x = 1; p_tl.y = 0; p_tl.z = 0; p_tl.w = 1
            local p_tr = buf[32];   p_tr.x = 0; p_tr.y = 1; p_tr.z = 0; p_tr.w = 1
            local p_bl = buf[993];  p_bl.x = 0; p_bl.y = 0; p_bl.z = 1; p_bl.w = 1

            -- 3. Receive Ball Position Data from Master Chip over Wire
            local incoming = inputs.array_vec.master_vec_data
            local pos_info = "None"

            if incoming and incoming[1] then
                local ball = incoming[1]
                local cx = math.floor(ball.x or 16)
                local cy = math.floor(ball.y or 16)
                local r  = ball.z or 3.0

                pos_info = string.format("(%d, %d)", cx, cy)

                -- Draw 3x3 Glowing Golden Ball
                for dx = -2, 2 do
                    for dy = -2, 2 do
                        if (dx * dx + dy * dy) <= (r * r) then
                            local px = cx + dx
                            local py = cy + dy
                            if px >= 0 and px < 32 and py >= 0 and py < 32 then
                                local idx = py * 32 + px + 1
                                local p = buf[idx]
                                p.x = 1.0; p.y = 0.85; p.z = 0.1; p.w = 1.0
                            end
                        end
                    end
                end
            end

            -- Status Output for in-game UI
            local msg = string.format("Worker T:%d | Recv Pos: %s", tick_cnt, pos_info)
            outputs.string.status = msg

            if tick_cnt % 10 == 0 then
                print("[WORKER-CHIP] " .. msg)
            end

            canvas_0:flush()
        end
        """

        # Add Master Control Chip
        master_idx = s.add_lua_chip(
            master_lua,
            outputs=[
                {"name": "master_to_worker_vec", "type": "array_vec"},
                {"name": "status", "type": "string"}
            ],
            x=0.0, y=-2.0,
            instruction_cost=100000
        )

        # Add Worker Display Chip (wired to cv)
        worker_idx = s.add_lua_chip(
            worker_lua,
            canvases=[cv],
            inputs=[{"name": "master_vec_data", "type": "array_vec"}],
            outputs=[{"name": "status", "type": "string"}],
            x=2.0, y=-2.0,
            instruction_cost=100000
        )

        # Wire Master (master_to_worker_vec) -> Worker (master_vec_data)
        s.connect(master_idx, "master_to_worker_vec", worker_idx, "master_vec_data")

        # Run 20 ticks simulation check
        res = s.debug_run(ticks=20)
        print("Simulator debug run status:", "OK" if not res.get("error") else res.get("error"))

        print("\nSimulator Debug Logs:")
        for log in res.get("logs", []):
            print(" ", log)

        s.save("two_chips_master_worker.melsave")
        print("\nSaved two_chips_master_worker.melsave successfully!")

if __name__ == "__main__":
    main()
