-- Physics demo: a crate falls onto a static floor and settles.
-- Keeps the crate in the middle of the narrow (1m) floor by using a small force.
local crate = Entity(1)

function OnInit()
    print("[physics demo] init")
end

function OnTick()
    if crate and not crate._nil then
        local x, y = crate:getPosition()
        local vx, vy = crate:getVelocity()

        outputs.num.x = x
        outputs.num.y = y
        outputs.num.vy = vy

        -- Tiny push so the crate stays on the small 1m floor.
        if env.frameCount() >= 10 and env.frameCount() <= 12 then
            crate:addForce(4, 0)
            outputs.string.status = "tiny push"
        elseif env.frameCount() < 10 then
            outputs.string.status = "falling"
        else
            outputs.string.status = "resting"
        end
    end
end
