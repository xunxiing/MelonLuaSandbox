-- Firework effect chip (spawn at exactly 2,2 and burst)
-- Spawns the Firework prefab at world (2, 2), launches it up, then bursts into sparks.
-- Uses catalog name "Firework" (objectId 182) for spawn.
--
-- Self-test:
--   python scripts/self_test_firework.py
-- or
--   melon-lua samples/firework_at_2_2.lua --ticks 120

local fw_id = nil
local fw = nil          -- entity proxy if provided
local state = "init"
local t = 0
local FUSE = 30

local pending = {}      -- spark plans: {name, x, y, vx, vy}

local spark_names = {"Apple","Corn","Ring","Wing","2","38","94","10"}

local function num(x)
    if type(x) == "number" then return x end
    if type(x) == "string" then return tonumber(x) or 0 end
    return 0
end

local function proxy(obj)
    if not obj then return nil end
    if type(obj) == "table" or type(obj) == "userdata" then
        if obj.setVelocity then return obj end
    end
    local id = num(obj)
    if id ~= 0 then return Entity(id) end
    return nil
end

local function remember(obj)
    local p = proxy(obj)
    local id = num(obj)
    if p then fw = p end
    if id ~= 0 then fw_id = id end
end

local function get_fw()
    if fw then return fw end
    if fw_id then return Entity(fw_id) end
    return nil
end

local function kill_fw()
    if fw_id then spawn.destroy(fw_id) end
    fw = nil
    fw_id = nil
end

function OnInit()
    -- Explicit (2, 2)
    local req = spawn.create("Firework", 2.0, 2.0)
    outputs.string.status = "spawning"
    outputs.num.x = 2
    outputs.num.y = 2
    print("[FW] requested Firework at (2,2), req=" .. tostring(req))
end

function OnSpawned(req, ents)
    if state == "init" and ents and #ents > 0 then
        remember(ents[1])
        local e = get_fw()
        if e then
            e:setVelocity(0.1, 15.5)   -- strong up launch
            state = "launched"
            outputs.string.status = "launched"
            local px, py = 2.0, 2.0
            if e.getPosition then
                local ok, x, y = pcall(e.getPosition, e)
                if ok and x and y then px, py = x, y end
            end
            print(string.format("[FW] launched id=%s from (%.2f,%.2f)", tostring(fw_id or fw), px, py))
        end
        return
    end
    -- Apply velocities to sparks created during burst
    if state == "burst" and ents and #ents > 0 and #pending > 0 then
        local pl = table.remove(pending, 1)
        for _, ent in ipairs(ents) do
            local se = proxy(ent)
            if se then se:setVelocity(pl.vx, pl.vy) end
        end
    end
end

local function plan(name, x, y, vx, vy)
    table.insert(pending, {name=name, x=x, y=y, vx=vx, vy=vy})
end

function OnTick()
    t = t + 1
    local e = get_fw()

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
            print(string.format("[FW] rise t=%d pos=(%.2f,%.2f) v=(%.1f,%.1f)", t, px, py, vx, vy))
        end

        if t >= FUSE then
            state = "burst"
            outputs.string.status = "bursting"
            outputs.num.x = px
            outputs.num.y = py
            print(string.format("[FW] BURST at (%.2f, %.2f)", px, py))

            local n = 16
            local r = 0.07
            local spd = 5.0
            for i = 0, n-1 do
                local a = (i / n) * (2 * math.pi)
                local sx = px + math.cos(a) * r
                local sy = py + math.sin(a) * r
                local svx = math.cos(a) * spd + (math.random()-0.5)*0.8
                local svy = math.sin(a) * spd + (math.random()-0.5)*0.8 + 2.5
                local nm = spark_names[(i % #spark_names) + 1]
                plan(nm, sx, sy, svx, svy)
                spawn.create(nm, sx, sy)
            end
            kill_fw()
        end

    elseif state == "burst" then
        if t % 5 == 0 then
            print(string.format("[FW] sparks t=%d", t))
        end
        if t > FUSE + 55 then
            state = "done"
            outputs.string.status = "done"
        end
    end
end
