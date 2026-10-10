"""Canvas Intrusive Performance Demo (videolua2 style).

Demonstrates zero-overhead intrusive direct table manipulation for highest FPS.
"""
from melon_lua import MelsaveSession


def main():
    with MelsaveSession() as s:
        cv = s.create_canvas(width=32, height=32, display_type="led_matrix")

        # Direct intrusive style: access pre-allocated buffer directly like videolua2
        lua_code = f"""
        local tick_count = 0
        local buf = {cv.lua_var}.buffer

        function OnTick()
            tick_count = tick_count + 1
            
            -- Fast clear
            for i = 1, 1024 do
                local p = buf[i]
                p.x = 0; p.y = 0; p.z = 0; p.w = 1
            end

            -- Moving diagonal pixel
            local pos = tick_count % 32
            local idx = pos * 32 + pos + 1
            local p = buf[idx]
            p.x = 1; p.y = 1; p.z = 1; p.w = 1

            {cv.lua_var}:flush()
        end
        """

        s.add_lua_chip(
            lua_code,
            canvases=[cv],
            inputs=[{"name": "target", "type": "entity"}],
            outputs=[{"name": "status", "type": "string", "value": "Intrusive Canvas Active"}],
        )

        res = s.debug_run(ticks=10)
        print("Intrusive debug run status:", "OK" if not res.get("error") else res.get("error"))

        s.save("canvas_intrusive_demo.melsave")
        print("Saved canvas_intrusive_demo.melsave successfully!")


if __name__ == "__main__":
    main()
