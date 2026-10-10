"""Sample script showing Canvas Package (V1: Direct Pixel Drawing) on LED Matrix."""
from melon_lua import MelsaveSession

def main():
    with MelsaveSession() as s:
        # 1. Create canvas instance (spawns LED Matrix display & returns handle)
        cv = s.create_canvas(width=32, height=32, display_type="led_matrix")
        print(f"Canvas created: ID={cv.canvas_id}, Item Index={cv.item_idx}, Variable={cv.lua_var}")

        # 2. Agent Lua code (clean, using the generated canvas handle)
        lua_code = f"""
        local tick_count = 0

        OnTick = {cv.lua_var}:bind(function()
            tick_count = tick_count + 1

            -- Clear canvas to black
            {cv.lua_var}:clear(0, 0, 0)

            -- Set individual pixels directly
            {cv.lua_var}:setPixel(10, 10, 1, 0, 0) -- Red pixel at (10,10)
            {cv.lua_var}:setPixel(20, 15, 0, 1, 0) -- Green pixel at (20,15)
            {cv.lua_var}:setPixel(5, 25, 0, 0, 1)  -- Blue pixel at (5,25)

            -- Animate a moving white pixel along the diagonal
            local pos = math.floor(tick_count % 32)
            {cv.lua_var}:setPixel(pos, pos, 1, 1, 1)
        end)
        """

        # 3. Add chip with auto-bound canvas & explicit ports (per persona.md)
        chip_idx = s.add_lua_chip(
            lua_code,
            canvases=[cv],
            inputs=[{"name": "target", "type": "entity"}],
            outputs=[{"name": "status", "type": "string", "value": "Canvas Active"}],
        )
        print(f"Lua Chip added at index {chip_idx}")

        # 4. Debug run for 10 ticks to verify
        res = s.debug_run(ticks=10)
        print("Debug run success! Error:", res["error"])

        # Check outputs from chip
        chip_vars = res.get("chip_variables", {})
        print("Final tick count:", chip_vars.get("tick_count"))

        # Save melsave file
        s.save("canvas_demo.melsave")
        print("Saved canvas_demo.melsave successfully!")

if __name__ == "__main__":
    main()
