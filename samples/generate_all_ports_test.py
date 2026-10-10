"""Generate a test melsave with separated chips containing all port types.

Positions are spread out so objects don't overlap in the editor:
- LED Display: x=0.0, y=3.0 (Top)
- Sender Chip A: x=-3.0, y=-2.0 (Bottom Left)
- Receiver Chip B: x=3.0, y=-2.0 (Bottom Right)
"""
from melon_lua.session import MelsaveSession

def main():
    with MelsaveSession() as s:
        # Create LED Matrix Display at Top (0.0, 3.0)
        cv = s.create_canvas(width=32, height=32, display_type="led_matrix", x=0.0, y=3.0)

        # Sender Chip A at Bottom Left (-3.0, -2.0)
        sender_lua = """
        -- Sender Chip A
        function OnTick()
            outputs.num.out_num = 42.0
            outputs.string.out_string = "Hello Wire"
            outputs.array_vec.out_array_vec = { {x=16, y=16, z=3, w=1} }
            outputs.string.status = "Sender Active"
        end
        """

        sender_idx = s.add_lua_chip(
            sender_lua,
            x=-3.0,
            y=-2.0,
            inputs=[
                {"name": "in_trigger", "type": "num"}
            ],
            outputs=[
                {"name": "out_num", "type": "num"},
                {"name": "out_string", "type": "string"},
                {"name": "out_vec", "type": "vec"},
                {"name": "out_array_num", "type": "array_num"},
                {"name": "out_array_string", "type": "array_string"},
                {"name": "out_array_vec", "type": "array_vec"},
                {"name": "status", "type": "string"}
            ]
        )

        # Receiver Chip B at Bottom Right (3.0, -2.0)
        receiver_lua = """
        -- Receiver Chip B
        local buf = canvas_0.buffer

        function OnTick()
            local num_val = inputs.num.in_num or 0
            local str_val = inputs.string.in_string or "none"
            local vec_arr = inputs.array_vec.in_array_vec

            for i = 1, 1024 do
                local p = buf[i]
                p.x = 0; p.y = 0; p.z = 0; p.w = 1.0
            end

            if vec_arr and vec_arr[1] then
                local bx = math.floor(vec_arr[1].x)
                local by = math.floor(vec_arr[1].y)
                local idx = by * 32 + bx + 1
                if idx >= 1 and idx <= 1024 then
                    local p = buf[idx]
                    p.x = 1.0; p.y = 0.8; p.z = 0.2; p.w = 1.0
                end
            end

            canvas_0:flush()
            outputs.string.status = string.format("Num:%.1f | Str:%s", num_val, str_val)
        end
        """

        receiver_idx = s.add_lua_chip(
            receiver_lua,
            x=3.0,
            y=-2.0,
            canvases=[cv],
            inputs=[
                {"name": "in_num", "type": "num"},
                {"name": "in_string", "type": "string"},
                {"name": "in_vec", "type": "vec"},
                {"name": "in_array_num", "type": "array_num"},
                {"name": "in_array_string", "type": "array_string"},
                {"name": "in_array_vec", "type": "array_vec"}
            ],
            outputs=[
                {"name": "status", "type": "string"}
            ]
        )

        # Save melsave
        s.save("chip_ports_test.melsave")
        print("Generated chip_ports_test.melsave with separated 2D positions!")

if __name__ == "__main__":
    main()
