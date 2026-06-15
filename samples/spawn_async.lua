local my_req = 0

function OnInit()
    my_req = spawn.create("202", 0, 8)
    print("create returned requestId", my_req)
end

function OnSpawned(requestId, entities)
    print("OnSpawned", requestId, "count", #entities)
    if entities[1] then
        local e = entities[1]
        local x, y = e:getPosition()
        outputs.num.id = e:getId()
        outputs.string.name = e:getName() or ""
        outputs.num.x = x
        outputs.num.y = y
    end
end

function OnTick()
end