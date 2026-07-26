function OnInit()
    -- Real-device menu alias (not objectId 202 / ResizablePlastic)
    spawn.create("plastic_plate", 0, 1)
end

function OnSpawned(requestId, entities)
    if entities[1] then
        outputs.num.id = entities[1]:getId()
        outputs.num.x, outputs.num.y = entities[1]:getPosition()
        outputs.string.name = entities[1]:getName() or ""
    end
end

function OnTick()
end