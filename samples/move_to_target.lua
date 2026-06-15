-- move_to_target.lua
-- Robust demo chip: drive an entity to (tx, ty) using setVelocity only.
-- Tunables via inputs: tx, ty, speed (for speed tuning / logs)
-- Uses a persistent mover_id captured in OnSpawned for reliable tracking.
-- Gravity disabled on the mover for clean horizontal/constant-height move.
-- Includes brake ramp near target and clean stop.

local mover_id = nil
local tick = 0

local TARGET_TOL = 0.06
local BRAKE_DIST = 1.0

function OnInit()
    -- Spawn the mover (Box, objectId ~23). OnSpawned will give us the real id.
    local req = spawn.create(23, -3.0, 2.5)
    print("[MOVE] OnInit: requested spawn id=" .. tostring(req) .. " (Box) target tuning via inputs")
end

function OnSpawned(requestId, entities)
    if entities and entities[1] then
        mover_id = entities[1]:getId()
        local e = Entity(mover_id)
        if e and e:isValid() == 1 then
            e:setGravityScale(0)
            print("[MOVE] OnSpawned: mover_id=" .. tostring(mover_id) .. " g=0 ready")
        end
    end
end

function OnTick()
    tick = tick + 1

    if not mover_id then
        if tick % 10 == 0 then print("[MOVE] waiting for OnSpawned mover_id...") end
        return
    end

    local e = Entity(mover_id)
    if (not e) or (e:isValid() ~= 1) then
        if tick % 10 == 0 then print("[MOVE] mover_id invalid, waiting...") end
        return
    end

    local tx = inputs.num.tx or 4.0
    local ty = inputs.num.ty or 2.5
    local max_speed = inputs.num.speed or 2.0

    local x, y = e:getPosition()
    local dx = tx - x
    local dy = ty - y
    local dist = math.sqrt(dx*dx + dy*dy)

    outputs.num.x = x
    outputs.num.y = y
    outputs.num.dist = dist
    outputs.num.tx = tx
    outputs.num.ty = ty
    outputs.num.max_speed = max_speed

    if dist <= TARGET_TOL then
        e:setVelocity(0, 0)
        outputs.string.status = "arrived"
        if tick % 3 == 0 then
            print(string.format("[MOVE] tick=%d ARRIVED pos=(%.2f,%.2f) dist=%.3f", tick, x, y, dist))
        end
        return
    end

    local nx = dx / dist
    local ny = dy / dist

    local cur = max_speed
    if dist < BRAKE_DIST then
        cur = max_speed * (dist / BRAKE_DIST)
    end

    local vx = nx * cur
    local vy = ny * cur
    e:setVelocity(vx, vy)

    outputs.string.status = "moving"
    outputs.num.cur_speed = cur
    outputs.vec.vel = {x=vx, y=vy, z=0, w=0}

    if tick % 5 == 0 then
        print(string.format(
            "[MOVE] tick=%d pos=(%.2f,%.2f) dist=%.3f tgt=(%.1f,%.1f) max=%.2f cur=%.2f",
            tick, x, y, dist, tx, ty, max_speed, cur
        ))
    end
end
