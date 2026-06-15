-- Turret demo from Example_ApiReference_en.lua
-- Tests: Entity OOP, env.time, inputs/outputs typed sub-tables, spawn.create,
--        collision subscription, OnSpawned callback, print/warn/error_log.

local lastFire = 0

function OnInit()
    print("[turret] OnInit fired")
    warn("[turret] warn test")
    error_log("[turret] error_log test")

    -- Seed a target entity in the world (entity_id 1, set via --seed-entity)
    local target = Entity(1)
    if target._nil then
        print("[turret] no target, will idle")
    else
        target:subscribeCollisionEnter(function(other, self, nx, ny)
            print("[turret] collision! other=" .. tostring(other:getId())
                  .. " nx=" .. tostring(nx) .. " ny=" .. tostring(ny))
        end)
    end
end

function OnTick()
    local now = env.time()
    local e = Entity(1)
    if e._nil then
        outputs.string.status = "idle"
        outputs.num.distance = -1
        return
    end

    -- Read position
    local px, py = e:getPosition()
    local vx, vy = e:getVelocity()

    -- Aim towards origin
    e:lookAt(0, 0)

    -- Fire every 0.5s (simulated, no actual spawn of bullet in this test)
    if now - lastFire > 0.5 then
        lastFire = now
        local req = spawn.create("barrel", px + 2, py)
        print("[turret] fired spawn request " .. tostring(req))
    end

    -- Distance to origin
    local dist = math.sqrt(px*px + py*py)

    outputs.num.distance = dist
    outputs.string.status = "active"
    outputs.vec.direction = { x = px, y = py, z = 0, w = 0 }
    outputs.color.tint = { r = 1, g = 0.5, b = 0, a = 1 }
end

function OnSpawned(requestId, entities)
    if entities then
        print("[turret] OnSpawned req=" .. tostring(requestId)
              .. " count=" .. tostring(#entities))
        for i = 1, #entities do
            local e = entities[i]
            if not e._nil then
                e:setVelocity(10, 0)
                e:setGravityScale(0)
                print("[turret] spawned entity " .. tostring(e:getId())
                      .. " name=" .. e:getName())
            end
        end
    end
end

function OnActivated()
    print("[turret] activated")
end

function OnDestroy()
    print("[turret] destroyed")
end
