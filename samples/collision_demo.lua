-- Collision subscription + dispatch demo
local hitCount = 0

function OnInit()
    local e = Entity(1)
    if e._nil then
        print("[col] no entity 1")
        return
    end
    e:subscribeCollisionEnter(function(other, self, nx, ny)
        hitCount = hitCount + 1
        print("[col] HIT #" .. hitCount .. " other=" .. other:getId()
              .. " nx=" .. tostring(nx) .. " ny=" .. tostring(ny))
    end)
    print("[col] subscribed for entity 1")
end

function OnTick()
    outputs.num.hits = hitCount
end
