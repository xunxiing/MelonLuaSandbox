"""Generate exact two chips save matching user persona.md spec:
1. Sender Chip (Outputs only, all 10 scalar & array types) at x=-3.0, y=0.0
2. Receiver Chip (Inputs only, all 10 scalar & array types) at x=3.0, y=0.0
"""
from melon_lua.session import MelsaveSession

def main():
    with MelsaveSession() as s:
        # 1. Sender Chip (Outputs)
        sender_lua = """
        function OnInit()
            -- noop
        end

        function OnTick()
            -- =================== Scalar outputs ===================
            outputs.num.tick      = (outputs.num.tick or 0) + 1
            outputs.int.counter   = 100
            outputs.string.status = "ok status"
            outputs.vec.heading   = { x = 1, y = 2, z = 0, w = 0 }
            outputs.color.glow    = { r = 1, g = 1, b = 0, a = 1 }
            outputs.entity.found  = 0

            -- =================== Array outputs ===================
            outputs.array_num.filtered    = { 1, 2, 3 }
            outputs.array_string.labels   = { "first", "second" }
            outputs.array_vec.path        = { { x=0, y=0, z=0, w=0 }, { x=1, y=2, z=0, w=0 } }
            outputs.array_entity.captured = { 0 }
        end
        """

        sender_idx = s.add_lua_chip(
            sender_lua,
            x=-3.0,
            y=0.0,
            inputs=[],
            outputs=[
                {"name": "tick", "type": "num"},
                {"name": "counter", "type": "int"},
                {"name": "status", "type": "string"},
                {"name": "heading", "type": "vec"},
                {"name": "glow", "type": "color"},
                {"name": "found", "type": "entity"},
                {"name": "filtered", "type": "array_num"},
                {"name": "labels", "type": "array_string"},
                {"name": "path", "type": "array_vec"},
                {"name": "captured", "type": "array_entity"},
            ]
        )

        # 2. Receiver Chip (Inputs)
        receiver_lua = """
        function OnInit()
            -- noop
        end

        function OnTick()
            -- =================== Scalar inputs ===================
            local n        = inputs.num.speed or 0           -- number (double)
            local i        = inputs.int.count or 0           -- integer
            local s        = inputs.string.label or ""       -- string
            local v        = inputs.vec.direction            -- {x, y, z, w}
            local c        = inputs.color.tint               -- {r, g, b, a}
            local targetId = inputs.entity.target or 0       -- instanceID

            local vx = v and v.x or 0
            local vy = v and v.y or 0
            local cr = c and c.r or 1

            -- =================== Array inputs ===================
            local arrN = inputs.array_num.values or {}       -- {1, 2.5, 3}
            local arrS = inputs.array_string.tags or {}      -- {"a", "b"}
            local arrV = inputs.array_vec.points or {}       -- {{x=,y=,z=,w=}, ...}
            local arrE = inputs.array_entity.targets or {}   -- {id1, id2}
        end
        """

        receiver_idx = s.add_lua_chip(
            receiver_lua,
            x=3.0,
            y=0.0,
            inputs=[
                {"name": "speed", "type": "num"},
                {"name": "count", "type": "int"},
                {"name": "label", "type": "string"},
                {"name": "direction", "type": "vec"},
                {"name": "tint", "type": "color"},
                {"name": "target", "type": "entity"},
                {"name": "values", "type": "array_num"},
                {"name": "tags", "type": "array_string"},
                {"name": "points", "type": "array_vec"},
                {"name": "targets", "type": "array_entity"},
            ],
            outputs=[]
        )

        s.save("chip_ports_test.melsave")
        print("Generated chip_ports_test.melsave matching persona.md spec exactly!")

if __name__ == "__main__":
    main()
