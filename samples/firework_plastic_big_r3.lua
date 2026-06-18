-- Big plastic block firework, radius 3
-- Uses "202" (ResizablePlastic / Plastic plate) for the burst elements.
-- Launches a small rocket from (2, 2), then at height explodes into a LARGE ring
-- of plastic blocks arranged in a circle of radius exactly 3, flying outward.
--
-- This demonstrates a "big" explosion effect with radius 3 made purely from plastic blocks.
--
-- Self-test:
--   python scripts/self_test_firework_plastic_r3.py
-- or
--   melon-lua samples/firework_plastic_big_r3.lua --ticks 100

local rocket_id = nil
local rocket = nil
local state = "init"
local t = 0
local FUSE = 28          -- launch duration before big burst

local pending = {}       -- {name="202", x, y, vx, vy}

local PLASTIC = "202"    -- ResizablePlastic / PlasticBlock

function OnInit()
    local req = spawn.create(PLASTIC, 2.0, 2.0)  -- start with a plastic "rocket"
    outputs.string.status = "spawning"
    outputs.num.x = 2
    outputs.num.y = 2
    print("[PLASTIC_FW] spawn plastic rocket at (2,2), req=" .. tostring(req))
end

local function as_proxy(obj)
    if not obj then return nil end
    if type(obj) == "table" or type(obj) == "userdata" then
        if obj.setVelocity then return obj end
    end
    local id = tonumber(obj) or 0
    if id ~= 0 then return Entity(id) end
    return nil
end

local function remember(obj)
    local p = as_proxy(obj)
    local id = tonumber(obj) or 0
    if p then rocket = p end
    if id ~= 0 then rocket_id = id end
end

local function get_rocket()
    if rocket then return rocket end
    if rocket_id then return Entity(rocket_id) end
    return nil
end

local function kill_rocket()
    if rocket_id then spawn.destroy(rocket_id) end
    rocket = nil
    rocket_id = nil
end

function OnSpawned(req, ents)
    if state == "init" and ents and #ents > 0 then
        remember(ents[1])
        local e = get_rocket()
        if e then
            -- Launch the plastic "rocket" upward (the big burst will be the real show)
            e:setVelocity(0.05, 14.0)
            state = "launched"
            outputs.string.status = "launched"
            local px, py = 2.0, 2.0
            if e.getPosition then
                local ok, x, y = pcall(e.getPosition, e)
                if ok and x and y then px, py = x, y end
            end
            print(string.format("[PLASTIC_FW] launched from (%.2f,%.2f)", px, py))
        end
        return
    end

    -- Burst phase: give the spawned plastic blocks their outward velocity
    if state == "burst" and ents and #ents > 0 and #pending > 0 then
        local pl = table.remove(pending, 1)
        for _, ent in ipairs(ents) do
            local se = as_proxy(ent)
            if se then
                se:setVelocity(pl.vx, pl.vy)
                -- Try to make them a bit bigger visually if the API supports it
                if se.setScale then
                    pcall(se.setScale, se, 1.8, 1.8)
                end
            end
        end
    end
end

local function plan_plastic(x, y, vx, vy)
    table.insert(pending, {name=PLASTIC, x=x, y=y, vx=vx, vy=vy})
end

function OnTick()
    t = t + 1
    local e = get_rocket()

    if state == "launched" and e then
        local px, py = 2.0, 2.0
        local vx, vy = 0, 0
        if e.getPosition then
            local ok, x, y = pcall(e.getPosition, e)
            if ok and x and y then px, py = x, y end
        end
        if e.getVelocity then
            local ok, x, y = pcall(e.getVelocity, e)
            if ok and x and y then vx, vy = x, y end
        end

        if t % 5 == 0 then
            print(string.format("[PLASTIC_FW] rising t=%d pos=(%.2f,%.2f) v=(%.1f,%.1f)", t, px, py, vx, vy))
        end

        if t >= FUSE then
            state = "burst"
            outputs.string.status = "bursting"
            outputs.num.x = px
            outputs.num.y = py
            print(string.format("[PLASTIC_FW] *** BIG PLASTIC BURST (radius 3) at (%.2f, %.2f) ***", px, py))

            -- Big ring of plastic blocks, radius exactly 3
            local radius = 3.0
            local n = 18
            local speed = 3.8
            for i = 0, n-1 do
                local ang = (i / n) * (2 * math.pi)
                local sx = px + math.cos(ang) * radius
                local sy = py + math.sin(ang) * radius
                local svx = math.cos(ang) * speed + (math.random() - 0.5) * 0.6
                local svy = math.sin(ang) * speed + (math.random() - 0.5) * 0.6 + 1.6
                plan_plastic(sx, sy, svx, svy)
                spawn.create(PLASTIC, sx, sy)
            end

            kill_rocket()
        end

    elseif state == "burst" then
        if t % 5 == 0 then
            print(string.format("[PLASTIC_FW] big plastic cloud t=%d (radius 3 ring)", t))
        end
        if t > FUSE + 50 then
            state = "done"
            outputs.string.status = "done"
        end
    end
end
